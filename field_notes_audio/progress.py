"""Worker labels, stage timing and cooperative batch cancellation."""

from __future__ import annotations

import argparse
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_episode: ContextVar[str | None] = ContextVar("episode", default=None)
_recorder: ContextVar[Timings | None] = ContextVar("recorder", default=None)
_observer: ContextVar[Callable[[str, str], None] | None] = ContextVar("observer", default=None)


@contextmanager
def observe(callback: Callable[[str, str], None]) -> Iterator[None]:
    """Deliver structured stage boundaries without parsing terminal output."""
    token = _observer.set(callback)
    try:
        yield
    finally:
        _observer.reset(token)


def stage(name: str, message: str) -> None:
    callback = _observer.get()
    if callback is not None:
        callback(name, message)


class Timings:
    """Record elapsed stages without request bodies, URIs or credentials."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[dict] = []

    def add(self, stage: str, seconds: float) -> None:
        with self._lock:
            self._events.append(
                {"episode": _episode.get(), "stage": stage, "seconds": round(seconds, 4)}
            )

    def events(self) -> list[dict]:
        with self._lock:
            return [dict(event) for event in self._events]


@contextmanager
def episode_scope(identifier: str, recorder: Timings) -> Iterator[None]:
    episode_token = _episode.set(identifier)
    recorder_token = _recorder.set(recorder)
    try:
        yield
    finally:
        _recorder.reset(recorder_token)
        _episode.reset(episode_token)


@contextmanager
def timed(stage: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        recorder = _recorder.get()
        if recorder is not None:
            recorder.add(stage, time.perf_counter() - start)


def report(message: str, *, flush: bool = False) -> None:
    label = _episode.get()
    print(f"[{label}] {message}" if label else message, flush=flush)


def raise_if_stopped(args: argparse.Namespace) -> None:
    event = getattr(args, "_cancel_event", None)
    if event is not None and event.is_set():
        raise RuntimeError("Batch stop requested; saved work is retained")
