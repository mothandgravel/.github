"""Detached single-owner worker; journalling and cancellation survive UI closure."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from field_notes_audio.locks import run_lock
from field_notes_audio.progress import observe
from field_notes_studio.health import process_id, revision
from field_notes_studio.models import StopRequested
from field_notes_studio.pipeline import Pipeline
from field_notes_studio.preparation_jobs import PreparationJobs
from field_notes_studio.preparation_models import CaptionsPending
from field_notes_studio.processes import launch_worker
from field_notes_studio.repository import Repository


def execute(repository: Repository, pipeline: Pipeline, job) -> None:
    def emit(stage: str, message: str) -> None:
        if stage.endswith("-complete"):
            # Persist completed writes even when a stop arrived during this stage.
            repository.event(job.identifier, stage, message)
        if repository.stopped(job.identifier):
            raise StopRequested
        if not stage.endswith("-complete"):
            repository.event(job.identifier, stage, message)

    try:
        emit("starting", "Worker owns this job; closing the window will not stop it")
        directory = repository.path.parent / "jobs" / job.identifier
        directory.mkdir(parents=True, exist_ok=True)
        with observe(emit):
            if job.action == "prepare":
                result = PreparationJobs(pipeline.root).run(
                    json.loads(job.request), emit, lambda: repository.stopped(job.identifier)
                )
            else:
                result = pipeline.run(
                    job.episode, job.action, json.loads(job.request), directory, emit
                )
        # A completed transactional operation wins over a late stop request.
        repository.finish(job.identifier, "succeeded", result=result)
    except CaptionsPending as exc:
        repository.pause(job.identifier, str(exc), exc.receipt)
    except StopRequested:
        repository.finish(
            job.identifier,
            "cancelled",
            error="Stopped at a stage boundary. Completed caches remain available.",
        )
    except Exception as exc:
        repository.finish(job.identifier, "failed", error=str(exc))


def advance_runs(root: Path, job=None, *, verify_review: bool = False) -> None:
    """Chain Make episode runs; a failure here never stops the worker or a job."""
    from field_notes_studio.make_runs import Runs
    from field_notes_studio.service import Studio

    try:
        runs = Runs(Studio(root))
        if job is not None:
            runs.record_durations(runs.repository.get(job.identifier))
        runs.advance_all(verify_review=verify_review)
    except Exception as exc:  # noqa: BLE001 - logged; the queue keeps working
        print(f"Make episode runs could not advance: {type(exc).__name__}: {exc}", flush=True)


def work(root: Path, *, once: bool = False) -> None:
    repository = Repository(root / "artifacts/studio/studio.sqlite3")
    pipeline = Pipeline(root)
    loaded = revision()
    replacement = False
    # The OS releases this lock after a crash. Only its owner can reconcile jobs.
    try:
        with run_lock(repository.path.parent, "studio worker"):
            repository.recover()
            # After a restart, pick up runs whose next step was not queued yet.
            advance_runs(root, verify_review=True)
            control = repository.state("worker_control").get("restart")
            stopped = threading.Event()
            activity = "idle"

            def heartbeat():
                while not stopped.is_set():
                    repository.checkpoint(
                        {
                            "worker": {
                                "pid": process_id(),
                                "revision": loaded,
                                "heartbeat": time.time(),
                                "activity": activity,
                            }
                        }
                    )
                    stopped.wait(2)

            monitor = threading.Thread(target=heartbeat, daemon=True, name="studio-heartbeat")
            monitor.start()
            idle = 0
            try:
                while True:
                    # Never unload code or terminate a media stage to perform an upgrade.
                    if (
                        revision() != loaded
                        or repository.state("worker_control").get("restart") != control
                    ):
                        replacement = not once
                        break
                    job = repository.claim()
                    if job is not None:
                        activity = f"{job.episode} · {job.action}"
                        execute(repository, pipeline, job)
                        activity = "idle"
                        advance_runs(root, job)
                        idle = 0
                    elif once:
                        break
                    else:
                        time.sleep(0.5)
                        idle += 1
                        if idle % 10 == 0:
                            # Caption polls and runs advanced by another window.
                            advance_runs(root)
            finally:
                stopped.set()
                monitor.join(timeout=12)
    except ValueError as exc:
        if "Another studio worker" not in str(exc):
            raise
    if replacement:
        # The replacement may claim jobs only after this process releases its flock.
        launch_worker(root)
