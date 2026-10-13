"""Bounded episode pipelines; Cloud calls overlap without sharing run ownership."""

from __future__ import annotations

import argparse
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from field_notes_audio import audio, workflow
from field_notes_audio.progress import Timings, episode_scope, raise_if_stopped, report


@dataclass(frozen=True)
class EpisodeResult:
    episode: dict
    directory: Path | None
    issue: str | None
    seconds: float
    pending: bool = False


def _run_episode(episode: dict, args: argparse.Namespace, recorder: Timings) -> EpisodeResult:
    start = time.perf_counter()
    with episode_scope(episode["id"], recorder):
        report("Start episode", flush=True)
        single = argparse.Namespace(**{**vars(args), "episode": episode["id"], "no_open": True})
        try:
            raise_if_stopped(single)
            directory = workflow.make(single)
            pending = directory is None
            issue = "transcription is still running" if pending else None
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
            directory, issue, pending = None, str(exc), False
        seconds = time.perf_counter() - start
        report(f"{'Ready' if issue is None else 'Pending: ' + issue} · {seconds:.1f}s", flush=True)
        return EpisodeResult(episode, directory, issue, seconds, pending)


def _await_episode(
    result: EpisodeResult, args: argparse.Namespace, recorder: Timings
) -> EpisodeResult:
    """Poll an existing caption job; this phase has no synthesis call."""
    start = time.perf_counter()
    with episode_scope(result.episode["id"], recorder):
        single = argparse.Namespace(
            **{**vars(args), "episode": result.episode["id"], "no_open": True}
        )
        try:
            raise_if_stopped(single)
            plan = audio.make_plan(single.episode, single.model, single.endpoint, audio.ROOT)
            path = (
                audio.ROOT
                / "artifacts/audio"
                / single.episode
                / plan["fingerprint"][:16]
                / "episode.mp3"
            )
            directory = workflow.caption_recording(path, single)
            pending = directory is None
            issue = "transcription is still running" if pending else None
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
            directory, issue, pending = None, str(exc), False
        seconds = result.seconds + time.perf_counter() - start
        report(
            f"{'Ready' if issue is None else 'Pending: ' + issue} · {seconds:.1f}s processing",
            flush=True,
        )
        return EpisodeResult(result.episode, directory, issue, seconds, pending)


def run_episodes(
    episodes: list[dict], args: argparse.Namespace, recorder: Timings
) -> list[EpisodeResult]:
    """Run each episode once, keep catalog order and cancel queued work on interruption."""
    jobs = getattr(args, "jobs", 3)
    if type(jobs) is not int or not 1 <= jobs <= 8:
        raise ValueError("--jobs must be between 1 and 8")
    stop = threading.Event()
    args = argparse.Namespace(**{**vars(args), "_cancel_event": stop})
    pool = ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="field-audio")
    pending = {}
    results = {}
    try:
        # Submit transcription with wait=0 so remote processing can overlap all
        # later synthesis, rather than holding a worker for a long-running job.
        initial = argparse.Namespace(**{**vars(args), "wait": 0})
        for index, episode in enumerate(episodes):
            pending[pool.submit(_run_episode, episode, initial, recorder)] = index
        for future in as_completed(pending):
            results[pending[future]] = future.result()
        if getattr(args, "wait", 0) > 0:
            awaiting = [index for index, result in results.items() if result.pending]
            report(
                f"Caption jobs are submitted; resume {len(awaiting)} saved jobs without resynthesis.",
                flush=True,
            )
            pending = {
                pool.submit(_await_episode, results[index], args, recorder): index
                for index in awaiting
            }
            for future in as_completed(pending):
                results[pending[future]] = future.result()
    except BaseException:
        stop.set()
        for future in pending:
            future.cancel()
        report(
            "Stopping queued work; active Cloud requests finish and save their outcome.", flush=True
        )
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    return [results[index] for index in range(len(episodes))]
