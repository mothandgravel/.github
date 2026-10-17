"""make-episode on the command line: the same summary, digest consent and rules as Studio."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from field_notes_audio import audio, spend_guard
from field_notes_audio.storage import write_json
from field_notes_studio import make_cli
from field_notes_studio.__main__ import main
from tests.studio.test_make_episode import Media
from tests.studio.test_spend_guard_studio import uncertain


class MakeCliTests(unittest.TestCase):
    def setUp(self):
        self.m = Media(self)

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--root", str(self.m.root), "make-episode", *args])
        return code, out.getvalue(), err.getvalue()

    def digest(self, text):
        return next(line.split()[1] for line in text.splitlines() if line.startswith("Digest:"))

    def test_without_confirm_it_only_prints_the_summary(self):
        code, out, _ = self.cli("104")
        self.assertEqual(code, 0)
        for expected in (
            "Make Field Note 104 into an episode · Window",
            "Narrate",
            "Paid",
            "Local",
            "You",
            "Estimate: ",
            "at most 2 uncertain paid attempts per part and 4 per episode",
            "No uncertain paid attempts",
            "Nothing was sent or queued.",
        ):
            self.assertIn(expected, out)
        self.assertEqual(self.digest(out), self.m.studio.make_plan(note="104").token)
        self.assertEqual(self.m.studio.repository.jobs(), [])
        self.m.launch.assert_not_called()

    def test_confirm_with_the_printed_digest_starts_exactly_that_plan(self):
        _, out, _ = self.cli("104")
        plan = self.m.studio.make_plan(note="104")
        code, started, _ = self.cli("104", "--confirm", self.digest(out))
        self.assertEqual(code, 0, started)
        self.assertIn("Started Make episode run", started)
        jobs = self.m.studio.repository.jobs()
        self.assertEqual([j.action for j in jobs], ["prepare"])
        self.assertEqual(json.loads(jobs[0].request), json.loads(plan.request_json))
        run = self.m.studio.repository.runs()[0]
        self.assertEqual(run["consent"]["token"], plan.token)

    def test_a_wrong_short_or_stale_digest_starts_nothing(self):
        _, out, _ = self.cli("104")
        digest = self.digest(out)
        for value in ("0" * 64, digest[:12], "yes"):
            with self.subTest(value=value):
                code, _, err = self.cli("104", "--confirm", value)
                self.assertEqual(code, 1)
                self.assertTrue(err.startswith("Studio: "))
        uncertain(self.m.root, "studio-essay", "captions", 1, estimate=None)
        code, _, err = self.cli("104", "--confirm", digest)
        self.assertEqual(code, 1)
        self.assertIn("does not match the summary as it is now", err)
        self.assertEqual(self.m.studio.repository.jobs(), [])

    def test_an_uncertain_resend_is_never_covered_and_no_override_exists(self):
        directory = self.m.f.adapter._recording(self.m.f.request["plan"])
        expected = audio.digest(
            json.dumps(self.m.f.request["plan"]["requests"][0], sort_keys=True).encode()
        )
        write_json(
            directory / "chunk-001.json",
            {"status": "uncertain", "request_sha256": expected, "http_status": 502},
        )
        code, out, _ = self.cli("104")
        self.assertEqual(code, 1)
        self.assertIn("Can't start yet:", out)
        self.assertIn("needs its own consent", out)
        code, _, err = self.cli("104", "--confirm", self.digest(out))
        self.assertEqual(code, 1)
        self.assertIn("own consent", err)
        for flag in ("--allow-spend-over-limit", "--retry-uncertain", "--spend-token"):
            with self.subTest(flag=flag), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main(["--root", str(self.m.root), "make-episode", "104", flag, "x"])
        self.assertEqual(self.m.studio.repository.jobs(), [])

    def test_a_reached_spend_guard_blocks_the_cli_too(self):
        uncertain(self.m.root, "studio-essay", "narration-1", 2)
        code, out, _ = self.cli("104")
        self.assertEqual(code, 1)
        self.assertIn("spend guard", out)
        code, _, _ = self.cli("104", "--confirm", self.digest(out))
        self.assertEqual(code, 1)
        self.assertEqual(self.m.studio.repository.jobs(), [])

    def test_status_shows_the_run_timeline_and_its_cost(self):
        code, out, _ = self.cli("104", "--status")
        self.assertEqual(code, 1)
        self.assertIn("No open Make episode run for studio-essay", out)
        _, summary, _ = self.cli("104")
        self.cli("104", "--confirm", self.digest(summary))
        code, out, _ = self.cli("studio-essay", "--status")
        self.assertEqual(code, 0)
        for expected in ("Narrate", "Caption", "Make video", "Upload package"):
            self.assertIn(expected, out)
        self.assertIn("Nothing paid is recorded for this episode yet.", out)

    def test_ids_are_a_note_number_or_an_episode_id(self):
        self.assertEqual(make_cli.target("014"), {"note": "014"})
        self.assertEqual(make_cli.target("maritime-study"), {"episode": "maritime-study"})
        for bad in ("../x", "Maritime", "a b", "--x"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                make_cli.target(bad)


class EpisodeCostTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def attempt(self, part, outcome, estimate):
        attempt_id = spend_guard.new_attempt_id()
        spend_guard.record_start(
            self.root, episode="ep", part=part, attempt_id=attempt_id, estimate_usd=estimate
        )
        if outcome:
            spend_guard.record_outcome(
                self.root, episode="ep", part=part, attempt_id=attempt_id, outcome=outcome
            )

    def test_nothing_recorded(self):
        cost = spend_guard.episode_cost(self.root, "ep")
        self.assertEqual(cost.sentence(), "Nothing paid is recorded for this episode yet.")

    def test_estimates_captions_and_uncertain_are_kept_apart(self):
        self.attempt("narration-1", "complete", 0.05)
        self.attempt("narration-2", "complete", 0.04)
        self.attempt("captions", "acknowledged", None)
        self.attempt("narration-3", None, 0.04)  # started, never settled: uncertain
        self.attempt("narration-3", "uncertain", 0.04)
        self.attempt("narration-3", "failed", 0.04)  # refused before output: not counted
        cost = spend_guard.episode_cost(self.root, "ep")
        self.assertEqual((cost.narration_parts, cost.narration_usd), (2, 0.09))
        self.assertEqual(cost.caption_submissions, 1)
        self.assertEqual((cost.uncertain, cost.uncertain_usd), (2, 0.08))
        self.assertEqual(
            cost.sentence(14.2),
            "So far, by local estimate (not a bill): narration about $0.09 (2 saved parts); "
            "captions: no local estimate (1 submission, about 14 min of audio). Possibly "
            "billed: 2 uncertain attempts, up to about $0.08. Check the Cloud billing report "
            "for actual charges.",
        )

    def test_only_uncertain_attempts_never_read_as_spent(self):
        self.attempt("captions", None, None)
        text = spend_guard.episode_cost(self.root, "ep").sentence()
        self.assertTrue(text.startswith("No completed paid request is recorded yet"))
        self.assertIn("Possibly billed: 1 uncertain attempt, no local estimate", text)
        self.assertNotIn("$", text)


if __name__ == "__main__":
    unittest.main()
