"""Uncertain-spend guard, attempt log and stop-and-wait failure text. No network."""

import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib import error

from field_notes_audio import audio, captions, cli, spend_guard
from field_notes_audio.diagnostics import http_meaning, http_uncertain, stop_and_wait
from field_notes_audio.storage import read_object, write_json


class Headers(dict):
    def get(self, name, default=None):
        return super().get(name.lower(), default)


class SpendGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.audio_root = self.root / "artifacts/audio"
        self.plan = audio.make_plan("note-001", "gemini-2.5-pro-tts", "eu")
        self.directory = self.audio_root / "note-001" / self.plan["fingerprint"][:16]
        self.directory.mkdir(parents=True)
        for name in (
            "FIELD_AUDIO_UNCERTAIN_PART_LIMIT",
            "FIELD_AUDIO_UNCERTAIN_EPISODE_LIMIT",
            "FIELD_AUDIO_UNCERTAIN_WINDOW_HOURS",
            "FIELD_AUDIO_TTS_TIMEOUT_SECONDS",
        ):
            patcher = patch.dict(os.environ, {}, clear=False)
            patcher.start()
            self.addCleanup(patcher.stop)
            os.environ.pop(name, None)

    def args(self, **extra):
        values = {
            "episode": "note-001",
            "model": "gemini-2.5-pro-tts",
            "endpoint": "eu",
            "project": "audio-pilot-project",
            "auth": "gcloud",
            "retry_uncertain": False,
        }
        return argparse.Namespace(**{**values, **extra})

    def run_once(self, failure, **extra):
        """One CLI-equivalent run; returns (exception, synthesis call count)."""
        with (
            patch.object(audio, "access_token", return_value="in-memory-token"),
            patch.object(audio, "synthesize", side_effect=failure) as synth,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            try:
                audio.generate_locked(self.args(**extra), self.plan, self.directory, root=self.root)
            except (RuntimeError, ValueError) as exc:
                return exc, synth.call_count, output.getvalue()
        self.fail("generation unexpectedly succeeded")

    def log(self):
        path = self.audio_root / "attempts.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    # --- classification and message text ------------------------------------

    def test_499_is_classified_cancelled_and_uncertain(self):
        self.assertTrue(http_uncertain(499))
        self.assertTrue(http_uncertain(400, "CANCELLED"))
        self.assertIn("cancelled", http_meaning(499))
        self.assertIn("CANCELLED", http_meaning(499))
        self.assertFalse(http_uncertain(403))
        self.assertIn("not retrying a cancelled request", stop_and_wait(499, retry="x"))
        cancelled = error.HTTPError("https://example.test", 499, "Client Closed", {}, None)
        exc, calls, _ = self.run_once(cancelled)
        self.assertEqual(calls, 1)
        state = read_object(self.directory / "chunk-001.json")
        self.assertEqual(state["status"], "uncertain")  # was "failed" before: never billed
        self.assertIn("cancelled before a result came back", str(exc))
        self.assertIn("Billing unknown", str(exc))
        self.assertEqual(
            spend_guard.tally(self.audio_root, "note-001", "narration-1").part_window, 1
        )

    def test_retryable_messages_say_stop_and_wait_not_repeat(self):
        for code in (500, 502, 503, 504, 408, 429, 499):
            with self.subTest(code=code):
                text = audio.http_guidance(code, "note-001")
                self.assertIn("Billing unknown", text)
                self.assertIn("Stop here", text)
                self.assertIn("do not repeat the command in a loop", text)
                self.assertIn("once by hand", text)
                self.assertNotIn("After a short pause", text)
                self.assertNotIn("repeat the same generate command", text)
        self.assertIn("quota", audio.http_guidance(429, "note-001"))
        self.assertIn("fault on Google's side", audio.http_guidance(502, "note-001"))
        self.assertNotIn("Billing unknown", audio.http_guidance(403, "note-001"))

    def test_failure_text_has_counts_spend_attempt_id_and_provider_ids(self):
        gateway = error.HTTPError(
            "https://example.test",
            502,
            "Bad Gateway",
            Headers({"x-goog-request-id": "req-123"}),
            io.BytesIO(b"<html><style>body{}</style>Bad Gateway</html>"),
        )
        exc, _, _ = self.run_once(gateway)
        text = str(exc)
        self.assertTrue(text.startswith("Narration part 1 of 1 failed: a Google gateway"))
        self.assertIn("narration part 1 has 1 (limit 2; 1 across all runs)", text)
        self.assertIn("episode note-001 has 1 (limit 4", text)
        self.assertIn("Possible spend: up to about $0.0846", text)
        self.assertIn("billing unknown", text)
        attempt = read_object(self.directory / "chunk-001.json")["attempt_id"]
        self.assertIn(f"attempt {attempt}", text)
        self.assertIn("req-123", text)
        self.assertIn("--retry-uncertain once by hand", text)
        entries = self.log()
        self.assertEqual([e["type"] for e in entries], ["start", "outcome"])
        self.assertEqual(entries[0]["attempt_id"], attempt)
        self.assertEqual(entries[0]["part"], "narration-1")
        self.assertTrue(entries[0]["at"])
        self.assertEqual(entries[1]["provider_ids"], {"x-goog-request-id": "req-123"})

    def test_timeout_message_is_plain_and_counts_as_uncertain(self):
        exc, _, _ = self.run_once(TimeoutError("hidden"))
        text = str(exc)
        self.assertIn(
            f"no answer arrived within the {audio.TTS_TIMEOUT_SECONDS}s client wait", text
        )
        self.assertIn("Billing unknown", text)
        self.assertNotIn("hidden", text)
        self.assertEqual(self.log()[-1]["outcome"], "uncertain")

    def test_uncertain_receipt_refusal_names_counts_and_says_stop(self):
        self.run_once(TimeoutError())
        exc, calls, _ = self.run_once(TimeoutError())
        self.assertIsInstance(exc, ValueError)
        self.assertEqual(calls, 0)
        self.assertIn("narration part 1 has 1", str(exc))
        self.assertIn("Stop and wait", str(exc))

    # --- guard ----------------------------------------------------------------

    def test_counts_persist_across_runs_and_refuse_at_part_limit(self):
        self.run_once(TimeoutError())
        self.run_once(
            error.HTTPError("https://x", 502, "Bad Gateway", {}, None), retry_uncertain=True
        )
        self.assertEqual(
            spend_guard.tally(self.audio_root, "note-001", "narration-1").part_window, 2
        )
        exc, calls, _ = self.run_once(TimeoutError(), retry_uncertain=True)
        self.assertIsInstance(exc, spend_guard.SpendLimitReached)
        self.assertEqual(calls, 0)  # nothing sent
        self.assertIn("Spend guard: no request was sent", str(exc))
        self.assertIn("has 2 (limit 2", str(exc))
        self.assertIn("Possible spend: up to about $0.1692", str(exc))
        self.assertIn("--allow-spend-over-limit", str(exc))

    def test_old_receipts_are_imported_and_survive_being_overwritten(self):
        write_json(
            self.directory / "chunk-001.json",
            {
                "status": "uncertain",
                "request_sha256": "0" * 64,
                "attempt_id": "a" * 32,
                "failure_kind": "TimeoutError",
            },
        )
        write_json(
            self.directory / f"recovery-001-{'b' * 64}.json",
            {"status": "requesting", "request_sha256": "0" * 64, "attempt_id": "c" * 32},
        )
        seen = spend_guard.tally(self.audio_root, "note-001", "narration-1")
        self.assertEqual((seen.part_window, seen.episode_total), (2, 2))
        self.assertFalse((self.audio_root / "attempts.jsonl").exists())  # reading writes nothing
        exc, calls, _ = self.run_once(TimeoutError(), retry_uncertain=True)
        self.assertIsInstance(exc, spend_guard.SpendLimitReached)
        self.assertEqual(calls, 0)
        # The refusal imported both receipts, so overwriting them loses nothing.
        (self.directory / "chunk-001.json").unlink()
        (self.directory / f"recovery-001-{'b' * 64}.json").unlink()
        self.assertEqual(
            spend_guard.tally(self.audio_root, "note-001", "narration-1").part_window, 2
        )

    def test_episode_limit_counts_every_part(self):
        for index in (2, 3, 4, 5):
            identifier = spend_guard.new_attempt_id()
            spend_guard.record_start(
                self.audio_root,
                episode="note-001",
                part=f"narration-{index}",
                attempt_id=identifier,
                estimate_usd=0.01,
            )
        seen = spend_guard.tally(self.audio_root, "note-001", "narration-1")
        self.assertEqual((seen.part_window, seen.episode_window), (0, 4))
        self.assertTrue(seen.over_episode)
        exc, calls, _ = self.run_once(TimeoutError())
        self.assertIsInstance(exc, spend_guard.SpendLimitReached)
        self.assertIn("episode note-001 has reached 4", str(exc))
        self.assertEqual(calls, 0)

    def test_completed_and_rejected_attempts_do_not_count(self):
        for outcome in ("complete", "failed"):
            identifier = spend_guard.new_attempt_id()
            kwargs = {"episode": "note-001", "part": "narration-1", "attempt_id": identifier}
            spend_guard.record_start(self.audio_root, estimate_usd=0.01, **kwargs)
            spend_guard.record_outcome(self.audio_root, outcome=outcome, **kwargs)
        self.assertEqual(
            spend_guard.tally(self.audio_root, "note-001", "narration-1").episode_total, 0
        )
        self.run_once(error.HTTPError("https://x", 403, "Forbidden", {}, None))
        self.assertEqual(
            spend_guard.tally(self.audio_root, "note-001", "narration-1").episode_total, 0
        )

    def test_override_is_deliberate_and_logged(self):
        self.run_once(TimeoutError())
        self.run_once(TimeoutError(), retry_uncertain=True)
        with self.assertRaisesRegex(ValueError, "written reason"):
            spend_guard.check(self.audio_root, "note-001", "narration-1", override="go")
        exc, calls, output = self.run_once(
            TimeoutError(),
            retry_uncertain=True,
            allow_spend_over_limit="Status page shows the TTS incident resolved",
        )
        self.assertEqual(calls, 1)  # the one deliberate attempt was sent
        self.assertIn("Spend guard override logged", output)
        overrides = spend_guard.overrides(self.audio_root, "note-001")
        self.assertEqual(len(overrides), 1)
        self.assertEqual(overrides[0]["reason"], "Status page shows the TTS incident resolved")
        self.assertEqual(overrides[0]["part_window"], 2)
        self.assertIn("has 3 (limit 2", str(exc))

    def test_studio_override_is_bound_to_the_count_that_was_shown(self):
        self.run_once(TimeoutError())
        self.run_once(TimeoutError(), retry_uncertain=True)
        with self.assertRaisesRegex(spend_guard.SpendLimitReached, "fewer uncertain attempts"):
            spend_guard.check(
                self.audio_root,
                "note-001",
                "narration-1",
                override="Checked the billing report first",
                acknowledged=1,
            )
        spend_guard.check(
            self.audio_root,
            "note-001",
            "narration-1",
            override="Checked the billing report first",
            acknowledged=2,
        )

    def test_window_expiry_lifts_the_limit_but_keeps_totals(self):
        self.run_once(TimeoutError())
        self.run_once(TimeoutError(), retry_uncertain=True)
        self.assertTrue(spend_guard.tally(self.audio_root, "note-001", "narration-1").blocked)
        later = spend_guard.now() + timedelta(hours=23, minutes=59)
        with patch.object(spend_guard, "now", return_value=later):
            self.assertTrue(spend_guard.tally(self.audio_root, "note-001", "narration-1").blocked)
        later = spend_guard.now() + timedelta(hours=24, minutes=1)
        with patch.object(spend_guard, "now", return_value=later):
            seen = spend_guard.tally(self.audio_root, "note-001", "narration-1")
            self.assertFalse(seen.blocked)
            self.assertEqual((seen.part_window, seen.part_total), (0, 2))
            spend_guard.check(self.audio_root, "note-001", "narration-1")

    def test_limits_are_configurable_by_file_and_environment(self):
        self.assertEqual(spend_guard.load_limits(self.audio_root), spend_guard.Limits(2, 4, 24))
        write_json(
            self.audio_root / "spend-guard.json",
            {"part_limit": 1, "episode_limit": 3, "window_hours": 12},
        )
        self.assertEqual(spend_guard.load_limits(self.audio_root), spend_guard.Limits(1, 3, 12))
        with patch.dict(os.environ, {"FIELD_AUDIO_UNCERTAIN_PART_LIMIT": "5"}):
            self.assertEqual(spend_guard.load_limits(self.audio_root).part, 5)
        for bad in ("0", "x", "500"):
            with (
                self.subTest(bad=bad),
                patch.dict(os.environ, {"FIELD_AUDIO_UNCERTAIN_EPISODE_LIMIT": bad}),
                self.assertRaises(ValueError),
            ):
                spend_guard.load_limits(self.audio_root)
        self.run_once(TimeoutError())
        exc, calls, _ = self.run_once(TimeoutError(), retry_uncertain=True)
        self.assertIsInstance(exc, spend_guard.SpendLimitReached)
        self.assertEqual(calls, 0)

    def test_damaged_log_fails_closed(self):
        (self.audio_root / "attempts.jsonl").write_text('{"v": 1}\nnot json\n')
        exc, calls, _ = self.run_once(TimeoutError())
        self.assertIn("damaged", str(exc))
        self.assertEqual(calls, 0)

    # --- timeout --------------------------------------------------------------

    def test_shorter_default_timeout_is_configurable(self):
        self.assertEqual(audio.TTS_TIMEOUT_SECONDS, 360)
        self.assertEqual(audio.tts_timeout_seconds(), 360)
        with patch.dict(os.environ, {"FIELD_AUDIO_TTS_TIMEOUT_SECONDS": "240"}):
            self.assertEqual(audio.tts_timeout_seconds(), 240)
            self.run_once(TimeoutError())
            self.assertEqual(read_object(self.directory / "chunk-001.json")["timeout_seconds"], 240)
        with (
            patch.dict(os.environ, {"FIELD_AUDIO_TTS_TIMEOUT_SECONDS": "30"}),
            self.assertRaises(ValueError),
        ):
            audio.tts_timeout_seconds()

    # --- CLI ------------------------------------------------------------------

    def test_cli_exposes_override_and_timeout_on_paid_commands(self):
        for command in (
            ["generate", "note-001"],
            ["make", "note-001"],
            ["make-all"],
            ["captions", "note-001"],
        ):
            with (
                self.subTest(command=command[0]),
                contextlib.redirect_stderr(io.StringIO()) as stderr,
                self.assertRaises(SystemExit),
            ):
                cli.main([*command, "--allow-spend-over-limit", "why"])
            self.assertIn("8–300 characters", stderr.getvalue())
        for command in (["generate", "note-001"], ["make", "note-001"], ["make-all"]):
            with (
                self.subTest(timeout=command[0]),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                cli.main([*command, "--tts-timeout-seconds", "5"])


class CaptionSpendTests(unittest.TestCase):
    def test_cancelled_caption_submission_is_uncertain_with_stop_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recording = root / "artifacts/audio/note-001/abc"
            recording.mkdir(parents=True)
            mp3 = recording / "episode.mp3"
            mp3.write_bytes(b"ID3" + b"\0" * 2000)
            args = argparse.Namespace(
                audio=mp3,
                project="audio-pilot-project",
                bucket="private-bucket",
                location="us",
                model="chirp_3",
                language="en-US",
                diarize=False,
                auth="gcloud",
                script=None,
                dry_run=False,
                wait=0,
                retry_uncertain=False,
                restart_failed=False,
            )
            with (
                patch.object(captions, "probe_audio", return_value=60.0),
                patch.object(captions.shutil, "which", return_value="installed"),
                patch.object(captions, "ensure_upload", return_value="1"),
                patch.object(
                    captions,
                    "cloud_json",
                    side_effect=captions.CloudError(
                        {"http_status": 499, "provider_status": "CANCELLED"}
                    ),
                ),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(captions.CloudError) as caught,
            ):
                captions.run(args)
            text = str(caught.exception)
            self.assertIn("cancelled before a result came back", text)
            self.assertIn("Billing unknown", text)
            self.assertIn("captions has 1 (limit 2", text)
            state = next(recording.glob("captions/*/state.json"))
            self.assertEqual(read_object(state)["status"], "uncertain")
            entries = [
                json.loads(line)
                for line in (root / "artifacts/audio/attempts.jsonl").read_text().splitlines()
            ]
            self.assertEqual([e["type"] for e in entries], ["start", "outcome"])
            self.assertEqual(entries[1]["outcome"], "uncertain")
            self.assertEqual(entries[0]["attempt_id"], read_object(state)["attempt_id"])


if __name__ == "__main__":
    unittest.main()
