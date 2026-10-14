"""Verified edition snapshots, human review records and portable upload folders."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from field_notes_audio import audio, captions, site
from field_notes_audio.locks import run_lock
from field_notes_audio.production.config import load_settings
from field_notes_audio.production.editions import AUDIO_FILES, VIDEO_FILES, cache_valid, fingerprint
from field_notes_audio.production.metadata import load_metadata, publishing_copy, text
from field_notes_audio.storage import digest_file, read_object, write_json
from field_notes_audio.transactions import FileTransaction


@dataclass(frozen=True)
class Edition:
    source: dict
    directory: Path
    audio: Path
    video: Path | None
    state: dict
    video_state: dict | None


def local_output(root: Path, supplied: Path | None, default: str) -> Path:
    path = (supplied or root / default).resolve()
    if path == root or any(
        path.is_relative_to(root / name)
        for name in (
            "docs",
            "audio",
            "field_notes_audio",
            "video",
            "tests",
            "tools",
            "scripts",
            ".git",
            ".github",
            "profile",
        )
    ):
        raise ValueError("Release output must be separate from source and published files")
    return path


def selected_entries(identifier: str, root: Path) -> list[dict]:
    entries = site.load_entries(root)
    selected = entries if identifier == "all" else [e for e in entries if e["id"] == identifier]
    if not selected:
        raise ValueError("No prepared episode matches this ID")
    return selected


def relative_edition(directory: Path, relative: object, video: bool = False) -> Path:
    pattern = r"[a-f0-9]{16}/video/[a-f0-9]{16}" if video else r"[a-f0-9]{16}"
    if not isinstance(relative, str) or not re.fullmatch(pattern, relative):
        raise ValueError("Invalid completed-edition pointer")
    path = directory / relative
    if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Edition pointer escapes its episode directory")
    return path


def snapshot(
    entry: dict, output: Path, full_video: bool = False, inspect_video: bool = True
) -> Edition:
    try:
        return _snapshot(entry, output, full_video, inspect_video)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("Invalid completed-edition metadata; repeat produce to repair it") from exc


def _snapshot(entry: dict, output: Path, full_video: bool, inspect_video: bool) -> Edition:
    directory = output / entry["id"]
    if directory.is_symlink():
        raise ValueError("Episode directory must not be a symbolic link")
    latest = read_object(directory / "latest.json")
    if type(latest.get("schema_version")) is not int or latest["schema_version"] != 2:
        raise ValueError("Run produce again to update the completed-edition pointer")
    source = site.source_entry(entry)
    finished = relative_edition(directory, latest.get("audio"))
    state = read_object(finished / "production.json")
    identity = state.get("fingerprint")
    if not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{64}", identity):
        raise ValueError("Invalid finished-audio identity")
    if finished.name != identity[:16] or not cache_valid(finished, identity, AUDIO_FILES):
        raise ValueError("Finished audio is missing or changed; repeat produce")
    settings = state.get("settings")
    if (
        not isinstance(settings, dict)
        or not isinstance(settings.get("music_mode"), str)
        or settings.get("music_mode") not in {"none", "file", "motif"}
        or not isinstance(settings.get("music_credit"), str)
    ):
        raise ValueError("Invalid finished-audio settings")
    pace = settings.get("speed")
    if type(pace) not in (int, float) or not math.isfinite(pace) or not 0.75 <= pace <= 1.5:
        raise ValueError("Invalid finished-audio pace")
    for field in ("timeline_duration_seconds", "duration_seconds"):
        value = state.get(field)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1200:
            raise ValueError("Invalid finished-audio duration")
    if (
        state.get("episode") != source["id"]
        or state.get("source_audio_sha256") != source["audio_sha256"]
        or state.get("source_files_sha256") != source["files_sha256"]
        or state.get("source_sha256") != source["source_sha256"]
        or latest.get("master_sha256") != state["files"]["master.wav"]
        or latest.get("cues_sha256") != state["files"]["cues.json"]
    ):
        raise ValueError("Finished audio belongs to a different source or latest pointer")
    duration = state.get("duration_seconds")
    if (
        type(duration) not in (int, float)
        or not math.isfinite(duration)
        or not 0 < duration <= 1200
    ):
        raise ValueError("Invalid finished-audio duration")
    if (
        abs(captions.probe_audio(finished / "episode.mp3") - duration)
        > site.MP3_DURATION_TOLERANCE_SECONDS
    ):
        raise ValueError("Finished MP3 duration disagrees with its encoded media")
    srt = captions.parse_captions((finished / "captions.srt").read_text(), duration)
    vtt = captions.parse_captions((finished / "captions.vtt").read_text(), duration, vtt=True)
    cues = read_object(finished / "cues.json").get("cues")
    if (
        not isinstance(cues, list)
        or len(cues) != len(srt)
        or len(vtt) != len(srt)
        or any(
            site.caption_text(a["text"]) != site.caption_text(b["text"])
            or abs(a["start"] - b["start"]) > 0.001
            or abs(a["end"] - b["end"]) > 0.001
            for sequence in (vtt, cues)
            for a, b in zip(srt, sequence, strict=True)
        )
    ):
        raise ValueError("Finished captions and timed transcript disagree")
    video = video_state = None
    if (full_video or inspect_video) and latest.get("video"):
        video = relative_edition(directory, latest["video"], video=True)
        video_state = read_object(video / "production.json")
        if any(
            video_state.get(key) != value
            for key, value in {
                "audio_fingerprint": identity,
                "master_sha256": state["files"]["master.wav"],
                "cues_sha256": state["files"]["cues.json"],
            }.items()
        ):
            raise ValueError("Video provenance is stale; repeat produce to verify/adopt the render")
        if video.name != str(video_state.get("fingerprint", ""))[:16]:
            raise ValueError("Video pointer and identity disagree")
        if video.parent.parent != finished or not cache_valid(
            video, video_state.get("fingerprint"), VIDEO_FILES
        ):
            raise ValueError("Full video is missing, changed or belongs to different audio")
        if (
            video_state.get("preview_seconds") is not None
            or read_object(video / "render.json").get("previewSeconds") is not None
        ):
            raise ValueError("A preview cannot be released as a full episode")
        rendered = read_object(video / "render.json")
        fps = rendered.get("fps")
        if (
            type(fps) is not int
            or not 12 <= fps <= 30
            or type(rendered.get("frames")) is not int
            or rendered.get("frames") != math.ceil(state["timeline_duration_seconds"] * fps)
        ):
            raise ValueError("Video timeline does not cover the full finished episode")
        inspected = json.loads(
            subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
                    "-of",
                    "json",
                    str(video / "episode.mp4"),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout
        )
        encoded_duration = float(inspected["format"]["duration"])
        visual = next(
            (stream for stream in inspected["streams"] if stream.get("codec_type") == "video"), {}
        )
        if (
            not math.isfinite(encoded_duration)
            or abs(encoded_duration - rendered["frames"] / fps) > 0.15
            or any(visual.get(field) != rendered.get(field) for field in ("width", "height"))
            or visual.get("r_frame_rate") != f"{fps}/1"
            or not all(
                any(
                    stream.get("codec_type") == kind and stream.get("codec_name") == codec
                    for stream in inspected.get("streams", [])
                )
                for kind, codec in (("video", "h264"), ("audio", "aac"))
            )
        ):
            raise ValueError("Upload video is not a complete H.264/AAC episode")
    if full_video and video is None:
        raise ValueError(
            f"{source['id']}: a full video is required; run produce without --preview-seconds"
        )
    return Edition(source, directory, finished, video, state, video_state)


@contextmanager
def locked_editions(
    entries: list[dict], output: Path, full_video: bool = False, inspect_video: bool = True
) -> Iterator[list[Edition]]:
    from contextlib import ExitStack

    with ExitStack() as stack:
        for entry in sorted(entries, key=lambda e: e["id"]):
            directory = output / entry["id"]
            if not directory.is_dir() or directory.is_symlink():
                raise ValueError(f"{entry['id']}: no completed local edition; run produce first")
            stack.enter_context(run_lock(directory, "release/review"))
        yield [snapshot(entry, output, full_video, inspect_video) for entry in entries]


def review_status(edition: Edition, full_video: bool = False) -> str:
    path = edition.audio / "review.json"
    if not path.exists():
        return "pending"
    review = read_object(path)
    if (
        type(review.get("schema_version")) is not int
        or review["schema_version"] != 1
        or not isinstance(review.get("reviewed_at"), str)
        or review.get("status") != "approved"
        or review.get("audio_fingerprint") != edition.state["fingerprint"]
        or review.get("audio_files") != edition.state["files"]
        or not isinstance(review.get("reviewer"), str)
        or not review["reviewer"].strip()
    ):
        return "pending"
    try:
        if datetime.fromisoformat(review["reviewed_at"]).tzinfo is None:
            return "pending"
    except ValueError:
        return "pending"
    if full_video and (
        edition.video_state is None
        or review.get("video_files") != edition.video_state["files"]
        or review.get("video_fingerprint") != edition.video_state["fingerprint"]
    ):
        return "pending"
    return "approved"


def record_review(edition: Edition, reviewer: str) -> None:
    """Record explicit human approval of a verified snapshot under its episode lock."""
    reviewer = text(reviewer, "Reviewer", 120)
    write_json(
        edition.audio / "review.json",
        {
            "schema_version": 1,
            "status": "approved",
            "reviewer": reviewer,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "audio_fingerprint": edition.state["fingerprint"],
            "audio_files": edition.state["files"],
            "video_fingerprint": edition.video_state["fingerprint"]
            if edition.video_state
            else None,
            "video_files": edition.video_state["files"] if edition.video_state else None,
        },
    )


def review(args: argparse.Namespace, root: Path = audio.ROOT) -> None:
    output = local_output(root, args.output_dir, "artifacts/production")
    entries = selected_entries(args.episode, root)
    if args.approve and not args.reviewer:
        raise ValueError(
            "--approve needs --reviewer with the person who listened and checked captions"
        )
    reviewer = text(args.reviewer, "Reviewer", 120) if args.reviewer else None
    with locked_editions(
        entries, output, inspect_video=not getattr(args, "audio_only", False)
    ) as editions:
        for edition in editions:
            if args.approve:
                record_review(edition, reviewer)
            print(
                f"{edition.source['id']}: audio {review_status(edition)}; "
                f"video {review_status(edition, True) if edition.video else 'not produced'}"
            )


UPLOAD_FILES = {
    "episode.mp4",
    "episode.mp3",
    "thumbnail.png",
    "captions.srt",
    "captions.vtt",
    "transcript.txt",
    "title.txt",
    "description.txt",
    "tags.txt",
    "hashtags.txt",
}


def upload_valid(
    destination: Path,
    identity: str,
    expected: dict[str, str] | None = None,
    manifest: dict | None = None,
) -> bool:
    try:
        if destination.is_symlink():
            return False
        saved = read_object(destination / "upload.json")
        return (
            saved.get("fingerprint") == identity
            and isinstance(saved.get("files"), dict)
            and all(
                not (destination / name).is_symlink() and digest_file(destination / name) == value
                for name, value in saved["files"].items()
                if re.fullmatch(r"[a-z]+\.(mp4|mp3|png|srt|vtt|txt)", name)
            )
            and set(saved["files"]) == UPLOAD_FILES
            and (expected is None or saved["files"] == expected)
            and (manifest is None or saved == manifest)
        )
    except (OSError, ValueError, TypeError):
        return False


def upload_transaction(uploads: Path) -> FileTransaction:
    return FileTransaction(
        uploads,
        uploads / ".transaction",
        lambda relative: relative
        in {"podcast-title.txt", "podcast-description.txt", "podcast-cover.png", "index.json"}
        or bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9.]+", relative))
        and relative.split("/")[1] in UPLOAD_FILES | {"upload.json"},
    )


def upload_inventory(uploads: Path) -> list[dict]:
    if not (uploads / "index.json").exists():
        return []
    saved = read_object(uploads / "index.json")
    items = saved.get("episodes")
    if (
        type(saved.get("schema_version")) is not int
        or saved["schema_version"] != 1
        or not isinstance(items, list)
    ):
        raise ValueError("Invalid upload inventory; preserve/repair index.json before exporting")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {
            "episode",
            "title",
            "folder",
            "review_status",
        }:
            raise ValueError("Invalid upload inventory entry")
        identifier = item["episode"]
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier)
            or identifier in seen
            or item["folder"] != identifier
            or item["review_status"] not in ("pending", "approved")
        ):
            raise ValueError("Invalid or duplicate upload inventory episode")
        text(item["title"], "Inventory title", 100)
        seen.add(identifier)
    return items


def check_upload_destinations(uploads: Path, entries: list[dict]) -> None:
    upload_inventory(uploads)
    for entry in entries:
        destination = uploads / entry["id"]
        if destination.is_symlink() or destination.exists() and not destination.is_dir():
            raise ValueError("Upload destination must be a normal directory")
        if destination.exists() and any(
            path.name not in UPLOAD_FILES | {"upload.json"}
            or not path.is_file()
            or path.is_symlink()
            for path in destination.iterdir()
        ):
            raise ValueError(f"Preserve unexpected files in {destination} before exporting")


def export(args: argparse.Namespace, root: Path = audio.ROOT) -> None:
    output = local_output(root, args.output_dir, "artifacts/production")
    uploads = local_output(root, args.upload_dir, "artifacts/uploads")
    if uploads.is_relative_to(output) or output.is_relative_to(uploads):
        raise ValueError("Upload folders and production caches must be separate")
    entries = selected_entries(args.episode, root)
    config = load_metadata((args.metadata or root / "audio/production/publishing.json").resolve())
    with locked_editions(entries, output, full_video=True) as editions:
        copies = [
            publishing_copy(
                config,
                edition.source,
                edition.state["settings"]["music_credit"]
                if edition.state["settings"]["music_mode"] != "none"
                else "No music.",
            )
            for edition in editions
        ]
        uploads.mkdir(parents=True, exist_ok=True)
        with run_lock(uploads, "upload export"):
            upload_transaction(uploads).recover()
            check_upload_destinations(uploads, entries)
            merged = {item["episode"]: item for item in upload_inventory(uploads)}
            with upload_transaction(uploads) as transaction:
                for edition, copy in zip(editions, copies, strict=True):
                    sources = {
                        "episode.mp4": edition.video / "episode.mp4",
                        "thumbnail.png": edition.video / "thumbnail.png",
                        **{
                            name: edition.audio / name
                            for name in (
                                "episode.mp3",
                                "captions.srt",
                                "captions.vtt",
                                "transcript.txt",
                            )
                        },
                    }
                    content = {
                        "title.txt": copy.title + "\n",
                        "description.txt": copy.description + "\n",
                        "tags.txt": ", ".join(copy.tags) + "\n",
                        "hashtags.txt": " ".join(copy.hashtags) + "\n",
                    }
                    status = review_status(edition, True)
                    identity = fingerprint(
                        {
                            "audio": edition.state["fingerprint"],
                            "video": edition.video_state["fingerprint"],
                            "copy": content,
                            "review": status,
                        }
                    )
                    destination = uploads / edition.source["id"]
                    expected = {
                        name: (
                            edition.video_state["files"]
                            if name in VIDEO_FILES
                            else edition.state["files"]
                        )[name]
                        for name in sources
                    }
                    expected.update(
                        {name: fingerprint_text(value) for name, value in content.items()}
                    )
                    manifest = {
                        "schema_version": 1,
                        "episode": edition.source["id"],
                        "fingerprint": identity,
                        "review_status": status,
                        "default_playback_rate": 1,
                        "audio_fingerprint": edition.state["fingerprint"],
                        "video_fingerprint": edition.video_state["fingerprint"],
                        "files": expected,
                    }
                    if not upload_valid(destination, identity, expected, manifest):
                        for name, source in sources.items():
                            transaction.copy(destination / name, source, expected[name])
                        for name, value in content.items():
                            transaction.write_text(destination / name, value)
                        transaction.write_json(destination / "upload.json", manifest)
                    merged[edition.source["id"]] = {
                        "episode": edition.source["id"],
                        "title": copy.title,
                        "folder": destination.name,
                        "review_status": status,
                    }
                for field in ("title", "description"):
                    transaction.write_text(
                        uploads / f"podcast-{field}.txt", config["show"][field] + "\n"
                    )
                transaction.copy(
                    uploads / "podcast-cover.png", root / "docs/assets/podcast-cover.png"
                )
                transaction.write_json(
                    uploads / "index.json", {"schema_version": 1, "episodes": list(merged.values())}
                )
            for edition in editions:
                print(
                    f"Upload folder: {uploads / edition.source['id']} ({review_status(edition, True)})"
                )
    print("Local upload folders prepared. Nothing was uploaded or pushed.")


def fingerprint_text(value: str) -> str:
    from hashlib import sha256

    return sha256(value.encode("utf-8")).hexdigest()


def preflight_release(args: argparse.Namespace, root: Path = audio.ROOT) -> None:
    """Reject invalid upload copy/locations before any finishing or rendering work."""
    output = local_output(root, args.output_dir, "artifacts/production")
    uploads = local_output(root, args.upload_dir, "artifacts/uploads")
    if uploads.is_relative_to(output) or output.is_relative_to(uploads):
        raise ValueError("Upload folders and production caches must be separate")
    config = load_metadata(args.metadata or root / "audio/production/publishing.json")
    entries = selected_entries(args.episode, root)
    if uploads.exists():
        with run_lock(uploads, "release preflight"):
            upload_transaction(uploads).recover()
            check_upload_destinations(uploads, entries)
    for entry in entries:
        source = site.source_entry(entry)
        settings = load_settings(
            args.config or root / "audio/production/settings.json", source["id"]
        )
        publishing_copy(
            config,
            source,
            settings["music_credit"] if settings["music_mode"] != "none" else "No music.",
        )


def add_arguments(commands: argparse._SubParsersAction) -> None:
    for name in ("export", "review", "promote"):
        command = commands.add_parser(
            name,
            help={
                "export": "Package completed full episodes with editable title, description and tags",
                "review": "Show review status or record explicit human approval of completed editions",
                "promote": "Prepare reviewed finished audio, retimed captions and 1× website playback",
            }[name],
        )
        command.add_argument("episode", help="Prepared episode ID, or all")
        command.add_argument(
            "--output-dir", type=Path, help="Production cache; defaults to artifacts/production"
        )
        if name == "export":
            command.add_argument(
                "--upload-dir", type=Path, help="Portable folders; defaults to artifacts/uploads"
            )
            command.add_argument(
                "--metadata",
                type=Path,
                help="Publishing copy; defaults to audio/production/publishing.json",
            )
        elif name == "review":
            command.add_argument(
                "--audio-only",
                action="store_true",
                help="Review audio/captions without requiring an available video",
            )
            command.add_argument(
                "--approve",
                action="store_true",
                help="Record that you listened and checked captions/video",
            )
            command.add_argument("--reviewer", help="Name of the human reviewer")
