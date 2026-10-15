"""Worker upgrades are fenced by job completion, ownership and process identity."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_audio.locks import run_lock
from field_notes_studio.health import lock_owner, process_id, restart, worker_status
from field_notes_studio.repository import Repository
from field_notes_studio.worker import work


class HealthTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = Repository(self.root / "artifacts/studio/studio.sqlite3")

    def test_reports_kernel_lock_owner_and_distinguishes_unknown_old_code(self):
        directory = self.repository.path.parent
        self.assertIsNone(lock_owner(directory))
        self.assertEqual(worker_status(self.repository)["state"], "stopped")
        with run_lock(directory, "studio worker"):
            self.assertEqual(lock_owner(directory), process_id())
            self.assertEqual(worker_status(self.repository)["state"], "unknown")
            self.repository.checkpoint(
                {
                    "worker": {
                        "pid": process_id(),
                        "heartbeat": time.time(),
                        "revision": "older",
                        "activity": "rendering",
                    }
                }
            )
            self.assertEqual(worker_status(self.repository)["state"], "outdated")
        self.assertIsNone(lock_owner(directory))

    def test_modern_restart_is_a_message_and_never_terminates_a_stage(self):
        with (
            patch("field_notes_studio.health.worker_status", return_value={"state": "current"}),
            patch("signal.pidfd_send_signal") as signal,
        ):
            message = restart(self.repository, self.root)
        self.assertIn("finish its current job", message)
        self.assertTrue(self.repository.state("worker_control")["restart"])
        signal.assert_not_called()

    def test_legacy_restart_is_blocked_while_any_job_runs(self):
        self.repository.submit("note-001", "audio", {})
        self.repository.claim()
        with (
            patch(
                "field_notes_studio.health.worker_status",
                return_value={"state": "unknown", "pid": os.getpid()},
            ),
            patch("os.pidfd_open") as opened,
        ):
            with self.assertRaisesRegex(ValueError, "job is running"):
                restart(self.repository, self.root)
            opened.assert_not_called()

    def test_legacy_restart_does_not_signal_an_unrelated_process(self):
        with (
            patch(
                "field_notes_studio.health.worker_status",
                return_value={"state": "unknown", "pid": process_id()},
            ),
            patch("signal.pidfd_send_signal") as sent,
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                restart(self.repository, self.root)
        sent.assert_not_called()

    def test_code_upgrade_finishes_claimed_job_then_releases_lock_before_relaunch(self):
        self.repository.submit("note-001", "audio", {})
        self.repository.submit("note-002", "audio", {})
        revisions = iter(["old", "old", "new"])
        launched = []

        def replacement(root):
            # Relaunch must happen outside the exclusive lock.
            with run_lock(self.repository.path.parent, "studio worker"):
                launched.append(root)

        with (
            patch("field_notes_studio.worker.Pipeline") as pipeline,
            patch("field_notes_studio.worker.revision", side_effect=lambda: next(revisions)),
            patch("field_notes_studio.worker.launch_worker", side_effect=replacement),
        ):
            pipeline.return_value.run.return_value = "/saved/edition"
            work(self.root)
        jobs = {job.episode: job for job in self.repository.jobs()}
        self.assertEqual(jobs["note-001"].status, "succeeded")
        self.assertEqual(jobs["note-002"].status, "queued")
        self.assertEqual(launched, [self.root])
