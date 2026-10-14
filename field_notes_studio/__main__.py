"""Launch the local studio, inspect its jobs or run its detached worker."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("gui", help="Open the Tkinter production studio (default)")
    worker = commands.add_parser("worker", help="Run the independent production worker")
    worker.add_argument("--once", action="store_true", help="Drain pending jobs and exit")
    commands.add_parser("jobs", help="Print saved job snapshots as JSON")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if not (root / "audio/production/settings.json").is_file():
            raise ValueError("--root must identify a Moth & Gravel production checkout")
        if args.command == "jobs":
            from field_notes_studio.repository import Repository

            repository = Repository(root / "artifacts/studio/studio.sqlite3")
            print(json.dumps([asdict(job) for job in repository.jobs()], indent=2))
        elif args.command == "worker":
            from field_notes_studio.worker import work

            work(root, once=args.once)
        else:
            if sys.platform != "linux":
                raise ValueError("Run the first studio in Ubuntu/WSL beside the pipeline checkout")
            from field_notes_studio.app import run

            run(root)
        return 0
    except (ValueError, OSError, ImportError) as exc:
        print(f"Studio: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
