"""Values for Make episode: the pre-flight summary, its consent and the run timeline.

A summary is what the person saw before the single confirm. Its ``token`` is a
digest of exactly those facts; the confirm is accepted only while a fresh
inspection still produces the same token. A run is a record of that consent plus
ordinary jobs; its state is always read back from the jobs, never stored twice.
"""

from __future__ import annotations

from dataclasses import dataclass

# Who or what does each step. "reused" means saved work is used again, at no charge.
KINDS = ("paid", "local", "you", "reused")


@dataclass(frozen=True)
class PlanStep:
    key: str  # narrate · caption · sound · video · review · package
    name: str
    detail: str
    kind: str


@dataclass(frozen=True)
class Attempt:
    """One uncertain paid attempt from the engine's attempts log, for display."""

    when: str
    part: str
    detail: str
    estimate: str


@dataclass(frozen=True)
class SpendState:
    """The spend guard as the summary shows it; read-only, from the attempts log."""

    limits: str
    part_limit: int
    episode_limit: int
    window_hours: float
    episode_window: int
    part_window: int
    possible: str
    attempts: tuple[Attempt, ...] = ()
    blocked: bool = False
    guard_token: str = ""

    def sentence(self) -> str:
        if not self.episode_window:
            return "No uncertain paid attempts for this episode in the last " + (
                f"{self.window_hours:g} h."
            )
        return (
            f"{self.episode_window} uncertain paid attempt(s) for this episode in the last "
            f"{self.window_hours:g} h (limit {self.episode_limit}; at most {self.part_limit} "
            f"per part). Possible spend: {self.possible}."
        )


@dataclass(frozen=True)
class MakePlan:
    episode: str
    note: str
    title: str
    words: int
    checked_at: str
    recipe_label: str
    steps: tuple[PlanStep, ...]
    spend: SpendState
    reused: tuple[str, ...]
    blockers: tuple[str, ...]
    project: str = ""
    estimate_usd: float | None = None
    captions_minutes: float = 0.0
    # The captured preparation request this consent covers; empty without paid steps.
    request_json: str = ""
    recipe: tuple[tuple[str, object], ...] = ()
    token: str = ""

    @property
    def paid(self) -> bool:
        return any(step.kind == "paid" for step in self.steps)

    @property
    def allowed(self) -> bool:
        return not self.blockers


@dataclass(frozen=True)
class TimelineRow:
    key: str
    name: str
    state: str  # Saved · Working · Waiting · Next · After review · Paused · Stopped · Reused
    detail: str
    kind: str  # ok · run · todo · warn · you


@dataclass(frozen=True)
class RunView:
    identifier: str
    episode: str
    title: str
    started: str
    phase: str  # working · review · paused · stopped · ready · done
    group: str  # needs-you · working · done
    headline: str
    detail: str
    rows: tuple[TimelineRow, ...]
    job: str = ""
    stop_after: bool = False
    current: str = ""
