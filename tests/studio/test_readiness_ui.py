"""Native overview actions, stale-evidence rejection and compact inline preflight."""

import json
import os
import unittest
from unittest.mock import patch

from field_notes_studio.readiness_models import Readiness
from tests.studio import test_ui


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class ReadinessUiTests(unittest.TestCase):
    def setUp(self):
        self.h = test_ui.UITests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.app, self.c = self.h.app, self.h.app.controller
        self.controls = self.c.episode_controls
        self.w = self.app.workspace
        self.h.wait(lambda: not self.controls.busy)

    def value(self, action="produce", detail="Checked source; one full episode job."):
        return Readiness(
            "note-001",
            action,
            {
                "produce": "Ready to produce",
                "export": "Package needs refreshing",
                "package": "Ready for manual upload",
                "review": "Review full episode",
            }.get(action, "Preflight needs attention"),
            detail,
            (
                "Recording: verified",
                "Full episode: verified",
                "Review: approved",
                "Package: upload copy changed",
            ),
            identity="fixture-checked-snapshot",
            checked_at="2026-10-16T10:00:00+00:00",
        )

    def ready(self, action="produce", detail="Checked source; one full episode job."):
        value = self.value(action, detail)
        self.app.readiness.show(value)
        self.app.root.update()
        return value

    def test_busy_evidence_requests_another_check_not_production_or_export(self):
        self.ready("check", "Another read owns the media lock; check again shortly.")
        with patch.object(self.c.studio, "readiness", return_value=self.value("review")) as checked:
            self.app.readiness.primary.invoke()
            self.h.wait(lambda: not self.controls.busy)
            checked.assert_called_once()
        self.assertEqual(self.c.studio.repository.jobs(), [])
        self.assertEqual(self.app.readiness.snapshot.action, "review")

    def test_contextual_produce_queues_one_full_job(self):
        self.ready()
        self.app.readiness.primary.invoke()
        self.app.readiness.primary.invoke()
        self.h.wait(lambda: not self.c.production.busy)
        jobs = self.c.studio.repository.jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].action, "video")
        self.assertEqual(json.loads(jobs[0].request)["settings"]["speed"], 1.15)
        self.assertEqual(self.c.studio.repository.publications(), {})

    def test_editing_invalidates_old_contextual_action_without_queueing(self):
        self.ready("export")
        self.w.speed.set("1.25")
        self.assertIsNone(self.app.readiness.snapshot)
        self.assertIn("Check readiness", self.app.readiness.primary.cget("text"))
        self.assertEqual(self.c.studio.repository.jobs(), [])

    def test_review_action_is_navigation_not_approval(self):
        self.ready("review")
        self.app.readiness.primary.invoke()
        self.assertEqual(self.w.tabs.select(), str(self.w.review))
        self.assertEqual(self.w.review.scope.get(), "Full video and audio")
        self.assertFalse(self.w.review.audio_checked.get())
        self.assertFalse(self.w.review.video_checked.get())
        self.assertEqual(self.c.studio.repository.publications(), {})
        self.assertEqual(self.c.studio.repository.jobs(), [])

    def test_card_export_preflights_and_queues_only_export(self):
        self.ready("export")
        with patch.object(
            self.c.studio, "checked_plan", return_value=({"edition": "fixture"}, "Approved package")
        ) as plan:
            self.app.readiness.primary.invoke()
            self.app.readiness.primary.invoke()
            self.h.wait(lambda: bool(self.c.studio.repository.jobs()))
            self.h.wait(lambda: not self.controls.busy)
        self.assertEqual(plan.call_count, 1)
        self.assertEqual(plan.call_args.args, ("note-001", "export", None, None))
        self.assertEqual([j.action for j in self.c.studio.repository.jobs()], ["export"])

    def test_export_blocker_appears_by_export_and_never_queues(self):
        self.ready("export")
        with patch.object(
            self.c.studio, "checked_plan", side_effect=ValueError("Full episode review is missing")
        ):
            self.app.readiness.primary.invoke()
            self.h.wait(lambda: not self.controls.busy)
        self.assertIn("Full episode review is missing", self.w.publication.preflight.cget("text"))
        self.assertEqual(self.c.studio.repository.jobs(), [])

    def test_production_blocker_visible_at_produce_and_card(self):
        with patch.object(
            self.c.studio.pipeline,
            "preflight",
            side_effect=ValueError("Video dependencies missing: npm ci --prefix video"),
        ):
            self.ready()
            self.app.readiness.primary.invoke()
            self.h.wait(lambda: not self.c.production.busy)
        self.assertIn("Video dependencies missing", self.w.guidance.cget("text"))
        self.assertEqual(self.c.studio.repository.jobs(), [])

    def test_package_navigation_rechecks_and_does_not_open_a_stale_package(self):
        self.ready("package")
        with (
            patch.object(self.c.studio, "readiness", return_value=self.value("export")) as checked,
            patch.object(self.c, "refresh_package") as opened,
        ):
            self.app.readiness.primary.invoke()
            self.h.wait(lambda: not self.controls.busy)
            checked.assert_called_once()
            opened.assert_not_called()
        self.assertEqual(self.app.readiness.snapshot.action, "export")
        self.assertEqual(self.c.studio.repository.jobs(), [])

    def test_late_readiness_result_cannot_unlock_changed_recipe(self):
        pending = []
        with patch.object(
            self.c,
            "task",
            side_effect=lambda op, cb, on_error=None: pending.append((op, cb, on_error)),
        ):
            self.controls.refresh()
        self.w.speed.set("1.25")
        pending[0][1](self.value("package"))
        self.assertIsNone(self.app.readiness.snapshot)
        self.assertEqual(self.c.studio.repository.jobs(), [])

    def test_late_export_plan_cannot_queue_for_another_selection(self):
        self.ready("export")
        pending = []
        with patch.object(
            self.c,
            "task",
            side_effect=lambda op, cb, on_error=None: pending.append((op, cb, on_error)),
        ):
            self.controls.export()
            self.c.selected = "note-002"
            self.c.generation += 1
            pending[0][1](({"edition": "old"}, "Old plan"))
        self.assertEqual(self.c.studio.repository.jobs(), [])
        # Restore selection so fixture close checkpoints the correct original draft.
        self.c.selected = "note-001"
        self.controls.busy = False

    def test_steady_queue_polls_do_not_repeat_readiness_hashing(self):
        self.controls.signature = None
        with patch.object(self.controls, "invalidate") as invalidate:
            for _ in range(30):
                self.controls.jobs_changed([])
            invalidate.assert_called_once_with(refresh=True)

    def test_check_requests_coalesce_and_closed_window_drops_late_result(self):
        pending = []
        with patch.object(
            self.c, "task", side_effect=lambda op, cb, on_error=None: pending.append(cb)
        ):
            for _ in range(20):
                self.controls.refresh()
        self.assertEqual(len(pending), 1)
        self.app.close()
        pending[0](self.value("package"))
        self.assertFalse(self.controls.busy)

    def test_compact_readiness_keeps_shelf_produce_and_release_controls_usable(self):
        self.app.root.geometry("1050x760+0+0")
        self.ready(
            "export",
            "Full episode remains approved. Export includes the current saved title, description and tags. Fixture only; no live publication.",
        )
        self.h.wait(lambda: self.w.plan.winfo_viewable())
        self.assertGreaterEqual(self.app.shelf.tree.winfo_height(), 90)
        self.assertGreaterEqual(self.w.plan.winfo_height(), 75)
        self.h.assert_visible(self.app.readiness.primary)
        self.assertGreaterEqual(
            self.app.readiness.primary.winfo_width(), self.app.readiness.primary.winfo_reqwidth()
        )
        self.assertIn("Checked 2026", self.app.readiness.detail.cget("text"))
        self.w.subtitle.configure(
            text="note-001 · Controlled fixture · saved full episode is approved"
        )
        self.w.preflight_status(
            "Saved full edition verified. No production needed for the checked recipe."
        )
        self.w.show_plan(
            "The checked saved episode has matching full-video approval.\n\nExport the updated package to include the current saved title, description and tags.\n\nControlled native Tk fixture, not a live publication."
        )
        self.h.capture("readiness-export-fixture")
        self.w.tabs.select(self.w.publication)
        self.w.preflight_status(
            "Full review and saved publishing copy checked. No rendering is needed to export.",
            "export",
        )
        self.app.root.update()
        for action in self.w.publication.actions.values():
            self.h.assert_visible(action)
        self.assertTrue(self.w.publication.preflight.winfo_viewable())
        self.w.publication.basis.configure(
            text="Controlled fixture: saved publishing copy differs from the last export."
        )
        self.h.capture("readiness-inline-export-fixture")

    def test_recipe_diff_updates_with_controls_and_stays_bound_to_episode(self):
        self.controls.open_recipes()
        self.controls.save_recipe("Field Notes", None)
        window = self.controls.window
        self.w.speed.set("1.25")
        self.assertIn("Pace ×: 1.15 → 1.25", window.diff.get("1.0", "end"))
        window.episode = "another-episode"
        self.controls.update_overrides()
        window.show_difference()
        self.assertTrue(window.apply.instate(["disabled"]))
        self.assertTrue(window.update.instate(["disabled"]))
        self.assertEqual(self.c.studio.repository.jobs(), [])
