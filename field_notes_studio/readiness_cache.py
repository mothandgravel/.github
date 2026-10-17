"""Verified readiness per episode, cached until a file or the recipe changes.

The shelf's Next column shows the result of the same readiness check as the
episode card (``readiness.inspect``), which verifies media hashes. That check is
too slow to repeat on every refresh, so its result is kept in the studio journal
with a *key*: a digest of every input the check reads, by file identity (path,
size, modification time and inode), plus the recipe, the source entry, the
episode's latest job and its release record. Any change to those inputs changes
the key, and the episode is checked again before its Next value is shown as
verified. A file rewritten with an identical size, time and inode is the known
limit of a stat-based key; Make, Approve and package jobs always re-verify.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from field_notes_audio.production import sources
from field_notes_studio.readiness_models import Readiness

# Readiness action → the shelf's Next label.
NEXT = {
    "produce": "Produce",
    "review": "Review",
    "export": "Release",
    "package": "Release",
    "job": "Working",
    "check": "Check",
    "health": "Repair",
    "repair": "Repair",
}


def _files(path: Path) -> list[list]:
    if not path.exists():
        return [[str(path), "missing"]]
    if path.is_file():
        found = [path]
    else:
        found = sorted(p for p in path.rglob("*") if p.is_file() and p.name != ".lock")
    result = []
    for item in found:
        try:
            info = item.stat()
        except OSError:
            result.append([str(item), "unreadable"])
            continue
        result.append([str(item), info.st_size, info.st_mtime_ns, info.st_ino])
    return result


def key(studio, episode: str, settings: dict) -> str:
    """Everything ``readiness.inspect`` reads, by identity rather than by content."""
    root, pipeline, repository = studio.root, studio.pipeline, studio.repository
    try:
        entry = pipeline.source(episode)
    except (OSError, ValueError) as exc:
        entry = {"unavailable": str(exc)}
    inputs: list = [entry, settings]
    for name in ("audio", "transcript"):
        if isinstance(entry.get(name), str):
            try:
                inputs.append(_files(sources.media_path(root, entry[name])))
            except (OSError, ValueError):
                inputs.append([name, "unavailable"])
    paths = [
        root / "artifacts/production" / episode,
        root / "artifacts/uploads" / episode,
        root / "audio/production/publishing.json",
        root / "audio/production/settings.json",
        root / "audio/production/episodes" / f"{episode}.json",
        root / "video/src",
        *sorted((root / "video").glob("*.mjs")),
        *sorted((root / "video").glob("*.json")),
    ]
    music = settings.get("music_file")
    if isinstance(music, str) and music:
        paths.append(Path(music))
    inputs.extend(_files(path) for path in paths)
    job = next((j for j in repository.jobs() if j.episode == episode), None)
    inputs.append([job.identifier, job.status] if job else None)
    inputs.append(repository.publications().get(episode))
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode()).hexdigest()


def encode(value: Readiness) -> dict:
    data = asdict(value)
    data["stages"] = list(value.stages)
    return data


def decode(data: dict) -> Readiness:
    return Readiness(**{**data, "stages": tuple(data.get("stages", ()))})


def cached(studio, episode: str, settings: dict) -> Readiness | None:
    """The saved verified result, only while its inputs are unchanged."""
    saved = studio.repository.cached_readiness(episode)
    if saved is None or saved[0] != key(studio, episode, settings):
        return None
    return decode(saved[1])


def verify(studio, episode: str, settings: dict) -> Readiness:
    """Run the full check and cache it, unless an input changed while checking."""
    before = key(studio, episode, settings)
    value = studio.readiness(episode, settings)
    if value.action != "job" and key(studio, episode, settings) == before:
        studio.repository.cache_readiness(episode, before, encode(value))
    return value


def verified_next(studio, episodes: list[str], *, check: bool = True) -> dict[str, tuple]:
    """Next label per episode: (label, verified, readiness or None).

    With ``check`` the stale or missing entries are verified now (slow; run off the
    UI thread). Without it, stale entries are returned unverified as ("Check", False).
    """
    result = {}
    for episode in episodes:
        try:
            settings = studio.settings(episode)
        except (OSError, ValueError, KeyError, TypeError):
            result[episode] = ("Repair", True, None)
            continue
        value = cached(studio, episode, settings)
        if value is None and check:
            try:
                value = verify(studio, episode, settings)
            except (OSError, ValueError, KeyError, TypeError):
                value = None
        if value is None:
            result[episode] = ("Check", False, None)
        else:
            label = NEXT.get(value.action, "Check")
            if studio.repository.publications().get(episode) and value.action == "package":
                label = "Done"
            result[episode] = (label, True, value)
    return result
