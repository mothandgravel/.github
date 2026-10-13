"""Exclusive, nonblocking per-recording process locks for Linux and WSL."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def run_lock(directory: Path, label: str = "caption") -> Iterator[None]:
    import fcntl  # Cloud Shell and WSL; OS releases the lock even after interruption.

    with (directory / ".lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(
                f"Another {label} command is using this recording; wait for it to finish"
            ) from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
