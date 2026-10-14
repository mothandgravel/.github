"""Exercise real Tk event delivery, planning and reopen behavior under Xvfb."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_audio.storage import read_object, write_json
from field_notes_studio.models import Episode


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class UITests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk

        from field_notes_studio.app import Application

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        defaults = Path(__file__).resolve().parents[2] / "audio/production/settings.json"
        write_json(self.directory / "audio/production/settings.json", read_object(defaults))
        episode = Episode("note-001", "Curiosity with calluses.", 199, "A studio transcript.")
        for mock in [
            patch("field_notes_studio.controller.launch_worker"),
            patch("field_notes_studio.service.launch_worker"),
            patch("field_notes_studio.pipeline.Pipeline.catalog", return_value=[episode]),
            patch("field_notes_studio.pipeline.Pipeline.source", return_value={"id": "note-001"}),
        ]:
            mock.start()
            self.addCleanup(mock.stop)
        self.root = tk.Tk()
        self.app = Application(self.root, self.directory)
        self.addCleanup(lambda: self.app.close() if not self.app.closed else None)
        self.wait(lambda: self.app.controller.selected and not self.app.controller.loading)

    def wait(self, condition):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(0.01)
        self.fail("UI did not reach the requested state")

    def test_edit_plan_queue_close_and_reopen(self):
        import tkinter as tk

        from field_notes_studio.app import Application

        self.app.workspace.outro.set("8")
        self.app.controller.inspect()
        self.wait(lambda: self.app.controller.ready is not None)
        self.assertEqual(str(self.app.workspace.produce["state"]), "normal")
        self.app.workspace.outro.set("10")
        self.assertIsNone(self.app.controller.ready)
        self.assertEqual(str(self.app.workspace.produce["state"]), "disabled")
        self.app.controller.inspect()
        self.wait(lambda: self.app.controller.ready is not None)
        self.app.workspace.produce.invoke()
        self.wait(lambda: bool(self.app.controller.studio.repository.jobs()))
        job = self.app.controller.studio.repository.claim()
        self.app.close()
        self.root = tk.Tk()
        self.app = Application(self.root, self.directory)
        self.wait(lambda: self.app.controller.selected and not self.app.controller.loading)
        self.assertEqual(self.app.workspace.outro.get(), "10")
        self.assertEqual(
            self.app.controller.studio.repository.get(job.identifier).status, "running"
        )
        self.app.controller.poll()
        self.wait(lambda: self.app.jobs.tree.exists(job.identifier))
        self.app.jobs.tree.selection_set(job.identifier)
        self.app.controller.stop()
        self.wait(lambda: self.app.controller.studio.repository.stopped(job.identifier))

    def test_publication_link_remains_separate_from_production(self):
        self.app.workspace.url.set("https://youtu.be/published-episode")
        self.app.workspace.date.set("2026-10-14")
        self.app.controller.publication()
        self.wait(lambda: bool(self.app.controller.studio.repository.publications()))
        self.assertEqual(self.app.controller.studio.repository.jobs(), [])

    def test_shelf_rows_and_status_remain_visible_at_minimum_window_size(self):
        self.root.geometry("1050x760")
        self.root.update()
        tree = self.app.shelf.tree
        bounds = tree.bbox("note-001")
        self.assertTrue(bounds)
        x, y, _, _ = bounds
        visible = self.root.winfo_containing(tree.winfo_rootx() + x + 5, tree.winfo_rooty() + y + 5)
        self.assertIs(visible, tree)
        bottom = self.app.message.winfo_rooty() + self.app.message.winfo_height()
        self.assertLessEqual(bottom, self.root.winfo_rooty() + self.root.winfo_height())
