#!/usr/bin/env python3
"""Measure cold finishing and verified cache reuse without any Cloud requests."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", default="all")
    parser.add_argument("--jobs", type=int, nargs="+", choices=range(1, 5), default=[1, 2])
    parser.add_argument("--report", type=Path, default=Path("artifacts/benchmarks/production.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = args.report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "ffmpeg": subprocess.run(
            ["ffmpeg", "-version"], check=True, capture_output=True, text=True, timeout=30
        ).stdout.splitlines()[0],
        "episode": args.episode,
        "measurements": [],
    }
    # Each worker count receives an empty output directory. Finished review
    # editions elsewhere are untouched; benchmark media are removed afterward.
    for workers in args.jobs:
        with tempfile.TemporaryDirectory(prefix="podcast-benchmark-") as temporary:
            output = Path(temporary)
            command = [
                sys.executable,
                "-m",
                "field_notes_audio",
                "produce",
                args.episode,
                "--audio-only",
                "--audio-jobs",
                str(workers),
                "--output-dir",
                str(output),
            ]
            started = time.perf_counter()
            subprocess.run(command, cwd=root, check=True, timeout=3600)
            cold = time.perf_counter() - started
            media = list(output.rglob("episode.mp3"))
            before = {str(path): path.stat().st_mtime_ns for path in media}
            started = time.perf_counter()
            subprocess.run(command, cwd=root, check=True, timeout=3600)
            warm = time.perf_counter() - started
            if not media or before != {str(path): path.stat().st_mtime_ns for path in media}:
                raise RuntimeError("Benchmark cache reuse did not preserve completed recordings")
            state["measurements"].append(
                {
                    "audio_jobs": workers,
                    "recordings": len(media),
                    "cold_seconds": round(cold, 3),
                    "warm_seconds": round(warm, 3),
                }
            )
            report.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"Benchmark report: {report}")


if __name__ == "__main__":
    main()
