#!/usr/bin/env python3
"""Run the offline Python quality and audio workflow gate from any directory."""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    commands = [
        [sys.executable, "-m", "ruff", "format", "--check"],
        [sys.executable, "-m", "ruff", "check"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/audio", "-t", "."],
        [sys.executable, "-m", "field_notes_audio", "check"],
        [sys.executable, "-m", "field_notes_audio.site", "--check"],
    ]
    for command in commands:
        subprocess.run(command, cwd=root, check=True)


if __name__ == "__main__":
    main()
