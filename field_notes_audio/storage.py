"""Atomic local state and bounded-memory file hashing."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path


def digest_file(path: Path) -> str:
    """Hash media without loading the complete recording into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    """Replace JSON atomically; failed writes preserve the previous state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_object(path: Path) -> dict:
    """Read saved state with an explicit object boundary and no duplicate keys."""

    def unique_fields(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON field in {path.name}: {key}")
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_fields)
    if not isinstance(value, dict):
        raise ValueError(f"Saved state must be a JSON object: {path.name}")
    return value
