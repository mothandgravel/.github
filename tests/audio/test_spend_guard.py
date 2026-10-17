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
from unittest.mock import Mock, patch
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

    def reserve(self, part="narration-1", **extra):
        return spend_guard.reserve(
            self.audio_root,
            "note-001",
            part,
            attempt_id=spend_guard.new_attempt_id(),
            estimate_usd=0.01,
            **extra,
        )

    def test_start_is_logged_durably_before_the_request_is_sent(self):
        def synthesize(*_args, **_kwargs):
            attempt = read_object(self.directory / "chunk-001.json")["attempt_id"]
            starts = [e for e in self.log() if e["type"] == "start"]
            self.assertEqual([e["attempt_id"] for e in starts], [attempt])
            self.assertFalse([e for e in self.log() if e["type"] == "outcome"])
            raise TimeoutError

        _, calls, _ = self.run_once(synthesize)
        self.assertEqual(calls, 1)
        self.assertEqual(self.log()[-1]["outcome"], "uncertain")

    def test_override_needs_reason_and_the_refusal_token_and_is_logged(self):
        self.run_once(TimeoutError())
        self.run_once(TimeoutError(), retry_uncertain=True)
        refused, calls, _ = self.run_once(TimeoutError(), retry_uncertain=True)
        self.assertEqual(calls, 0)
        token = refused.tally.token
        self.assertIn(f"--spend-token {token}", str(refused))
        with self.assertRaisesRegex(ValueError, "written reason"):
            self.reserve(override="go", token=token)
        reason = "Status page shows the TTS incident resolved"
        exc, calls, _ = self.run_once(
            TimeoutError(), retry_uncertain=True, allow_spend_over_limit=reason
        )
        self.assertIn("old or missing spend token", str(exc))
        self.assertEqual(calls, 0)
        exc, calls, output = self.run_once(
            TimeoutError(),
            retry_uncertain=True,
            allow_spend_over_limit=reason,
            spend_token=token,
        )
        self.assertEqual(calls, 1)  # the one deliberate attempt was sent
        self.assertIn("Spend guard override logged", output)
        logged = spend_guard.overrides(self.audio_root, "note-001")
        self.assertEqual(len(logged), 1)
        self.assertEqual(logged[0]["reason"], reason)
        self.assertEqual((logged[0]["part_window"], logged[0]["token"]), (2, token))
        self.assertIn("has 3 (limit 2", str(exc))

    def test_a_repeated_override_is_refused_even_with_a_fresh_token(self):
        reason = "Checked the billing report first"
        self.run_once(TimeoutError())
        self.run_once(TimeoutError(), retry_uncertain=True)
        token = spend_guard.tally(self.audio_root, "note-001", "narration-1").token
        override = {"allow_spend_over_limit": reason, "spend_token": token}
        self.run_once(TimeoutError(), retry_uncertain=True, **override)
        # The same command again, as a shell loop would repeat it.
        exc, calls, _ = self.run_once(TimeoutError(), retry_uncertain=True, **override)
        self.assertIn("old or missing spend token", str(exc))
        self.assertEqual(calls, 0)
        fresh = spend_guard.tally(self.audio_root, "note-001", "narration-1").token
        self.assertNotEqual(fresh, token)
        exc, calls, _ = self.run_once(
            TimeoutError(), retry_uncertain=True, allow_spend_over_limit=reason, spend_token=fresh
        )
        self.assertIn("already overridden once", str(exc))
        self.assertEqual(calls, 0)
        self.assertEqual(len(spend_guard.overrides(self.audio_root, "note-001")), 1)

    def test_check_and_start_are_atomic_across_processes(self):
        import multiprocessing

        context = multiprocessing.get_context("fork")
        with context.Pool(8) as pool:
            results = pool.map(_reserve_in_process, [str(self.audio_root)] * 8)
        self.assertEqual(results.count("sent"), 2)
        self.assertEqual(results.count("refused"), 6)
        self.assertEqual(
            spend_guard.tally(self.audio_root, "note-001", "narration-1").part_window, 2
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
            self.reserve()

    def test_limits_can_only_be_made_stricter_and_are_logged(self):
        self.assertEqual(spend_guard.load_limits(self.audio_root), spend_guard.Limits(2, 4, 24))
        write_json(
            self.audio_root / "spend-guard.json",
            {"part_limit": 1, "episode_limit": 3, "window_hours": 48},
        )
        self.assertEqual(spend_guard.load_limits(self.audio_root), spend_guard.Limits(1, 3, 48))
        loosening = {
            "FIELD_AUDIO_UNCERTAIN_PART_LIMIT": ("3", "50", "0", "x", "true"),
            "FIELD_AUDIO_UNCERTAIN_EPISODE_LIMIT": ("5", "50", "0"),
            "FIELD_AUDIO_UNCERTAIN_WINDOW_HOURS": ("0.0001", "23", "1000"),
        }
        for name, values in loosening.items():
            for value in values:
                with (
                    self.subTest(name=name, value=value),
                    patch.dict(os.environ, {name: value}),
                    self.assertRaises(ValueError),
                ):
                    spend_guard.load_limits(self.audio_root)
        with patch.dict(os.environ, {"FIELD_AUDIO_UNCERTAIN_PART_LIMIT": "50"}):
            exc, calls, _ = self.run_once(TimeoutError())
            self.assertIn("would loosen", str(exc))
            self.assertEqual(calls, 0)
        _, _, output = self.run_once(TimeoutError())
        self.assertIn(
            "at most 1 uncertain paid attempts per part and 3 per episode in 48 h", output
        )
        self.assertEqual([e["limits"] for e in self.log() if e["type"] == "limits"], [[1, 3, 48.0]])
        exc, calls, _ = self.run_once(TimeoutError(), retry_uncertain=True)
        self.assertIsInstance(exc, spend_guard.SpendLimitReached)
        self.assertEqual(calls, 0)

    def test_malformed_lines_count_as_uncertain_instead_of_vanishing(self):
        (self.audio_root / "attempts.jsonl").write_text(
            'not json\n[]\n{"type": "start", "attempt_id": "x", "episode": "note-001", '
            '"part": "narration-1", "at": "garbage"}\n'
        )
        seen = spend_guard.tally(self.audio_root, "note-001", "narration-1")
        self.assertEqual((seen.episode_window, seen.part_window), (3, 1))
        self.assertIn("damaged log line", seen.attempts[0].detail)

    def test_torn_final_line_counts_and_is_terminated_before_appending(self):
        torn = (
            '{"at": "2026-10-17T00:00:00+00:00", "attempt_id": "' + "d" * 32 + '", '
            '"episode": "note-001", "estimate_usd": 0.01, "part": "narr'
        )
        (self.audio_root / "attempts.jsonl").write_text(torn)
        with patch.object(
            spend_guard, "now", return_value=spend_guard._parse_time("2026-10-17T01:00:00+00:00")
        ):
            seen = spend_guard.tally(self.audio_root, "note-001", "narration-1")
            self.assertEqual(seen.episode_window, 1)
            self.reserve()
            lines = (self.audio_root / "attempts.jsonl").read_text().splitlines()
        self.assertEqual(lines[0], torn)  # kept as evidence, now on its own line
        self.assertEqual(json.loads(lines[1])["type"], "start")
        self.assertEqual(
            spend_guard.tally(self.audio_root, "note-001", "narration-1").episode_total, 2
        )

    def test_failure_text_survives_an_unreadable_log(self):
        gateway = error.HTTPError("https://x", 502, "Bad Gateway", {}, None)
        real = spend_guard.tally

        def flaky(*args, **kwargs):
            if kwargs.get("import_receipts"):
                return real(*args, **kwargs)
            raise ValueError("disk vanished")

        with patch.object(spend_guard, "tally", side_effect=flaky):
            exc, calls, _ = self.run_once(gateway)
        self.assertEqual(calls, 1)
        self.assertIn("a Google gateway got no valid answer", str(exc))
        self.assertIn("could not be read (disk vanished)", str(exc))

    def test_complete_receipt_settles_a_start_whose_outcome_line_was_lost(self):
        identifier = spend_guard.new_attempt_id()
        receipt = self.directory / "chunk-001.json"
        spend_guard.record_start(
            self.audio_root,
            episode="note-001",
            part="narration-1",
            attempt_id=identifier,
            estimate_usd=0.01,
            receipt=str(receipt.relative_to(self.audio_root)),
        )
        write_json(receipt, {"status": "complete", "attempt_id": identifier})
        self.assertEqual(
            spend_guard.tally(self.audio_root, "note-001", "narration-1").episode_total, 0
        )
        with contextlib.redirect_stdout(io.StringIO()) as output:
            audio._log_outcome(Mock(side_effect=OSError("disk full")), "complete", "", 1.0)
        self.assertIn("could not record outcome 'complete'", output.getvalue())

    def test_identical_legacy_receipts_in_two_folders_are_two_attempts(self):
        for folder in ("aaaa", "bbbb"):
            path = self.audio_root / "note-001" / "rec" / "captions" / folder / "state.json"
            write_json(path, {"status": "uncertain", "audio_sha256": "f" * 64})
        self.assertEqual(spend_guard.tally(self.audio_root, "note-001", "captions").part_window, 2)

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
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = cli.main(["make-all", "--allow-spend-over-limit", "One more try for all"])
        self.assertEqual(code, 1)
        self.assertIn("make-all never overrides the spend guard", stderr.getvalue())
        for command in (["generate", "note-001"], ["make", "note-001"], ["make-all"]):
            with (
                self.subTest(timeout=command[0]),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                cli.main([*command, "--tts-timeout-seconds", "5"])


def _reserve_in_process(audio_root: str) -> str:
    try:
        spend_guard.reserve(
            Path(audio_root),
            "note-001",
            "narration-1",
            attempt_id=spend_guard.new_attempt_id(),
            estimate_usd=0.01,
        )
    except spend_guard.SpendLimitReached:
        return "refused"
    return "sent"


def caption_args(mp3):
    return argparse.Namespace(
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


class CaptionSpendTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        patcher = patch.object(audio, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def cloud(self, failure):
        return contextlib.ExitStack(), [
            patch.object(captions, "probe_audio", return_value=60.0),
            patch.object(captions.shutil, "which", return_value="installed"),
            patch.object(captions, "ensure_upload", return_value="1"),
            patch.object(captions, "cloud_json", side_effect=failure),
        ]

    def run_captions(self, mp3, failure):
        stack, patches = self.cloud(failure)
        with stack, contextlib.redirect_stdout(io.StringIO()):
            mocks = [stack.enter_context(p) for p in patches]
            try:
                captions.run(caption_args(mp3))
            except (RuntimeError, ValueError) as exc:
                return exc, mocks
        return None, mocks

    def test_caption_guard_refuses_at_the_limit_before_upload(self):
        recording = self.root / "artifacts/audio/note-001/abc"
        recording.mkdir(parents=True)
        mp3 = recording / "episode.mp3"
        mp3.write_bytes(b"ID3" + b"\0" * 2000)
        episode = "recording-" + audio.digest(mp3.read_bytes())[:12]
        for _ in range(2):
            spend_guard.record_start(
                self.root / "artifacts/audio",
                episode=episode,
                part="captions",
                attempt_id=spend_guard.new_attempt_id(),
                estimate_usd=None,
            )
        exc, (_, _, upload, cloud) = self.run_captions(mp3, AssertionError("sent"))
        self.assertIsInstance(exc, spend_guard.SpendLimitReached)
        self.assertIn("captions has reached 2 uncertain attempts", str(exc))
        upload.assert_not_called()
        cloud.assert_not_called()

    def test_caption_mp3_outside_artifacts_logs_to_the_checkout(self):
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        mp3 = Path(elsewhere.name) / "episode.mp3"
        mp3.write_bytes(b"ID3" + b"\0" * 2000)
        exc, _ = self.run_captions(mp3, TimeoutError())
        self.assertIn("Billing unknown", str(exc))
        self.assertTrue((self.root / "artifacts/audio/attempts.jsonl").exists())
        self.assertFalse(list(Path(elsewhere.name).rglob("attempts.jsonl")))

    def test_cancelled_caption_submission_is_uncertain_with_stop_text(self):
        root = self.root
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
