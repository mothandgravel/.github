"""Episode-level evidence, not an inference from the last job's exit status."""

import re
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
    # Exception text for a Details disclosure; never the headline or the next step.
    technical: str = ""


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


# One plain sentence per place a check can fail: what is wrong, then what to do.
PLAIN = {
    "inputs": "Recording details are incomplete. Prepare the note again.",
    "inputs-file": "A recording file can't be read. Check the artifacts folder.",
    "copy": "Upload title, description or tags are invalid. Fix them in Release.",
    "busy": "Another job is using these files. Wait for it, then Check.",
    "edition": "The saved episode can't be verified. Produce it again.",
    "package": "The upload folder can't be verified. Make it again.",
    "preflight": "A production check failed; nothing was queued. See Setup check.",
}


def technical(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:600]


_STDLIB_MARKS = re.compile(
    r"""['"`<>{}\[\]/\\]|Errno|line \d+ column|Traceback|\bis not\b|\bobject\b|\bargument\b"""
)


def _authored(text: str) -> bool:
    """A sentence this codebase wrote for people, not stdlib exception text.

    Authored messages are capitalised sentences without the quotes, brackets, paths
    and phrases that stdlib errors carry (stdlib messages also tend to start lower case).
    """
    return (
        20 <= len(text) <= 300
        and text[:1].isupper()
        and len(text.split()) >= 4
        and not _STDLIB_MARKS.search(text)
    )


def plain(exc: BaseException, context: str) -> str:
    """A readable sentence for the card, never a bare exception such as 'audio_sha256'.

    Messages this codebase raises on purpose are kept. Everything else, including
    stdlib ValueError text, gets the context's sentence; the technical text stays
    behind Details.
    """
    text = str(exc).strip()
    authored_type = (
        type(exc) in {ValueError, ReadinessBusy} or type(exc).__name__ == "RecordingBusy"
    )
    if authored_type and _authored(text):
        return text
    if context == "inputs" and isinstance(exc, OSError):
        return PLAIN["inputs-file"]
    return PLAIN[context]


def readable(message: str, context: str = "preflight") -> tuple[str, str]:
    """(sentence, technical) for an error that only arrived as text."""
    text = (message or "").strip()
    if _authored(text):
        return text, ""
    return PLAIN[context], text[:600]
