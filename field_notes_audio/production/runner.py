"""Cache complete editions by their inputs, settings and implementation."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from field_notes_audio import audio, captions, site
from field_notes_audio.locks import run_lock
from field_notes_audio.production.config import audio_settings, load_settings
from field_notes_audio.production.mix import finish_audio
from field_notes_audio.production.timeline import caption_pages, retime
from field_notes_audio.storage import digest_file, read_object, write_json

AUDIO_FILES = {
    "episode.mp3",
    "master.wav",
    "captions.srt",
    "captions.vtt",
    "transcript.txt",
    "cues.json",
    "description.txt",
}
VIDEO_FILES = {"episode.mp4", "thumbnail.png", "render.json"}


def fingerprint(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def cache_valid(directory: Path, identity: str, files: set[str]) -> bool:
    try:
        if directory.is_symlink():
            return False
        state = read_object(directory / "production.json")
        return (
            state.get("fingerprint") == identity
            and state.get("files", {}).keys() == files
            and all(digest_file(directory / name) == state["files"][name] for name in files)
        )
    except (ValueError, OSError, TypeError, AttributeError):
        return False


def commit_stage(stage: Path, destination: Path, state: dict, files: set[str]) -> None:
    state["files"] = {name: digest_file(stage / name) for name in sorted(files)}
    write_json(stage / "production.json", state)
    if destination.is_symlink():
        raise ValueError("Production cache directories must not be symbolic links")
    backup = destination.parent / f".previous-{destination.name}-{uuid.uuid4().hex}"
    replaced = destination.exists()
    if replaced:
        destination.rename(backup)
    moved_video = False
    try:
        if replaced and files == AUDIO_FILES and (backup / "video").exists():
            (backup / "video").rename(stage / "video")
            moved_video = True
        stage.rename(destination)
    except (OSError, KeyboardInterrupt):
        if replaced:
            if moved_video:
                (stage / "video").rename(backup / "video")
            backup.rename(destination)
        raise
    # Audio repairs retain separately validated video caches. Their identities
    # also include actual master/cue hashes, so changed sound cannot reuse them.
    if replaced:
        shutil.rmtree(backup)


def produce_audio(entry: dict, root: Path, output: Path, settings: dict) -> Path:
    source = site.media_path(root, entry["audio"])
    implementation = {
        name: digest_file(Path(__file__).parent / name)
        for name in ("config.py", "mix.py", "sound.py", "timeline.py", "runner.py")
    }
    encoder = subprocess.run(
        ["ffmpeg", "-version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    recipe = audio_settings(settings)
    identity = fingerprint(
        {
            "source_audio": entry["audio_sha256"],
            "source_captions": entry["files_sha256"],
            "source_script": entry["script_sha256"],
            "source_articles": entry["source_sha256"],
            "title": entry["title"],
            "description": entry["description"],
            "id": entry["id"],
            "kind": entry.get("kind"),
            "slug": entry.get("slug"),
            "review_status": entry["review_status"],
            "settings": recipe,
            "implementation": implementation,
            "encoder": encoder,
            "music_sha256": digest_file(Path(settings["music_file"]))
            if settings["music_file"]
            else None,
        }
    )
    destination = output / identity[:16]
    if cache_valid(destination, identity, AUDIO_FILES):
        print(f"{entry['id']}: finished audio reused.", flush=True)
        return destination
    print(f"{entry['id']}: finishing narration, motif and loudness locally…", flush=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=".audio-", dir=output) as temporary:
        stage = Path(temporary) / "edition"
        stage.mkdir()
        measured = finish_audio(source, stage, settings)
        cues = json.loads(site.media_path(root, entry["cues"]).read_text(encoding="utf-8"))
        try:
            cues = retime(
                cues,
                settings["speed"],
                settings["intro_seconds"],
                measured["voice_duration_seconds"],
            )
            # Validate against the actual encoded output, not just the planned timeline.
            for vtt, name in ((False, "captions.srt"), (True, "captions.vtt")):
                text = captions.render_captions(cues, vtt=vtt)
                captions.parse_captions(text, measured["duration_seconds"], vtt=vtt)
                (stage / name).write_text(text, encoding="utf-8")
        except ValueError as exc:
            diagnostic = output / "failures" / f"{identity[:16]}-captions.json"
            write_json(
                diagnostic,
                {
                    "episode": entry["id"],
                    "fingerprint": identity,
                    "error": str(exc),
                    "measurements": measured,
                    "settings": recipe,
                    "cues": cues,
                },
            )
            raise ValueError(
                f"{entry['id']}: caption export failed; diagnostic saved to {diagnostic}"
            ) from exc
        write_json(stage / "cues.json", {"cues": cues, "pages": caption_pages(cues)})
        shutil.copyfile(site.media_path(root, entry["transcript"]), stage / "transcript.txt")
        credit = settings["music_credit"] if settings["music_mode"] != "none" else "No music."
        link = site.DOMAIN + (
            "/notes/" + entry["slug"] if entry.get("slug") else "/notes/#listen-archive"
        )
        (stage / "description.txt").write_text(
            f"{entry['title']}\n\n{entry['description']}\n\nWritten edition: {link}\n\n"
            f"AI-narrated. Machine-generated transcript; listening review: {entry['review_status']}.\n"
            f"Narration paced at {settings['speed']:g}× in this recording.\n{credit}\n",
            encoding="utf-8",
        )
        commit_stage(
            stage,
            destination,
            {
                "schema_version": 1,
                "fingerprint": identity,
                "episode": entry["id"],
                "source_audio_sha256": entry["audio_sha256"],
                "source_files_sha256": entry["files_sha256"],
                "source_sha256": entry["source_sha256"],
                "settings": recipe,
                **measured,
                "processing_seconds": round(time.monotonic() - started, 3),
                "review_status": "pending",
                "source_review_status": entry["review_status"],
            },
            AUDIO_FILES,
        )
    return destination


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
        render_video(root, entry, edition, stage, settings, args, assets)
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
    preflight(root, args)
    for entry, settings in recipes:
        directory = output / entry["id"]
        if directory.is_symlink():
            raise ValueError("Production episode directories must not be symbolic links")
        directory.mkdir(parents=True, exist_ok=True)
        with run_lock(directory, "production"):
            edition = produce_audio(entry, root, directory, settings)
            update_latest(directory, edition)
            print(f"Finished audio: {edition / 'episode.mp3'}", flush=True)
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
