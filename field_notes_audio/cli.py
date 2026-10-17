"""Parse commands and coordinate the audio workflow."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave

from field_notes_audio import audio, captions, release, spend_guard, workflow
from field_notes_audio.production import packages, promotion
from field_notes_audio.production import runner as production


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "check", help="Validate all source fingerprints, scripts and request boundaries offline"
    )
    captions.add_arguments(commands)
    workflow.add_arguments(commands)
    release.add_arguments(commands)
    production.add_arguments(commands)
    packages.add_arguments(commands)
    for name in ("plan", "generate"):
        sub = commands.add_parser(name)
        sub.add_argument("episode")
        sub.add_argument("--model", choices=audio.MODELS)
        sub.add_argument("--endpoint", choices=audio.ENDPOINTS)
        if name == "plan":
            sub.add_argument(
                "--json",
                action="store_true",
                help="Print the bounded requests; contains no credentials",
            )
        else:
            sub.add_argument("--project")
            sub.add_argument("--auth", choices=("gcloud", "adc"))
            sub.add_argument("--retry-uncertain", action="store_true")
            spend_guard.add_override_argument(sub)
            audio.add_timeout_argument(sub)
    args = parser.parse_args(argv)
    try:
        if args.command == "make-all":
            release.refuse_override(args)
        if args.command in {"setup", "make", "generate", "captions", "make-all"}:
            if args.command == "make-all" and args.dry_run and not args.project:
                args.project = "offline-plan-project"
            workflow.resolve_defaults(args, discover_project=not getattr(args, "dry_run", False))
        if args.command == "check":
            episodes = json.loads((audio.ROOT / "audio/episodes.json").read_text(encoding="utf-8"))
            for episode in episodes:
                plan = audio.make_plan(episode["id"], "gemini-2.5-pro-tts", "global")
                for data in plan["requests"]:
                    assert len(data["input"]["text"].encode("utf-8")) <= 3000
                    assert sum(len(v.encode("utf-8")) for v in data["input"].values()) <= 4000
                audio.summarize(plan)
            print(f"Checked {len(episodes)} pilot scripts; no Google requests made.")
        elif args.command == "plan":
            saved = workflow.read_settings()
            args.model = args.model or saved.get("model", "gemini-2.5-pro-tts")
            args.endpoint = args.endpoint or saved.get("endpoint", "global")
            if args.model not in audio.MODELS or args.endpoint not in audio.ENDPOINTS:
                raise ValueError("Invalid model or endpoint in saved settings")
            plan = audio.make_plan(args.episode, args.model, args.endpoint)
            if args.json:
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                audio.summarize(plan)
                print("Dry run only; no Google requests made.")
        elif args.command == "captions":
            workflow.prepare_captions(args)
            # Check request support before preparing resources.
            if args.model == "chirp_3" and args.location == "global":
                raise ValueError("Chirp 3 captions use --location us or eu")
            if not args.dry_run:
                workflow.ensure_setup(args)
            workflow.finish(captions.run(args), args.no_open)
        elif args.command == "setup":
            workflow.setup(args)
        elif args.command == "make":
            if not 0 <= args.wait <= 3600:
                raise ValueError("--wait must be between 0 and 3600 seconds")
            workflow.make(args)
        elif args.command == "make-all":
            if not 0 <= args.wait <= 3600:
                raise ValueError("--wait must be between 0 and 3600 seconds")
            release.make_all(args)
        elif args.command == "publish":
            release.publish()
        elif args.command == "sync":
            added = release.sync_catalog()
            if not added:
                print("Every published note already has an audio script. No Google requests made.")
        elif args.command == "verify-live":
            release.verify_live()
        elif args.command == "produce":
            production.produce(args)
        elif args.command == "release":
            if args.audio_only or args.preview_seconds is not None:
                raise ValueError(
                    "release needs full videos; use produce for audio-only or preview work"
                )
            packages.preflight_release(args)
            production.produce(args)
            packages.export(args)
        elif args.command == "export":
            packages.export(args)
        elif args.command == "review":
            packages.review(args)
        elif args.command == "promote":
            promotion.promote(args)
        else:
            audio.generate(args)
        return 0
    except KeyboardInterrupt:
        print(
            "\nStopped. Repeat produce to reuse completed local editions."
            if args.command in {"produce", "release", "export", "review", "promote"}
            else "\nStopped. Repeat the same command to resume saved audio and transcription jobs.",
            file=sys.stderr,
        )
        return 130
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError, wave.Error) as exc:
        print(f"Audio setup: {exc}", file=sys.stderr)
        return 1
