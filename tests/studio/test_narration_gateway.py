"""502 receipts must not be confused with an older socket timeout or authorize retries."""

import io
import json
import os
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from field_notes_audio import audio
from field_notes_audio.diagnostics import provider_text
from field_notes_audio.storage import digest_file, read_object
from field_notes_studio.preparation_jobs import narration_diagnostic
from field_notes_studio.worker import execute
from tests.studio import test_narration_timeout as timeout_fixtures
from tests.studio import test_preparation_app as app_fixtures
from tests.studio import test_preparation_execution as media_fixtures

HTML_ERROR = (
    "<!DOCTYPE html><html><head><title>Error 502 (Server Error)</title>"
    "<style>"
    + "*{margin:0;padding:0}body{background:url(robot.png)}"
    * 35
    + "</style><script>secret-script-code()</script></head>"
    "<body><p><b>502.</b> That is an error.</p>"
    "<p>The server encountered a temporary error and could not complete your request.</p>"
    "<p>Bearer secret-value</p></body></html>"
)


class GatewayDiagnosticTests(unittest.TestCase):
    def test_google_style_html_keeps_message_not_css_or_script(self):
        failure = HTTPError(
            "https://service.invalid", 502, "Bad Gateway", {}, io.BytesIO(HTML_ERROR.encode())
        )
        diagnostic = audio.http_diagnostic(failure, "secret-value")
        self.assertEqual(diagnostic["http_status"], 502)
        self.assertIn("temporary error", diagnostic["provider_message"])
        for hidden in (
            "margin",
            "padding",
            "background",
            "robot.png",
            "secret-script-code",
            "secret-value",
        ):
            self.assertNotIn(hidden, diagnostic["provider_message"])
        self.assertLessEqual(len(diagnostic["provider_message"]), 500)

    def test_incomplete_style_never_leaks_css_as_error_message(self):
        self.assertEqual(provider_text("<title>502</title><style>margin secret-css"), "502")

    def test_template_svg_comments_and_scripts_are_not_visible_diagnostics(self):
        raw = "<!-- hidden-comment --><template><svg>hidden-svg</svg>hidden-template</template>"
        raw += "<script>hidden-script</script><p>Bad &amp; Gateway</p>"
        self.assertEqual(provider_text(raw), "Bad & Gateway")

    def test_quoted_json_and_plain_text_secrets_are_redacted(self):
        for raw in (
            'Bad Gateway access_token="secret-value" refresh_token=another-secret',
            'Bad Gateway {"api_key": "another-secret"}',
            "Bad Gateway Authorization: Bearer another-secret",
            "Bad Gateway token=secret&#45;value",
        ):
            with self.subTest(raw=raw):
                result = provider_text(raw, "secret-value")
                self.assertIn("Bad Gateway", result)
                self.assertNotIn("secret-value", result)
                self.assertNotIn("another-secret", result)

    def test_structured_json_diagnostic_keeps_provider_status(self):
        raw = json.dumps({"error": {"status": "UNAVAILABLE", "message": "Upstream unavailable"}})
        failure = HTTPError(
            "https://service.invalid", 503, "Unavailable", {}, io.BytesIO(raw.encode())
        )
        self.assertEqual(
            audio.http_diagnostic(failure, ""),
            {
                "http_status": 503,
                "provider_status": "UNAVAILABLE",
                "provider_message": "Upstream unavailable",
            },
        )

    def test_error_body_read_and_rendering_are_bounded(self):
        stream = Mock()
        stream.read.return_value = b"x" * 8192
        failure = HTTPError("https://service.invalid", 502, "Bad Gateway", {}, stream)
        result = audio.http_diagnostic(failure, "")
        stream.read.assert_called_once_with(8192)
        self.assertEqual(len(result["provider_message"]), 500)

    def test_current_receipt_has_http_elapsed_limit_and_attempt_not_old_css(self):
        state = {
            "status": "uncertain",
            "http_status": 502,
            "timeout_seconds": 600,
            "attempt_seconds": 240.2283,
            "attempt_id": "a" * 32,
            "provider_message": "Already truncated CSS margin:0",
        }
        rendered = narration_diagnostic(state)
        for value in (
            "HTTP 502",
            "Bad Gateway",
            "240.228",
            "600s",
            "saved attempt aaaaaaaa",
            "billing unknown",
        ):
            self.assertIn(value, rendered)
        self.assertNotIn("margin", rendered)
        self.assertNotIn("TimeoutError", rendered)

    def test_receipt_summary_does_not_render_unvalidated_attempt_data(self):
        for value in ("Bearer secret", "<style>secret</style>", False, 123, "f" * 400):
            with self.subTest(value=value):
                result = narration_diagnostic({"attempt_id": value})
                self.assertNotIn("secret", result)
                self.assertNotIn("saved attempt", result)


class GatewayRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.h = timeout_fixtures.NarrationTimeoutTests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.f, self.service = self.h.f, self.h.service
        self.previous_id = self.h.fail_third()
        self.previous_error = self.f.repository.get(self.previous_id).error
        self.completed = {
            n: digest_file(self.h.directory / n) for n in ("chunk-001.wav", "chunk-002.wav")
        }

    def gateway_failure(self):
        self.snapshot = self.service.inspect("104")
        with patch("field_notes_studio.preparation_service.launch_worker"):
            self.identifier = self.service.submit(self.snapshot, True, recover_uncertain=True)
        with (
            self.f.cloud() as calls,
            patch.object(
                audio,
                "time",
                SimpleNamespace(perf_counter=Mock(side_effect=[100.0, 340.2283, 340.2283])),
            ),
        ):
            calls[1].side_effect = HTTPError(
                "https://service.invalid", 502, "Bad Gateway", {}, io.BytesIO(HTML_ERROR.encode())
            )
            execute(self.f.repository, self.f.pipeline, self.f.repository.claim())
            calls[1].assert_called_once()
            self.assertEqual(calls[1].call_args.kwargs["timeout_seconds"], 360)
            self.assertEqual(calls[1].call_args.args[0], self.h.request["plan"]["requests"][2])

    def test_502_is_current_evidence_while_old_job_result_stays_historical(self):
        self.gateway_failure()
        job = self.f.repository.get(self.identifier)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.stage, "narration-3-of-3")
        self.assertIn("HTTP 502", job.error)
        self.assertIn("240.2s", job.error)
        self.assertIn("360s", job.error)
        self.assertNotIn("TimeoutError", job.error)
        self.assertNotIn("margin", job.error)
        self.assertEqual(self.f.repository.get(self.previous_id).error, self.previous_error)
        item = self.service.catalog()[0]
        self.assertEqual(item.job_id, self.identifier)
        self.assertIn(self.identifier[:8], item.detail)
        self.assertIn("Job history from the last refresh", item.detail)
        self.assertIn("not a fresh read", item.detail)
        self.assertIn("HTTP 502", item.detail)
        current = self.service.inspect("104")
        self.assertIn("HTTP 502", current.summary)
        self.assertIn("Current receipt:", current.summary)
        self.assertIn("2/3 narration cache records", current.summary)
        self.assertNotIn("180.2", current.summary)
        self.assertEqual(
            self.completed, {n: digest_file(self.h.directory / n) for n in self.completed}
        )

    def test_502_remains_uncertain_and_requires_new_receipt_bound_consent(self):
        self.gateway_failure()
        path = self.h.directory / "chunk-003.json"
        original = path.read_bytes()
        receipt = read_object(path)
        self.assertEqual(receipt["status"], "uncertain")
        self.assertEqual(receipt["http_status"], 502)
        self.assertEqual(receipt["timeout_seconds"], 360)
        self.assertAlmostEqual(receipt["attempt_seconds"], 240.2283)
        with self.assertRaisesRegex(ValueError, "receipt changed"):
            self.service.submit(self.snapshot, True, recover_uncertain=True)
        current = self.service.inspect("104")
        self.assertFalse(current.request_json)
        self.assertEqual(
            json.loads(current.recovery_json)["uncertain_chunks"], {"3": digest_file(path)}
        )
        with patch("field_notes_studio.preparation_service.launch_worker"):
            for general, recovery in ((False, True), (True, False)):
                with self.assertRaises(ValueError):
                    self.service.submit(current, general, recover_uncertain=recovery)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.f.repository.publications(), {})


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class GatewayHistoryUiTests(unittest.TestCase):
    def setUp(self):
        media_fixtures.PreparationExecutionTests.setUpClass()
        self.h = app_fixtures.PreparationApplicationTests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.app, self.view, self.f = self.h.app, self.h.view, self.h.fixture

    def failed(self, error):
        identifier = self.f.repository.submit("studio-essay", "prepare", self.f.request)
        self.f.repository.claim()
        self.f.repository.event(identifier, "narration-3-of-3", "Narration")
        self.f.repository.finish(identifier, "failed", error=error)
        return identifier

    def test_reopening_existing_window_refreshes_old_catalog_result(self):
        old = self.failed("TimeoutError after 180.2s")
        self.app.preparation.refresh()
        self.h.wait(lambda: not self.app.preparation.busy)
        self.assertEqual(self.view.items["104"].job_id, old)
        latest = self.failed("HTTP 502 after 240.2s (client socket timeout 600s)")
        self.assertEqual(self.view.items["104"].job_id, old)
        self.app.open_preparation(note="104")
        self.h.wait(lambda: not self.app.preparation.busy)
        self.assertEqual(self.view.items["104"].job_id, latest)
        self.assertIn("HTTP 502", self.view.plan.get("1.0", "end"))
        self.assertNotIn("TimeoutError", self.view.plan.get("1.0", "end"))
        self.assertFalse(self.view.authorized.get())
        self.assertFalse(self.view.recover_uncertain.get())
        self.assertIsNone(self.view.snapshot)

    def test_queue_ack_replaces_stale_failure_only_for_the_submitted_note(self):
        original = self.view.items["104"]
        stale = replace(
            original, state="Needs recovery", detail="TimeoutError after 180.2s", job_id="old"
        )
        self.view.show_catalog([stale])
        self.view.reveal("104")
        self.h.root.update()
        self.view.queued("studio-essay", "new-job-123")
        self.assertEqual(self.view.items["104"].state, "Queued")
        self.assertEqual(self.view.items["104"].job_id, "new-job-123")
        self.assertIn("queued as job", self.view.plan.get("1.0", "end"))
        self.assertNotIn("TimeoutError", self.view.plan.get("1.0", "end"))
        self.assertTrue(self.view.queue_button.instate(["disabled"]))

    def test_late_submission_ack_does_not_replace_another_selected_note(self):
        original = self.view.items["104"]
        other = replace(
            original,
            note="105",
            episode="other-essay",
            title="Another note",
            detail="Other note details",
        )
        self.view.show_catalog([original, other])
        self.view.reveal("105")
        self.h.root.update()
        self.view.queued("studio-essay", "new-job-123")
        self.assertEqual(self.view.selected(), "105")
        self.assertEqual(self.view.plan.get("1.0", "end").strip(), "Other note details")
        self.assertEqual(self.view.items["104"].job_id, "new-job-123")
