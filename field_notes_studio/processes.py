"""Process lifecycle adapter for the local worker; no Tk or production imports."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path


def upload_path(path: Path) -> str:
    """Give Windows file pickers a usable WSL path without copying the media."""
    if os.environ.get("WSL_DISTRO_NAME") or "microsoft" in platform.release().lower():
        try:
            result = subprocess.run(
                ["wslpath", "-w", str(path)], capture_output=True, text=True, check=True, timeout=5
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError(
                "Could not create a Windows upload path. Check WSL interop or open the upload folder."
            ) from exc
        value = result.stdout.strip()
        if not value:
            raise ValueError("WSL returned an empty upload path. Open the upload folder instead.")
        return value
    return str(path)


def open_publisher() -> None:
    if not webbrowser.open("https://studio.youtube.com"):
        raise ValueError("Open https://studio.youtube.com in your browser to upload these files")


def open_url(url: str) -> None:
    if not url.startswith("https://") or not webbrowser.open(url):
        raise ValueError(f"Open {url} in your browser")


def notify(title: str, body: str) -> bool:
    """A desktop notification where notify-send exists; silently nothing elsewhere."""
    command = shutil.which("notify-send")
    if not command:
        return False
    try:
        subprocess.Popen(
            [command, "--app-name=Moth & Gravel studio", title, body[:200]],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return True


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
        raise ValueError("Produce this version first")
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(
            ["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
