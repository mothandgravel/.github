"""Studio surfaces the spend guard and plain errors; every Cloud call is mocked."""

import json
import os
import unittest
from unittest.mock import patch

from field_notes_audio import spend_guard
from field_notes_studio.preparation_service import PreparationService
from field_notes_studio.readiness_models import PLAIN, Readiness, plain, readable
from field_notes_studio.service import Studio
from field_notes_studio.worker import execute
from tests.studio import test_preparation_app as app_fixtures
from tests.studio import test_preparation_execution as media_fixtures
from tests.studio import test_ui as ui_fixtures


def uncertain(root, episode, part, count, estimate=0.02):
    for _ in range(count):
        spend_guard.record_start(
            root / "artifacts/audio",
            episode=episode,
            part=part,
            attempt_id=spend_guard.new_attempt_id(),
            estimate_usd=estimate,
        )


class PlainErrorTests(unittest.TestCase):
    def test_raw_exceptions_become_sentences_with_technical_detail_kept(self):
        for context in ("inputs", "copy", "edition", "package", "preflight"):
            with self.subTest(context=context):
                text = plain(KeyError("audio_sha256"), context)
                self.assertEqual(text, PLAIN[context])
                self.assertNotIn("audio_sha256", text)
                self.assertTrue(text.endswith("."))
                self.assertLessEqual(len("Blocked: " + text), 85)
        self.assertEqual(plain(OSError(2, "No such file"), "inputs"), PLAIN["inputs-file"])
        authored = ValueError("Preserved audio is missing or changed. Inspect preparation.")
        self.assertEqual(plain(authored, "inputs"), str(authored))
        self.assertEqual(readable("'audio_sha256'"), (PLAIN["preflight"], "'audio_sha256'"))
        for stdlib in (
            "Expecting value: line 1 column 1 (char 0)",
            "KeyError: 'audio_sha256'",
            "Invalid isoformat string: 'x'",
            "[Errno 2] No such file or directory",
            "I/O operation on closed file.",
            "invalid literal for int() with base 10: 'x'",
        ):
            with self.subTest(stdlib=stdlib):
                self.assertEqual(readable(stdlib)[0], PLAIN["preflight"])
        try:
            json.loads("")
        except ValueError as exc:
            self.assertEqual(plain(exc, "inputs"), PLAIN["inputs"])
        try:
            __import__("datetime").datetime.fromisoformat("not a date at all")
        except ValueError as exc:
            self.assertEqual(plain(exc, "edition"), PLAIN["edition"])

    def test_readiness_inspect_never_returns_a_bare_key(self):
        from field_notes_studio import readiness

        class Pipeline:
            root = None

            def source(self, episode):
                return {"id": episode}

        with patch.object(readiness, "recipe", return_value={}):
            value = readiness.inspect(Pipeline(), "note-001", {})
        self.assertEqual(value.detail, PLAIN["inputs"])
        self.assertEqual(value.technical, "KeyError: 'audio_sha256'")
        self.assertEqual(value.action, "repair")


