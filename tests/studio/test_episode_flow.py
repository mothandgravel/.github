"""Real actions for one full episode, one human review, and explicit publication data."""

import json
import os
import unittest
from datetime import date
from unittest.mock import patch

from field_notes_studio.job_history import resolved_failures
from field_notes_studio.models import Episode, Job, ReviewSnapshot
from tests.studio import test_preparation_execution, test_ui


class HistoryClassificationTests(unittest.TestCase):
    @staticmethod
    def job(identifier, action, status, episode="note-013"):
        return Job(
            identifier,
            episode,
            action,
            status,
            status,
            "2026-10-15T00:00:00+00:00",
            "old failure",
            "",
            "{}",
        )

    def test_later_success_resolves_prior_same_stage_without_mutating_history(self):
        earlier = self.job("old", "prepare", "failed")
        current = self.job("new", "prepare", "succeeded")
        self.assertEqual(resolved_failures([current, earlier]), {"old"})
        self.assertEqual(earlier.status, "failed")
        self.assertEqual(earlier.error, "old failure")

    def test_preview_and_export_do_not_resolve_full_video_failure(self):
        failed = self.job("old", "video", "failed")
        for action in ("preview", "export", "prepare", "audio"):
            with self.subTest(action=action):
                self.assertEqual(
                    resolved_failures([self.job("new", action, "succeeded"), failed]), set()
                )

    def test_full_video_resolves_earlier_audio_failure_not_a_new_failure(self):
        old = self.job("old", "audio", "failed")
        full = self.job("full", "video", "succeeded")
        newer = self.job("new", "video", "failed")
        self.assertEqual(resolved_failures([newer, full, old]), {"old"})

    def test_other_episode_success_is_not_recovery(self):
        self.assertEqual(
            resolved_failures(
                [
                    self.job("new", "prepare", "succeeded", "other"),
                    self.job("old", "prepare", "failed"),
                ]
            ),
            set(),
        )


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class EpisodeFlowUiTests(unittest.TestCase):
    def setUp(self):
        self.h = test_ui.UITests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.app, self.root = self.h.app, self.h.root
        self.c, self.w = self.app.controller, self.app.workspace
        self.repo = self.c.studio.repository
        self.forbid = patch(
            "socket.create_connection", side_effect=AssertionError("No network in local production")
        )
        self.forbid.start()
        self.addCleanup(self.forbid.stop)
        self.h.wait(lambda: self.w.publication.editor.loaded)
        self.root.update()

    def test_primary_button_queues_one_full_job_despite_an_audio_only_draft(self):
        self.w.action.set("audio")
        self.w.speed.set("1.25")
        self.w.outro.set("8")
        self.w.full_episode.invoke()
        self.w.full_episode.invoke()
        self.h.wait(lambda: not self.c.production.busy)
        jobs = self.repo.jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].action, "video")
        recipe = json.loads(jobs[0].request)["settings"]
        self.assertEqual(recipe["speed"], 1.25)
        self.assertEqual(recipe["outro_seconds"], 8)
        self.assertIn("full episode queued", self.w.plan.get("1.0", "end"))
        self.assertEqual(self.repo.publications(), {})
        self.assertFalse(self.w.review.audio_checked.get())

    def test_invalid_current_sound_recipe_shows_error_and_queues_nothing(self):
        self.w.speed.set("unfinished")
        self.w.full_episode.invoke()
        self.h.wait(lambda: not self.c.production.busy)
        self.assertEqual(self.repo.jobs(), [])
        self.assertIn("not queued", self.app.message.cget("text"))
        self.assertFalse(self.w.full_episode.instate(["disabled"]))

    def test_edit_during_inspection_cannot_queue_stale_recipe(self):
        pending = []
        original = self.c.task
        self.c.task = lambda operation, callback, on_error=None: pending.append(
            (operation, callback, on_error)
        )
        try:
            self.w.full_episode.invoke()
            self.w.speed.set("1.5")
            operation, callback, _ = pending[0]
            callback(operation())
            self.assertEqual(len(pending), 1)
            self.assertFalse(self.c.production.busy)
            self.assertEqual(self.repo.jobs(), [])
            self.assertIn("changed during the checks", self.app.message.cget("text"))
        finally:
            self.c.task = original

    def test_duplicate_active_job_remains_one_job_with_visible_error(self):
        self.w.full_episode.invoke()
        self.h.wait(lambda: not self.c.production.busy)
        self.w.full_episode.invoke()
        self.h.wait(lambda: not self.c.production.busy)
        self.assertEqual(len(self.repo.jobs()), 1)
        self.assertIn("already has", self.app.message.cget("text"))

    def test_prepare_job_button_captures_its_episode_not_another_episodes_controls(self):
        other = Episode("note-002", "Different episode", 10, "Other transcript")
        current = self.c.episodes["note-001"]
        self.c.episodes[other.identifier] = other
        self.repo.checkpoint(
            {"draft:note-002": {"recipe": {"speed": "1.25", "outro": "8", "action": "audio"}}}
        )
        identifier = self.repo.submit("note-002", "prepare", {})
        self.repo.claim()
        self.repo.finish(identifier, "succeeded", result="/fixture/prepared")
        self.app.jobs.render(self.repo.jobs())
        with patch.object(self.c.studio, "catalog", return_value=[current, other]):
            self.app.jobs.buttons["review"].invoke()
            self.h.wait(lambda: not self.c.production.busy)
        jobs = self.repo.jobs()
        self.assertEqual(len(jobs), 2)
        self.assertEqual((jobs[0].episode, jobs[0].action), ("note-002", "video"))
        self.assertEqual(json.loads(jobs[0].request)["settings"]["speed"], 1.25)
        self.assertEqual(json.loads(jobs[0].request)["settings"]["outro_seconds"], 8)

    def test_prepare_job_missing_recording_reports_failure_without_queueing(self):
        identifier = self.repo.submit("absent", "prepare", {})
        self.repo.claim()
        self.repo.finish(identifier, "succeeded", result="/fixture/missing")
        self.app.jobs.render(self.repo.jobs())
        self.app.jobs.buttons["review"].invoke()
        self.h.wait(lambda: not self.c.production.busy)
        self.assertEqual(len(self.repo.jobs()), 1)
        self.assertIn("unavailable", self.app.message.cget("text"))

    def test_full_review_has_one_combined_explicit_confirmation_and_one_approval(self):
        review = self.w.review
        self.assertTrue(review.full_video())
        snapshot = ReviewSnapshot(
            "full-identity", "Full episode pending", "audio.mp3", "captions.srt", "video.mp4", True
        )
        with (
            patch.object(self.c.studio, "review_snapshot", return_value=snapshot),
            patch.object(self.c.studio, "approve") as approve,
        ):
            self.c.show_review(True)
            self.h.wait(lambda: review.snapshot == snapshot)
            review.reviewer.set("Test reviewer")
            self.assertTrue(review.approve.instate(["disabled"]))
            review.video_check.invoke()
            self.assertTrue(review.audio_checked.get())
            self.assertTrue(review.video_checked.get())
            self.assertTrue(review.approve.instate(["disabled"]))
            review.captions_check.invoke()
            self.assertFalse(review.approve.instate(["disabled"]))
            review.approve.invoke()
            self.h.wait(lambda: approve.called and not review.busy)
            approve.assert_called_once_with("note-001", snapshot, "Test reviewer")
        self.assertFalse(review.video_checked.get())
        self.assertFalse(review.audio_checked.get())
        self.assertEqual(self.repo.publications(), {})

    def test_audio_only_remains_explicit_and_never_approves_video(self):
        snapshot = ReviewSnapshot("audio-identity", "Audio only", "audio.mp3", "captions.srt")
        with (
            patch.object(self.c.studio, "review_snapshot", return_value=snapshot),
            patch.object(self.c.studio, "approve") as approve,
        ):
            self.c.show_review(False)
            self.h.wait(lambda: self.w.review.snapshot == snapshot)
            self.w.review.audio_check.invoke()
            self.w.review.captions_check.invoke()
            self.w.review.reviewer.set("Listener")
            self.w.review.approve.invoke()
            self.h.wait(lambda: approve.called and not self.w.review.busy)
            self.assertFalse(approve.call_args.args[1].full_video)
            self.c.show_review(True)
            self.assertFalse(self.w.review.audio_checked.get())
            self.assertFalse(self.w.review.video_checked.get())

    def test_source_link_is_generated_but_does_not_become_published_destination(self):
        publication = self.w.publication
        episode = Episode(
            "private-note",
            "Private",
            20,
            "Text",
            written_url="https://mothandgravel.com/notes/013-work-outlives-the-window.html",
        )
        publication.load_episode(episode)
        self.assertEqual(publication.measures["Written note link"].cget("text"), "65 characters")
        publication.copy_buttons["Written note link"].invoke()
        self.assertEqual(self.root.clipboard_get(), episode.written_url)
        self.assertEqual(publication.url.get(), "")
        self.assertEqual(publication.date.get(), "")
        publication.today.invoke()
        self.assertEqual(publication.date.get(), date.today().isoformat())
        self.assertEqual(self.repo.publications(), {})
        publication.url.set("https://youtu.be/actual")
        publication.date.set("2026-10-15")
        publication.load_episode(episode)
        self.assertEqual(publication.url.get(), "https://youtu.be/actual")
        self.assertEqual(publication.date.get(), "2026-10-15")

    def test_later_success_removes_old_failure_attention_and_disables_its_retry(self):
        # A poll that read the empty queue earlier must not land after this render.
        self.h.wait(lambda: not self.c.polling)
        old = self.repo.submit("note-001", "prepare", {})
        self.repo.claim()
        self.repo.finish(old, "failed", error="Earlier TimeoutError")
        new = self.repo.submit("note-001", "prepare", {})
        self.repo.claim()
        self.repo.finish(new, "succeeded", result="/fixture/prepared")
        self.app.jobs.render(self.repo.jobs())
        self.app.jobs.tree.selection_set(old)
        self.root.update()
        self.c.job_detail()
        self.h.wait(lambda: "Historical attempt" in self.app.jobs.detail.cget("text"))
        self.assertNotIn("need", self.app.jobs.summary.cget("text"))
        self.assertTrue(self.app.jobs.buttons["retry"].instate(["disabled"]))
        self.assertEqual(self.repo.get(old).error, "Earlier TimeoutError")
        with self.assertRaisesRegex(ValueError, "later attempt completed"):
            self.c.studio.retry(old)

    def test_failed_video_job_detail_shows_the_sentence_and_hides_renderer_output(self):
        self.h.wait(lambda: not self.c.polling)
        job = self.repo.submit("note-001", "video", {"settings": {}})
        self.repo.claim()
        sentence = (
            "The video renderer stopped: a frame took longer than 2 minutes, usually because "
            "the computer is busy. Your audio and captions are saved; choose Make it again to "
            "retry the video only."
        )
        self.repo.finish(job, "failed", error=sentence + "\n\nDetails:\nTimeout (120000ms) frame 9")
        self.app.jobs.render(self.repo.jobs())
        self.app.jobs.tree.selection_set(job)
        self.root.update()
        self.c.job_detail()
        self.h.wait(lambda: "Make it again" in self.app.jobs.detail.cget("text"))
        text = self.app.jobs.detail.cget("text")
        self.assertNotIn("Details:", text)
        self.assertNotIn("frame 9", text)
        self.assertIn("Full renderer output is in Job history.", text)
        self.assertIn("frame 9", self.repo.get(job).error)

    def test_compact_full_episode_controls_and_unified_review_are_not_clipped(self):
        self.root.geometry("1050x760+0+0")
        self.w.show_plan_tab()
        self.w.toggle_more(True)
        self.w.preflight_status("Checks · fixture")
        self.root.update()
        for widget in (self.w.full_episode, self.w.produce, self.w.guidance):
            self.assertTrue(widget.winfo_viewable())
            self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth())
            self.assertLessEqual(
                widget.winfo_rootx() + widget.winfo_width(),
                self.root.winfo_rootx() + self.root.winfo_width(),
            )
        self.h.capture("full-episode-produce-fixture")
        self.w.review.load(
            ReviewSnapshot("full", "Fixture: full episode pending", "a.mp3", "a.srt", "a.mp4", True)
        )
        self.w.show_review()
        self.root.update()
        for widget in (
            self.w.review.video_check,
            self.w.review.captions_check,
            self.w.review.approve,
        ):
            self.h.assert_visible(widget)
        self.h.capture("full-episode-review-fixture")


class GeneratedPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_preparation_execution.PreparationExecutionTests.setUpClass()

    def test_real_private_catalog_exposes_written_link_but_no_publication_record(self):
        f = test_preparation_execution.PreparationExecutionTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.prepare()
        episode = f.pipeline.catalog()[0]
        self.assertEqual(episode.written_url, "https://mothandgravel.com/notes/104-window.html")
        self.assertEqual(episode.publication_url, "")
        self.assertEqual(episode.publication_date, "")
        self.assertFalse(episode.publication_saved)
