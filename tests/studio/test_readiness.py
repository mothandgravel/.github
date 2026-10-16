"""Readiness and action-specific preflight against real local media, not job labels."""

import argparse
import math
import shutil
import subprocess
import unittest
from unittest.mock import patch

from field_notes_audio.locks import run_lock
from field_notes_audio.production import packages, runner
from field_notes_audio.production.editions import VIDEO_FILES
from field_notes_audio.storage import digest_file, read_object, write_json
from field_notes_studio.readiness import (
    expected_audio_identity,
    expected_video_identity,
    inspect,
    preflight,
)
from field_notes_studio.readiness_models import Readiness
from field_notes_studio.service import Studio
from tests.studio import test_pipeline as media_fixture

ROOT = media_fixture.ROOT


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.f = media_fixture.PipelineTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        for name in ("podcast-cover.png", "moth-mark.svg"):
            shutil.copyfile(ROOT / "docs/assets" / name, self.f.root / "docs/assets" / name)
        self.p = self.f.pipeline
        self.studio = Studio(self.f.root)
        self.settings = self.p.settings("fixture")
        self.settings["video"].update(width=640, height=360, fps=12)
        write_json(self.f.root / "audio/production/settings.json", self.settings)

    def full(self, approve=False, export=False):
        audio = self.f.run_audio(0.5)
        state = read_object(audio / "production.json")
        identity = expected_video_identity(self.f.root, self.f.entry, audio, self.settings)
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
                "-threads",
                "1",
                "-c:a",
                "aac",
                str(video / "episode.mp4"),
            ],
            check=True,
            timeout=30,
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
        runner.update_latest(self.p.output / "fixture", audio, video)
        if approve:
            self.p.approve("fixture", self.p.review_snapshot("fixture", True), "Fixture reviewer")
        if export:
            packages.export(
                argparse.Namespace(
                    episode="fixture", output_dir=None, upload_dir=None, metadata=None
                ),
                self.f.root,
            )
        return audio, video

    def snapshot(self):
        return inspect(self.p, "fixture", self.settings)

    def test_no_edition_has_production_next_not_review_or_publication(self):
        value = self.snapshot()
        self.assertEqual(value.action, "produce", value.detail)
        self.assertIn("Recording: verified", value.stages)
        self.assertFalse(self.p.output.exists())

    def test_audio_only_cannot_be_readiness_for_full_episode(self):
        self.f.run_audio(0.5)
        self.assertEqual(self.snapshot().action, "produce")

    def test_one_full_approval_then_export_then_current_package(self):
        self.full()
        self.assertEqual(self.snapshot().action, "review")
        self.p.approve("fixture", self.p.review_snapshot("fixture", True), "Real fixture review")
        self.assertEqual(self.snapshot().action, "export")
        packages.export(
            argparse.Namespace(episode="fixture", output_dir=None, upload_dir=None, metadata=None),
            self.f.root,
        )
        ready = self.snapshot()
        self.assertEqual(ready.action, "package", ready.detail)
        self.assertIn("not verified", ready.detail)
        self.assertTrue(ready.identity)
        self.assertEqual(self.f.repository.publications(), {})

    def test_saved_copy_change_requires_export_not_another_review_or_production(self):
        audio, _ = self.full(approve=True, export=True)
        review = (audio / "review.json").read_bytes()
        path = self.f.root / "audio/production/publishing.json"
        settings = read_object(path)
        settings["episodes"]["fixture"] = {"title": "Changed export title"}
        write_json(path, settings)
        value = self.snapshot()
        self.assertEqual(value.action, "export", value.detail)
        self.assertIn("Review: approved", value.stages)
        self.assertEqual((audio / "review.json").read_bytes(), review)

    def test_edited_recipe_preserves_saved_approval_but_offers_new_production(self):
        audio, _ = self.full(approve=True)
        approval = (audio / "review.json").read_bytes()
        self.settings["speed"] = 1.25
        value = self.snapshot()
        self.assertEqual(value.action, "produce")
        self.assertIn("speed", value.detail)
        self.assertEqual((audio / "review.json").read_bytes(), approval)

    def test_valid_audio_identity_matches_engine_and_detects_source_metadata_changes(self):
        audio, _ = self.full(approve=True)
        self.assertEqual(
            expected_audio_identity(self.f.entry, self.settings),
            read_object(audio / "production.json")["fingerprint"],
        )
        self.f.entry["script_sha256"] = "another-script"
        self.assertEqual(self.snapshot().action, "produce")

    def test_changed_video_bytes_cannot_use_saved_approval(self):
        _, video = self.full(approve=True)
        (video / "episode.mp4").write_bytes(b"damaged")
        value = self.snapshot()
        self.assertEqual(value.action, "produce")
        self.assertNotIn("Review: approved", value.stages)

    def test_changed_narration_blocks_without_queueing_or_remote_calls(self):
        (self.f.root / "docs/assets/audio/fixture.mp3").write_bytes(b"changed")
        with patch("socket.create_connection", side_effect=AssertionError("network")):
            value = self.snapshot()
        self.assertEqual(value.action, "repair")
        self.assertIn("changed", value.detail)
        self.assertEqual(self.f.repository.jobs(), [])

    def test_bad_publishing_settings_keep_the_valid_full_approval(self):
        self.full(approve=True)
        write_json(self.f.root / "audio/production/publishing.json", {"bad": "settings"})
        value = self.snapshot()
        self.assertEqual(value.action, "repair", value.detail)
        self.assertIn("Review: approved", value.stages)

    def test_corrupt_upload_requires_export_not_new_narration(self):
        self.full(approve=True, export=True)
        path = self.f.root / "artifacts/uploads/fixture/episode.mp4"
        path.write_bytes(b"damaged")
        value = self.snapshot()
        self.assertEqual(value.action, "export")
        self.assertIn("Review: approved", value.stages)

    def test_export_preflight_requires_full_review_not_renderer_installation(self):
        self.full()
        req = self.p.request("fixture", "export", None, None)
        with self.assertRaisesRegex(ValueError, "Review the full episode"):
            preflight(self.p, "fixture", "export", req)
        self.p.approve("fixture", self.p.review_snapshot("fixture", True), "Fixture")
        with patch.object(runner, "preflight", side_effect=AssertionError("renderer preflight")):
            preflight(self.p, "fixture", "export", req)

    def test_saved_video_identity_matches_engine_cache_and_detects_artwork_changes(self):
        audio, video = self.full(approve=True)
        (self.f.root / "video/node_modules/@remotion/renderer").mkdir(parents=True)
        with patch(
            "field_notes_audio.production.video.render_video", side_effect=AssertionError("render")
        ):
            self.assertEqual(
                runner.produce_video(
                    self.f.entry,
                    self.f.root,
                    audio,
                    self.settings,
                    argparse.Namespace(preview_seconds=None),
                ),
                video,
            )
        mark = self.f.root / "docs/assets/moth-mark.svg"
        mark.write_text(mark.read_text() + "\n<!-- revised -->")
        value = self.snapshot()
        self.assertEqual(value.action, "produce")
        self.assertIn("artwork", value.detail)
        self.assertEqual(read_object(audio / "review.json")["status"], "approved")

    def test_preflight_rejects_unexpected_export_files_without_deleting_them(self):
        self.full(approve=True, export=True)
        extra = self.f.root / "artifacts/uploads/fixture/personal.txt"
        extra.write_text("do not delete")
        req = self.p.request("fixture", "export", None, None)
        with self.assertRaisesRegex(ValueError, "unexpected files"):
            preflight(self.p, "fixture", "export", req)
        self.assertEqual(extra.read_text(), "do not delete")

    def test_production_preflight_and_missing_dependency_are_shown_before_queue(self):
        with patch.object(
            runner,
            "preflight",
            side_effect=ValueError("Video dependencies are missing. Run: npm ci --prefix video"),
        ):
            value = self.studio.readiness("fixture", self.settings)
            self.assertEqual(value.action, "health")
            self.assertIn("npm ci", value.detail)
            with self.assertRaisesRegex(ValueError, "Video dependencies"):
                self.studio.checked_plan("fixture", "video", 1.15, 0.5)
        self.assertEqual(self.f.repository.jobs(), [])

    def test_audio_preflight_does_not_require_video_assets(self):
        req = self.p.request("fixture", "audio", 1.15, 0.5)
        preflight(self.p, "fixture", "audio", req)
        self.assertFalse((self.f.root / "video").exists())

    def test_job_queued_during_preflight_takes_precedence_over_ready_action(self):
        def queued(*_args):
            self.f.repository.submit("fixture", "video", {"settings": self.settings})

        with patch.object(self.studio.pipeline, "preflight", side_effect=queued):
            value = self.studio.readiness("fixture", self.settings)
        self.assertEqual(value.action, "job")
        self.assertEqual(value.job, self.f.repository.jobs()[0].identifier)

    def test_active_work_routes_to_job_without_claiming_media_or_review_ready(self):
        job = self.f.repository.submit("fixture", "video", {})
        with patch.object(
            self.studio.pipeline, "readiness", side_effect=AssertionError("heavy read")
        ):
            value = self.studio.readiness("fixture", self.settings)
        self.assertEqual((value.action, value.job), ("job", job))
        self.assertEqual(value.stages, ())

    def test_new_active_work_during_check_wins_over_stale_ready_snapshot(self):
        def checking(*_):
            self.f.repository.submit("fixture", "video", {})
            return Readiness("fixture", "package", "Ready", "stale")

        with patch.object(self.studio.pipeline, "readiness", side_effect=checking):
            self.assertEqual(self.studio.readiness("fixture", self.settings).action, "job")

    def test_broken_or_locked_edition_is_not_claimed_ready(self):
        audio, _ = self.full(approve=True)
        with run_lock(audio.parent, "busy production"):
            value = self.studio.readiness("fixture", self.settings)
            self.assertEqual(value.action, "check", value.detail)
            self.assertIn("in use", value.title)
            self.assertEqual(self.f.repository.jobs()[-1].action, "audio")

    def test_busy_upload_directory_does_not_request_an_unnecessary_export(self):
        self.full(approve=True, export=True)
        with run_lock(self.f.root / "artifacts/uploads", "busy export"):
            value = self.studio.readiness("fixture", self.settings)
            self.assertEqual(value.action, "check", value.detail)
            self.assertNotIn("needs production", value.title)

    def test_busy_recording_preflight_does_not_become_tool_health_failure(self):
        from field_notes_studio.readiness_models import ReadinessBusy

        with patch.object(
            self.studio.pipeline, "preflight", side_effect=ReadinessBusy("A read owns the lock")
        ):
            value = self.studio.readiness("fixture", self.settings)
        self.assertEqual(value.action, "check")
