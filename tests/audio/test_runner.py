"""Concurrency, ordering, cancellation and timing tests without paid requests."""

import argparse
import io
import threading
from contextlib import redirect_stdout
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from field_notes_audio import runner
from field_notes_audio.progress import Timings, report, timed


class RunnerTests(TestCase):
    def test_every_transcription_is_submitted_before_waiting_and_no_synthesis_runs_in_wait_phase(
        self,
    ):
        episodes = [{"id": f"note-{index:03d}"} for index in range(6)]
        submitted = []
        lock = threading.Lock()

        def start(args):
            self.assertEqual(args.wait, 0)
            with lock:
                submitted.append(args.episode)
            return None

        def await_result(result, args, recorder):
            self.assertEqual(len(submitted), len(episodes))
            self.assertEqual(args.wait, 30)
            return runner.EpisodeResult(result.episode, Path(result.episode["id"]), None, 0.1)

        with (
            patch.object(runner.workflow, "make", side_effect=start) as make,
            patch.object(runner, "_await_episode", side_effect=await_result) as await_job,
            redirect_stdout(io.StringIO()),
        ):
            results = runner.run_episodes(episodes, argparse.Namespace(jobs=3, wait=30), Timings())
        self.assertEqual(make.call_count, 6)
        self.assertEqual(await_job.call_count, 6)
        self.assertTrue(all(result.issue is None for result in results))
        self.assertEqual([result.episode for result in results], episodes)

    def test_poll_phase_only_captions_the_exact_saved_recording(self):
        original = runner.EpisodeResult({"id": "note-001"}, None, "running", 1.0, True)
        args = argparse.Namespace(model="gemini-2.5-pro-tts", endpoint="global", wait=30)
        with (
            patch.object(runner.audio, "make_plan", return_value={"fingerprint": "a" * 64}),
            patch.object(runner.audio, "generate") as synth,
            patch.object(
                runner.workflow, "caption_recording", return_value=Path("captions")
            ) as caption,
            redirect_stdout(io.StringIO()),
        ):
            result = runner._await_episode(original, args, Timings())
        synth.assert_not_called()
        self.assertEqual(
            caption.call_args.args[0],
            runner.audio.ROOT / "artifacts/audio/note-001" / ("a" * 16) / "episode.mp3",
        )
        self.assertIsNone(result.issue)

    def test_three_pipelines_overlap_but_release_order_and_retry_policy_are_preserved(self):
        episodes = [{"id": f"note-{index:03d}"} for index in range(9)]
        barrier = threading.Barrier(3)
        lock = threading.Lock()
        active = peak = 0
        seen = []

        def make(args):
            nonlocal active, peak
            self.assertFalse(args.retry_uncertain)
            self.assertTrue(args.no_open)
            with lock:
                active += 1
                peak = max(peak, active)
                seen.append(args.episode)
            with timed("mock_provider"):
                report("provider wait")
                barrier.wait(timeout=5)
            with lock:
                active -= 1
            return Path(args.episode)

        recorder = Timings()
        with (
            patch.object(runner.workflow, "make", side_effect=make),
            redirect_stdout(io.StringIO()) as log,
        ):
            results = runner.run_episodes(
                episodes, argparse.Namespace(jobs=3, retry_uncertain=False), recorder
            )
        self.assertEqual(peak, 3)
        self.assertCountEqual(seen, [e["id"] for e in episodes])
        self.assertEqual([r.episode for r in results], episodes)
        self.assertTrue(all(r.issue is None for r in results))
        self.assertEqual(len(recorder.events()), 9)
        self.assertIn("[note-000] provider wait", log.getvalue())

    def test_pending_and_unknown_outcomes_do_not_turn_into_success_or_retry(self):
        episodes = [{"id": "pending"}, {"id": "uncertain"}, {"id": "ready"}]

        def make(args):
            if args.episode == "uncertain":
                raise ValueError("Chunk has an uncertain prior attempt")
            return None if args.episode == "pending" else Path("ready")

        with (
            patch.object(runner.workflow, "make", side_effect=make) as work,
            redirect_stdout(io.StringIO()),
        ):
            results = runner.run_episodes(episodes, argparse.Namespace(jobs=3), Timings())
        self.assertEqual(work.call_count, 3)
        self.assertEqual(results[0].issue, "transcription is still running")
        self.assertIn("uncertain", results[1].issue)
        self.assertIsNone(results[2].issue)

    def test_invalid_concurrency_never_starts_work(self):
        for jobs in (0, 9, True):
            with self.subTest(jobs=jobs), patch.object(runner.workflow, "make") as work:
                with self.assertRaises(ValueError):
                    runner.run_episodes([{"id": "one"}], argparse.Namespace(jobs=jobs), Timings())
                work.assert_not_called()

    def test_stopped_worker_never_starts_the_cloud_workflow(self):
        stop = threading.Event()
        stop.set()
        with patch.object(runner.workflow, "make") as work, redirect_stdout(io.StringIO()):
            result = runner._run_episode(
                {"id": "stopped"}, argparse.Namespace(_cancel_event=stop), Timings()
            )
        work.assert_not_called()
        self.assertIn("stop requested", result.issue)
