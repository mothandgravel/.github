"""Cache complete editions by their inputs, settings and implementation."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from functools import partial
from pathlib import Path

from field_notes_audio import audio, site
from field_notes_audio.locks import run_lock
from field_notes_audio.production.batch import completed_jobs
from field_notes_audio.production.config import load_settings
from field_notes_audio.production.editions import (
    VIDEO_FILES,
    cache_valid,
    commit_stage,
    fingerprint,
    produce_audio,
)
from field_notes_audio.production.toolchain import inspect_audio_toolchain
from field_notes_audio.storage import digest_file, read_object, write_json


def produce_video(
    entry: dict, root: Path, edition: Path, settings: dict, args: argparse.Namespace
) -> Path:
    from field_notes_audio.production.video import render_video, visual_assets

    renderer = root / "video"
    if not (renderer / "node_modules/@remotion/renderer").is_dir():
        raise ValueError(
            "Video dependencies are missing. Run: npm ci --prefix video (or use --audio-only)"
        )
    assets = visual_assets(root, entry)
    code = {
        str(p.relative_to(renderer)): digest_file(p)
        for p in [
            *renderer.glob("*.mjs"),
            *renderer.glob("*.json"),
            *renderer.joinpath("src").rglob("*"),
        ]
        if p.is_file()
    }
    code["python-video"] = digest_file(Path(__file__).parent / "video.py")
    identity = fingerprint(
        {
            "audio": read_object(edition / "production.json")["fingerprint"],
            "master_sha256": digest_file(edition / "master.wav"),
            "cues_sha256": digest_file(edition / "cues.json"),
            "timeline": read_object(edition / "production.json")["timeline_duration_seconds"],
            "assets": {name: digest_file(path) for name, path in assets.items()},
            "renderer": code,
            "video": settings["video"],
            "preview_seconds": args.preview_seconds,
        }
    )
    parent = edition / "video"
    if parent.is_symlink():
        raise ValueError("Production video directories must not be symbolic links")
    parent.mkdir(exist_ok=True)
    destination = parent / identity[:16]
    if cache_valid(destination, identity, VIDEO_FILES):
        print(f"{entry['id']}: video and thumbnail reused.", flush=True)
        return destination
    print(
        f"{entry['id']}: rendering {'preview' if args.preview_seconds else 'full video'}…",
        flush=True,
    )
    with tempfile.TemporaryDirectory(prefix=".video-", dir=parent) as temporary:
        stage = Path(temporary) / "edition"
        stage.mkdir()
        bundles = edition.parent.parent / ".renderer"
        if bundles.is_symlink():
            raise ValueError("Renderer cache directories must not be symbolic links")
        bundles.mkdir(exist_ok=True)
        renderer_identity = fingerprint(code)[:16]
        with run_lock(bundles, f"bundle-{renderer_identity}"):
            render_video(
                root,
                entry,
                edition,
                stage,
                settings,
                args,
                assets,
                bundles / renderer_identity,
            )
        commit_stage(
            stage,
            destination,
            {
                "fingerprint": identity,
                "review_status": "pending",
                "preview_seconds": args.preview_seconds,
            },
            VIDEO_FILES,
        )
    return destination


def produce(args: argparse.Namespace, root: Path = audio.ROOT) -> None:
    workers = getattr(args, "audio_jobs", 2)
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("--audio-jobs must be an integer between 1 and 4")
    if args.preview_seconds is not None and not 1 <= args.preview_seconds <= 60:
        raise ValueError("--preview-seconds must be between 1 and 60")
    if args.audio_only and args.preview_seconds is not None:
        raise ValueError("--preview-seconds needs video output")
    config = (args.config or root / "audio/production/settings.json").resolve()
    output = (args.output_dir or root / "artifacts/production").resolve()
    if any(
        output.is_relative_to(root / name)
        for name in ("docs", "audio", "field_notes_audio", "video", ".git")
    ):
        raise ValueError("Production output must be separate from source and published assets")
    entries = site.load_entries(root)
    selected = entries if args.episode == "all" else [e for e in entries if e["id"] == args.episode]
    if not selected:
        raise ValueError(
            "No prepared episode found; run make-all first or choose a published episode ID"
        )
    # Validate all recipes before a batch creates outputs.
    recipes = [(entry, load_settings(config, entry["id"])) for entry in selected]
    video_workers = getattr(args, "video_workers", None)
    if video_workers is not None:
        if type(video_workers) is not int or not 1 <= video_workers <= 8:
            raise ValueError("--video-workers must be an integer between 1 and 8")
        for _, settings in recipes:
            settings["video"]["concurrency"] = video_workers
    preflight(root, args)
    toolchain = inspect_audio_toolchain()

    def finish(entry: dict, settings: dict) -> Path:
        directory = output / entry["id"]
        if directory.is_symlink():
            raise ValueError("Production episode directories must not be symbolic links")
        directory.mkdir(parents=True, exist_ok=True)
        with run_lock(directory, "production"):
            edition = produce_audio(entry, root, directory, settings, toolchain)
            update_latest(directory, edition)
            print(f"Finished audio: {edition / 'episode.mp3'}", flush=True)
        return edition

    # Finish every audio edition before starting the browser. Audio workers
    # overlap native FFmpeg work; one bounded renderer owns the video phase.
    jobs = [partial(finish, entry, settings) for entry, settings in recipes]
    editions = list(completed_jobs(jobs, min(workers, len(jobs))))
    for (entry, settings), edition in zip(recipes, editions, strict=True):
        directory = output / entry["id"]
        with run_lock(directory, "production"):
            video = None if args.audio_only else produce_video(entry, root, edition, settings, args)
            if video:
                update_latest(directory, edition, video, args.preview_seconds)
        if video:
            print(
                f"{'Preview' if args.preview_seconds else 'YouTube edition'}: {video / 'episode.mp4'}",
                flush=True,
            )
            print(f"Thumbnail: {video / 'thumbnail.png'}", flush=True)
    print(
        "Local review editions only. The website, podcast feed and original recordings were not changed."
    )


def preflight(root: Path, args: argparse.Namespace) -> None:
    """Fail before processing media when the requested toolchain is unavailable."""
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise ValueError(f"Production requires {tool}; install FFmpeg first")
    if args.audio_only:
        return
    if not shutil.which("node"):
        raise ValueError("Video production requires Node 22+ and npm ci --prefix video")
    version = subprocess.run(
        ["node", "--version"], capture_output=True, text=True, check=True, timeout=30
    ).stdout.strip()
    if int(version.lstrip("v").split(".")[0]) < 22:
        raise ValueError("Video production requires Node 22+ (or use --audio-only)")
    package = read_object(root / "video/package.json")
    for name in ("@remotion/renderer", "@remotion/bundler", "remotion", "react", "react-dom"):
        installed = root / "video/node_modules" / name / "package.json"
        if (
            not installed.is_file()
            or read_object(installed).get("version") != package["dependencies"][name]
        ):
            raise ValueError("Video dependencies are missing or stale. Run: npm ci --prefix video")
    if args.browser_executable and not args.browser_executable.resolve().is_file():
        raise ValueError("--browser-executable does not identify an installed browser")


def update_latest(
    directory: Path, edition: Path, video: Path | None = None, preview: float | None = None
) -> None:
    """Keep full videos distinct from previews; audio-only never erases a full render."""
    audio_path = str(edition.relative_to(directory))
    previous = {}
    if (directory / "latest.json").exists():
        try:
            previous = read_object(directory / "latest.json")
        except ValueError:
            pass
    media = read_object(edition / "production.json")["files"]
    state = {
        "schema_version": 2,
        "audio": audio_path,
        "master_sha256": media["master.wav"],
        "cues_sha256": media["cues.json"],
        "video": None,
        "preview": None,
        "preview_seconds": None,
    }
    if (
        previous.get("audio") == audio_path
        and previous.get("master_sha256") == state["master_sha256"]
        and previous.get("cues_sha256") == state["cues_sha256"]
    ):
        if previous.get("schema_version") == 2:
            state.update(
                {key: previous.get(key) for key in ("video", "preview", "preview_seconds")}
            )
    if video is not None:
        if preview is None:
            state["video"] = str(video.relative_to(directory))
        else:
            state.update(preview=str(video.relative_to(directory)), preview_seconds=preview)
    write_json(directory / "latest.json", state)


def add_arguments(commands: argparse._SubParsersAction) -> None:
    command = commands.add_parser(
        "produce", help="Finish existing narration and render a reusable video edition locally"
    )
    command.add_argument("episode", help="Published episode ID, or all")
    command.add_argument(
        "--audio-only",
        action="store_true",
        help="Skip Node/Remotion; finish MP3 and retimed subtitles",
    )
    command.add_argument(
        "--audio-jobs",
        type=int,
        choices=range(1, 5),
        default=2,
        help="Finish 1–4 recordings concurrently (default: 2); video workers use settings",
    )
    command.add_argument(
        "--video-workers",
        type=int,
        choices=range(1, 9),
        help="Override 1–8 video frame workers; default is the configured concurrency",
    )
    command.add_argument(
        "--config", type=Path, help="Shared settings; optional sibling episodes/<id>.json overrides"
    )
    command.add_argument(
        "--output-dir", type=Path, help="Review output; defaults to artifacts/production"
    )
    command.add_argument(
        "--preview-seconds",
        type=float,
        help="Render only the first 1–60 seconds of video; full audio is retained",
    )
    command.add_argument(
        "--browser-executable",
        type=Path,
        help="Optional installed Chrome Headless Shell executable",
    )
