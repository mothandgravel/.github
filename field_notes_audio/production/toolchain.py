"""Immutable encoder/implementation identity shared by a single invocation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from field_notes_audio.storage import digest_file


@dataclass(frozen=True)
class AudioToolchain:
    implementation: tuple[tuple[str, str], ...]
    encoder: str


def inspect_audio_toolchain() -> AudioToolchain:
    directory = Path(__file__).parent
    implementation = tuple(
        (name, digest_file(directory / name))
        for name in (
            "config.py",
            "mix.py",
            "sound.py",
            "timeline.py",
            "editions.py",
            "sources.py",
            "toolchain.py",
        )
    )
    encoder = subprocess.run(
        ["ffmpeg", "-version"], check=True, capture_output=True, text=True, timeout=30
    ).stdout.splitlines()[0]
    return AudioToolchain(implementation, encoder)
