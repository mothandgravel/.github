"""Worker behavior at durable boundaries, independent of Tk availability."""

import tempfile
import unittest
from pathlib import Path

from field_notes_audio.progress import stage
from field_notes_studio.repository import Repository
from field_notes_studio.worker import execute


class WorkerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repository = Repository(Path(temporary.name) / "studio.sqlite3")
        self.identifier = self.repository.submit("note-001", "audio", {})
        self.job = self.repository.claim()

    def test_cancelled_queued_job_never_calls_production(self):
        self.repository.cancel(self.identifier)

        class Pipeline:
            def run(self, *_args):
                raise AssertionError("A stopped job must not produce")

        execute(self.repository, Pipeline(), self.job)
        self.assertEqual(self.repository.get(self.identifier).status, "cancelled")

    def test_stop_during_audio_keeps_completed_cache_and_prevents_next_stage(self):
        repository, identifier = self.repository, self.identifier

        class Pipeline:
            def run(self, _episode, _action, _request, directory, emit):
                emit("audio", "Finishing")
                (directory / "completed.mp3").write_bytes(b"saved")
                repository.cancel(identifier)
                stage("audio-complete", "Saved")
                raise AssertionError("The next stage must not start")

        execute(repository, Pipeline(), self.job)
        self.assertEqual(repository.get(identifier).status, "cancelled")
        self.assertTrue((repository.path.parent / "jobs" / identifier / "completed.mp3").exists())

    def test_failure_and_success_are_recorded_without_a_window(self):
        class Pipeline:
            def run(self, *_args):
                raise ValueError("Missing FFmpeg")

        execute(self.repository, Pipeline(), self.job)
        self.assertEqual(self.repository.get(self.identifier).error, "Missing FFmpeg")
        self.assertEqual(self.repository.get(self.identifier).status, "failed")
        self.repository.submit("note-002", "audio", {})
        job = self.repository.claim()

        class Success:
            def run(self, *_args):
                stage("audio", "Checked")
                return "/completed/edition"

        execute(self.repository, Success(), job)
        self.assertEqual(self.repository.get(job.identifier).result, "/completed/edition")
        self.assertEqual(self.repository.events(job.identifier)[1]["stage"], "audio")
