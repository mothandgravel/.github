"""Verify the handoff against real exported media, current review and changed files."""

import shutil
import unittest

from field_notes_audio.production import packages, runner
from field_notes_audio.production.editions import fingerprint
from field_notes_audio.storage import read_object, write_json
from field_notes_studio.pipeline import Pipeline
from tests.audio import test_production_release as fixtures


class PackageHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.PublishingTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        fixtures.PublishingTests.tearDownClass()

    def setUp(self):
        self.case = fixtures.PublishingTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.pipeline = Pipeline(self.case.root)

    def test_missing_package_is_actionable_without_writing_outputs(self):
        snapshot = self.pipeline.package_snapshot("note-001")
        self.assertEqual(snapshot.status, "missing")
        self.assertFalse(snapshot.files)
        self.assertFalse(self.case.upload.exists())

    def test_pending_then_approved_review_requires_a_fresh_export(self):
        c = self.case
        packages.export(c.args, c.root)
        pending = self.pipeline.package_snapshot("note-001")
        self.assertEqual(pending.status, "review")
        self.assertEqual(len(pending.files), 6)
        self.assertEqual(pending.files[0].name, "episode.mp4")
        self.assertEqual(pending.details.title, (c.upload / "title.txt").read_text().strip())
        self.assertEqual(
            self.pipeline.package_file(pending, "thumbnail.png"), c.upload / "thumbnail.png"
        )
        c.approve()
        self.assertEqual(self.pipeline.package_snapshot("note-001").status, "stale")
        packages.export(c.args, c.root)
        ready = self.pipeline.package_snapshot("note-001")
        self.assertEqual(ready.status, "ready")
        self.assertNotEqual(pending.identity, ready.identity)
        with self.assertRaisesRegex(ValueError, "changed after checking"):
            self.pipeline.package_file(pending, "episode.mp4")

    def test_new_completed_video_makes_previous_upload_stale(self):
        c = self.case
        c.approve()
        packages.export(c.args, c.root)
        state = read_object(c.video / "production.json")
        state["fingerprint"] = fingerprint({"new_video_recipe": state["fingerprint"]})
        newer = c.video.with_name(state["fingerprint"][:16])
        shutil.copytree(c.video, newer)
        write_json(newer / "production.json", state)
        runner.update_latest(c.directory, c.finished, newer)
        self.assertEqual(self.pipeline.package_snapshot("note-001").status, "stale")

    def test_damaged_upload_is_rejected_and_changed_selected_file_cannot_be_opened(self):
        c = self.case
        packages.export(c.args, c.root)
        snapshot = self.pipeline.package_snapshot("note-001")
        (c.upload / "thumbnail.png").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed after checking"):
            self.pipeline.package_file(snapshot, "thumbnail.png")
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            self.pipeline.package_snapshot("note-001")
        with self.assertRaisesRegex(ValueError, "Select a checked"):
            self.pipeline.package_file(snapshot, "../episode.mp4")
        (c.upload / "episode.mp4").unlink()
        with self.assertRaisesRegex(ValueError, "files are unavailable"):
            self.pipeline.package_file(snapshot, "episode.mp4")

    def test_portable_package_stays_inspectable_without_claiming_current_approval(self):
        c = self.case
        c.approve()
        packages.export(c.args, c.root)
        shutil.rmtree(c.directory)
        snapshot = self.pipeline.package_snapshot("note-001")
        self.assertEqual(snapshot.status, "unverified")
        self.assertEqual(len(snapshot.files), 6)
        self.assertTrue(self.pipeline.package_file(snapshot, "episode.mp4").is_file())
