"""Detached single-owner worker; journalling and cancellation survive UI closure."""

from __future__ import annotations

import json
import time
from pathlib import Path

from field_notes_audio.locks import run_lock
from field_notes_audio.progress import observe
from field_notes_studio.models import StopRequested
from field_notes_studio.pipeline import Pipeline
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
            result = pipeline.run(job.episode, job.action, json.loads(job.request), directory, emit)
        # A completed transactional operation wins over a late stop request.
        repository.finish(job.identifier, "succeeded", result=result)
    except StopRequested:
        repository.finish(
            job.identifier,
            "cancelled",
            error="Stopped at a stage boundary. Completed caches remain available.",
        )
    except Exception as exc:
        repository.finish(job.identifier, "failed", error=str(exc))


def work(root: Path, *, once: bool = False) -> None:
    repository = Repository(root / "artifacts/studio/studio.sqlite3")
    pipeline = Pipeline(root)
    # The OS releases this lock after a crash. Only its owner can reconcile jobs.
    try:
        with run_lock(repository.path.parent, "studio worker"):
            repository.recover()
            while True:
                job = repository.claim()
                if job is not None:
                    execute(repository, pipeline, job)
                elif once:
                    return
                else:
                    time.sleep(0.5)
    except ValueError as exc:
        if "Another studio worker" not in str(exc):
            raise
