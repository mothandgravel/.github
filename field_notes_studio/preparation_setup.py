"""Local setup validation and deliberate import; never authenticate or contact Cloud."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from field_notes_audio import audio, workflow
from field_notes_audio.production.sources import private_path

LIMIT = 32768


@dataclass(frozen=True)
class SetupPreview:
    path: str
    identity: str
    summary: str


def validate_configuration(saved: dict) -> dict:
    if not isinstance(saved, dict):
        raise ValueError("Setup must contain a JSON object")
    config = {
        key: saved.get(key, fallback)
        for key, fallback in (
            ("project", ""),
            ("bucket", ""),
            ("model", "gemini-2.5-pro-tts"),
            ("endpoint", "global"),
            ("location", "us"),
            ("auth", "gcloud"),
            ("caption_model", "chirp_3"),
        )
    }
    if (
        any(not isinstance(value, str) for value in config.values())
        or not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", config["project"])
        or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,61}[a-z0-9]", config["bucket"])
        or config["model"] not in audio.MODELS
        or config["endpoint"] not in audio.ENDPOINTS
        or config["location"] not in {"us", "eu"}
        or config["auth"] not in {"gcloud", "adc"}
        or config["caption_model"] not in {"chirp_3", "long"}
        or saved.get("prepared") != workflow.resource_key(argparse.Namespace(**config))
    ):
        raise ValueError(
            "Saved Cloud setup is incomplete or changed. Use a valid existing setup; do not invent a prepared marker."
        )
    return config


def _read(path: Path) -> tuple[dict, str]:
    # O_NONBLOCK prevents a selected FIFO from hanging the desktop before fstat.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
            raise ValueError("Choose a regular settings.json file smaller than 32 KiB")
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("Setup file grew while reading; choose it again")
    try:
        config = validate_configuration(json.loads(raw))
    except (ValueError, UnicodeError, TypeError):
        raise ValueError(
            "Invalid or incomplete saved Cloud setup. No settings were imported."
        ) from None
    return config, hashlib.sha256(raw).hexdigest()


def load_configuration(root: Path) -> dict:
    path = private_path(root, "artifacts/audio/settings.json")
    if not path.is_file():
        raise ValueError(
            "Cloud setup is missing from this checkout. Expected: "
            + str(path)
            + "\nUse Import existing setup… to choose settings.json from the checkout that produced your earlier episodes. "
            "Nothing will be overwritten and no Cloud setup will run automatically."
        )
    return _read(path)[0]


def preview_setup(path: str) -> SetupPreview:
    source = Path(path).absolute()
    config, identity = _read(source)
    summary = (
        f"From: {source}\nProject: {config['project']}\nPrivate bucket: {config['bucket']}\n"
        f"Narration: {config['model']} / {config['endpoint']}\nCaptions: {config['caption_model']} / {config['location']}\n"
        "Import only validated setup fields. No credentials, caches or receipts are copied. "
        "No authentication, resource changes or service requests. Existing destination settings are never overwritten."
    )
    return SetupPreview(str(source), identity, summary)


def import_setup(root: Path, preview: SetupPreview) -> None:
    config, identity = _read(Path(preview.path))
    if identity != preview.identity:
        raise ValueError("Selected setup changed after preview. Choose and review it again.")
    target = private_path(root, "artifacts/audio/settings.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Recheck containment after directory creation; no follows of existing symlinks.
    target = private_path(root, "artifacts/audio/settings.json")
    safe = {"version": 1, **config, "prepared": workflow.resource_key(argparse.Namespace(**config))}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(safe, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Atomic no-clobber publication, including two concurrent import windows.
        os.link(temporary, target)
    except FileExistsError:
        raise ValueError(
            "This checkout already has settings. Nothing was overwritten; inspect its current setup."
        ) from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
