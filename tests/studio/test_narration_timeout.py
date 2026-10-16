"""Regression for the operator's chunk-3 timeout; Cloud boundaries remain simulated."""

import base64
import io
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib import error

from field_notes_audio import audio
from field_notes_audio.storage import digest_file, read_object
from field_notes_studio.preparation_jobs import narration_diagnostic
from field_notes_studio.preparation_service import PreparationService
from field_notes_studio.worker import execute
from tests.studio import test_preparation_app as app_fixtures
from tests.studio import test_preparation_execution as media_fixtures


class NarrationTimeoutTests(unittest.TestCase):
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
        self.snapshot = self.service.inspect("104")
        self.request = json.loads(self.snapshot.request_json)
        self.directory = self.f.adapter._recording(self.request["plan"])
        self.assertEqual(len(self.request["plan"]["requests"]), 3)

    def fail_third(self, *, failure=None):
        legacy = dict(self.request)
        legacy.pop("tts_timeout_seconds")
        identifier = self.f.repository.submit("studio-essay", "prepare", legacy)
        with self.f.cloud() as calls:
            calls[1].side_effect = [self.f.wav, self.f.wav, failure or TimeoutError("secret")]
            execute(self.f.repository, self.f.pipeline, self.f.repository.claim())
            self.assertEqual(calls[1].call_count, 3)
            for call in calls[1].call_args_list:
                self.assertEqual(call.kwargs["timeout_seconds"], 180)
        job = self.f.repository.get(identifier)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.stage, "narration-3-of-3")
        self.assertIn("socket timeout 180s", job.error)
        self.assertNotIn("secret", job.error)
        return identifier

    def response(self):
        return io.BytesIO(
            json.dumps({"audioContent": base64.b64encode(self.f.wav).decode()}).encode()
        )

    def test_new_inspection_captures_600_second_socket_policy_without_changing_the_plan(self):
        self.assertEqual(self.request["tts_timeout_seconds"], 600)
        self.assertIn("socket timeout: 600s", self.snapshot.summary)
        with patch.object(audio, "TTS_TIMEOUT_SECONDS", 180):
            previous = json.loads(self.service.inspect("104").request_json)
        self.assertEqual(previous["tts_timeout_seconds"], 180)
        self.assertEqual(previous["plan"], self.request["plan"])
        self.assertEqual(previous["source_identity"], self.request["source_identity"])
        self.assertEqual(self.f.adapter._recording(previous["plan"]), self.directory)

    def test_real_http_adapter_uses_new_timeout_without_changing_payload_or_retrying(self):
        data = self.request["plan"]["requests"][2]
        with patch.object(audio.request, "urlopen", return_value=self.response()) as opened:
            self.assertEqual(
                audio.synthesize(data, "fixture-project", "global", "token"), self.f.wav
            )
        opened.assert_called_once()
        self.assertEqual(opened.call_args.kwargs["timeout"], 600)
        self.assertEqual(json.loads(opened.call_args.args[0].data), data)

    def test_wrapped_socket_timeout_remains_uncertain_and_never_retries_automatically(self):
        self.fail_third(failure=error.URLError(TimeoutError("secret")))
        receipt = read_object(self.directory / "chunk-003.json")
        self.assertEqual(receipt["status"], "uncertain")
        self.assertEqual(receipt["failure_kind"], "TimeoutError")
        self.assertEqual(receipt["failure_phase"], "narration_request")
        self.assertEqual(receipt["timeout_seconds"], 180)
        self.assertNotIn("secret", json.dumps(receipt))
        self.assertIn("remote processing/billing unknown", narration_diagnostic(receipt))

    def test_actual_http_timeout_is_one_attempt_not_a_hidden_retry_loop(self):
        with patch.object(audio.request, "urlopen", side_effect=TimeoutError()) as opened:
            with self.assertRaises(TimeoutError):
                audio.synthesize(
                    self.request["plan"]["requests"][0], "fixture-project", "global", "token"
                )
        opened.assert_called_once()
        self.assertEqual(opened.call_args.kwargs["timeout"], 600)

    def test_legacy_third_chunk_recovers_only_that_chunk_with_a_longer_wait(self):
        self.fail_third()
        original = {
            name: digest_file(self.directory / name) for name in ("chunk-001.wav", "chunk-002.wav")
        }
        receipt_path = self.directory / "chunk-003.json"
        receipt_hash = digest_file(receipt_path)
        snapshot = self.service.inspect("104")
        captured = json.loads(snapshot.recovery_json)
        self.assertEqual(captured["uncertain_chunks"], {"3": receipt_hash})
        self.assertEqual(captured["tts_timeout_seconds"], 600)
        self.assertEqual(captured["plan"], self.request["plan"])
        self.assertIn("2/3 narration cache records", snapshot.summary)
        with patch("field_notes_studio.preparation_service.launch_worker"):
            for general, recovery in ((False, True), (True, False)):
                with self.assertRaises(ValueError):
                    self.service.submit(snapshot, general, recover_uncertain=recovery)
            identifier = self.service.submit(snapshot, True, recover_uncertain=True)
        real_synthesize = audio.synthesize

        def slow_response(req, *, timeout):
            # Simulate a response that requires 240s, without wall-clock sleep.
            self.assertEqual(json.loads(req.data), captured["plan"]["requests"][2])
            if timeout < 240:
                raise TimeoutError()
            return self.response()

        with (
            self.f.cloud() as calls,
            patch.object(audio.request, "urlopen", side_effect=slow_response) as opened,
        ):
            calls[1].side_effect = real_synthesize
            execute(self.f.repository, self.f.pipeline, self.f.repository.claim())
            calls[1].assert_called_once()
            opened.assert_called_once()
            self.assertEqual(opened.call_args.kwargs["timeout"], 600)
        job = self.f.repository.get(identifier)
        self.assertEqual(job.status, "succeeded", job.error)
        self.assertEqual(original, {name: digest_file(self.directory / name) for name in original})
        self.assertTrue((self.directory / f"recovery-003-{receipt_hash}.json").is_file())
        complete = read_object(receipt_path)
        self.assertEqual(complete["status"], "complete")
        self.assertEqual(complete["timeout_seconds"], 600)
        self.assertIn("attempt_seconds", complete)
        self.assertEqual(self.f.repository.publications(), {})

    def test_captured_timeout_is_used_even_when_code_default_changes(self):
        with self.f.cloud() as calls, patch.object(audio, "TTS_TIMEOUT_SECONDS", 900):
            self.f.adapter.run(self.request, lambda *_: None, lambda: False)
            for call in calls[1].call_args_list:
                self.assertEqual(call.kwargs["timeout_seconds"], 600)

    def test_invalid_timeout_is_rejected_before_cache_write_or_cloud_call(self):
        for value in (
            None,
            False,
            True,
            "600",
            0,
            -1,
            59,
            901,
            600.0,
            float("inf"),
            float("nan"),
            {},
        ):
            with self.subTest(value=value), self.f.cloud() as calls:
                bad = {**self.request, "tts_timeout_seconds": value}
                with self.assertRaisesRegex(ValueError, "socket timeout"):
                    self.f.adapter.run(bad, lambda *_: None, lambda: False)
                for call in calls:
                    call.assert_not_called()
        self.assertFalse(self.directory.exists())

    def test_longer_wait_does_not_reuse_a_stale_or_deleted_recovery_receipt(self):
        self.fail_third()
        snapshot = self.service.inspect("104")
        path = self.directory / "chunk-003.json"
        raw = path.read_bytes()
        for replacement in (None, raw + b"\n"):
            if replacement is None:
                path.unlink()
            else:
                path.write_bytes(replacement)
            with (
                self.f.cloud() as calls,
                self.assertRaisesRegex(ValueError, "receipt changed or disappeared"),
            ):
                self.service.submit(snapshot, True, recover_uncertain=True)
            for call in calls:
                call.assert_not_called()

    def test_second_timeout_requires_a_new_recovery_authorization(self):
        self.fail_third()
        snapshot = self.service.inspect("104")
        with patch("field_notes_studio.preparation_service.launch_worker"):
            identifier = self.service.submit(snapshot, True, recover_uncertain=True)
        with self.f.cloud() as calls:
            calls[1].side_effect = TimeoutError()
            execute(self.f.repository, self.f.pipeline, self.f.repository.claim())
            calls[1].assert_called_once()
            self.assertEqual(calls[1].call_args.kwargs["timeout_seconds"], 600)
        job = self.f.repository.get(identifier)
        self.assertEqual(job.status, "failed")
        self.assertIn("socket timeout 600s", job.error)
        with self.assertRaisesRegex(ValueError, "receipt changed"):
            self.service.submit(snapshot, True, recover_uncertain=True)

    def test_original_note_013_plan_keeps_the_operators_cache_directory(self):
        plan = audio.make_plan("note-013", "gemini-2.5-pro-tts", "global")
        self.assertEqual(plan["fingerprint"][:16], "1f83cef69740a4af")
        self.assertEqual(len(plan["requests"]), 3)
        self.assertNotIn("tts_timeout_seconds", plan)


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class NarrationWaitUiTests(unittest.TestCase):
    def setUp(self):
        media_fixtures.PreparationExecutionTests.setUpClass()
        self.h = app_fixtures.PreparationApplicationTests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.app, self.f = self.h.app, self.h.fixture
        self.identifier = self.f.repository.submit("studio-essay", "prepare", self.f.request)
        self.f.repository.claim()
        self.f.repository.event(
            self.identifier, "narration-3-of-3", "Client socket timeout 600s. No automatic resend."
        )
        self.now = datetime.now(timezone.utc)
        with self.f.repository.connection() as db:
            db.execute(
                "UPDATE events SET time=? WHERE job=?",
                ((self.now - timedelta(seconds=241)).isoformat(), self.identifier),
            )
        self.app.preparation.close()
        self.app.root.geometry("1050x760+0+0")
        self.app.jobs.render(self.f.repository.jobs())

    def test_waiting_beyond_180s_has_elapsed_not_fake_provider_progress(self):
        with patch("field_notes_studio.controller.datetime") as clock:
            clock.now.return_value = self.now
            clock.fromisoformat.side_effect = datetime.fromisoformat
            self.app.controller.job_detail()
            self.h.wait(lambda: "4:01 elapsed locally" in self.app.jobs.detail.cget("text"))
        self.assertIn("provider progress unavailable", self.app.jobs.detail.cget("text"))
        self.assertIn("600s", self.app.jobs.detail.cget("text"))
        self.assertEqual(self.f.repository.get(self.identifier).status, "running")
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

    def test_stop_explanation_takes_priority_over_waiting_feedback(self):
        self.f.repository.cancel(self.identifier)
        self.app.controller.job_detail()
        self.h.wait(lambda: "Stop requested" in self.app.jobs.detail.cget("text"))
        self.assertNotIn("provider progress unavailable", self.app.jobs.detail.cget("text"))

    def test_bad_legacy_event_time_does_not_break_job_inspection(self):
        with self.f.repository.connection() as db:
            db.execute("UPDATE events SET time='not-a-time' WHERE job=?", (self.identifier,))
        self.app.controller.job_detail()
        self.h.wait(lambda: "Waiting for narration response" in self.app.jobs.detail.cget("text"))
        self.assertNotIn("elapsed locally", self.app.jobs.detail.cget("text"))
