"""Real FFmpeg finishing through the studio adapter, with a tiny offline source."""

import copy
import json
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_audio.locks import run_lock
from field_notes_audio.production import packages, runner
from field_notes_audio.production.editions import VIDEO_FILES, fingerprint
from field_notes_audio.storage import digest_file, read_object, write_json
from field_notes_studio.pipeline import Pipeline
from field_notes_studio.repository import Repository
from field_notes_studio.worker import execute

ROOT = Path(__file__).resolve().parents[2]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        assets = self.root / "docs/assets/audio"
        assets.mkdir(parents=True)
        source = assets / "fixture.mp3"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=4",
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "libmp3lame",
                str(source),
            ],
            check=True,
        )
        (assets / "fixture.json").write_text(
            json.dumps([{"start": 0.3, "end": 3.4, "text": "A caption."}])
        )
        (assets / "fixture.txt").write_text("A caption.")
        self.entry = {
            "id": "fixture",
            "title": "A fixture",
            "description": "Offline source",
            "slug": None,
            "audio": "assets/audio/fixture.mp3",
            "cues": "assets/audio/fixture.json",
            "transcript": "assets/audio/fixture.txt",
            "audio_sha256": digest_file(source),
            "script_sha256": "fixture",
            "source_sha256": {},
            "kind": "note",
            "files_sha256": {
                "cues": digest_file(assets / "fixture.json"),
                "transcript": digest_file(assets / "fixture.txt"),
            },
            "review_status": "pending",
        }
        settings = read_object(ROOT / "audio/production/settings.json")
        settings.update(intro_seconds=0.5, outro_seconds=0.5, music_overlap_seconds=0.2)
        write_json(self.root / "audio/production/settings.json", settings)
        self.pipeline = Pipeline(self.root)
        self.repository = Repository(self.root / "artifacts/studio/studio.sqlite3")
        mock = patch("field_notes_audio.site.load_entries", return_value=[self.entry])
        mock.start()
        self.addCleanup(mock.stop)

    def run_audio(self, outro):
        request = self.pipeline.request("fixture", "audio", 1.15, outro)
        identifier = self.repository.submit("fixture", "audio", request)
        execute(self.repository, self.pipeline, self.repository.claim())
        job = self.repository.get(identifier)
        self.assertEqual(job.status, "succeeded", job.error)
        return Path(job.result)

    def test_outro_changes_create_another_edition_and_repeating_recipe_reuses_media(self):
        before = digest_file(self.root / "docs/assets/audio/fixture.mp3")
        first = self.run_audio(0.5)
        second = self.run_audio(1)
        self.assertNotEqual(first, second)
        self.assertGreater(
            read_object(second / "production.json")["duration_seconds"],
            read_object(first / "production.json")["duration_seconds"],
        )
        stamp = (second / "episode.mp3").stat().st_mtime_ns
        repeated = self.run_audio(1)
        self.assertEqual(second, repeated)
        self.assertEqual((repeated / "episode.mp3").stat().st_mtime_ns, stamp)
        self.assertEqual(digest_file(self.root / "docs/assets/audio/fixture.mp3"), before)
        self.assertEqual(read_object(second / "production.json")["review_status"], "pending")

    def test_changed_source_blocks_queued_job_before_producing_media(self):
        request = self.pipeline.request("fixture", "audio", 1.15, 1)
        self.entry["script_sha256"] = "changed"
        identifier = self.repository.submit("fixture", "audio", request)
        execute(self.repository, self.pipeline, self.repository.claim())
        self.assertEqual(self.repository.get(identifier).status, "failed")
        self.assertIn("source changed", self.repository.get(identifier).error)
        self.assertFalse(self.pipeline.output.exists())

    def test_export_refuses_a_changed_edition(self):
        self.run_audio(0.5)
        request = self.pipeline.request("fixture", "export", 1.15, 0.5)
        write_json(self.pipeline.output / "fixture/latest.json", {"changed": True})
        with self.assertRaisesRegex(ValueError, "edition changed"):
            self.pipeline.run(
                "fixture", "export", request, self.root / "export-job", lambda *_: None
            )

    def test_plan_identifies_sound_changes_without_claiming_unverified_reuse(self):
        self.run_audio(0.5)
        request = self.pipeline.request("fixture", "audio", 1.15, 1)
        plan = self.pipeline.plan("fixture", "audio", request)
        self.assertIn("outro_seconds", plan)
        unchanged = copy.deepcopy(request)
        unchanged["settings"]["outro_seconds"] = 0.5
        self.assertIn(
            "verifies source, toolchain", self.pipeline.plan("fixture", "audio", unchanged)
        )

    def test_review_checks_saved_identity_and_preserves_source_media(self):
        original = digest_file(self.root / "docs/assets/audio/fixture.mp3")
        edition = self.run_audio(0.5)
        snapshot = self.pipeline.review_snapshot("fixture")
        self.assertTrue(snapshot.identity, snapshot.summary)
        self.assertIn("pending", snapshot.summary)
        self.assertEqual(Path(snapshot.audio), edition / "episode.mp3")
        self.pipeline.approve("fixture", snapshot, "Test listener")
        self.assertIn("approved", self.pipeline.review_snapshot("fixture").summary)
        review = read_object(edition / "review.json")
        self.assertEqual(review["reviewer"], "Test listener")
        self.assertIsNone(review["video_fingerprint"])
        self.assertEqual(digest_file(self.root / "docs/assets/audio/fixture.mp3"), original)
        self.run_audio(1)
        with self.assertRaisesRegex(ValueError, "Edition changed"):
            self.pipeline.approve("fixture", snapshot, "Test listener")
        self.assertIn("pending", self.pipeline.review_snapshot("fixture").summary)

    def test_review_blocks_missing_changed_locked_or_preview_only_media(self):
        self.assertFalse(self.pipeline.review_snapshot("fixture").identity)
        edition = self.run_audio(0.5)
        self.assertFalse(self.pipeline.review_snapshot("fixture", full_video=True).identity)
        snapshot = self.pipeline.review_snapshot("fixture")
        with self.assertRaises(ValueError):
            self.pipeline.approve("fixture", snapshot, " ")
        with run_lock(self.pipeline.output / "fixture", "test production"):
            self.assertFalse(self.pipeline.review_snapshot("fixture").identity)
            with self.assertRaisesRegex(ValueError, "Another"):
                self.pipeline.approve("fixture", snapshot, "Test listener")
        (edition / "captions.srt").write_text("Changed captions")
        self.assertFalse(self.pipeline.review_snapshot("fixture").identity)
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            self.pipeline.approve("fixture", snapshot, "Test listener")
        self.assertFalse((edition / "review.json").exists())

    def test_full_video_review_verifies_video_and_does_not_treat_preview_as_full(self):
        audio = self.run_audio(0.5)
        state = read_object(audio / "production.json")
        identity = fingerprint({"fixture": "video", "audio": state["fingerprint"]})
        video = audio / "video" / identity[:16]
        video.mkdir(parents=True)
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=640x360:r=12",
                "-i",
                str(audio / "master.wav"),
                "-t",
                str(state["timeline_duration_seconds"]),
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-c:a",
                "aac",
                str(video / "episode.mp4"),
            ],
            check=True,
        )
        shutil.copyfile(ROOT / "docs/assets/podcast-cover.png", video / "thumbnail.png")
        write_json(
            video / "render.json",
            {
                "previewSeconds": None,
                "frames": math.ceil(state["timeline_duration_seconds"] * 12),
                "fps": 12,
                "width": 640,
                "height": 360,
            },
        )
        write_json(
            video / "production.json",
            {
                "fingerprint": identity,
                "preview_seconds": None,
                "audio_fingerprint": state["fingerprint"],
                "master_sha256": state["files"]["master.wav"],
                "cues_sha256": state["files"]["cues.json"],
                "files": {name: digest_file(video / name) for name in VIDEO_FILES},
            },
        )
        runner.update_latest(self.pipeline.output / "fixture", audio, video, preview=1)
        self.assertFalse(self.pipeline.review_snapshot("fixture", True).identity)
        runner.update_latest(self.pipeline.output / "fixture", audio, video)
        audio_review = self.pipeline.review_snapshot("fixture")
        self.pipeline.approve("fixture", audio_review, "Test listener")
        full_review = self.pipeline.review_snapshot("fixture", True)
        self.assertTrue(full_review.identity, full_review.summary)
        self.assertIn("pending", full_review.summary)
        self.assertEqual(Path(full_review.video), video / "episode.mp4")
        self.pipeline.approve("fixture", full_review, "Test listener")
        self.assertIn("approved", self.pipeline.review_snapshot("fixture", True).summary)
        verified = packages.snapshot(self.entry, self.pipeline.output, True)
        self.assertEqual(packages.review_status(verified, True), "approved")
        (video / "episode.mp4").write_bytes(b"changed")
        self.assertFalse(self.pipeline.review_snapshot("fixture", True).identity)
        with self.assertRaises(ValueError):
            self.pipeline.approve("fixture", full_review, "Test listener")
