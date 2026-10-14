"""Bounded local audio jobs; complete running writes before propagating failure."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")


def completed_jobs(jobs: list[Callable[[], T]], workers: int) -> Iterator[T]:
    """Yield in input order, retaining completed caches if another job fails."""
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("Audio jobs must be an integer between 1 and 4")
    if workers == 1:
        for job in jobs:
            yield job()
        return
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="audio-production")
    try:
        futures = [executor.submit(job) for job in jobs]
        for future in futures:
            yield future.result()
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
