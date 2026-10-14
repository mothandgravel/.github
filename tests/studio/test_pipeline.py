"""Real FFmpeg finishing through the studio adapter, with a tiny offline source."""

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
