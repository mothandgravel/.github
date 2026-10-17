"""Exercise real Tk event delivery, planning and reopen behavior under Xvfb."""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_audio.storage import read_object, write_json
from field_notes_studio.models import (
    Episode,
    PackageFile,
    PackageSnapshot,
    ReleaseDetails,
    ReviewSnapshot,
)


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
        write_json(
            self.directory / "audio/production/publishing.json",
            read_object(defaults.with_name("publishing.json")),
        )
        episode = Episode(
            "note-001",
            "Curiosity with calluses.",
            199,
            "A studio transcript.",
            "https://mothandgravel.com/notes/001-curiosity-with-calluses.html",
            "2026-10-13",
            "Podcast catalog in this checkout; external platforms have not been checked.",
            podcast_url="https://mothandgravel.com/notes/001-curiosity-with-calluses.html",
            podcast_date="2026-10-13",
        )
        for mock in [
            patch("field_notes_studio.controller.launch_worker"),
            patch("field_notes_studio.service.launch_worker"),
            patch("field_notes_studio.pipeline.Pipeline.preflight"),
            patch("field_notes_studio.pipeline.Pipeline.catalog", return_value=[episode]),
            patch(
                "field_notes_studio.pipeline.Pipeline.source",
                return_value={
                    "id": "note-001",
                    "title": episode.title,
                    "description": "Episode summary",
                    "slug": "001-curiosity-with-calluses.html",
                    "published_at": "2026-10-13T22:04:00+00:00",
                },
            ),
        ]:
            mock.start()
            self.addCleanup(mock.stop)
        self.root = tk.Tk()
        self.app = Application(self.root, self.directory)
        self.addCleanup(lambda: self.app.close() if not self.app.closed else None)
        self.wait(lambda: self.app.controller.selected and not self.app.controller.loading)
        self.wait(lambda: self.app.workspace.publication.details is not None)

    def wait(self, condition):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(0.01)
        self.fail("UI did not reach the requested state")

    def capture(self, name):
        """Optional CI evidence from the real Tk window, using existing FFmpeg tooling."""
        destination = os.environ.get("STUDIO_SCREENSHOT_DIR")
        if not destination:
            return
        directory = Path(destination)
        directory.mkdir(parents=True, exist_ok=True)
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
                f"{self.root.winfo_width()}x{self.root.winfo_height()}",
                "-i",
                f"{os.environ['DISPLAY']}+{self.root.winfo_rootx()},{self.root.winfo_rooty()}",
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

    def assert_visible(self, widget):
        """Check the button's edges too; a visible center can conceal clipping."""
        left, top = widget.winfo_rootx(), widget.winfo_rooty()
        right, bottom = left + widget.winfo_width() - 3, top + widget.winfo_height() - 3
        for x, y in ((left + 2, top + 2), (right, top + 2), (left + 2, bottom), (right, bottom)):
            self.assertIs(self.root.winfo_containing(x, y), widget)

    def test_edit_plan_queue_close_and_reopen(self):
        import tkinter as tk

        from field_notes_studio.app import Application

        self.app.workspace.outro.set("8")
        self.app.controller.inspect()
        self.wait(lambda: self.app.controller.ready is not None)
        self.assertEqual(str(self.app.workspace.produce["state"]), "normal")
        # The two-step plan is an expert path behind More options; Produce episode is primary.
        self.assertFalse(self.app.workspace.produce.winfo_ismapped())
        self.app.workspace.more_button.invoke()
        self.root.update()
        self.app.workspace.produce.focus_force()
        self.root.update()
        self.assertIs(self.root.focus_get(), self.app.workspace.produce)
        self.capture("produce-inspected-plan")
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

    def test_unqueued_partial_edits_and_session_survive_closing(self):
        import tkinter as tk

        from field_notes_studio.app import Application

        workspace = self.app.workspace
        self.wait(lambda: workspace.publication.editor.loaded)
        workspace.speed.set("1.")
        workspace.outro.set("")
        workspace.sound.values["music_gain_db"].set("-2")
        workspace.sound.values["music_credit"].set("A credit\nLicense details")
        workspace.url.set("unfinished link")
        workspace.date.set("2026-")
        workspace.publication.editor.values["description"].set(
            "Paragraph one.\n\nUnfinished paragraph two"
        )
        workspace.batch.choices["note-001"].set(True)
        workspace.tabs.select(workspace.publication)
        workspace.publication.open_editor()
        self.root.update()
        self.app.close()
        self.assertTrue(self.app.closed)
        self.root = tk.Tk()
        self.app = Application(self.root, self.directory)
        self.wait(lambda: self.app.controller.selected and not self.app.controller.loading)
        workspace = self.app.workspace
        self.wait(lambda: workspace.publication.editor.loaded)
        self.assertEqual(workspace.speed.get(), "1.")
        self.assertEqual(workspace.outro.get(), "")
        self.assertEqual(workspace.sound.raw()["music_credit"], "A credit\nLicense details")
        self.assertEqual(workspace.url.get(), "unfinished link")
        self.assertEqual(workspace.date.get(), "2026-")
        self.assertEqual(workspace.batch.selection(), ["note-001"])
        self.assertEqual(
            workspace.publication.editor.raw()["description"],
            "Paragraph one.\n\nUnfinished paragraph two",
        )
        self.assertEqual(workspace.tabs.select(), str(workspace.publication))
        self.assertIsNone(self.app.controller.ready)
        self.assertFalse(workspace.review.audio_checked.get())
        self.assertEqual(self.app.controller.studio.repository.jobs(), [])
        self.assertEqual(self.app.controller.studio.repository.publications(), {})

    def test_drafts_checkpoint_without_closing_and_loading_does_not_replace_them(self):
        repository = self.app.controller.studio.repository
        self.app.workspace.speed.set("unfinished")
        self.wait(
            lambda: repository.state("draft:note-001").get("recipe", {}).get("speed")
            == "unfinished"
        )
        self.app.controller.loading = True
        self.app.workspace.speed.set("temporary loading value")
        self.app.controller.checkpoint()
        self.assertEqual(repository.state("draft:note-001")["recipe"]["speed"], "unfinished")
        self.app.controller.loading = False

    def test_checkpoint_failure_keeps_the_window_and_edits_open(self):
        self.app.workspace.outro.set("unfinished")
        with patch.object(
            self.app.controller.studio.repository, "checkpoint", side_effect=OSError("disk full")
        ):
            self.app.close()
        self.assertFalse(self.app.closed)
        self.assertFalse(self.app.controller.closed)
        self.assertEqual(self.app.workspace.outro.get(), "unfinished")
        self.assertIn("disk full", self.app.message["text"])

    def test_other_window_draft_conflict_keeps_both_versions_and_can_be_resolved(self):
        from field_notes_studio.models import DraftConflict
        from field_notes_studio.repository import Repository

        controller = self.app.controller
        self.wait(lambda: self.app.workspace.publication.editor.loaded)
        controller.checkpoint()
        other = Repository(controller.studio.repository.path)
        draft = other.state("draft:note-001")
        draft["recipe"]["outro"] = "9"
        other.checkpoint({"draft:note-001": draft})
        self.app.workspace.outro.set("7")
        with self.assertRaises(DraftConflict):
            controller.checkpoint()
        self.root.update()
        self.assertEqual(other.state("draft:note-001")["recipe"]["outro"], "9")
        self.assertEqual(self.app.workspace.outro.get(), "7")
        for button in self.app.workspace.conflict.winfo_children()[1].winfo_children():
            self.assert_visible(button)
        self.capture("draft-conflict")
        controller.resolve_draft(True)
        self.assertEqual(other.state("draft:note-001")["recipe"]["outro"], "7")
        copies = list((other.path.parent / "draft-recovery").glob("*.json"))
        self.assertEqual(
            {read_object(path)["draft"]["recipe"]["outro"] for path in copies}, {"7", "9"}
        )
        self.assertFalse(self.app.workspace.conflict.winfo_ismapped())

    def test_unchanged_window_can_close_without_overwriting_the_other_draft(self):
        controller = self.app.controller
        self.wait(lambda: self.app.workspace.publication.editor.loaded)
        controller.checkpoint()
        repository = controller.studio.repository
        draft = repository.state("draft:note-001")
        draft["recipe"]["outro"] = "9"
        repository.checkpoint({"draft:note-001": draft})
        self.app.close()
        self.assertTrue(self.app.closed)
        self.assertEqual(repository.state("draft:note-001")["recipe"]["outro"], "9")

    def test_failed_settings_load_cannot_queue_or_checkpoint_the_previous_controls(self):
        controller = self.app.controller
        self.wait(lambda: self.app.workspace.publication.editor.loaded)
        controller.checkpoint()
        episode = Episode("note-002", "Second episode", 90, "Second transcript")
        controller.episodes[episode.identifier] = episode
        self.app.shelf.load(list(controller.episodes.values()))
        repository = controller.studio.repository
        repository.checkpoint({"draft:note-002": {"recipe": {"speed": "1.3", "outro": "6"}}})
        self.app.workspace.speed.set("1.1")
        with patch.object(
            controller.studio, "settings", side_effect=OSError("settings unavailable")
        ):
            controller.select("note-002")
            self.wait(lambda: controller.selected is None and not controller.loading)
        controller.checkpoint()
        controller.inspect()
        self.assertIsNone(controller.ready)
        self.assertEqual(repository.state("draft:note-002")["recipe"]["speed"], "1.3")
        controller.select("note-002")
        self.wait(lambda: controller.selected == "note-002" and not controller.loading)
        self.assertEqual(self.app.workspace.speed.get(), "1.3")

    def test_sound_batch_and_health_surfaces_fit_the_minimum_window(self):
        workspace = self.app.workspace
        self.wait(lambda: workspace.publication.editor.loaded)
        self.root.geometry("1050x760")
        self.queue_job(status="interrupted")
        workspace.tabs.select(workspace.sound)
        self.root.update()
        workspace.sound.form.reveal(workspace.sound.widgets["music_credit"])
        self.root.update()
        self.capture("sound-recipe")
        workspace.tabs.select(workspace.batch)
        self.root.update()
        self.assert_visible(workspace.batch.queue)
        group = workspace.batch.form.content.winfo_children()[0]
        self.assertEqual(group.legend.cget("text"), "Episodes to include")
        self.assert_visible(group.body.winfo_children()[0])
        self.capture("batch-inspection")
        workspace.tabs.select(workspace.publication)
        workspace.publication.open_editor()
        workspace.publication.editor_window.geometry("+0+0")
        self.root.update()
        self.assert_visible(workspace.publication.editor.save)
        self.assert_visible(workspace.publication.editor.widgets["title"])
        workspace.publication.close_editor()
        self.capture("publishing-editor")
        workspace.tool_buttons[str(workspace.health.master)].invoke()
        with patch.object(
            self.app.controller.studio,
            "health",
            return_value="Worker current · idle\nAudio preflight: ready\nFull video preflight: ready",
        ):
            self.app.controller.health()
            self.wait(lambda: "Worker current" in workspace.health.get("1.0", "end"))
        self.root.update()
        for button in workspace.health_actions.winfo_children():
            self.assert_visible(button)
        self.capture("worker-health")

    def test_batch_inspection_is_invalidated_by_new_recipe_edits(self):
        workspace = self.app.workspace
        workspace.batch.choices["note-001"].set(True)
        self.app.controller.inspect_batch()
        self.wait(lambda: self.app.controller.batch_ready is not None)
        workspace.outro.set("7")
        self.assertIsNone(self.app.controller.batch_ready)
        self.assertTrue(workspace.batch.queue.instate(["disabled"]))
        self.app.controller.inspect_batch()
        self.wait(lambda: self.app.controller.batch_ready is not None)
        workspace.batch.queue.invoke()
        self.wait(lambda: bool(self.app.controller.studio.repository.jobs()))
        self.assertIsNone(self.app.controller.batch_ready)
        self.assertEqual(len(self.app.controller.studio.repository.jobs()), 1)

    def test_publication_link_remains_separate_from_production(self):
        self.app.workspace.url.set("https://youtu.be/published-episode")
        self.app.workspace.date.set("2026-10-14")
        self.app.controller.publication()
        self.wait(lambda: bool(self.app.controller.studio.repository.publications()))
        self.wait(lambda: self.app.controller.episodes["note-001"].publication_saved)
        self.assertNotIn("note-001", self.app.workspace.publication.drafts)
        self.assertEqual(self.app.workspace.date.get(), "2026-10-14")
        self.assertEqual(self.app.controller.studio.repository.jobs(), [])

    def test_release_copy_is_ready_and_refresh_keeps_unsaved_publication_fields(self):
        publication = self.app.workspace.publication
        self.assertEqual(publication.details.title, "Curiosity with calluses.")
        publication.copy_buttons["Description"].invoke()
        self.assertIn("Written edition:", self.root.clipboard_get())
        self.assertIn("AI-narrated", self.root.clipboard_get())
        publication.url.set("https://youtu.be/finished-release")
        publication.date.set("2026-10-14")
        self.app.controller.refresh_release()
        self.wait(lambda: publication.details is not None)
        self.assertEqual(publication.url.get(), "https://youtu.be/finished-release")
        self.assertEqual(publication.date.get(), "2026-10-14")
        publication.use_defaults()
        self.assertEqual(publication.date.get(), "2026-10-13")
        publication.url.set("https://youtu.be/another-release")
        self.assertEqual(publication.date.get(), "")
        publication.use_defaults()
        publication.date.set("2026-10-15")
        publication.url.set("https://youtu.be/another-release")
        self.assertEqual(publication.date.get(), "2026-10-15")

    def test_release_makes_the_upload_folder_from_a_checked_export_plan_only(self):
        publication = self.app.workspace.publication
        self.app.workspace.tabs.select(publication)
        controls = self.app.controller.episode_controls
        self.wait(lambda: not controls.busy)
        with patch.object(
            self.app.controller.studio,
            "checked_plan",
            return_value=({"edition": {}}, "Upload folder plan"),
        ) as plan:
            publication.actions["package"].invoke()
            self.wait(lambda: bool(self.app.controller.studio.repository.jobs()))
            self.wait(lambda: not controls.busy)
        self.assertEqual(plan.call_args.args, ("note-001", "export", None, None))
        self.assertEqual(
            [j.action for j in self.app.controller.studio.repository.jobs()], ["export"]
        )
        self.assertEqual(self.app.workspace.tabs.select(), str(publication))
        self.assertEqual(self.app.controller.studio.repository.publications(), {})

    def test_publication_drafts_survive_episode_switch_and_save_ack_keeps_newer_edits(self):
        controller = self.app.controller
        publication = self.app.workspace.publication
        other = Episode("note-002", "Other episode", 10, "Other transcript")
        controller.episodes[other.identifier] = other
        publication.url.set("https://youtu.be/unfinished")
        publication.date.set("2026-10-14")
        controller.select(other.identifier)
        self.wait(lambda: not controller.loading)
        self.assertEqual(publication.url.get(), "")
        controller.select("note-001")
        self.wait(lambda: not controller.loading)
        self.assertEqual(publication.url.get(), "https://youtu.be/unfinished")
        self.assertEqual(publication.date.get(), "2026-10-14")
        # A save in flight must not consume edits made after clicking Save.
        pending = []
        controller.task = lambda operation, callback, on_error=None: pending.append(
            (operation, callback)
        )
        controller.publication()
        operation, callback = pending.pop(0)
        callback(operation())
        publication.url.set("https://youtu.be/newer-draft")
        operation, callback = pending.pop(0)
        callback(operation())
        self.assertEqual(publication.url.get(), "https://youtu.be/newer-draft")
        publication.load_episode(controller.episodes["note-001"])
        self.assertEqual(publication.url.get(), "https://youtu.be/newer-draft")
        self.assertEqual(
            controller.studio.repository.publications()["note-001"][0],
            "https://youtu.be/unfinished",
        )

    def test_podcast_defaults_remain_available_when_upload_copy_fails(self):
        publication = self.app.workspace.publication
        publication.url.set("https://youtu.be/unfinished")
        with patch.object(
            self.app.controller.studio, "release_details", side_effect=ValueError("Damaged package")
        ):
            self.app.controller.refresh_release()
            self.wait(lambda: "Damaged package" in publication.basis["text"])
        self.assertFalse(publication.refresh.instate(["disabled"]))
        publication.defaults_button.invoke()
        self.assertEqual(
            publication.url.get(),
            "https://mothandgravel.com/notes/001-curiosity-with-calluses.html",
        )
        self.assertEqual(publication.date.get(), "2026-10-13")
        self.assertIsNone(publication.details)
        self.assertEqual(self.app.controller.studio.repository.publications(), {})

    def test_copy_feedback_is_local_and_resets_for_new_content_or_refresh(self):
        publication = self.app.workspace.publication
        title, description = (
            publication.copy_buttons["Title"],
            publication.copy_buttons["Description"],
        )
        title.invoke()
        self.assertEqual(title["text"], "Copied")
        self.assertTrue(title["image"])
        description.invoke()
        self.assertEqual(title["text"], "Copy")
        self.assertEqual(description["text"], "Copied")
        size = len((publication.details.description + "\n").encode("utf-8"))
        self.assertEqual(publication.measures["Description"]["text"], f"{size:,} / 5,000 bytes")
        self.assertEqual(publication.measures["Title"]["text"], "24 / 100")
        self.app.controller.refresh_release()
        self.assertTrue(description.instate(["disabled"]))
        self.assertNotEqual(description["text"], "Copied")
        self.assertEqual(publication.refresh["text"], "Refreshing…")
        self.wait(lambda: publication.details is not None)
        self.assertEqual(publication.refresh["text"], "Refresh")
        self.assertFalse(publication.refresh.instate(["disabled"]))

    def test_saved_feedback_resets_immediately_when_record_is_edited(self):
        publication = self.app.workspace.publication
        publication.url.set("https://youtu.be/published")
        publication.date.set("2026-10-15")
        self.assertEqual(publication.record_status["text"], "Unsaved changes")
        publication.save.invoke()
        self.wait(lambda: publication.record_status["text"] == "Saved locally")
        self.assertEqual(publication.save["text"], "Saved")
        publication.date.set("2026-10-16")
        self.assertEqual(publication.save["text"], "Save release record")
        self.assertEqual(publication.record_status["text"], "Unsaved changes")

    def test_shelf_reports_empty_search_and_recovers_without_changing_episode(self):
        self.app.shelf.query.set("No such episode")
        self.assertFalse(self.app.shelf.tree.get_children())
        self.assertIn("Nothing matches", self.app.shelf.count["text"])
        self.assertEqual(self.app.controller.selected, "note-001")
        self.app.shelf.query.set("")
        self.assertIn("1 of 1", self.app.shelf.count["text"])
        self.assertTrue(self.app.shelf.tree.exists("note-001"))
        self.assertEqual(self.app.shelf.tree.selection(), ("note-001",))

    def test_an_old_release_copy_cannot_replace_a_new_episode(self):
        pending = []
        self.app.controller.task = lambda operation, callback, on_error=None: pending.append(
            callback
        )
        self.app.controller.refresh_release()
        self.app.controller.selected = "note-002"
        pending.pop()(ReleaseDetails("Old", "", "", "", "", "", "Old episode"))
        self.assertIsNone(self.app.workspace.publication.details)

    def test_release_actions_and_record_save_remain_accessible_at_minimum_size(self):
        self.root.geometry("1050x760")
        publication = self.app.workspace.publication
        self.app.workspace.tabs.select(publication)
        self.root.update()
        self.assertFalse(self.app.workspace.controls.winfo_ismapped())
        self.capture("release-upload-details")
        for widget in (*publication.copy_buttons.values(), *publication.actions.values()):
            publication.page.reveal(widget)
            self.root.update()
            self.assert_visible(widget)
        publication.copy_buttons["Description"].invoke()
        self.capture("release-upload-description")
        for widget in (publication.url_entry, publication.date_entry, publication.save):
            publication.page.reveal(widget)
            self.root.update()
            x = widget.winfo_rootx() + widget.winfo_width() // 2
            y = widget.winfo_rooty() + widget.winfo_height() // 2
            self.assertIs(self.root.winfo_containing(x, y), widget)
        self.capture("release-publication-record")

    def test_shelf_rows_and_status_remain_visible_at_minimum_window_size(self):
        self.root.geometry("1050x760")
        self.root.update()
        tree = self.app.shelf.tree
        bounds = tree.bbox("note-001")
        self.assertTrue(bounds)
        x, y, _, _ = bounds
        visible = self.root.winfo_containing(tree.winfo_rootx() + x + 5, tree.winfo_rooty() + y + 5)
        self.assertIs(visible, tree)
        self.assert_visible(self.app.shelf.count)
        self.assert_visible(self.app.readiness.primary)
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
        self.capture("review-saved-edition")
        for widget in (*review.asset_buttons.values(), review.approve):
            review.reveal(widget)
            self.root.update()
            x = widget.winfo_rootx() + widget.winfo_width() // 2
            y = widget.winfo_rooty() + widget.winfo_height() // 2
            self.assertIs(self.root.winfo_containing(x, y), widget)

    def queue_job(self, action="audio", episode="note-001", status="queued", result=""):
        # A poll that read the empty queue earlier must not land after this render.
        self.wait(lambda: not self.app.controller.polling)
        repository = self.app.controller.studio.repository
        identifier = repository.submit(
            episode, action, {"settings": {"speed": 1.15, "outro_seconds": 8}}
        )
        if status != "queued":
            repository.finish(identifier, status, result=result)
        self.app.jobs.render(repository.jobs())
        self.app.toggle_jobs(True)
        self.app.jobs.tree.selection_set(identifier)
        self.root.update()
        return identifier

    def test_queue_controls_follow_job_state_and_conflicting_retries(self):
        repository = self.app.controller.studio.repository
        buttons = self.app.jobs.buttons
        self.assertTrue(all(button.instate(["disabled"]) for button in buttons.values()))
        self.assertFalse(self.app.jobs.region.winfo_ismapped())
        identifier = self.queue_job()
        self.assertTrue(self.app.jobs.region.winfo_ismapped())
        self.assertFalse(buttons["stop"].instate(["disabled"]))
        self.assertTrue(buttons["retry"].instate(["disabled"]))
        repository.cancel(identifier)
        self.app.jobs.render(repository.jobs())
        self.assertTrue(buttons["stop"].instate(["disabled"]))
        repository.finish(identifier, "interrupted", error="Unknown outcome")
        self.app.jobs.render(repository.jobs())
        self.assertFalse(buttons["retry"].instate(["disabled"]))
        self.assertIn("1 needs you", self.app.jobs.summary["text"])
        self.assertIn("1 job needs you", self.app.activity["text"])
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

    def test_attention_state_and_release_feedback_fit_minimum_window(self):
        self.root.geometry("1050x760")
        publication = self.app.workspace.publication
        self.app.workspace.tabs.select(publication)
        interrupted = self.queue_job(status="interrupted")
        self.queue_job(episode="note-002")
        self.root.update()
        self.assertEqual(self.app.jobs.tree.item(interrupted, "values")[2], "Interrupted")
        self.assertNotIn("Jobs will appear here", self.app.jobs.detail["text"])
        publication.copy_buttons["Title"].invoke()
        self.root.update()
        self.capture("release-copy-feedback")
        for widget in (*publication.copy_buttons.values(), *publication.actions.values()):
            publication.page.reveal(widget)
            self.root.update()
            self.assert_visible(widget)
        for widget in self.app.jobs.buttons.values():
            self.assert_visible(widget)

    def show_package_files(self, status="ready"):
        files = self.app.workspace.publication.files
        assets = tuple(
            PackageFile(
                name, purpose, size, str(self.directory / "artifacts/uploads/note-001" / name)
            )
            for name, purpose, size in (
                ("episode.mp4", "Video", 123456789),
                ("thumbnail.png", "Thumbnail", 123456),
                ("captions.srt", "Subtitles · SRT", 12345),
            )
        )
        snapshot = PackageSnapshot(
            "note-001",
            "package-version",
            status,
            "Files checked · current full edition · review approved. Ready for manual upload; platform publication is not checked.",
            assets,
        )
        # Keep the fixture for the whole test: polls and refreshes re-read the package.
        fixture = patch.object(
            self.app.controller.studio, "package_snapshot", return_value=snapshot
        )
        fixture.start()
        self.addCleanup(fixture.stop)
        self.app.workspace.tabs.select(self.app.workspace.publication)
        self.wait(lambda: files.snapshot == snapshot)
        return files

    def test_package_files_are_lazy_and_missing_package_has_a_next_step(self):
        files = self.app.workspace.publication.files
        self.assertIsNone(files.snapshot)
        self.app.workspace.tabs.select(self.app.workspace.publication)
        self.wait(lambda: files.snapshot is not None)
        self.assertEqual(files.snapshot.status, "missing")
        self.assertEqual(files.copy_buttons, {})
        self.assertIn("Make upload folder", files.summary["text"])
        self.assertFalse(files.folder.instate(["disabled"]))

    def test_package_file_actions_copy_picker_path_and_reset_for_another_asset(self):
        files = self.show_package_files()
        expected = r"\\wsl.localhost\Ubuntu\home\user\episode.mp4"
        self.assertEqual(list(files.copy_buttons), ["episode.mp4", "thumbnail.png", "captions.srt"])
        video = files.copy_buttons["episode.mp4"]
        with patch.object(
            self.app.controller.studio, "package_upload_path", return_value=expected
        ) as copied:
            video.invoke()
            self.wait(lambda: video["text"] == "Path copied")
            self.assertEqual(self.root.clipboard_get(), expected)
            copied.assert_called_once_with(files.snapshot, "episode.mp4")
        self.assertEqual(files.copy_buttons["thumbnail.png"]["text"], "Copy path")
        self.assertEqual(self.app.controller.studio.repository.publications(), {})

    def test_package_copy_completion_respects_new_file_selection_and_refresh(self):
        files = self.show_package_files()
        self.root.clipboard_clear()
        self.root.clipboard_append("Keep this clipboard")
        pending = []
        self.app.controller.task = lambda operation, callback, on_error=None: pending.append(
            callback
        )
        files.copy_buttons["episode.mp4"].invoke()
        self.assertTrue(files.copy_buttons["episode.mp4"].instate(["disabled"]))
        self.assertTrue(files.copy_buttons["thumbnail.png"].instate(["disabled"]))
        self.app.controller.refresh_package()
        pending.pop(0)("Old video path")
        self.assertEqual(self.root.clipboard_get(), "Keep this clipboard")
        self.app.controller.refresh_package()
        old = pending.pop(0)
        self.app.controller.refresh_package()
        old(PackageSnapshot("note-001", "old", "ready", "Old result"))
        self.assertEqual(files.copy_buttons, {})
        self.assertIsNone(files.snapshot)

    def test_package_action_failure_keeps_recovery_available(self):
        files = self.show_package_files()
        with patch.object(
            self.app.controller.studio,
            "package_upload_path",
            side_effect=ValueError("Package changed. Check files again."),
        ):
            files.copy_buttons["episode.mp4"].invoke()
            self.wait(lambda: "Package changed" in files.summary["text"])
        self.assertNotEqual(files.copy_buttons["episode.mp4"]["text"], "Path copied")
        self.assertFalse(files.copy_buttons["episode.mp4"].instate(["disabled"]))
        self.assertFalse(files.refresh.instate(["disabled"]))
        files.clear("Package files changed. Export again.")
        with patch.object(self.app.controller.studio, "open_output") as opened:
            files.folder.invoke()
            self.wait(lambda: opened.called)
            opened.assert_called_once_with("note-001", "uploads")

    def test_package_files_actions_fit_minimum_window_with_an_active_queue(self):
        self.root.geometry("1050x760")
        self.queue_job()
        files = self.show_package_files()
        # Layout only: a poll finishing now would rebuild the rows being measured.
        self.app.controller.polling = True
        self.root.update()
        self.assertFalse(self.app.workspace.outputs.winfo_ismapped())
        page = self.app.workspace.publication.page
        page.reveal(files)
        self.root.update()
        self.capture("release-package-files")
        for widget in (*files.copy_buttons.values(), files.folder, files.refresh):
            page.reveal(widget)
            self.root.update()
            self.assert_visible(widget)
