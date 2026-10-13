#!/usr/bin/env python3
"""Compatibility adapter for the editorial build and old build command."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(check: bool = False, root: Path = ROOT) -> None:
    arguments = [sys.executable, "-m", "field_notes_audio.site"]
    if check:
        arguments.append("--check")
    subprocess.run(arguments, cwd=root, check=True)


if __name__ == "__main__":
    subprocess.run(
        [sys.executable, "-m", "field_notes_audio.site", *sys.argv[1:]], cwd=ROOT, check=True
    )
