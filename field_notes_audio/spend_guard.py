"""Append-only paid-attempt log and the uncertain-spend guard shared by CLI and Studio.

Every paid narration request and caption submission gets a unique attempt ID that
is written to ``artifacts/audio/attempts.jsonl`` before the request is sent, with
its outcome appended afterwards. The log is never rewritten, so it can be
reconciled against the Cloud billing report.

An attempt is *uncertain* when it may have been billed but no result was saved:
server errors, 408, 429, 499 (CANCELLED), client timeouts, lost connections and
crashes between start and outcome. Receipts written before this log existed are
imported once from the cache files (timestamped by file modification time), so
earlier evidence is not lost when a retry overwrites a receipt.

The guard refuses another paid request when uncertain attempts in the rolling
window reach the per-part or per-episode limit. Only a deliberate override with a
written reason passes it, and the override itself is logged. There is no automatic
retry anywhere in this module.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from field_notes_audio.storage import digest_file, read_object

DEFAULT_PART_LIMIT = 2
DEFAULT_EPISODE_LIMIT = 4
DEFAULT_WINDOW_HOURS = 24
LOG_NAME = "attempts.jsonl"
CONFIG_NAME = "spend-guard.json"
UNCERTAIN = "uncertain"
SETTLED = {"complete", "failed", "acknowledged"}
_PROVIDER_ID = re.compile(r"[A-Za-z0-9._:/;=+-]{1,160}")
_REASON = re.compile(r"[^\x00-\x1f\x7f]{8,300}")


class SpendLimitReached(ValueError):
    """Another paid attempt would pass the uncertain-spend limit without an override."""

    def __init__(self, message: str, tally: Tally):
        super().__init__(message)
        self.tally = tally


@dataclass(frozen=True)
class Limits:
    part: int = DEFAULT_PART_LIMIT
    episode: int = DEFAULT_EPISODE_LIMIT
    window_hours: float = DEFAULT_WINDOW_HOURS


@dataclass(frozen=True)
class Attempt:
    attempt_id: str
    at: datetime
    episode: str
    part: str
    outcome: str
    detail: str = ""
    estimate_usd: float | None = None
    provider_ids: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Tally:
    episode: str
    part: str
    limits: Limits
    part_window: int
    part_total: int
    episode_window: int
    episode_total: int
    estimate_usd: float
    unestimated: int
    attempts: tuple[Attempt, ...] = ()

    @property
    def over_part(self) -> bool:
        return self.part_window >= self.limits.part

    @property
    def over_episode(self) -> bool:
        return self.episode_window >= self.limits.episode

    @property
    def blocked(self) -> bool:
        return self.over_part or self.over_episode

    def spend_text(self) -> str:
        if not self.episode_window:
            return "no uncertain spend recorded in this window"
        estimated = self.episode_window - self.unestimated
        parts = []
        if estimated:
            parts.append(f"up to about ${self.estimate_usd:.4f} in speech output")
        if self.unestimated:
            parts.append(f"{self.unestimated} attempt(s) with no local price estimate")
        return " plus ".join(parts) + "; billing unknown"

    def sentence(self) -> str:
        hours = f"{self.limits.window_hours:g} h"
        return (
            f"Uncertain paid attempts in the last {hours}: {part_label(self.part)} has "
            f"{self.part_window} (limit {self.limits.part}; {self.part_total} across all runs), "
            f"episode {self.episode} has {self.episode_window} (limit {self.limits.episode}; "
            f"{self.episode_total} across all runs). Possible spend: {self.spend_text()}."
        )


def part_label(part: str) -> str:
    if part.startswith("narration-"):
        return "narration part " + part.removeprefix("narration-")
    return "captions" if part == "captions" else part


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_attempt_id() -> str:
    return uuid.uuid4().hex


def log_root(path: Path, default: Path | None = None) -> Path:
    """The ``artifacts/audio`` folder that owns ``path``.

    Outside such a folder, use ``default`` (the checkout's ``artifacts/audio``), or
    the folder holding ``path`` when no default is given.
    """
    path = path.resolve()
    for parent in (path, *path.parents):
        if parent.name == "audio" and parent.parent.name == "artifacts":
            return parent
    if default is not None:
        return default
    return path if path.is_dir() else path.parent


def load_limits(audio_root: Path) -> Limits:
    """Read ``artifacts/audio/spend-guard.json``; environment variables win."""
    values: dict = {}
    config = audio_root / CONFIG_NAME
    if config.exists():
        values = read_object(config)
    names = {
        "part": "FIELD_AUDIO_UNCERTAIN_PART_LIMIT",
        "episode": "FIELD_AUDIO_UNCERTAIN_EPISODE_LIMIT",
        "window_hours": "FIELD_AUDIO_UNCERTAIN_WINDOW_HOURS",
    }
    keys = {"part": "part_limit", "episode": "episode_limit", "window_hours": "window_hours"}
    result = {}
    for name, environment in names.items():
        raw = os.environ.get(environment, values.get(keys[name]))
        if raw is None:
            continue
        try:
            number = float(raw) if name == "window_hours" else int(raw)
        except (TypeError, ValueError):
            raise ValueError(
                f"Spend guard setting {keys[name]} must be a number; check {CONFIG_NAME} or {environment}"
            ) from None
        if isinstance(raw, bool) or not (
            0 < number <= 24 * 30 if name == "window_hours" else 1 <= number <= 50
        ):
            raise ValueError(
                f"Spend guard setting {keys[name]} is out of range; check {CONFIG_NAME} or {environment}"
            )
        result[name] = number
    return Limits(**result)


def validate_reason(reason: object) -> str:
    text = reason.strip() if isinstance(reason, str) else ""
    if not _REASON.fullmatch(text):
        raise ValueError(
            "An override needs a written reason of 8–300 characters on one line, "
            'e.g. --allow-spend-over-limit "provider status page shows the incident resolved"'
        )
    return text


def add_override_argument(parser) -> None:
    """``--allow-spend-over-limit REASON`` for every command that can send paid work."""
    import argparse

    def reason(value: str) -> str:
        try:
            return validate_reason(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc)) from None

    parser.add_argument(
        "--allow-spend-over-limit",
        metavar="REASON",
        type=reason,
        help="Deliberately pass the uncertain-spend guard for this run; the reason is logged",
    )


def provider_ids(headers) -> dict:
    """Keep only recognisable provider request/trace IDs from response headers."""
    if headers is None:
        return {}
    found = {}
    for name in (
        "x-goog-request-id",
        "x-request-id",
        "x-cloud-trace-context",
        "x-guploader-uploadid",
    ):
        try:
            value = headers.get(name)
        except AttributeError:
            return {}
        if isinstance(value, str) and _PROVIDER_ID.fullmatch(value.strip()):
            found[name] = value.strip()
    return found


def _append(audio_root: Path, entry: dict) -> None:
    audio_root.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"v": 1, **entry}, ensure_ascii=False, sort_keys=True) + "\n"
    with (audio_root / LOG_NAME).open("a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _entries(audio_root: Path) -> list[dict]:
    path = audio_root / LOG_NAME
    if not path.exists():
        return []
    entries = []
    with path.open(encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_SH)
        try:
            lines = handle.read().splitlines()
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            raise ValueError(
                f"The paid-attempt log {path} is damaged at line {number}. Inspect it before any "
                "further paid request; nothing was sent."
            ) from None
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def record_start(
    audio_root: Path,
    *,
    episode: str,
    part: str,
    attempt_id: str,
    estimate_usd: float | None,
    request_sha256: str = "",
    receipt: str = "",
) -> None:
    _append(
        audio_root,
        {
            "type": "start",
            "at": now().isoformat(timespec="seconds"),
            "attempt_id": attempt_id,
            "episode": episode,
            "part": part,
            "estimate_usd": estimate_usd,
            "request_sha256": request_sha256,
            "receipt": receipt,
        },
    )


def record_outcome(
    audio_root: Path,
    *,
    episode: str,
    part: str,
    attempt_id: str,
    outcome: str,
    detail: str = "",
    ids: dict | None = None,
    seconds: float | None = None,
) -> None:
    _append(
        audio_root,
        {
            "type": "outcome",
            "at": now().isoformat(timespec="seconds"),
            "attempt_id": attempt_id,
            "episode": episode,
            "part": part,
            "outcome": outcome,
            "detail": detail[:200],
            "provider_ids": ids or {},
            "attempt_seconds": seconds,
        },
    )


def _parse_time(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _receipt_detail(state: dict) -> str:
    if type(state.get("http_status")) is int:
        return f"HTTP {state['http_status']}"
    kind = state.get("failure_kind")
    if isinstance(kind, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", kind):
        return kind
    return "no saved outcome"


def _chunk_estimate(plan_path: Path, index: int) -> float | None:
    try:
        plan = read_object(plan_path)
        texts = [len(r["input"]["text"]) for r in plan["requests"]]
        return round(plan["estimated_output_cost_usd"] * texts[index - 1] / sum(texts), 6)
    except (OSError, ValueError, KeyError, TypeError, IndexError, ZeroDivisionError):
        return None


def _receipts(audio_root: Path, episode: str) -> list[tuple[Path, dict, str]]:
    """Uncertain receipts already on disk: (path, state, part)."""
    directory = audio_root / episode
    if not directory.is_dir():
        return []
    found = []
    patterns = (
        ("*/chunk-*.json", r"chunk-(\d{3})\.json"),
        ("*/recovery-*.json", r"recovery-(\d{3})-[0-9a-f]{64}\.json"),
    )
    for pattern, name in patterns:
        for path in sorted(directory.glob(pattern)):
            match = re.fullmatch(name, path.name)
            if match:
                found.append((path, f"narration-{int(match.group(1))}"))
    found.extend((path, "captions") for path in sorted(directory.glob("*/captions/*/state.json")))
    found.extend((path, "captions") for path in sorted(directory.glob("captions/*/state.json")))
    result = []
    for path, part in found:
        try:
            state = read_object(path)
        except (OSError, ValueError):
            continue
        if state.get("status") in {"requesting", "uncertain"}:
            result.append((path, state, part))
    return result


def _receipt_id(path: Path, state: dict) -> str:
    attempt = state.get("attempt_id")
    if isinstance(attempt, str) and re.fullmatch(r"[0-9a-f]{32}", attempt):
        return attempt
    return "receipt-" + digest_file(path)[:32]


def attempts(audio_root: Path, episode: str, *, import_receipts: bool = False) -> list[Attempt]:
    """Every recorded paid attempt for the episode, newest last, with its settled outcome."""
    entries = [e for e in _entries(audio_root) if e.get("episode") == episode]
    starts: dict[str, dict] = {}
    outcomes: dict[str, dict] = {}
    for entry in entries:
        identifier = entry.get("attempt_id")
        if not isinstance(identifier, str):
            continue
        if entry.get("type") in {"start", "imported"}:
            starts.setdefault(identifier, entry)
        elif entry.get("type") == "outcome":
            outcomes[identifier] = entry
        if entry.get("type") == "imported":
            outcomes.setdefault(identifier, {"outcome": UNCERTAIN, "detail": entry.get("detail")})
    for path, state, part in _receipts(audio_root, episode):
        identifier = _receipt_id(path, state)
        if identifier in starts:
            continue
        index = int(part.split("-")[1]) if part.startswith("narration-") else 0
        imported = {
            "type": "imported",
            "at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(
                timespec="seconds"
            ),
            "attempt_id": identifier,
            "episode": episode,
            "part": part,
            "estimate_usd": _chunk_estimate(path.parent / "plan.json", index) if index else None,
            "detail": _receipt_detail(state),
            "receipt": str(path.relative_to(audio_root)),
        }
        if import_receipts:
            _append(audio_root, imported)
        starts[identifier] = imported
        outcomes[identifier] = {"outcome": UNCERTAIN, "detail": imported["detail"]}
    result = []
    for identifier, start in starts.items():
        at = _parse_time(start.get("at"))
        if at is None:
            continue
        settled = outcomes.get(identifier, {})
        outcome = settled.get("outcome")
        if outcome not in SETTLED and outcome != UNCERTAIN:
            # Started but never settled: a crash or a request still in flight elsewhere.
            outcome = UNCERTAIN
        estimate = start.get("estimate_usd")
        result.append(
            Attempt(
                identifier,
                at,
                episode,
                str(start.get("part", "")),
                outcome,
                str(settled.get("detail") or ("no outcome recorded" if not settled else "")),
                estimate if isinstance(estimate, int | float) and estimate >= 0 else None,
                settled.get("provider_ids") or {},
            )
        )
    return sorted(result, key=lambda a: a.at)


def tally(
    audio_root: Path,
    episode: str,
    part: str,
    *,
    limits: Limits | None = None,
    import_receipts: bool = False,
) -> Tally:
    limits = load_limits(audio_root) if limits is None else limits
    every = attempts(audio_root, episode, import_receipts=import_receipts)
    uncertain = [a for a in every if a.outcome == UNCERTAIN]
    since = now() - timedelta(hours=limits.window_hours)
    window = [a for a in uncertain if a.at >= since]
    return Tally(
        episode,
        part,
        limits,
        part_window=sum(a.part == part for a in window),
        part_total=sum(a.part == part for a in uncertain),
        episode_window=len(window),
        episode_total=len(uncertain),
        estimate_usd=round(sum(a.estimate_usd or 0 for a in window), 4),
        unestimated=sum(a.estimate_usd is None for a in window),
        attempts=tuple(every),
    )


def check(
    audio_root: Path,
    episode: str,
    part: str,
    *,
    override: str | None = None,
    acknowledged: int | None = None,
    command: str = "",
) -> Tally:
    """Refuse a paid attempt past the limit unless a reasoned override was supplied.

    ``acknowledged`` is the episode's uncertain count that a Studio user saw when
    confirming an override; a later uncertain attempt invalidates that confirmation.
    """
    current = tally(audio_root, episode, part, import_receipts=True)
    if not current.blocked:
        return current
    if override is not None:
        reason = validate_reason(override)
        if acknowledged is not None and current.episode_window > acknowledged:
            raise SpendLimitReached(
                "The override was confirmed for fewer uncertain attempts than are now recorded. "
                "Inspect the attempt ledger again; nothing was sent.",
                current,
            )
        _append(
            audio_root,
            {
                "type": "override",
                "at": now().isoformat(timespec="seconds"),
                "episode": episode,
                "part": part,
                "reason": reason,
                "part_window": current.part_window,
                "episode_window": current.episode_window,
                "estimate_usd": current.estimate_usd,
                "limits": [current.limits.part, current.limits.episode],
                "command": command[:40],
            },
        )
        return current
    which = (
        f"{part_label(part)} has reached {current.part_window} uncertain attempts"
        if current.over_part
        else f"episode {episode} has reached {current.episode_window} uncertain attempts"
    )
    raise SpendLimitReached(
        f"Spend guard: no request was sent. {which} in the last "
        f"{current.limits.window_hours:g} h, each possibly billed. {current.sentence()} "
        "Stop and wait: check the Google Cloud status page and the billing report before "
        "spending more. The limit lifts as attempts age out of the window. To spend anyway, "
        'run once by hand with --allow-spend-over-limit "your reason" (Studio: tick the '
        "override and give a reason). The override is logged.",
        current,
    )


def overrides(audio_root: Path, episode: str) -> list[dict]:
    return [
        e
        for e in _entries(audio_root)
        if e.get("type") == "override" and e.get("episode") == episode
    ]


def summary_line(audio_root: Path, episode: str) -> str:
    """One short line about the episode's uncertain paid attempts for a failure view."""
    try:
        seen = tally(audio_root, episode, "captions")
    except (OSError, ValueError) as exc:
        return f"Attempt log unreadable; stop before any paid retry. {exc}"
    if not seen.episode_total:
        return ""
    money = seen.spend_text().removesuffix("; billing unknown")
    return (
        f"Billing unknown · {seen.episode_window} uncertain paid attempt(s) in "
        f"{seen.limits.window_hours:g} h, limit {seen.limits.episode} "
        f"({seen.episode_total} across runs) · {money.replace(' in speech output', '')}"
        + (" · spend guard reached" if seen.over_episode else "")
        + " · stop and wait."
    )
