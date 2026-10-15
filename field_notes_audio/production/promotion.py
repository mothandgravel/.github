"""Promote reviewed finished sound, captions and playback defaults as one local release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from field_notes_audio import audio, captions, release, site
from field_notes_audio.production.packages import (
    Edition,
    local_output,
    locked_editions,
    review_status,
)
from field_notes_audio.storage import digest_file, read_object


def promoted_entry(edition: Edition) -> tuple[dict, dict[str, Path | bytes]]:
    if review_status(edition) != "approved":
        raise ValueError(
            f"{edition.source['id']}: listen and approve this finished edition before promotion"
        )
    state, source = edition.state, edition.source
    measured = captions.probe_audio(edition.audio / "episode.mp3")
    if abs(measured - state["duration_seconds"]) > site.MP3_DURATION_TOLERANCE_SECONDS:
        raise ValueError("Finished duration differs from the encoded recording")
    prefix = source["id"] + "-" + state["files"]["episode.mp3"][:16]
    audio_relative = "assets/audio/" + prefix + ".mp3"
    assets: dict[str, Path | bytes] = {audio_relative: edition.audio / "episode.mp3"}
    hashes, files = {}, {}
    cues = (
        json.dumps(read_object(edition.audio / "cues.json")["cues"], ensure_ascii=False, indent=2)
        + "\n"
    ).encode()
    for kind, name, extension in (
        ("srt", "captions.srt", "srt"),
        ("vtt", "captions.vtt", "vtt"),
        ("transcript", "transcript.txt", "txt"),
        ("cues", "cues.json", "json"),
    ):
        data = cues if kind == "cues" else edition.audio / name
        digest = audio.digest(data) if isinstance(data, bytes) else digest_file(data)
        relative = f"assets/audio/{prefix}-{digest[:16]}.{extension}"
        assets[relative], hashes[kind], files[kind] = data, digest, relative
    entry = {
        **source,
        **files,
        "files_sha256": hashes,
        "audio": audio_relative,
        "audio_sha256": state["files"]["episode.mp3"],
        "bytes": (edition.audio / "episode.mp3").stat().st_size,
        "duration_seconds": round(measured, 3),
        "default_playback_rate": 1,
        "review_status": "approved",
        "production": {
            "fingerprint": state["fingerprint"],
            "pace": state["settings"]["speed"],
            "music_credit": state["settings"]["music_credit"]
            if state["settings"]["music_mode"] != "none"
            else "No music.",
            "source": source,
            "review": read_object(edition.audio / "review.json"),
        },
    }
    return entry, assets


def promote(args: argparse.Namespace, root: Path = audio.ROOT) -> None:
    output = local_output(root, args.output_dir, "artifacts/production")
    output.mkdir(parents=True, exist_ok=True)
    with release.collection_lock(root):
        entries = site.load_entries(root)
        selected = (
            entries
            if args.episode == "all"
            else [entry for entry in entries if entry["id"] == args.episode]
        )
        if not selected:
            raise ValueError("No prepared episode matches this ID")
        with locked_editions(selected, output, inspect_video=False) as editions:
            prepare(editions, entries, root)
    print(f"Prepared {len(selected)} reviewed finished editions, retimed captions and 1× defaults.")
    print("The website/feed changes are local. Next: python3 -m field_notes_audio publish")


def prepare(editions: list[Edition], entries: list[dict], root: Path) -> None:
    # Validate the entire selected batch, including human review, before touching public files.
    replacements, assets = {}, {}
    for edition in editions:
        entry, material = promoted_entry(edition)
        replacements[entry["id"]] = entry
        assets.update(material)
    updated = [replacements.get(entry["id"], entry) for entry in entries]
    manifest = root / "docs/assets/audio/episodes.json"
    notes = json.loads((root / "docs/assets/notes.json").read_text())
    generated = [
        manifest,
        root / "docs/notes/podcast.xml",
        root / "docs/notes/index.html",
        *(root / "docs/notes" / note["slug"] for note in notes),
    ]
    journal = root / "artifacts/audio/release.json"
    generated.append(journal)
    with release.publication_transaction(root) as transaction:
        for relative, material in assets.items():
            destination = root / "docs" / relative
            expected = (
                audio.digest(material) if isinstance(material, bytes) else digest_file(material)
            )
            if destination.exists() and digest_file(destination) != expected:
                raise ValueError("Content-addressed finished asset changed")
            if isinstance(material, bytes):
                transaction.write_bytes(destination, material)
            else:
                transaction.copy(destination, material, expected)
        transaction.write_json(manifest, updated)
        site.build(root=root, writer=transaction.write_text)
        site.build(check=True, root=root)
        saved = (
            release.release_state()
            if root == audio.ROOT
            else read_object(journal)
            if journal.exists()
            else {}
        )
        # Carry forward a make-all batch's prepared new scripts and other valid assets.
        hashes = {
            relative: digest_file(root / relative)
            for relative, value in saved.get("files", {}).items()
            if (root / relative).is_file() and digest_file(root / relative) == value
        }
        paths = [*generated[:-1], *(root / "docs" / relative for relative in assets)]
        hashes.update({str(path.relative_to(root)): digest_file(path) for path in paths})
        transaction.write_json(
            journal,
            {
                "version": 1,
                "phase": "complete",
                "episodes": [entry["id"] for entry in updated],
                "files": hashes,
                "edition": "finished",
            },
        )
