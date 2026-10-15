"""Durable raw drafts, atomic batches and publishing conflict boundaries."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_audio.storage import read_object, write_json
from field_notes_studio.pipeline import Pipeline
from field_notes_studio.repository import Repository
from field_notes_studio.service import Studio


class WorkspaceStateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        source = Path(__file__).resolve().parents[2] / "audio/production"
        for name in ("settings.json", "publishing.json"):
            write_json(self.root / "audio/production" / name, read_object(source / name))
        self.studio = Studio(self.root)
        self.repository = self.studio.repository
        self.entry = {
            "id": "note-001",
            "title": "Episode",
            "description": "Summary",
            "slug": "episode",
            "published_at": "2026-10-13T00:00:00+00:00",
        }
        for mock in (
            patch.object(Pipeline, "source", return_value=self.entry),
            patch.object(Pipeline, "entries", return_value=[self.entry]),
        ):
            mock.start()
            self.addCleanup(mock.stop)

    def test_partial_raw_draft_survives_reopen_without_becoming_a_release_or_job(self):
        draft = {
            "recipe": {"speed": "1.", "outro": ""},
            "publication": ["unfinished link", "2026-", "old", True],
        }
        self.repository.checkpoint(
            {"draft:note-001": draft, "session": {"episode": "note-001", "tab": 2}}
        )
        reopened = Repository(self.repository.path)
        self.assertEqual(reopened.state("draft:note-001"), draft)
        self.assertEqual(reopened.state("session")["tab"], 2)
        self.assertEqual(reopened.publications(), {})
        self.assertEqual(reopened.jobs(), [])

    def test_late_batch_conflict_rolls_back_every_insert(self):
        self.repository.submit("note-002", "audio", {})
        with self.assertRaisesRegex(ValueError, "already has"):
            self.repository.submit_batch([("note-001", "audio", {}), ("note-002", "video", {})])
        self.assertEqual([job.episode for job in self.repository.jobs()], ["note-002"])

    def test_batch_capacity_and_duplicates_leave_queue_unchanged(self):
        with self.assertRaises(ValueError):
            self.repository.submit_batch([("note-001", "audio", {}), ("note-001", "audio", {})])
        for index in range(31):
            self.repository.submit(f"old-{index}", "audio", {})
        with self.assertRaisesRegex(ValueError, "full"):
            self.repository.submit_batch([("a", "audio", {}), ("b", "audio", {})])
        self.assertEqual(len(self.repository.jobs()), 31)

    def test_batch_captures_each_draft_sound_recipe_and_rejects_partial_numbers(self):
        settings = self.studio.settings("note-001")
        sound = {
            name: settings[name]
            for name in (
                "intro_seconds",
                "music_overlap_seconds",
                "music_gain_db",
                "target_lufs",
                "true_peak_db",
                "music_mode",
                "music_file",
                "music_credit",
            )
        }
        sound["music_gain_db"] = "-22"
        self.repository.checkpoint(
            {"draft:note-001": {"sound": sound, "recipe": {"speed": "1.2", "outro": "3"}}}
        )
        plans, summary = self.studio.batch_plan(["note-001"], "audio")
        self.assertEqual(plans[0][2]["settings"]["music_gain_db"], -22)
        self.assertEqual(plans[0][2]["settings"]["speed"], 1.2)
        self.assertIn("note-001", summary)
        self.repository.checkpoint({"draft:note-001": {"recipe": {"speed": "unfinished"}}})
        with self.assertRaises(ValueError):
            self.studio.batch_plan(["note-001"], "audio")
        self.assertEqual(self.repository.jobs(), [])

    def test_publishing_edit_is_validated_atomic_and_rejects_lost_updates(self):
        pipeline = self.studio.pipeline
        snapshot = pipeline.metadata_editor("note-001")
        old = copy.deepcopy(snapshot)
        snapshot["values"].update(
            title="A better title", description="First paragraph.\n\nSecond paragraph."
        )
        saved = pipeline.save_metadata("note-001", snapshot)
        self.assertNotEqual(saved["baseline"], old["baseline"])
        self.assertEqual(pipeline.release_details("note-001").title, "A better title")
        with self.assertRaisesRegex(ValueError, "changed elsewhere"):
            pipeline.save_metadata("note-001", old)
        path = self.root / "audio/production/publishing.json"
        before = path.read_bytes()
        saved["values"]["shared_hashtags"] = "#One #Two #Three #Four"
        with self.assertRaises(ValueError):
            pipeline.save_metadata("note-001", saved)
        self.assertEqual(path.read_bytes(), before)

    def test_full_sound_recipe_uses_shared_validator_and_is_immutable_after_capture(self):
        sound = {"intro_seconds": 8, "music_mode": "none", "music_file": None, "target_lufs": -18}
        request = self.studio.pipeline.request("note-001", "audio", 1.1, 2, sound)
        sound["intro_seconds"] = 99
        self.assertEqual(request["settings"]["intro_seconds"], 8)
        with self.assertRaisesRegex(ValueError, "intro_seconds"):
            self.studio.pipeline.request("note-001", "audio", 1.1, 2, sound)
        with self.assertRaisesRegex(ValueError, "Custom music"):
            self.studio.pipeline.request(
                "note-001",
                "audio",
                1.1,
                2,
                {"music_mode": "file", "music_file": "missing", "music_credit": ""},
            )
