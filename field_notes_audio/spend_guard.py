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
window reach the per-part or per-episode limit. Configuration can only make the
limits stricter. Only a deliberate override passes it: a written reason plus the
spend token printed by the refusal, which any newer uncertain attempt invalidates,
and at most one override per part per window. Overrides are logged. Checking the
limit and logging the start happen under one exclusive lock, so concurrent runs
cannot both pass. There is no automatic retry anywhere in this module.

Repairing the log: a torn or unreadable line counts as one uncertain attempt (at
its recorded time when readable, otherwise now), so the guard errs towards
stopping. Copy the file aside for the record, check the Cloud billing report, then
correct or remove only that line. Dates come from this computer's clock; imported
receipts are dated by file modification time.
"""

from __future__ import annotations

import fcntl
import hashlib
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
LOCK_NAME = "attempts.lock"
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

    @property
    def token(self) -> str:
        """Names exactly the uncertain attempts seen; any newer one changes it."""
        since = now() - timedelta(hours=self.limits.window_hours)
        seen = sorted(
            a.attempt_id for a in self.attempts if a.outcome == UNCERTAIN and a.at >= since
        )
        material = json.dumps(
            [self.episode, seen, [self.limits.part, self.limits.episode, self.limits.window_hours]]
        )
        return hashlib.sha256(material.encode()).hexdigest()[:12]

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


def limits_text(limits: Limits) -> str:
    return (
        f"Spend guard: at most {limits.part} uncertain paid attempts per part and "
        f"{limits.episode} per episode in {limits.window_hours:g} h"
        + ("" if limits == Limits() else " (stricter than the defaults)")
        + "."
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
    """Read ``artifacts/audio/spend-guard.json``; environment variables win.

    Settings may only make the guard stricter: fewer attempts, or a window of 24 h
    or longer. Looser values are refused; spending past the limit takes the logged
    override instead.
    """
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
    allowed = {
        "part": (1, DEFAULT_PART_LIMIT),
        "episode": (1, DEFAULT_EPISODE_LIMIT),
        "window_hours": (DEFAULT_WINDOW_HOURS, 24 * 30),
    }
    result = {}
    for name, environment in names.items():
        raw = os.environ.get(environment, values.get(keys[name]))
        if raw is None:
            continue
        try:
            if isinstance(raw, bool):
                raise TypeError
            number = float(raw) if name == "window_hours" else int(raw)
        except (TypeError, ValueError):
            raise ValueError(
                f"Spend guard setting {keys[name]} must be a number; check {CONFIG_NAME} or {environment}"
            ) from None
        low, high = allowed[name]
        if not low <= number <= high:
            raise ValueError(
                f"Spend guard setting {keys[name]}={raw} would loosen or break the guard. "
                f"Settings can only make it stricter ({low}–{high:g}); spending past the "
                f"limit needs --allow-spend-over-limit. Check {CONFIG_NAME} or {environment}."
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
        help="Deliberately pass the uncertain-spend guard once; needs --spend-token; logged",
    )
    parser.add_argument(
        "--spend-token",
        metavar="TOKEN",
        help="The token printed by the spend-guard refusal; a newer uncertain attempt voids it",
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
    with (audio_root / LOG_NAME).open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            # A crash mid-append leaves an unterminated line. Close it so it stays one
            # (counted, damaged) line instead of merging with this entry.
            size = handle.seek(0, os.SEEK_END)
            if size:
                handle.seek(size - 1)
                torn = handle.read(1) != b"\n"
                handle.seek(0, os.SEEK_END)
                if torn:
                    handle.write(b"\n")
            handle.write(line.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


_FIELD = r'"{}"\s*:\s*"([^"\\]{{1,200}})"'


def _damaged(line: str, number: int) -> dict:
    """A torn or malformed line becomes one uncertain attempt, never a silent skip."""

    def field_value(name):
        match = re.search(_FIELD.format(name), line)
        return match.group(1) if match else None

    return {
        "type": "damaged",
        "line": number,
        "attempt_id": field_value("attempt_id") or f"damaged-line-{number}",
        "episode": field_value("episode"),
        "part": field_value("part") or "unknown",
        "at": field_value("at"),
    }


def _entries(audio_root: Path) -> list[dict]:
    path = audio_root / LOG_NAME
    if not path.exists():
        return []
    entries = []
    with path.open(encoding="utf-8", errors="replace") as handle:
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
            entries.append(_damaged(line, number))
            continue
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("attempt_id", ""), str)
            or (entry.get("type") in {"start", "imported"} and _parse_time(entry.get("at")) is None)
        ):
            entries.append(_damaged(line, number))
            continue
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


def _receipt_id(path: Path, state: dict, audio_root: Path) -> str:
    attempt = state.get("attempt_id")
    if isinstance(attempt, str) and re.fullmatch(r"[0-9a-f]{32}", attempt):
        return attempt
    # Identical legacy receipts in different folders are different attempts.
    where = str(path.relative_to(audio_root)).encode()
    return "receipt-" + hashlib.sha256(where + digest_file(path).encode()).hexdigest()[:32]


def attempts(audio_root: Path, episode: str, *, import_receipts: bool = False) -> list[Attempt]:
    """Every recorded paid attempt for the episode, newest last, with its settled outcome."""
    every_entry = _entries(audio_root)
    entries = [e for e in every_entry if e.get("episode") == episode]
    starts: dict[str, dict] = {}
    outcomes: dict[str, dict] = {}
    known = {e.get("attempt_id") for e in every_entry if e.get("type") in {"start", "imported"}}
    for entry in every_entry:
        if entry.get("type") != "damaged" or entry["attempt_id"] in known:
            continue  # A torn outcome of a logged start leaves that start unsettled anyway.
        if entry["episode"] not in {None, episode}:
            continue
        # Unattributable damage counts against every episode until repaired.
        starts[entry["attempt_id"]] = {
            "at": entry["at"] if _parse_time(entry["at"]) else now().isoformat(),
            "part": entry["part"],
            "estimate_usd": None,
        }
        outcomes[entry["attempt_id"]] = {
            "outcome": UNCERTAIN,
            "detail": f"damaged log line {entry['line']}",
        }
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
        identifier = _receipt_id(path, state, audio_root)
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
        if not settled and start.get("type") == "start":
            settled = _receipt_outcome(audio_root, start, identifier)
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


def _receipt_outcome(audio_root: Path, start: dict, identifier: str) -> dict:
    """A start whose outcome line failed to write: trust its own saved receipt."""
    receipt = start.get("receipt")
    if not isinstance(receipt, str) or not receipt:
        return {}
    path = audio_root / receipt
    try:
        if not path.resolve().is_relative_to(audio_root.resolve()):
            return {}
        state = read_object(path)
    except (OSError, ValueError):
        return {}
    if state.get("attempt_id") == identifier and state.get("status") == "complete":
        return {"outcome": "complete", "detail": "complete receipt; outcome line missing"}
    return {}


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


def refusal(current: Tally, part: str, lead: str = "") -> str:
    which = (
        f"{part_label(part)} has reached {current.part_window} uncertain attempts"
        if current.over_part
        else f"episode {current.episode} has reached {current.episode_window} uncertain attempts"
    )
    return (
        f"Spend guard: no request was sent. {lead}{which} in the last "
        f"{current.limits.window_hours:g} h, each possibly billed. {current.sentence()} "
        "Stop and wait: check the Google Cloud status page and the billing report before "
        "spending more. The limit lifts as attempts age out of the window. To spend anyway, "
        "run one command by hand with "
        f'--allow-spend-over-limit "your reason" --spend-token {current.token} '
        "(Studio: tick the override and give a reason). The override is logged, works "
        "once per part per window, and any newer uncertain attempt invalidates the token."
    )


def _limits_changed(entries: list[dict], limits: Limits) -> bool:
    if limits == Limits():
        return False
    logged = [e for e in entries if e.get("type") == "limits"]
    return not logged or logged[-1].get("limits") != [
        limits.part,
        limits.episode,
        limits.window_hours,
    ]


def reserve(
    audio_root: Path,
    episode: str,
    part: str,
    *,
    attempt_id: str,
    estimate_usd: float | None,
    request_sha256: str = "",
    receipt: str = "",
    override: str | None = None,
    token: str | None = None,
    command: str = "",
) -> Tally:
    """Check the limit and log the attempt's start as one atomic step.

    Raises ``SpendLimitReached`` and logs nothing when the attempt may not be sent.
    On return the start is durably logged (fsync) and the request may be sent.
    """
    audio_root.mkdir(parents=True, exist_ok=True)
    with (audio_root / LOCK_NAME).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            current = tally(audio_root, episode, part, import_receipts=True)
            if _limits_changed(_entries(audio_root), current.limits):
                limits = current.limits
                _append(
                    audio_root,
                    {
                        "type": "limits",
                        "at": now().isoformat(timespec="seconds"),
                        "limits": [limits.part, limits.episode, limits.window_hours],
                        "defaults": [
                            DEFAULT_PART_LIMIT,
                            DEFAULT_EPISODE_LIMIT,
                            DEFAULT_WINDOW_HOURS,
                        ],
                    },
                )
            if current.blocked:
                if override is None:
                    raise SpendLimitReached(refusal(current, part), current)
                reason = validate_reason(override)
                if token != current.token:
                    raise SpendLimitReached(
                        refusal(
                            current,
                            part,
                            "The override names an old or missing spend token. ",
                        ),
                        current,
                    )
                if overridden_recently(audio_root, episode, part, current.limits):
                    raise SpendLimitReached(
                        f"Spend guard: no request was sent. {part_label(part)} of episode "
                        f"{episode} was already overridden once in the last "
                        f"{current.limits.window_hours:g} h; a second override is not "
                        f"accepted. {current.sentence()} Stop and wait for the window to pass.",
                        current,
                    )
                _append(
                    audio_root,
                    {
                        "type": "override",
                        "at": now().isoformat(timespec="seconds"),
                        "attempt_id": attempt_id,
                        "episode": episode,
                        "part": part,
                        "reason": reason,
                        "token": current.token,
                        "part_window": current.part_window,
                        "episode_window": current.episode_window,
                        "estimate_usd": current.estimate_usd,
                        "limits": [current.limits.part, current.limits.episode],
                        "command": command[:40],
                    },
                )
            record_start(
                audio_root,
                episode=episode,
                part=part,
                attempt_id=attempt_id,
                estimate_usd=estimate_usd,
                request_sha256=request_sha256,
                receipt=receipt,
            )
            return current
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def describe(audio_root: Path, episode: str, part: str) -> str:
    """The tally sentence for a failure message; never hides the original failure."""
    try:
        return tally(audio_root, episode, part).sentence()
    except (OSError, ValueError) as exc:
        return f"The attempt log could not be read ({exc}); assume the attempt may be billed."


def overrides(audio_root: Path, episode: str) -> list[dict]:
    return [
        e
        for e in _entries(audio_root)
        if e.get("type") == "override" and e.get("episode") == episode
    ]


def overridden_recently(audio_root: Path, episode: str, part: str, limits: Limits) -> bool:
    """At most one override per part per window, however the token changes."""
    since = now() - timedelta(hours=limits.window_hours)
    return any(
        entry.get("part") == part and (_parse_time(entry.get("at")) or now()) >= since
        for entry in overrides(audio_root, episode)
    )


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
        f"{seen.limits.window_hours:g} h ({seen.episode_total} across runs; limits "
        f"{seen.limits.part}/part, {seen.limits.episode}/episode) · "
        f"{money.replace(' in speech output', '')}"
        + (" · spend guard reached" if seen.over_episode else "")
        + " · stop and wait."
    )
