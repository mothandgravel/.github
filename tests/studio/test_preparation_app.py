"""The real Studio entry point and durable queue; Cloud calls remain forbidden."""

import os
import subprocess
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_studio.models import Episode
from tests.studio import test_preparation_execution as fixtures


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class PreparationApplicationTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk

        from field_notes_studio.app import Application

        self.fixture = fixtures.PreparationExecutionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        for name in (
            "field_notes_studio.controller.launch_worker",
            "field_notes_studio.preparation_service.launch_worker",
            "field_notes_studio.service.launch_worker",
        ):
            mock = patch(name)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch("socket.create_connection", side_effect=AssertionError("Unexpected network"))
        mock.start()
        self.addCleanup(mock.stop)
        self.root = tk.Tk()
        self.app = Application(self.root, self.fixture.root)
        self.addCleanup(lambda: self.app.close() if not self.app.closed else None)
        self.app.prepare_button.invoke()
        self.wait(lambda: self.app.preparation.view.tree.exists("104"))
        self.view = self.app.preparation.view
        self.view.tree.selection_set("104")
        self.root.update()

    def wait(self, condition):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(0.01)
        self.fail("Studio did not reach the requested state")

    def inspect(self):
        self.view.inspect_button.invoke()
        self.wait(lambda: self.view.snapshot is not None)
        self.assertTrue(self.view.snapshot.request_json)

    def capture(self, name):
        destination = os.environ.get("STUDIO_SCREENSHOT_DIR")
        if not destination:
            return
        directory = Path(destination)
        directory.mkdir(parents=True, exist_ok=True)
        window = self.view.window
        window.geometry("760x580+0+0")
        window.lift()
        self.root.update()
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "x11grab",
                "-draw_mouse",
                "0",
                "-video_size",
                f"{window.winfo_width()}x{window.winfo_height()}",
                "-i",
                f"{os.environ['DISPLAY']}+{window.winfo_rootx()},{window.winfo_rooty()}",
                "-frames:v",
                "1",
                "-threads",
                "1",
                "-update",
                "1",
                "-y",
                str(directory / f"{name}.png"),
            ],
            check=True,
            timeout=15,
            stdout=subprocess.DEVNULL,
        )

    def test_real_header_inspection_consent_and_queue_handoff(self):
        original = self.app.preparation
        self.app.prepare_button.invoke()
        self.assertIs(self.app.preparation, original)
        self.wait(lambda: not self.app.preparation.busy)
        self.inspect()
        self.view.queue_button.invoke()
        self.assertEqual(self.fixture.repository.jobs(), [])
        self.view.authorization.invoke()
        self.assertFalse(self.view.queue_button.instate(["disabled"]))
        self.capture("preparation-authorized-fixture")
        self.view.queue_button.invoke()
        self.wait(lambda: len(self.fixture.repository.jobs()) == 1)
        identifier = self.fixture.repository.jobs()[0].identifier
        self.app.controller.poll()
        self.wait(lambda: identifier in self.app.jobs.jobs)
        self.assertEqual(self.app.jobs.jobs[identifier].action, "prepare")
        self.assertEqual(self.app.jobs.jobs[identifier].status, "queued")
        self.assertIsNone(self.view.snapshot)
        self.assertFalse(self.view.authorized.get())
        self.assertTrue(self.app.jobs.buttons["review"].instate(["disabled"]))

    def test_closing_preparation_keeps_the_job_but_never_restores_authorization(self):
        self.inspect()
        self.view.authorization.invoke()
        self.view.queue_button.invoke()
        self.wait(lambda: len(self.fixture.repository.jobs()) == 1)
        self.app.preparation.close()
        self.app.open_preparation()
        self.view = self.app.preparation.view
        self.wait(lambda: self.view.tree.exists("104"))
        self.assertFalse(self.view.authorized.get())
        self.assertEqual(len(self.fixture.repository.jobs()), 1)
        self.view.tree.selection_set("104")
        self.root.update()
        self.view.inspect_button.invoke()
        self.wait(lambda: self.view.snapshot is not None)
        self.assertEqual(self.view.snapshot.request_json, "")
        self.assertTrue(self.view.queue_button.instate(["disabled"]))

    def test_waiting_job_shows_resume_and_never_offers_media_review(self):
        repository = self.fixture.repository
        identifier = repository.submit("studio-essay", "prepare", self.fixture.request)
        repository.claim()
        repository.pause(
            identifier,
            "Captions are still running",
            {
                "operation": "projects/fixture-project/locations/us/operations/fixture",
                "fingerprint": "a" * 64,
                "audio_sha256": "b" * 64,
            },
        )
        self.app.jobs.render(repository.jobs())
        self.root.update()
        self.assertEqual(self.app.jobs.buttons["retry"].cget("text"), "Resume")
        self.assertFalse(self.app.jobs.buttons["retry"].instate(["disabled"]))
        self.assertTrue(self.app.jobs.buttons["stop"].instate(["disabled"]))
        self.assertTrue(self.app.jobs.buttons["review"].instate(["disabled"]))
        self.app.jobs.buttons["retry"].invoke()
        self.wait(lambda: repository.get(identifier).status == "queued")
        self.assertEqual([job.identifier for job in repository.jobs()], [identifier])
        self.assertIn("resume", repository.get(identifier).request)

    def test_new_recording_refresh_preserves_existing_unsaved_controls_and_filter(self):
        existing = Episode("already-prepared", "Existing edition", 10, "An existing transcript")
        added = Episode("studio-essay", "New prepared note", 4, "New transcript")
        with (
            patch.object(self.app.controller.studio, "catalog", return_value=[existing]),
            patch.object(
                self.app.controller.studio,
                "review_snapshot",
                side_effect=ValueError("Not produced"),
            ),
            patch.object(
                self.app.controller.studio,
                "release_details",
                side_effect=ValueError("Not exported"),
            ),
            patch.object(
                self.app.controller.studio,
                "metadata_editor",
                side_effect=ValueError("Not exported"),
            ),
        ):
            self.app.controller.loaded([existing])
            self.wait(
                lambda: self.app.controller.selected == existing.identifier
                and not self.app.controller.loading
            )
            self.app.workspace.speed.set("1.")
            self.app.workspace.outro.set("unfinished")
            self.app.workspace.publication.url.set("https://example.invalid/unfinished")
            self.app.workspace.publication.date.set("2026-")
            self.app.shelf.query.set("Existing")
            self.app.workspace.batch.choices[existing.identifier].set(True)
            self.root.update()
            self.app.controller.refresh_prepared_shelf([existing, added])
            self.root.update()
            self.assertEqual(self.app.controller.selected, existing.identifier)
            self.assertEqual(self.app.workspace.speed.get(), "1.")
            self.assertEqual(self.app.workspace.outro.get(), "unfinished")
            self.assertEqual(self.app.workspace.publication.date.get(), "2026-")
            self.assertEqual(
                self.app.workspace.publication.url.get(), "https://example.invalid/unfinished"
            )
            self.assertEqual(self.app.shelf.query.get(), "Existing")
            self.assertEqual(self.app.workspace.batch.selection(), [existing.identifier])
            self.assertIn(added.identifier, self.app.controller.episodes)
