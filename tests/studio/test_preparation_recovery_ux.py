"""Regression evidence from the real operator's setup, discovery and uncertain-chunk run."""

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from field_notes_audio import audio, workflow
from field_notes_audio.storage import digest_file, read_object, write_json
from field_notes_studio.preparation_service import PreparationService
from field_notes_studio.preparation_setup import import_setup, load_configuration, preview_setup
from field_notes_studio.service import Studio
from field_notes_studio.worker import execute
from tests.studio import test_preparation_app as app_fixtures
from tests.studio import test_preparation_execution as media_fixtures
from tests.studio import test_ui as ui_fixtures


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        media_fixtures.PreparationExecutionTests.setUpClass()
        self.f = media_fixtures.PreparationExecutionTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.service = PreparationService(self.f.root)
        self.f.text(
            "audio/scripts/window.txt",
            "\n\n".join(word + " " + "Hello world. " * 160 for word in ("One.", "Two.", "Three.")),
        )
        self.snapshot = self.f.adapter.inspect("104")
        self.request = json.loads(self.snapshot.request_json)
        self.directory = self.f.adapter._recording(self.request["plan"])
        self.assertEqual(len(self.request["plan"]["requests"]), 3)

    def fail_second(self):
        identifier = self.f.repository.submit("studio-essay", "prepare", self.request)
        with self.f.cloud() as calls:
            calls[1].side_effect = [
                self.f.wav,
                TimeoutError("never store arbitrary exception secrets"),
            ]
            execute(self.f.repository, self.f.pipeline, self.f.repository.claim())
            self.assertEqual(calls[1].call_count, 2)
        job = self.f.repository.get(identifier)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.stage, "narration-2-of-3")
        self.assertIn("TimeoutError", job.error)
        self.assertNotIn("exception secrets", job.error)
        return identifier

    def test_observed_three_chunk_failure_recovery_reuses_first_chunk(self):
        self.fail_second()
        original = digest_file(self.directory / "chunk-001.wav")
        snapshot = self.service.inspect("104")
        self.assertFalse(snapshot.request_json)
        self.assertTrue(snapshot.recovery_json)
        self.assertIn("Part 2: TimeoutError", snapshot.summary)
        self.assertIn("charge twice", snapshot.summary)
        with patch("field_notes_studio.preparation_service.launch_worker"):
            for authorized, recovery in ((False, True), (True, False), (True, 1)):
                with (
                    self.subTest(authorized=authorized, recovery=recovery),
                    self.assertRaises(ValueError),
                ):
                    self.service.submit(snapshot, authorized, recover_uncertain=recovery)
            identifier = self.service.submit(snapshot, True, recover_uncertain=True)
        with self.f.cloud() as calls:
            execute(self.f.repository, self.f.pipeline, self.f.repository.claim())
            self.assertEqual(calls[1].call_count, 2)  # only chunks 2 and 3
            self.assertEqual(
                calls[1].call_args_list[0].args[0], self.request["plan"]["requests"][1]
            )
        job = self.f.repository.get(identifier)
        self.assertEqual(job.status, "succeeded", job.error)
        self.assertEqual(digest_file(self.directory / "chunk-001.wav"), original)
        self.assertEqual(len(list(self.directory.glob("recovery-002-*.json"))), 1)
        self.assertEqual(self.service.catalog()[0].state, "Ready for production")

    def test_repeated_uncertainty_changes_receipt_and_needs_new_consent(self):
        self.fail_second()
        snapshot = self.service.inspect("104")
        request = json.loads(snapshot.recovery_json)
        with patch("field_notes_studio.preparation_service.launch_worker"):
            identifier = self.service.submit(snapshot, True, recover_uncertain=True)
        with self.f.cloud() as calls:
            calls[1].side_effect = TimeoutError()
            execute(self.f.repository, self.f.pipeline, self.f.repository.claim())
            calls[1].assert_called_once()
        with self.f.cloud() as calls:
            with self.assertRaisesRegex(ValueError, "receipt changed"):
                self.service.submit(snapshot, True, recover_uncertain=True)
            with self.assertRaisesRegex(ValueError, "recovery receipt changed"):
                self.f.adapter.run(request, lambda *_: None, lambda: False)
            calls[0].assert_not_called()
            calls[1].assert_not_called()
        with self.assertRaisesRegex(ValueError, "previous resend consent"):
            Studio(self.f.root).retry(identifier)

    def test_deleted_receipt_or_changed_script_cannot_authorize_a_replacement(self):
        self.fail_second()
        snapshot = self.service.inspect("104")
        path = self.directory / "chunk-002.json"
        raw = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, "disappeared"):
            self.service.submit(snapshot, True, recover_uncertain=True)
        path.write_bytes(raw)
        self.f.text("audio/scripts/window.txt", "Changed content")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.service.submit(snapshot, True, recover_uncertain=True)

    def test_wait_after_recovery_consumes_resend_consent_and_resumes_captions_only(self):
        self.fail_second()
        with patch("field_notes_studio.preparation_service.launch_worker"):
            identifier = self.service.submit(
                self.service.inspect("104"), True, recover_uncertain=True
            )
        with self.f.cloud(pending=True):
            execute(self.f.repository, self.f.pipeline, self.f.repository.claim())
        job = self.f.repository.get(identifier)
        self.assertEqual(job.status, "waiting", job.error)
        request = json.loads(job.request)
        self.assertNotIn("uncertain_chunks", request)
        self.assertIn("resume", request)
        self.assertTrue(
            any(e["stage"] == "recovery-consumed" for e in self.f.repository.events(identifier))
        )
        with patch("field_notes_studio.service.launch_worker"):
            self.assertEqual(Studio(self.f.root).retry(identifier), identifier)

    def test_job_failure_keeps_actionable_stage_and_recovery_catalog(self):
        identifier = self.fail_second()
        item = self.service.catalog()[0]
        self.assertEqual(item.state, "Needs recovery")
        self.assertEqual(item.job_id, identifier)
        self.assertIn("narration-2-of-3", item.detail)
        self.assertIn("TimeoutError", item.detail)

    def test_recovery_suppressed_while_an_episode_has_active_work(self):
        self.fail_second()
        identifier = self.f.repository.submit("studio-essay", "prepare", self.request)
        snapshot = self.service.inspect("104")
        self.assertFalse(snapshot.request_json)
        self.assertFalse(snapshot.recovery_json)
        self.assertEqual(self.service.catalog()[0].job_id, identifier)


