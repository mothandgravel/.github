"""Process lifecycle adapter for the local worker; no Tk or production imports."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def open_publisher() -> None:
    if not webbrowser.open("https://studio.youtube.com"):
        raise ValueError("Open https://studio.youtube.com in your browser to upload this package")


def launch_worker(root: Path) -> subprocess.Popen:
    if sys.platform != "linux":
        raise ValueError("The first studio runs in Linux/WSL beside the production checkout")
    directory = root / "artifacts/studio"
    directory.mkdir(parents=True, exist_ok=True)
    # A duplicate launch exits under the worker's exclusive lock.
    with (directory / "worker.log").open("ab") as log:
        return subprocess.Popen(
            [sys.executable, "-m", "field_notes_studio", "--root", str(root), "worker"],
            cwd=Path(__file__).resolve().parents[1],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )


def open_path(path: Path) -> None:
    if not path.exists():
        raise ValueError("Produce this edition first")
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(
            ["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
