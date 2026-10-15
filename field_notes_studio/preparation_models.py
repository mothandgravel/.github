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


@dataclass(frozen=True)
class PreparationSnapshot:
    note: str
    episode: str
    title: str
    script: str
    summary: str
    identity: str
    request_json: str = ""


class CaptionsPending(Exception):
    """Remote captions have a saved operation; explicit resume is safe polling."""

    def __init__(self, message: str, receipt: dict):
        super().__init__(message)
        self.receipt = receipt
