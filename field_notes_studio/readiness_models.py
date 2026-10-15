"""Episode-level evidence, not an inference from the last job's exit status."""

from dataclasses import dataclass


class ReadinessBusy(ValueError):
    """A prerequisite cannot be inspected while another local operation owns it."""


@dataclass(frozen=True)
class Readiness:
    episode: str
    action: str
    title: str
    detail: str
    stages: tuple[str, ...] = ()
    identity: str = ""
    job: str = ""
    checked_at: str = ""


LABELS = {
    "check": "Check readiness",
    "produce": "Produce episode",
    "review": "Review full episode",
    "export": "Export updated package",
    "package": "Open upload package",
    "job": "Show current job",
    "health": "Inspect blockers",
    "repair": "Inspect blockers",
}
