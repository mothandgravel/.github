"""Run the Remotion renderer and explain its failures in plain words.

Kept out of video.py on purpose: video.py is digested into every video's cache identity,
so rewording a message here must not re-render finished videos.
"""

from __future__ import annotations

import codecs
import io
import os
import re
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path

# Studio splits job errors on this exact text (field_notes_studio.readiness_models).
DETAILS_MARK = "\n\nDetails:\n"
TAIL_CHARS = 1500
STDERR_CHUNK_BYTES = 4096
STDERR_TAIL_CHUNKS = 200
SAVED = "Your audio and captions are saved; choose Make it again to retry the video only."
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# Remotion's own text: "Timeout (30000ms) exceeded rendering the component at frame N".
_FRAME_TIMEOUT = re.compile(r"Timeout \((\d+)ms\) exceeded rendering", re.IGNORECASE)
_TOOL_MISSING = re.compile(
    r"enoent[^\n]*(\bnode\b|\bnpx\b|\bnpm\b|ffmpeg|ffprobe|node_modules)"
    r"|(\bnode\b|\bnpx\b|ffmpeg|ffprobe)[^\n]*(not found|enoent)"
    r"|cannot find module|command not found",
    re.IGNORECASE,
)


class RenderFailed(ValueError):
    """The renderer stopped. The sentence is for people; the stderr tail follows DETAILS_MARK."""


def explain_render_failure(returncode: int | None, stderr: str) -> str:
    text = stderr.lower()
    timeout = _FRAME_TIMEOUT.search(stderr)
    if returncode is None:
        why = "it ran for over an hour, usually because the computer is busy"
    elif timeout:
        seconds = int(timeout.group(1)) / 1000
        spoken = f"{seconds / 60:g} minutes" if seconds >= 120 else f"{seconds:g} seconds"
        why = f"a frame took longer than {spoken}, usually because the computer is busy"
    elif (
        "out of memory" in text
        or "enomem" in text
        or ("heap" in text and "limit" in text)
        or returncode in {-9, 137}
    ):
        why = "the computer ran out of memory; close other programs first"
    elif _TOOL_MISSING.search(stderr):
        why = "a video tool is missing or damaged; run npm ci --prefix video and check Setup"
    else:
        return f"The video renderer stopped unexpectedly. {SAVED}"
    return f"The video renderer stopped: {why}. {SAVED}"


def renderer_concurrency(configured: int) -> int:
    """Never ask for more frame workers than this process's cores minus the 1-minute load.

    The load average lags (a long `produce all` sees the previous episode's load) and on
    WSL2 it counts only the Linux VM, not the Windows side. It is a cap, not a guarantee.
    """
    try:
        cores = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        cores = os.cpu_count() or 1
    try:
        idle = cores - os.getloadavg()[0]
    except (OSError, AttributeError):
        return configured
    return max(1, min(configured, int(idle)))


def _tail(text: str) -> str:
    return _ANSI.sub("", text)[-TAIL_CHARS:].strip()


def _failure(returncode: int | None, stderr: str, empty: str) -> RenderFailed:
    return RenderFailed(
        explain_render_failure(returncode, stderr) + DETAILS_MARK + (_tail(stderr) or empty)
    )


def run_renderer(command: list[str], cwd: Path, timeout: float = 3600) -> None:
    chunks: deque[str] = deque(maxlen=STDERR_TAIL_CHUNKS)

    try:
        process = subprocess.Popen(command, cwd=cwd, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise RenderFailed(
            f"The video renderer stopped: Node is missing; install Node 22 or newer and check "
            f"Setup. {SAVED}{DETAILS_MARK}{type(exc).__name__}: {exc}"
        ) from None

    def drain() -> None:
        decoder = io.IncrementalNewlineDecoder(
            codecs.getincrementaldecoder("utf-8")(errors="replace"), translate=True
        )
        with process.stderr:
            while chunk := process.stderr.read1(STDERR_CHUNK_BYTES):
                text = decoder.decode(chunk)
                chunks.append(text)
                print(text, end="", file=sys.stderr, flush=True)
            # An incomplete final character is replaced, as text-mode stderr was.
            text = decoder.decode(b"", final=True)
            if text:
                chunks.append(text)
                print(text, end="", file=sys.stderr, flush=True)

    reader = threading.Thread(target=drain, daemon=True, name="renderer-stderr")
    reader.start()
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        reader.join(timeout=5)
        raise _failure(None, "".join(chunks), "The renderer ran for over an hour.") from None
    reader.join(timeout=5)
    if returncode:
        raise _failure(
            returncode,
            "".join(chunks),
            f"Renderer exited with status {returncode} and printed nothing.",
        )
