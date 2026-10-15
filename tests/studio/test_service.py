"""Opening a durable job must not follow a newer edition's latest pointer."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_studio.models import Episode
from field_notes_studio.service import Studio


class JobOutputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.studio = Studio(self.root)

    def test_catalog_defaults_do_not_write_or_override_saved_release_records(self):
        episode = Episode(
            "fixture",
            "Fixture",
            10,
            "Transcript",
            "https://mothandgravel.com/notes/fixture.html",
            "2026-10-13",
            "Podcast catalog",
        )
        with patch.object(self.studio.pipeline, "catalog", return_value=[episode]):
            automatic = self.studio.catalog()[0]
            self.assertEqual(automatic.publication_url, episode.publication_url)
            self.assertEqual(automatic.publication_date, "2026-10-13")
            self.assertFalse(automatic.publication_saved)
            self.assertEqual(self.studio.repository.publications(), {})
            self.studio.publication("fixture", "https://youtu.be/already-published", "")
            saved = self.studio.catalog()[0]
            self.assertEqual(saved.publication_url, "https://youtu.be/already-published")
            self.assertEqual(saved.publication_date, "")
            self.assertTrue(saved.publication_saved)
            self.studio.publication("fixture", "", "")
            cleared = self.studio.catalog()[0]
            self.assertEqual(cleared.publication_url, "")
            self.assertEqual(cleared.publication_date, "")

    def test_each_completed_output_opens_the_exact_saved_job(self):
        for action, filename in (
            ("audio", "episode.mp3"),
            ("preview", "episode.mp4"),
            ("video", "episode.mp4"),
            ("export", ""),
        ):
            with self.subTest(action=action):
                parent = "uploads" if action == "export" else "production"
                saved = self.root / "artifacts" / parent / "fixture" / "old-edition"
                identifier = self.studio.repository.submit("fixture", action, {})
                self.studio.repository.finish(identifier, "succeeded", result=str(saved))
                with patch("field_notes_studio.service.open_path") as opened:
                    self.studio.open_job_output(identifier)
                    opened.assert_called_once_with(saved / filename if filename else saved)

    def test_unfinished_missing_and_outside_results_are_not_opened(self):
        identifier = self.studio.repository.submit("fixture", "audio", {})
        with patch("field_notes_studio.service.open_path") as opened:
            with self.assertRaisesRegex(ValueError, "completed"):
                self.studio.open_job_output(identifier)
            self.studio.repository.finish(identifier, "succeeded")
            with self.assertRaisesRegex(ValueError, "completed"):
                self.studio.open_job_output(identifier)
            self.studio.repository.finish(identifier, "succeeded", result="/tmp/unrelated")
            with self.assertRaisesRegex(ValueError, "outside"):
                self.studio.open_job_output(identifier)
            opened.assert_not_called()
        self.studio.repository.finish(
            identifier, "succeeded", result=str(self.root / "artifacts/production/missing")
        )
        with self.assertRaisesRegex(ValueError, "Produce"):
            self.studio.open_job_output(identifier)
