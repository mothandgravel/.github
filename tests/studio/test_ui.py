"""Exercise real Tk event delivery, planning and reopen behavior under Xvfb."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_audio.storage import read_object, write_json
from field_notes_studio.models import Episode, ReviewSnapshot


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

    def test_review_requires_explicit_checks_and_resets_on_scope_change(self):
        snapshot = ReviewSnapshot("identity", "Audio pending", "/tmp/audio", "/tmp/captions")
        review = self.app.workspace.review
        review.load(snapshot)
        review.reviewer.set("Test listener")
        review.audio_checked.set(True)
        self.assertEqual(str(review.approve["state"]), "disabled")
        review.captions_checked.set(True)
        self.assertEqual(str(review.approve["state"]), "normal")
        with (
            patch.object(self.app.controller.studio, "approve") as approve,
            patch.object(self.app.controller.studio, "review_snapshot", return_value=snapshot),
        ):
            review.approve.invoke()
            self.wait(lambda: approve.called)
            self.wait(lambda: not review.busy)
            approve.assert_called_once_with("note-001", snapshot, "Test listener")
        self.assertFalse(review.audio_checked.get())
        self.assertEqual(str(review.approve["state"]), "disabled")
        self.assertEqual(str(review.asset_buttons["video"]["state"]), "disabled")
        review.scope.set("Full video and audio")
        self.app.controller.refresh_review()
        self.assertIsNone(review.snapshot)
        self.assertFalse(review.captions_checked.get())

    def test_selected_episode_cannot_receive_an_old_review_snapshot(self):
        pending = []
        self.app.controller.task = lambda operation, callback, on_error=None: pending.append(
            (operation, callback)
        )
        self.app.controller.refresh_review()
        _, callback = pending.pop()
        self.app.controller.selected = "note-002"
        callback(ReviewSnapshot("old", "Old episode", "/tmp/audio", "/tmp/captions"))
        self.assertIsNone(self.app.workspace.review.snapshot)

    def test_failed_review_clears_checks_and_reenables_refresh(self):
        review = self.app.workspace.review
        review.load(ReviewSnapshot("identity", "Pending", "/tmp/audio", "/tmp/captions"))
        review.reviewer.set("Test listener")
        review.audio_checked.set(True)
        review.captions_checked.set(True)
        with patch.object(
            self.app.controller.studio, "approve", side_effect=ValueError("Edition changed")
        ):
            review.approve.invoke()
            self.wait(lambda: not review.busy)
        self.assertIsNone(review.snapshot)
        self.assertFalse(review.captions_checked.get())
        self.assertIn("Edition changed", review.summary["text"])

    def test_review_approval_and_assets_are_visible_at_minimum_window_size(self):
        from tkinter import ttk

        self.root.geometry("1050x760")
        review = self.app.workspace.review
        review.load(
            ReviewSnapshot(
                "identity",
                "Audio and captions: pending · 3.1 min\n"
                "Saved edition: 0123456789abcdef · 1.15× pace · 8s outro\n"
                "Open the saved assets below, check them, then record your review.",
                "/tmp/audio",
                "/tmp/captions",
            )
        )
        ttk.Notebook.nametowidget(self.app.workspace, review.winfo_parent()).select(review)
        self.root.update()
        for widget in (*review.asset_buttons.values(), review.approve):
            review.reveal(widget)
            self.root.update()
            x = widget.winfo_rootx() + widget.winfo_width() // 2
            y = widget.winfo_rooty() + widget.winfo_height() // 2
            self.assertIs(self.root.winfo_containing(x, y), widget)

    def queue_job(self, action="audio", episode="note-001", status="queued", result=""):
        repository = self.app.controller.studio.repository
        identifier = repository.submit(
            episode, action, {"settings": {"speed": 1.15, "outro_seconds": 8}}
        )
        if status != "queued":
            repository.finish(identifier, status, result=result)
        self.app.jobs.render(repository.jobs())
        self.app.jobs.tree.selection_set(identifier)
        self.root.update()
        return identifier

    def test_queue_controls_follow_job_state_and_conflicting_retries(self):
        repository = self.app.controller.studio.repository
        buttons = self.app.jobs.buttons
        self.assertTrue(all(button.instate(["disabled"]) for button in buttons.values()))
        identifier = self.queue_job()
        self.assertFalse(buttons["stop"].instate(["disabled"]))
        self.assertTrue(buttons["retry"].instate(["disabled"]))
        repository.cancel(identifier)
        self.app.jobs.render(repository.jobs())
        self.assertTrue(buttons["stop"].instate(["disabled"]))
        repository.finish(identifier, "interrupted", error="Unknown outcome")
        self.app.jobs.render(repository.jobs())
        self.assertFalse(buttons["retry"].instate(["disabled"]))
        self.assertIn("1 need attention", self.app.jobs.summary["text"])
        self.assertTrue(buttons["open"].instate(["disabled"]))
        repository.submit("note-001", "audio", {"settings": {}})
        self.app.jobs.render(repository.jobs())
        self.assertTrue(buttons["retry"].instate(["disabled"]))

    def test_completed_preview_opens_selected_job_and_is_not_offered_for_approval(self):
        identifier = self.queue_job("preview", status="succeeded", result="/tmp/preview")
        buttons = self.app.jobs.buttons
        self.assertEqual(buttons["open"]["text"], "Watch preview")
        self.assertTrue(buttons["review"].instate(["disabled"]))
        with patch.object(self.app.controller.studio, "open_job_output") as opened:
            buttons["open"].invoke()
            self.wait(lambda: opened.called)
            opened.assert_called_once_with(identifier)

    def test_review_job_reveals_filtered_episode_and_selects_full_video_scope(self):
        from field_notes_studio.models import Episode

        episode = Episode("note-002", "Second episode", 90, "Second transcript")
        self.app.controller.episodes[episode.identifier] = episode
        self.app.shelf.load(list(self.app.controller.episodes.values()))
        self.app.shelf.query.set("Curiosity")
        self.assertFalse(self.app.shelf.tree.exists("note-002"))
        self.queue_job("video", episode="note-002", status="succeeded", result="/tmp/video")
        snapshot = ReviewSnapshot("video", "Full video pending", full_video=True)
        with patch.object(self.app.controller.studio, "review_snapshot", return_value=snapshot):
            self.app.jobs.buttons["review"].invoke()
            self.wait(lambda: self.app.workspace.review.snapshot == snapshot)
        self.assertEqual(self.app.controller.selected, "note-002")
        self.assertEqual(self.app.shelf.tree.selection(), ("note-002",))
        self.assertTrue(self.app.workspace.review.full_video())
        self.assertEqual(self.app.workspace.tabs.select(), str(self.app.workspace.review))
        self.assertFalse(self.app.workspace.review.audio_checked.get())

    def test_export_disables_recipe_controls_and_queue_actions_fit_small_window(self):
        workspace = self.app.workspace
        workspace.action.set("export")
        self.assertTrue(workspace.speed_control.instate(["disabled"]))
        self.assertTrue(workspace.outro_control.instate(["disabled"]))
        workspace.action.set("audio")
        self.assertFalse(workspace.speed_control.instate(["disabled"]))
        self.queue_job(status="succeeded", result="/tmp/audio")
        self.root.geometry("1050x760")
        self.root.update()
        for widget in (*self.app.jobs.buttons.values(), self.app.message):
            x = widget.winfo_rootx() + widget.winfo_width() // 2
            y = widget.winfo_rooty() + widget.winfo_height() // 2
            self.assertIs(self.root.winfo_containing(x, y), widget)
