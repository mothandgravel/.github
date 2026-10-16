"""Evidence-based progress and native tab navigation; no Cloud or inferred approval."""

import os
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from field_notes_studio.job_progress import progress_for
from field_notes_studio.models import Job, ReviewSnapshot
from tests.studio import test_ui


def job(action="video", status="running", stage="video", **changes):
    value = Job(
        "job-1", "note-013", action, status, stage, "2026-10-16T00:00:00+00:00", "", "", "{}"
    )
    return replace(value, **changes)


def events(*stages):
    return [
        {"stage": stage, "message": "", "time": "2026-10-16T00:00:00+00:00"} for stage in stages
    ]


def states(snapshot):
    return [milestone.state for milestone in snapshot.milestones]


class JobProgressTests(unittest.TestCase):
    def test_full_video_shows_saved_audio_and_active_video_not_separate_required_job(self):
        value = progress_for(job(), events("audio", "audio-complete", "video"))
        self.assertEqual(states(value), ["Saved", "Working", "Next"])
        self.assertEqual(value.milestones[0].label, "Audio + captions")
        self.assertNotIn("%", str(value))

    def test_later_stage_does_not_manufacture_an_earlier_completion(self):
        value = progress_for(job(), events("video"))
        self.assertEqual(states(value), ["Next", "Working", "Next"])

    def test_narration_counts_completed_events_not_current_chunk_index(self):
        value = progress_for(
            job("prepare", stage="narration-3-of-3"),
            events("narration-1-of-3-complete", "narration-3-of-3"),
        )
        self.assertIn("1 chunk saved", value.title)
        self.assertEqual(states(value), ["Working", "Next", "Next"])

    def test_repeated_receipt_events_are_not_double_counted(self):
        value = progress_for(
            job("prepare", stage="narration-3-of-3"),
            events(
                "narration-1-of-3-complete",
                "narration-1-of-3-complete",
                "narration-2-of-3-complete",
            ),
        )
        self.assertIn("2 chunks saved", value.title)

    def test_bounded_caption_wait_is_not_running_or_approved(self):
        value = progress_for(
            job("prepare", "waiting", "waiting"), events("narration-complete", "captions")
        )
        self.assertEqual(states(value), ["Saved", "Waiting", "Next"])
        self.assertIn("Resume", value.next_step)
        self.assertIn("No new narration", value.next_step)

    def test_failed_stage_retains_prior_saved_milestone(self):
        value = progress_for(
            job(status="failed", stage="failed"), events("audio-complete", "video", "failed")
        )
        self.assertEqual(states(value), ["Saved", "Failed", "Next"])

    def test_interrupted_never_becomes_success(self):
        value = progress_for(job(status="interrupted"), events("audio-complete", "video"))
        self.assertEqual(states(value), ["Saved", "Uncertain", "Next"])

    def test_stop_requested_keeps_current_stage_and_completed_work(self):
        value = progress_for(job(cancel_requested=True), events("audio-complete", "video"))
        self.assertEqual(states(value), ["Saved", "Stopping", "Next"])
        self.assertIn("current operation finishes first", value.next_step)

    def test_preflight_failure_does_not_claim_audio_started(self):
        value = progress_for(job(status="failed", stage="preflight"), events("preflight", "failed"))
        self.assertEqual(states(value), ["Next", "Next", "Next"])

    def test_queued_and_queued_stop_do_not_claim_to_be_running(self):
        for stopping in (False, True):
            with self.subTest(stopping=stopping):
                value = progress_for(
                    job(status="queued", stage="queued", cancel_requested=stopping), []
                )
                self.assertEqual(states(value), ["Next", "Next", "Next"])
                self.assertIn("Stop requested" if stopping else "not started", value.next_step)

    def test_last_completed_stage_moves_to_saving_only_after_completion_event(self):
        value = progress_for(
            job(stage="video-complete"), events("audio-complete", "video-complete")
        )
        self.assertEqual(states(value), ["Saved", "Saved", "Working"])

    def test_success_says_review_next_not_published(self):
        value = progress_for(job(status="succeeded", stage="succeeded"), [])
        self.assertEqual(states(value), ["Saved", "Saved", "Saved"])
        self.assertIn("Review full episode once", value.next_step)
        self.assertIn("Nothing has been published", value.next_step)

    def test_prepare_success_does_not_claim_full_video_exists(self):
        value = progress_for(job("prepare", "succeeded", "succeeded"), [])
        self.assertIn("not yet a finished video", value.next_step)
        self.assertNotIn("Full video", [stage.label for stage in value.milestones])

    def test_preview_and_export_keep_their_actual_scope(self):
        preview = progress_for(job("preview", "succeeded", "succeeded"), [])
        exported = progress_for(job("export", "succeeded", "succeeded"), [])
        self.assertIn("Video preview", [stage.label for stage in preview.milestones])
        self.assertIn("not a full video", preview.next_step)
        self.assertIn("Export is not publication", exported.next_step)

    def test_historical_failure_is_not_a_retry_instruction_or_changed_history(self):
        original = job(status="failed", error="Original diagnostic")
        value = progress_for(original, events("audio-complete", "video"), historical=True)
        self.assertEqual(states(value), ["Saved", "History", "Next"])
        self.assertIn("No retry needed", value.next_step)
        self.assertEqual(original.error, "Original diagnostic")

    def test_malformed_or_unknown_stages_stay_unverified(self):
        for at in ("narration-9-of-3", "unknown", "narration-1-of-9999999"):
            with self.subTest(at=at):
                value = progress_for(job("prepare", stage=at), events("unrecognized-complete"))
                self.assertNotIn("Saved", states(value))
                self.assertNotIn("chunks saved", value.title)


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class JobProgressUiTests(unittest.TestCase):
    def setUp(self):
        self.h = test_ui.UITests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.app, self.root = self.h.app, self.h.root
        self.repo = self.app.controller.studio.repository
        self.h.wait(lambda: self.app.workspace.publication.editor.loaded)
        self.root.geometry("1050x760+0+0")
        self.root.update()

    def working_video(self):
        request, _ = self.app.controller.studio.plan("note-001", "video", 1.15, 5)
        identifier = self.repo.submit("note-001", "video", request)
        self.repo.claim()
        self.repo.event(identifier, "audio-complete", "Audio saved")
        self.repo.event(identifier, "video", "Rendering the full video")
        self.app.jobs.render(self.repo.jobs())
        self.app.jobs.tree.selection_set(identifier)
        self.app.controller.job_detail()
        self.h.wait(lambda: self.app.jobs.progress.snapshot is not None)
        return identifier

    def test_all_seven_tabs_have_named_icons_and_are_clickable_at_minimum_width(self):
        tabs = self.app.workspace.tabs
        names = [tabs.tab(tab, "text") for tab in tabs.tabs()]
        self.assertEqual(
            names, ["Produce", "Review", "Release", "Transcript", "Audio", "Batch", "Health"]
        )
        for tab in tabs.tabs():
            self.assertTrue(tabs.tab(tab, "image"))
            self.assertEqual(str(tabs.tab(tab, "compound")), "left")
        from tkinter import TclError

        def tab_at(x):
            try:
                return tabs.index(f"@{x},15")
            except TclError:
                return None

        visible = {tab_at(x) for x in range(tabs.winfo_width())} - {None}
        self.assertEqual(visible, set(range(7)))

    def test_real_events_drive_visible_progress_without_network_or_approval(self):
        self.working_video()
        self.assertEqual(states(self.app.jobs.progress.snapshot), ["Saved", "Working", "Next"])
        self.root.update()
        self.assertGreaterEqual(self.app.workspace.plan.winfo_height(), 65)
        for cell in self.app.jobs.progress.cells:
            self.h.assert_visible(cell)
        self.assertFalse(self.app.workspace.review.video_checked.get())
        self.assertEqual(self.repo.publications(), {})
        self.h.capture("progress-rendering-fixture")

    def test_success_shows_one_review_next_and_preserves_history(self):
        identifier = self.working_video()
        self.repo.finish(identifier, "succeeded", result="/fixture/video")
        self.app.jobs.render(self.repo.jobs())
        self.app.controller.job_detail()
        self.h.wait(lambda: states(self.app.jobs.progress.snapshot) == ["Saved", "Saved", "Saved"])
        self.assertIn("Review full episode once", self.app.jobs.detail.cget("text"))
        self.assertFalse(self.app.workspace.review.audio_checked.get())
        self.h.capture("progress-finished-fixture")

    def test_failed_progress_does_not_turn_saved_audio_into_failed_audio(self):
        identifier = self.working_video()
        self.repo.finish(identifier, "failed", error="Renderer stopped; retain the saved audio")
        self.app.jobs.render(self.repo.jobs())
        self.app.controller.job_detail()
        self.h.wait(lambda: states(self.app.jobs.progress.snapshot) == ["Saved", "Failed", "Next"])
        self.assertIn("retain the saved audio", self.app.jobs.detail.cget("text"))
        self.h.capture("progress-failure-fixture")

    def test_repeated_snapshots_reuse_native_icons_without_timers(self):
        self.working_video()
        progress = self.app.jobs.progress
        images = tuple(self.root.tk.call("image", "names"))
        timers = tuple(self.root.tk.call("after", "info"))
        for _ in range(100):
            progress.show(progress.snapshot)
        self.assertEqual(tuple(self.root.tk.call("image", "names")), images)
        self.assertEqual(tuple(self.root.tk.call("after", "info")), timers)

    def test_audio_batch_health_and_review_content_still_fit_with_progress(self):
        self.working_video()
        w = self.app.workspace
        for tab in (w.sound, w.batch, w.health.master, w.review):
            w.tabs.select(tab)
            self.root.update()
            for cell in self.app.jobs.progress.cells:
                self.h.assert_visible(cell)
            for button in self.app.jobs.buttons.values():
                self.h.assert_visible(button)
        self.h.capture("progress-review-layout-fixture")

    def test_local_render_wait_has_elapsed_time_not_a_provider_percentage(self):
        identifier = self.working_video()
        now = datetime.now(timezone.utc)
        with self.repo.connection() as db:
            db.execute(
                "UPDATE events SET time=? WHERE job=? AND stage='video'",
                ((now - timedelta(seconds=75)).isoformat(), identifier),
            )
        with patch("field_notes_studio.controller.datetime") as clock:
            clock.now.return_value = now
            clock.fromisoformat.side_effect = datetime.fromisoformat
            self.app.controller.job_detail()
            self.h.wait(lambda: "1:15 elapsed locally" in self.app.jobs.detail.cget("text"))
        self.assertIn("completion estimate unavailable", self.app.jobs.detail.cget("text"))
        self.assertNotIn("%", self.app.jobs.detail.cget("text"))

    def test_matching_saved_full_approval_does_not_ask_for_another_review(self):
        identifier = self.working_video()
        self.app.controller.polling = True
        self.repo.finish(identifier, "succeeded", result="/fixture/full-video")
        self.app.jobs.render(self.repo.jobs())
        self.root.update()
        self.app.workspace.review.load(
            ReviewSnapshot(
                "verified",
                "Approved fixture",
                video="/fixture/full-video/episode.mp4",
                full_video=True,
                approved=True,
            )
        )
        self.app.controller.job_detail()
        self.h.wait(lambda: "already has saved approval" in self.app.jobs.detail.cget("text"))
        self.assertIn("inspect/export", self.app.jobs.detail.cget("text"))
        self.assertFalse(self.app.workspace.review.video_checked.get())
        self.assertTrue(self.app.workspace.review.approve.instate(["disabled"]))
        self.assertEqual(self.repo.publications(), {})