class StudioSpendTests(unittest.TestCase):
    def setUp(self):
        media_fixtures.PreparationExecutionTests.setUpClass()
        self.f = media_fixtures.PreparationExecutionTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.service = PreparationService(self.f.root)

    def blocked_snapshot(self):
        uncertain(self.f.root, "studio-essay", "narration-1", 2)
        snapshot = self.service.inspect("104")
        self.assertTrue(snapshot.spend_blocked)
        self.assertEqual(snapshot.spend_count, 2)
        self.assertTrue(snapshot.spend_overridable)
        self.assertRegex(snapshot.spend_token, r"^[0-9a-f]{12}$")
        return snapshot

    def test_inspection_shows_ledger_counts_spend_and_guard(self):
        snapshot = self.blocked_snapshot()
        self.assertIn("Uncertain spend: ", snapshot.summary)
        self.assertNotIn("UNCERTAIN", snapshot.summary)
        self.assertIn("Spend guard: at most 2 uncertain paid attempts per part", snapshot.summary)
        self.assertEqual(
            snapshot.spend_label,
            "2 uncertain attempts in 24 h, up to about $0.0400, billing unknown",
        )
        self.assertIn("narration part 1 has 2 (limit 2", snapshot.summary)
        self.assertIn("up to about $0.0400", snapshot.summary)
        self.assertIn("billing unknown", snapshot.summary)
        self.assertIn("Stop and wait", snapshot.summary)
        self.assertIn("Spend guard: Studio will not queue", snapshot.summary)

    def test_studio_refuses_at_the_limit_without_a_reasoned_override(self):
        snapshot = self.blocked_snapshot()
        with patch("field_notes_studio.preparation_service.launch_worker"):
            with self.assertRaisesRegex(ValueError, "spend guard blocks"):
                self.service.submit(snapshot, True)
            with self.assertRaisesRegex(ValueError, "written reason"):
                self.service.submit(snapshot, True, spend_override="ok")
        self.assertEqual(self.f.repository.jobs(), [])
        # The engine refuses too, whatever the caller: a raw captured request has no override.
        request = json.loads(snapshot.request_json)
        with self.f.cloud() as calls, self.assertRaises(spend_guard.SpendLimitReached):
            self.f.adapter.run(request, lambda *_: None, lambda: False)
        calls[1].assert_not_called()

    def test_override_queues_once_logs_reason_and_cannot_be_retried(self):
        snapshot = self.blocked_snapshot()
        with patch("field_notes_studio.preparation_service.launch_worker"):
            identifier = self.service.submit(
                snapshot, True, spend_override="Incident resolved on the status page"
            )
        request = json.loads(self.f.repository.get(identifier).request)
        self.assertEqual(
            request["spend_override"],
            {"reason": "Incident resolved on the status page", "token": snapshot.spend_token},
        )
        with self.f.cloud() as calls:
            calls[1].side_effect = TimeoutError()
            execute(self.f.repository, self.f.pipeline, self.f.repository.claim())
            calls[1].assert_called_once()
        job = self.f.repository.get(identifier)
        self.assertEqual(job.status, "failed")
        self.assertIn("Billing unknown", job.error)
        self.assertIn("narration part 1 has 3", job.error)
        self.assertIn("Inspect recovery in Studio", job.error)
        self.assertNotIn("--retry-uncertain", job.error)
        logged = spend_guard.overrides(self.f.root / "artifacts/audio", "studio-essay")
        self.assertEqual(logged[0]["reason"], "Incident resolved on the status page")
        with self.assertRaisesRegex(ValueError, "one run only"):
            Studio(self.f.root).retry(identifier)

    def test_a_part_is_overridden_at_most_once_per_window(self):
        snapshot = self.blocked_snapshot()
        with patch("field_notes_studio.preparation_service.launch_worker"):
            self.service.submit(
                snapshot, True, spend_override="Incident resolved on the status page"
            )
        with self.f.cloud() as calls:
            calls[1].side_effect = TimeoutError()
            execute(self.f.repository, self.f.pipeline, self.f.repository.claim())
        again = self.service.inspect("104")
        self.assertTrue(again.spend_blocked)
        self.assertFalse(again.spend_overridable)
        self.assertIn("already overridden once", again.summary)
        with (
            patch("field_notes_studio.preparation_service.launch_worker"),
            self.assertRaisesRegex(ValueError, "already overridden once"),
        ):
            self.service.submit(
                again, True, recover_uncertain=True, spend_override="Trying once more after a pause"
            )

    def test_waiting_captions_resume_after_an_override_without_spending(self):
        snapshot = self.blocked_snapshot()
        with patch("field_notes_studio.preparation_service.launch_worker"):
            identifier = self.service.submit(
                snapshot, True, spend_override="Incident resolved on the status page"
            )
        with self.f.cloud(pending=True):
            execute(self.f.repository, self.f.pipeline, self.f.repository.claim())
        job = self.f.repository.get(identifier)
        self.assertEqual(job.status, "waiting", job.error)
        self.assertNotIn("spend_override", json.loads(job.request))
        with patch("field_notes_studio.service.launch_worker"):
            self.assertEqual(Studio(self.f.root).retry(identifier), identifier)
        self.assertEqual(
            len(spend_guard.overrides(self.f.root / "artifacts/audio", "studio-essay")), 1
        )

    def test_catalog_failure_detail_shows_the_attempt_total(self):
        identifier = self.f.repository.submit("studio-essay", "prepare", self.f.request)
        self.f.repository.claim()
        self.f.repository.finish(identifier, "failed", error="Narration part 1 of 3 failed.")
        uncertain(self.f.root, "studio-essay", "narration-1", 1)
        item = next(i for i in self.service.catalog() if i.note == "104")
        self.assertIn("Billing unknown · 1 uncertain paid attempt(s) in 24 h", item.detail)
        self.assertIn("stop and wait before any paid retry", item.detail)


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class ReadinessCardUiTests(unittest.TestCase):
    def setUp(self):
        self.h = ui_fixtures.UITests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.app, self.root = self.h.app, self.h.root
        self.root.geometry("1050x760+0+0")

    def test_card_and_preflight_show_a_sentence_and_details_on_request(self):
        card = self.app.readiness
        # The fixture catalog entry lacks audio_sha256, as an older catalog could.
        self.app.controller.episode_controls.refresh()
        self.h.wait(lambda: card.snapshot is not None and card.snapshot.title != "Checking…")
        self.assertEqual(card.snapshot.detail, PLAIN["inputs"])
        self.assertNotIn("audio_sha256", card.detail.cget("text"))
        guidance = self.app.workspace.guidance.cget("text")
        self.assertEqual(guidance, "Checks · " + PLAIN["inputs"])
        self.assertFalse(card.details.winfo_ismapped())
        self.assertTrue(card.details_button.winfo_ismapped())
        self.h.capture("readiness-plain-error-fixture")
        card.details_button.invoke()
        self.root.update()
        self.assertIn("audio_sha256", card.details.cget("text"))
        self.assertEqual(card.details_button.cget("text"), "▾ Details")
        self.h.capture("readiness-plain-error-details-fixture")
        card.show(Readiness("note-001", "produce", "Ready to produce", "One job."))
        self.root.update()
        self.assertFalse(card.details_button.winfo_ismapped())
        self.assertFalse(card.details.winfo_ismapped())


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class PreparationSpendUiTests(unittest.TestCase):
    def setUp(self):
        media_fixtures.PreparationExecutionTests.setUpClass()
        self.h = app_fixtures.PreparationApplicationTests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.app, self.view, self.f = self.h.app, self.h.view, self.h.fixture

    def test_override_needs_tick_and_reason_before_queueing(self):
        uncertain(self.f.root, "studio-essay", "narration-1", 2)
        self.view.inspect_button.invoke()
        self.h.wait(lambda: self.view.snapshot is not None)
        self.assertTrue(self.view.snapshot.spend_blocked)
        token = self.view.snapshot.spend_token
        self.assertIn("Uncertain spend: ", self.view.plan.get("1.0", "end"))
        self.assertEqual(
            self.view.spend_override.cget("text"),
            "Override once (2 uncertain attempts in 24 h, up to about $0.0400, billing unknown).",
        )
        self.assertTrue(self.view.spend.winfo_ismapped())
        self.assertIn("Spend guard reached", self.view.message.cget("text"))
        self.view.authorization.invoke()
        self.assertTrue(self.view.queue_button.instate(["disabled"]))
        self.view.spend_override.invoke()
        self.assertTrue(self.view.queue_button.instate(["disabled"]))
        self.view.spend_reason.set("short")
        self.assertTrue(self.view.queue_button.instate(["disabled"]))
        self.view.spend_reason.set("Checked status page and billing report")
        self.assertFalse(self.view.queue_button.instate(["disabled"]))
        self.h.capture("preparation-spend-guard-fixture")
        self.view.queue_button.invoke()
        self.h.wait(lambda: len(self.f.repository.jobs()) == 1)
        request = json.loads(self.f.repository.jobs()[0].request)
        self.assertEqual(request["spend_override"]["token"], token)
        self.assertFalse(self.view.spend_allowed.get())
        self.assertEqual(self.view.spend_reason.get(), "")

    def test_no_override_controls_below_the_limit(self):
        uncertain(self.f.root, "studio-essay", "narration-1", 1)
        self.h.inspect()
        self.assertFalse(self.view.snapshot.spend_blocked)
        self.assertFalse(self.view.spend.winfo_ismapped())
        self.assertIn("has 1 (limit 2", self.view.plan.get("1.0", "end"))

    def test_main_window_failure_shows_attempt_total_and_spend(self):
        identifier = self.f.repository.submit("studio-essay", "prepare", self.f.request)
        self.f.repository.claim()
        self.f.repository.event(identifier, "narration-2-of-3", "Contacting service")
        uncertain(self.f.root, "studio-essay", "narration-2", 3, estimate=0.0071)
        self.f.repository.finish(
            identifier,
            "failed",
            error="Narration part 2 of 3 failed: a Google gateway got no valid answer "
            "from the service (HTTP 502). " + "Technical detail " * 30,
        )
        self.app.preparation.close()
        self.app.root.geometry("1050x760+0+0")
        self.app.jobs.render(self.f.repository.jobs())
        self.app.jobs.tree.selection_set(identifier)
        self.app.controller.job_detail()
        self.h.wait(lambda: "Billing unknown" in self.app.jobs.detail.cget("text"))
        text = self.app.jobs.detail.cget("text")
        self.assertIn(
            "3 uncertain paid attempt(s) in 24 h (3 across runs; limits 2/part, 4/episode)", text
        )
        self.assertNotIn("narration-2-of-3:", text)
        self.assertIn("(HTTP 502). Full details in History.", text)
        self.assertIn("up to about $0.0213", text)
        self.assertIn("stop and wait", text)
        self.assertNotIn("blindly resend", text)
        ui_fixtures.UITests.capture(self.h, "preparation-failed-spend-fixture")


if __name__ == "__main__":
    unittest.main()
