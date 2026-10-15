"""Exercise durable jobs, cross-window exclusivity and uncertain crash outcomes."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from field_notes_studio.repository import Repository


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "studio.sqlite3"
        self.repository = Repository(self.path)

    def test_active_job_stays_visible_after_newer_history_fills_the_display(self):
        active = self.repository.submit("running", "audio", {})
        self.repository.claim()
        for index in range(101):
            job = self.repository.submit(f"other-{index}", "audio", {})
            self.repository.finish(job, "succeeded")
        jobs = self.repository.jobs()
        self.assertEqual(len(jobs), 101)
        self.assertEqual(jobs[-1].identifier, active)
        self.assertEqual(jobs[-1].status, "running")

    def test_closing_and_reopening_clients_preserves_claimed_job_recipe_events_and_publication(
        self,
    ):
        recipe = {"settings": {"outro_seconds": 8}, "source": "original"}
        identifier = self.repository.submit("note-001", "audio", recipe)
        recipe["settings"]["outro_seconds"] = 2
        self.repository.claim()
        self.repository.event(identifier, "audio", "Finishing audio")
        self.repository.publication("note-001", "https://youtu.be/example", "2026-10-14")
        reopened = Repository(self.path)
        self.assertEqual(reopened.get(identifier).status, "running")
        self.assertEqual(
            json.loads(reopened.get(identifier).request)["settings"]["outro_seconds"], 8
        )
        self.assertEqual(reopened.events(identifier)[0]["message"], "Finishing audio")
        self.assertEqual(reopened.publications()["note-001"][1], "2026-10-14")

    def test_concurrent_windows_cannot_queue_conflicting_jobs(self):
        def submit(index):
            try:
                return Repository(self.path).submit("note-001", "audio", {})
            except ValueError:
                return None

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(submit, range(4)))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_distinct_episodes_are_claimed_in_submission_order(self):
        first = self.repository.submit("note-001", "audio", {})
        second = self.repository.submit("note-002", "audio", {})
        self.assertEqual(self.repository.claim().identifier, first)
        self.repository.finish(first, "succeeded")
        self.assertEqual(self.repository.claim().identifier, second)

    def test_worker_recovery_never_claims_unknown_work_succeeded(self):
        identifier = self.repository.submit("note-001", "audio", {})
        self.repository.claim()
        self.repository.recover()
        self.assertEqual(self.repository.get(identifier).status, "interrupted")
        self.assertIn("Inspect outputs", self.repository.get(identifier).error)
        retry = self.repository.submit("note-001", "audio", {})
        self.assertNotEqual(identifier, retry)

    def test_stop_request_is_durable_and_terminal_jobs_cannot_be_stopped(self):
        identifier = self.repository.submit("note-001", "audio", {})
        self.repository.cancel(identifier)
        self.assertTrue(Repository(self.path).stopped(identifier))
        self.repository.finish(identifier, "cancelled")
        second = self.repository.submit("note-002", "audio", {})
        self.repository.finish(second, "succeeded")
        self.repository.cancel(second)
        self.assertFalse(self.repository.stopped(second))
