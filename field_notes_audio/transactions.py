"""Journaled local file updates with bounded copying and restart-safe rollback."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from field_notes_audio.storage import digest_file, read_object, write_json


class FileTransaction:
    """Callers hold their collection lock; recovery never overwrites unknown edits."""

    def __init__(self, root: Path, directory: Path, allowed: Callable[[str], bool]):
        self.root = root.resolve()
        self.directory = directory
        self.allowed = allowed
        self.entries: list[dict] = []

    def target(self, relative: str) -> Path:
        if not isinstance(relative, str) or not self.allowed(relative):
            raise ValueError("Transaction journal contains an unexpected output path")
        path = self.root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("Transaction output must not escape its directory")
        if path.exists() and not path.is_file():
            raise ValueError("Transaction output must be a regular file")
        return path

    def recover(self) -> None:
        if not self.directory.exists():
            return
        if self.directory.is_symlink():
            raise ValueError("Transaction directory must not be a symbolic link")
        if not self.directory.resolve().is_relative_to(self.root) or any(
            (self.directory / name).is_symlink() for name in ("journal.json", "backups", "stage")
        ):
            raise ValueError("Transaction state must stay within its owner directory")
        journal = self.directory / "journal.json"
        if not journal.exists():
            if any(
                p.name not in {"backups", "stage"} and not p.name.startswith(".journal.json.")
                for p in self.directory.iterdir()
            ):
                raise ValueError("Unrecognized files in the transaction directory")
            shutil.rmtree(self.directory)
            return
        saved = read_object(journal)
        if (
            type(saved.get("schema_version")) is not int
            or saved["schema_version"] != 1
            or not isinstance(saved.get("phase"), str)
            or saved.get("phase") not in {"active", "committed"}
        ):
            raise ValueError("Invalid transaction journal")
        entries = saved.get("entries")
        if not isinstance(entries, list) or len(entries) > 10000:
            raise ValueError("Invalid transaction file list")
        seen, targets = set(), []
        for number, entry in enumerate(entries):
            if not isinstance(entry, dict) or set(entry) != {"path", "before", "after"}:
                raise ValueError("Invalid transaction entry")
            relative = entry["path"]
            target = self.target(relative)
            if relative in seen:
                raise ValueError("Duplicate transaction output")
            seen.add(relative)
            hashes = [entry["before"], *entry["after"]] if isinstance(entry["after"], list) else []
            if not hashes or any(
                value is not None
                and (not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value))
                for value in hashes
            ):
                raise ValueError("Invalid transaction hash")
            if (
                not entry["after"]
                or len(entry["after"]) > 128
                or any(value is None for value in entry["after"])
            ):
                raise ValueError("Invalid transaction write history")
            backup = self.directory / "backups" / str(number)
            if saved["phase"] == "active":
                current = digest_file(target) if target.exists() else None
                if current not in hashes:
                    raise ValueError(
                        f"Interrupted release has a later edit; preserve/resolve {relative} before retrying"
                    )
                if entry["before"] is not None and (
                    not backup.is_file()
                    or backup.is_symlink()
                    or digest_file(backup) != entry["before"]
                ):
                    raise ValueError("Interrupted release backup is missing or changed")
            targets.append((target, backup, entry))
        # Validate every preimage before restoring any file. A later user edit stays intact.
        if saved["phase"] == "active":
            for target, backup, entry in reversed(targets):
                if entry["before"] is None:
                    target.unlink(missing_ok=True)
                else:
                    self._install(target, backup)
        shutil.rmtree(self.directory)

    def __enter__(self) -> FileTransaction:
        self.recover()
        (self.directory / "backups").mkdir(parents=True)
        (self.directory / "stage").mkdir()
        self._save("active")
        return self

    def _save(self, phase: str) -> None:
        write_json(
            self.directory / "journal.json",
            {"schema_version": 1, "phase": phase, "entries": self.entries},
        )
        with (self.directory / "journal.json").open("rb") as handle:
            os.fsync(handle.fileno())

    def _install(self, target: Path, source: Path) -> None:
        # Temporary data stays in ignored transaction storage, never in docs/.
        with tempfile.NamedTemporaryFile(dir=self.directory / "stage", delete=False) as handle:
            stage = Path(handle.name)
            with source.open("rb") as material:
                shutil.copyfileobj(material, handle, 1024 * 1024)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            stage.replace(target)
        finally:
            stage.unlink(missing_ok=True)

    def copy(self, target: Path, source: Path, expected: str | None = None) -> None:
        relative = target.relative_to(self.root).as_posix()
        target = self.target(relative)
        expected = expected or digest_file(source)
        current = digest_file(target) if target.exists() else None
        if current == expected:
            return
        entry = next((item for item in self.entries if item["path"] == relative), None)
        if entry is None:
            entry = {"path": relative, "before": current, "after": []}
            if current is not None:
                backup = self.directory / "backups" / str(len(self.entries))
                shutil.copyfile(target, backup)
                if digest_file(backup) != current:
                    raise ValueError("Output changed while preparing its backup")
                with backup.open("rb") as handle:
                    os.fsync(handle.fileno())
            self.entries.append(entry)
        entry["after"].append(expected)
        self._save("active")
        if digest_file(source) != expected:
            raise ValueError("Release input changed after validation")
        self._install(target, source)

    def write_text(self, target: Path, value: str) -> None:
        self.write_bytes(target, value.encode("utf-8"))

    def write_bytes(self, target: Path, encoded: bytes) -> None:
        with tempfile.NamedTemporaryFile(dir=self.directory / "stage", delete=False) as handle:
            stage = Path(handle.name)
            handle.write(encoded)
        try:
            self.copy(target, stage, hashlib.sha256(encoded).hexdigest())
        finally:
            stage.unlink(missing_ok=True)

    def write_json(self, target: Path, value: object) -> None:
        self.write_text(target, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def __exit__(self, exception_type, exception, traceback) -> None:
        if exception_type is None:
            self._save("committed")
        self.recover()