class SetupImportTests(unittest.TestCase):
    def setUp(self):
        self.f = media_fixtures.PreparationExecutionTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.source = Path(self.t.name) / "settings.json"
        self.source.write_bytes(self.f.settings.read_bytes())
        self.f.settings.unlink()

    def test_preview_and_import_are_offline_strip_unrelated_keys_and_preserve_source(self):
        saved = read_object(self.source)
        saved.update(access_token="do-not-copy", arbitrary="do-not-copy")
        write_json(self.source, saved)
        raw = self.source.read_bytes()
        with (
            patch.object(audio, "access_token", side_effect=AssertionError("auth")),
            patch.object(workflow, "setup", side_effect=AssertionError("setup")),
        ):
            preview = preview_setup(str(self.source))
            self.assertNotIn("do-not-copy", preview.summary)
            self.assertFalse(self.f.settings.exists())
            import_setup(self.f.root, preview)
        self.assertEqual(load_configuration(self.f.root), self.f.config)
        self.assertNotIn("access_token", read_object(self.f.settings))
        self.assertEqual(self.source.read_bytes(), raw)
        self.assertEqual(self.f.settings.stat().st_mode & 0o777, 0o600)

    def test_import_never_overwrites_existing_settings_or_changes_after_preview(self):
        preview = preview_setup(str(self.source))
        self.source.write_text(self.source.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "changed after preview"):
            import_setup(self.f.root, preview)
        preview = preview_setup(str(self.source))
        import_setup(self.f.root, preview)
        original = self.f.settings.read_bytes()
        with self.assertRaisesRegex(ValueError, "Nothing was overwritten"):
            import_setup(self.f.root, preview)
        self.assertEqual(self.f.settings.read_bytes(), original)

    def test_import_rejects_symlinks_oversized_invalid_and_fifo_without_hanging(self):
        linked = self.source.with_name("link.json")
        linked.symlink_to(self.source)
        with self.assertRaises(OSError):
            preview_setup(str(linked))
        for raw in (b"x" * 32769, b"invalid token secret", b"[]"):
            self.source.write_bytes(raw)
            with self.assertRaises(ValueError) as caught:
                preview_setup(str(self.source))
            self.assertNotIn("token secret", str(caught.exception))
        self.source.unlink()
        os.mkfifo(self.source)
        with self.assertRaises(ValueError):
            preview_setup(str(self.source))

    def test_import_is_blocked_when_saved_work_is_active(self):
        preview = preview_setup(str(self.source))
        self.f.repository.submit("studio-essay", "prepare", self.f.request)
        with self.assertRaisesRegex(ValueError, "Existing jobs are unchanged"):
            PreparationService(self.f.root).import_setup(preview)
        self.assertFalse(self.f.settings.exists())


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class PreparationUxTests(unittest.TestCase):
    def setUp(self):
        media_fixtures.PreparationExecutionTests.setUpClass()
        self.h = app_fixtures.PreparationApplicationTests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.app, self.view, self.f = self.h.app, self.h.view, self.h.fixture

    def recovery_snapshot(self):
        snapshot = self.f.snapshot
        return replace(
            snapshot,
            request_json="",
            recovery_json=snapshot.request_json,
            recovery_summary="Chunk 2 has an uncertain outcome",
            summary="RECOVERY TEST FIXTURE: Chunk 2 has an uncertain outcome. TimeoutError. Resending can charge twice. Completed chunk 1 is retained.",
        )

    def test_new_note_is_reachable_from_failed_main_shelf_search(self):
        # Every written note is on the main shelf, so the new note is its own front door.
        self.app.preparation.close()
        self.app.shelf.query.set("104")
        self.h.wait(lambda: self.app.shelf.tree.exists("note:104"))
        self.app.shelf.tree.selection_set("note:104")
        self.h.wait(lambda: self.app.readiness.primary.cget("text") == "Prepare this note…")
        self.assertIsNone(self.app.controller.selected)
        self.app.readiness.primary.invoke()
        self.h.wait(
            lambda: self.app.preparation is not None
            and not self.app.preparation.busy
            and self.app.preparation.view.selected() == "104"
        )

    def test_uncertain_recovery_needs_both_checkboxes_and_clears_on_navigation(self):
        self.view.show_snapshot(self.recovery_snapshot())
        self.view.authorization.invoke()
        self.assertTrue(self.view.queue_button.instate(["disabled"]))
        self.view.recovery_consent.invoke()
        self.assertFalse(self.view.queue_button.instate(["disabled"]))
        self.assertEqual(self.view.queue_button.cget("text"), "Queue recovery")
        self.h.capture("preparation-recovery-fixture")
        self.view.query.set("no such note")
        self.assertFalse(self.view.authorized.get())
        self.assertFalse(self.view.recover_uncertain.get())
        self.assertTrue(self.view.queue_button.instate(["disabled"]))

    def test_compact_recovery_controls_and_script_remain_visible(self):
        self.view.show_snapshot(self.recovery_snapshot())
        self.view.context.configure(
            text="Working checkout: /home/operator/source/repos/mothandgravel/.github"
        )
        self.view.window.geometry("760x580+0+0")
        self.app.root.update()
        window = self.view.window
        for widget in (
            self.view.tree,
            self.view.plan,
            self.view.search,
            self.view.authorization,
            self.view.recovery_consent,
            self.view.queue_button,
            self.view.setup_button,
            self.view.production_button,
            self.view.job_button,
            self.view.message,
        ):
            with self.subTest(widget=widget):
                self.assertTrue(widget.winfo_viewable())
                self.assertGreater(widget.winfo_height(), 12)
                self.assertGreaterEqual(widget.winfo_rootx(), window.winfo_rootx())
                self.assertLessEqual(
                    widget.winfo_rootx() + widget.winfo_width(),
                    window.winfo_rootx() + window.winfo_width(),
                )
                self.assertLessEqual(
                    widget.winfo_rooty() + widget.winfo_height(),
                    window.winfo_rooty() + window.winfo_height(),
                )

    def test_failure_routes_to_selected_note_recovery_without_queueing(self):
        identifier = self.f.repository.submit("studio-essay", "prepare", self.f.request)
        self.f.repository.claim()
        self.f.repository.event(identifier, "narration-2-of-3", "Chunk 2/3")
        self.f.repository.finish(identifier, "failed", error="TimeoutError; receipt retained")
        self.app.jobs.render(self.f.repository.jobs())
        self.app.root.update()
        self.assertEqual(self.app.jobs.buttons["retry"].cget("text"), "Check recovery")
        self.app.jobs.buttons["retry"].invoke()
        self.app.root.update()
        self.assertEqual(self.app.preparation.view.selected(), "104")
        self.assertEqual(len(self.f.repository.jobs()), 1)
        self.assertIn(
            "Stopped: narrating part 2 of 3", self.app.jobs.tree.item(identifier, "values")
        )

    def test_import_cancel_then_confirm_has_no_cloud_effect(self):
        source = self.f.settings.with_name("previous-setup.json")
        source.write_bytes(self.f.settings.read_bytes())
        self.f.settings.unlink()
        with (
            patch.object(self.view, "choose_setup", return_value=str(source)),
            patch.object(self.view, "confirm_setup", return_value=False),
        ):
            self.view.setup_button.invoke()
            self.h.wait(lambda: not self.app.preparation.busy)
        self.assertFalse(self.f.settings.exists())
        with (
            patch.object(self.view, "choose_setup", return_value=str(source)),
            patch.object(self.view, "confirm_setup", return_value=True),
        ):
            self.view.setup_button.invoke()
            self.h.wait(lambda: self.f.settings.exists() and not self.app.preparation.busy)
        self.assertIn("imported locally", self.view.message.cget("text"))
        self.assertFalse(self.view.authorized.get())

    def test_ready_recording_opens_production_without_starting_or_approving_media(self):
        self.f.prepare()
        self.view.show_catalog(PreparationService(self.f.root).catalog())
        self.view.reveal("104")
        self.app.root.update()
        self.assertFalse(self.view.production_button.instate(["disabled"]))
        self.app.shelf.query.set("unrelated filter")
        self.view.production_button.invoke()
        self.h.wait(
            lambda: self.app.controller.selected == "studio-essay"
            and not self.app.controller.loading
        )
        self.assertTrue(self.app.preparation.closed)
        self.assertEqual(self.app.shelf.query.get(), "")
        self.assertEqual(self.f.repository.jobs(), [])
        self.assertEqual(self.f.repository.publications(), {})
        self.assertIsNone(self.app.controller.ready)

    def test_failure_error_is_visible_without_opening_history(self):
        identifier = self.f.repository.submit("studio-essay", "prepare", self.f.request)
        self.f.repository.claim()
        self.f.repository.event(identifier, "narration-2-of-3", "Contacting service")
        self.f.repository.finish(
            identifier, "failed", error="TimeoutError: chunk 2 outcome uncertain"
        )
        self.app.jobs.render(self.f.repository.jobs())
        self.app.controller.job_detail()
        self.h.wait(lambda: "TimeoutError" in self.app.jobs.detail.cget("text"))
        self.assertIn("Narrating part 2 of 3", self.app.jobs.detail.cget("text"))
        self.assertNotIn("narration-2-of-3:", self.app.jobs.detail.cget("text"))
        self.assertIn("Check recovery", self.app.jobs.detail.cget("text"))

    def test_legacy_failed_row_and_long_error_fit_the_main_window(self):
        identifier = self.f.repository.submit("studio-essay", "prepare", self.f.request)
        self.f.repository.claim()
        self.f.repository.event(identifier, "narration", "Contacting service")
        self.f.repository.finish(
            identifier, "failed", error="HTTP 503: uncertain outcome. " + "diagnostic detail " * 60
        )
        with self.f.repository.connection() as db:
            db.execute("UPDATE jobs SET stage='failed' WHERE identifier=?", (identifier,))
        self.app.preparation.close()
        self.app.root.geometry("1050x760+0+0")
        self.app.jobs.render(self.f.repository.jobs())
        self.app.controller.job_detail()
        self.h.wait(lambda: "Full details in History" in self.app.jobs.detail.cget("text"))
        self.assertEqual(self.app.jobs.tree.item(identifier, "values")[-1], "Next: check recovery")
        self.assertIn("narration", self.app.jobs.detail.cget("text"))
        for button in self.app.jobs.buttons.values():
            self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
        for widget in (*self.app.jobs.buttons.values(), self.app.jobs.detail):
            self.assertTrue(widget.winfo_viewable())
            self.assertLessEqual(
                widget.winfo_rootx() + widget.winfo_width(),
                self.app.root.winfo_rootx() + self.app.root.winfo_width(),
            )
            self.assertLessEqual(
                widget.winfo_rooty() + widget.winfo_height(),
                self.app.root.winfo_rooty() + self.app.root.winfo_height(),
            )
        ui_fixtures.UITests.capture(self.h, "preparation-failed-queue-fixture")
