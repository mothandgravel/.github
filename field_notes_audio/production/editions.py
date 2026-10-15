"""Validated, transactional finished audio editions and their content identities."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from field_notes_audio import captions, site
from field_notes_audio.production.config import audio_settings
from field_notes_audio.production.mix import finish_audio
from field_notes_audio.production.sources import media_path
from field_notes_audio.production.timeline import caption_pages, retime
from field_notes_audio.production.toolchain import AudioToolchain, inspect_audio_toolchain
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


def produce_audio(
    entry: dict,
    root: Path,
    output: Path,
    settings: dict,
    toolchain: AudioToolchain | None = None,
) -> Path:
    source = media_path(root, entry["audio"])
    toolchain = toolchain or inspect_audio_toolchain()
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
            "implementation": dict(toolchain.implementation),
            "encoder": toolchain.encoder,
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
        cues = json.loads(media_path(root, entry["cues"]).read_text(encoding="utf-8"))
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
        shutil.copyfile(media_path(root, entry["transcript"]), stage / "transcript.txt")
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
