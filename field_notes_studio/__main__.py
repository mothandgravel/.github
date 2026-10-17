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
    make = commands.add_parser(
        "make-episode",
        help="Show the Make episode summary, or start it with --confirm DIGEST",
        description="Without --confirm nothing is sent or queued. There is no override "
        "or resend option: those keep their own consent in Studio's expert path.",
    )
    make.add_argument("id", help="A note number (014) or an episode id")
    action = make.add_mutually_exclusive_group()
    action.add_argument(
        "--confirm", metavar="DIGEST", help="Start exactly the summary with this digest"
    )
    action.add_argument("--status", action="store_true", help="Show the run timeline")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if not (root / "audio/production/settings.json").is_file():
            raise ValueError("--root must identify a Moth & Gravel production checkout")
        if args.command == "jobs":
            from field_notes_studio.repository import Repository

            repository = Repository(root / "artifacts/studio/studio.sqlite3")
            print(json.dumps([asdict(job) for job in repository.jobs()], indent=2))
        elif args.command == "make-episode":
            from field_notes_studio.make_cli import run as make_episode
            from field_notes_studio.service import Studio

            return make_episode(Studio(root), args.id, confirm=args.confirm, status=args.status)
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
