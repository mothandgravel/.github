"""Read-only preparation values; a source plan is not a media approval."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PreparationItem:
    note: str
    title: str
    slug: str
    episode: str
    state: str
    detail: str
    job_id: str = ""


@dataclass(frozen=True)
class PreparationSnapshot:
    note: str
    episode: str
    title: str
    script: str
    summary: str
    identity: str
    request_json: str = ""
    recovery_json: str = ""
    recovery_summary: str = ""
    scope_summary: str = ""
    # Uncertain-spend ledger as shown; blocked means queueing needs a reasoned override.
    spend_summary: str = ""
    spend_blocked: bool = False
    spend_count: int = 0
    spend_token: str = ""
    spend_label: str = ""
    spend_overridable: bool = False
    # Structured facts for the Make episode summary; the same inspection as above.
    parts_total: int = 0
    parts_saved: int = 0
    missing_parts: tuple[int, ...] = ()
    narration_estimate_usd: float | None = None
    recording_saved: bool = False
    captions_status: str = ""
    word_count: int = 0
    minutes: float = 0.0
    project: str = ""
    blockers: tuple[str, ...] = ()
    uncertain_parts: tuple[str, ...] = ()


class CaptionsPending(Exception):
    """Remote captions have a saved operation; explicit resume is safe polling."""

    def __init__(self, message: str, receipt: dict):
        super().__init__(message)
        self.receipt = receipt
