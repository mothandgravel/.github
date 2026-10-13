#!/usr/bin/env python3
"""Compatibility launcher; implementation lives in field_notes_audio/."""

import os
import sys
from pathlib import Path

if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    os.execv(sys.executable, [sys.executable, "-m", "field_notes_audio", *sys.argv[1:]])
