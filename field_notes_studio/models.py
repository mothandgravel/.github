"""Immutable values shared across application, storage and presentation boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Action = Literal["audio", "video", "preview", "export"]
ACTIONS = ("audio", "video", "preview", "export")
TERMINAL = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


@dataclass(frozen=True)
class Episode:
    identifier: str
    title: str
    duration: float
    transcript: str
    publication_url: str = ""
    publication_date: str = ""


@dataclass(frozen=True)
class Job:
    identifier: str
    episode: str
    action: Action
    status: str
    stage: str
    created: str
    error: str
    result: str
    request: str
    cancel_requested: bool = False


class StopRequested(Exception):
    """A cooperative stop reached a safe production boundary."""
