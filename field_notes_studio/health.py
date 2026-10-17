"""Linux worker identity and bounded local tool diagnostics, independent of Tk."""

from __future__ import annotations

import hashlib
import os
import select
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

from field_notes_studio.processes import launch_worker


def revision() -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for package in ("field_notes_studio", "field_notes_audio"):
        for path in sorted((root / package).rglob("*.py")):
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def lock_owner(directory: Path) -> int | None:
    """Resolve the actual flock owner, not a possibly reused PID in a saved file."""
    path = directory / ".lock"
    if not path.exists():
        return None
    stat = path.stat()
    for line in Path("/proc/locks").read_text().splitlines():
        fields = line.split()
        if len(fields) < 6 or fields[1:4] != ["FLOCK", "ADVISORY", "WRITE"]:
            continue
        major, minor, inode = fields[5].split(":")
        if (int(major, 16), int(minor, 16), int(inode)) == (
            os.major(stat.st_dev),
            os.minor(stat.st_dev),
            stat.st_ino,
        ):
            return int(fields[4])
    return None


def process_id() -> int:
    # /proc may expose the parent PID namespace (containers and some WSL setups).
    return int(Path("/proc/self").readlink().name)


def namespace_pid(owner: int) -> int:
    def ids(path):
        for line in path.read_text().splitlines():
            if line.startswith("NSpid:"):
                return [int(value) for value in line.split()[1:]]
        raise ValueError("Linux process namespace identity is unavailable")

    depth = len(ids(Path("/proc/self/status")))
    values = ids(Path(f"/proc/{owner}/status"))
    if len(values) < depth:
        raise ValueError("Worker belongs to a different process namespace; nothing was stopped")
    return values[depth - 1]


def worker_status(repository) -> dict:
    owner = lock_owner(repository.path.parent)
    record = repository.state("worker")
    if owner is None:
        return {
            "state": "stopped",
            "message": "Background producer stopped. Start it to resume queued jobs.",
        }
    if record.get("pid") != owner or time.time() - record.get("heartbeat", 0) > 15:
        return {
            "state": "unknown",
            "pid": owner,
            "message": "The background producer holds the lock but reports no heartbeat. It may run older code. Restart is allowed only while no job is running.",
        }
    current = revision()
    state = "current" if record.get("revision") == current else "outdated"
    return {
        "state": state,
        "pid": owner,
        "message": f"Background producer {owner} · {state} · {record.get('activity', 'idle')} · heartbeat {int(time.time() - record['heartbeat'])}s ago. Code {record.get('revision', '')[:10]} / checkout {current[:10]}.",
    }


def restart(repository, root: Path) -> str:
    status = worker_status(repository)
    if status["state"] == "stopped":
        launch_worker(root)
        return "Background producer starting; check setup again to confirm its heartbeat."
    if status["state"] in {"current", "outdated"}:
        repository.checkpoint({"worker_control": {"restart": uuid.uuid4().hex}})
        return "Restart requested. The background producer finishes its current job, then starts this checkout's code."
    # Legacy workers do not understand control messages. Fence claims while checking
    # idleness and bind termination to a kernel process handle to prevent PID reuse.
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise ValueError(
            "A safe restart of the old background producer needs Linux pidfd support. Let it stop before starting a new one."
        )
    with repository.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM jobs WHERE status='running'").fetchone():
            raise ValueError(
                "A job is running. Restarting the old background producer waits until it finishes; check setup afterwards."
            )
        owner = status["pid"]
        try:
            descriptor = os.pidfd_open(namespace_pid(owner))
        except OSError as exc:
            raise ValueError(
                "The background producer cannot be identified. Check setup again; nothing was stopped."
            ) from exc
        try:
            args = Path(f"/proc/{owner}/cmdline").read_bytes().split(b"\0")
            expected = [b"-m", b"field_notes_studio", b"--root", os.fsencode(str(root)), b"worker"]
            if (
                args[1:6] != expected
                or Path(f"/proc/{owner}/cwd").resolve() != Path(__file__).resolve().parents[1]
                or lock_owner(repository.path.parent) != owner
            ):
                raise ValueError(
                    "The background producer could not be verified. Nothing was stopped."
                )
            signal.pidfd_send_signal(descriptor, signal.SIGTERM)
            if not select.select([descriptor], [], [], 5)[0]:
                raise ValueError(
                    "The background producer did not stop. No new one was started; check setup again."
                )
        finally:
            os.close(descriptor)
    launch_worker(root)
    return "The idle old background producer stopped safely; a new one is starting. Check setup to confirm."


def tool_status(root: Path) -> str:
    lines = []
    for name in ("ffmpeg", "ffprobe", "node"):
        path = shutil.which(name)
        if path is None:
            lines.append(f"{name}: MISSING")
            continue
        try:
            result = subprocess.run(
                [path, "--version" if name == "node" else "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            lines.append(f"{name}: {result.stdout.splitlines()[0][:160]}")
        except (OSError, subprocess.SubprocessError, IndexError):
            lines.append(f"{name}: version check failed")
    renderer = root / "video/node_modules/@remotion/renderer"
    lines.append(
        "Video dependencies: "
        + ("installed" if renderer.is_dir() else "MISSING · run npm ci in video/")
    )
    lines.append(f"Background producer log: {root / 'artifacts/studio/worker.log'}")
    return "\n".join(lines)
