"""Anti-corruption adapter: the only studio module that calls production APIs."""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from field_notes_audio import site
from field_notes_audio.locks import run_lock
from field_notes_audio.production import packages, runner
from field_notes_audio.production.config import load_settings, number
from field_notes_audio.production.editions import AUDIO_FILES, cache_valid, fingerprint
from field_notes_audio.production.metadata import load_metadata, publishing_copy
from field_notes_audio.storage import read_object, write_json
from field_notes_studio.models import ACTIONS, Episode, ReleaseDetails, ReviewSnapshot


class Pipeline:
    def __init__(self, root: Path):
        self.root = root
        self.output = root / "artifacts/production"

    def entries(self) -> list[dict]:
        return site.load_entries(self.root)

    def catalog(self) -> list[Episode]:
        return [
            Episode(
                entry["id"],
                entry["title"],
                entry["duration_seconds"],
                site.media_path(self.root, entry["transcript"]).read_text(encoding="utf-8"),
                *self.publication_defaults(entry),
                "Podcast catalog in this checkout; external platforms have not been checked.",
            )
            for entry in self.entries()
        ]

    @staticmethod
    def publication_defaults(entry: dict) -> tuple[str, str]:
        # Match the existing podcast feed's article/archive destinations.
        link = site.DOMAIN + (
            "/notes/" + entry["slug"] if entry.get("slug") else "/notes/#listen-archive"
        )
        published = entry.get("published_at", "")
        return link, datetime.fromisoformat(published).date().isoformat() if published else ""

    def release_details(self, identifier: str) -> ReleaseDetails:
        entry = self.source(identifier)
        link, published = self.publication_defaults(entry)
        uploads = self.root / "artifacts/uploads"
        directory = uploads / identifier
        if (directory / "upload.json").exists():
            with run_lock(uploads, "upload export"):
                manifest = read_object(directory / "upload.json")
                names = ("title.txt", "description.txt", "tags.txt", "hashtags.txt")
                message = "Saved upload text changed. Export again to repair the package."
                if (
                    directory.is_symlink()
                    or manifest.get("episode") != identifier
                    or not isinstance(manifest.get("files"), dict)
                ):
                    raise ValueError(message)
                values = []
                for name in names:
                    path = directory / name
                    content = path.read_bytes()
                    if path.is_symlink() or hashlib.sha256(content).hexdigest() != manifest[
                        "files"
                    ].get(name):
                        raise ValueError(message)
                    values.append(content.decode("utf-8").removesuffix("\n"))
            return ReleaseDetails(
                *values,
                link,
                published,
                "Saved upload package text (checksummed). Export again to apply later changes; media approval stays in Review.",
            )
        config = load_metadata(self.root / "audio/production/publishing.json")
        settings = self.settings(identifier)
        basis = (
            "Draft copy from publishing settings. Produce an edition to confirm its music credit."
        )
        if (self.output / identifier / "latest.json").exists():
            with packages.locked_editions([entry], self.output, full_video=False) as editions:
                settings = editions[0].state["settings"]
                basis = "Copy from publishing settings and the verified saved audio's music credit."
        copy = publishing_copy(
            config,
            entry,
            settings["music_credit"] if settings["music_mode"] != "none" else "No music.",
        )
        return ReleaseDetails(
            copy.title,
            copy.description,
            ", ".join(copy.tags),
            " ".join(copy.hashtags),
            link,
            published,
            basis,
        )

    def source(self, identifier: str) -> dict:
        matches = [entry for entry in self.entries() if entry["id"] == identifier]
        if len(matches) != 1:
            raise ValueError("Choose a prepared episode")
        return site.source_entry(matches[0])

    def settings(self, identifier: str) -> dict:
        return load_settings(self.root / "audio/production/settings.json", identifier)

    def output_path(self, identifier: str, kind: str) -> Path:
        directory = self.output / identifier
        if kind == "uploads":
            return self.root / "artifacts/uploads" / identifier
        if kind == "folder":
            return directory
        latest = read_object(directory / "latest.json")
        if kind == "video":
            return (
                packages.relative_edition(directory, latest.get("video"), video=True)
                / "episode.mp4"
            )
        audio = packages.relative_edition(directory, latest.get("audio"))
        return audio / {"audio": "episode.mp3", "captions": "captions.srt"}[kind]

    @staticmethod
    def review_identity(edition: packages.Edition) -> str:
        return fingerprint(
            {
                "source": edition.source,
                "audio": edition.state["fingerprint"],
                "audio_files": edition.state["files"],
                "video": edition.video_state["fingerprint"] if edition.video_state else None,
                "video_files": edition.video_state["files"] if edition.video_state else None,
            }
        )

    def review_snapshot(self, identifier: str, full_video: bool = False) -> ReviewSnapshot:
        if not (self.output / identifier / "latest.json").exists():
            return ReviewSnapshot(
                "", "No local edition yet. Select audio, inspect changes, then queue production."
            )
        try:
            with packages.locked_editions(
                [self.source(identifier)], self.output, full_video, inspect_video=full_video
            ) as editions:
                edition = editions[0]
                status = packages.review_status(edition, full_video)
                scope = "Audio, captions and full video" if full_video else "Audio and captions"
                settings = edition.state["settings"]
                detail = (
                    f"{scope}: {status} · {edition.state['duration_seconds'] / 60:.1f} min\n"
                    f"Saved edition: {edition.audio.name} · {settings['speed']:g}× pace · "
                    f"{settings['outro_seconds']:g}s outro\n"
                )
                if status == "approved":
                    detail += (
                        "Review recorded. Select export, inspect changes, then queue the upload package."
                        if full_video
                        else "Review recorded. For a YouTube package, produce and review the full video, then export."
                    )
                else:
                    detail += "Open the saved assets below, check them, then record your review."
                return ReviewSnapshot(
                    self.review_identity(edition),
                    detail,
                    str(edition.audio / "episode.mp3"),
                    str(edition.audio / "captions.srt"),
                    str(edition.video / "episode.mp4") if edition.video else "",
                    full_video,
                )
        except (ValueError, OSError) as exc:
            return ReviewSnapshot("", f"Review unavailable: {exc}")

    def approve(self, identifier: str, expected: ReviewSnapshot, reviewer: str) -> None:
        if not expected.identity:
            raise ValueError("Load a completed edition before reviewing it")
        with packages.locked_editions(
            [self.source(identifier)],
            self.output,
            expected.full_video,
            inspect_video=expected.full_video,
        ) as editions:
            edition = editions[0]
            if self.review_identity(edition) != expected.identity:
                raise ValueError(
                    "Edition changed while you were reviewing. Refresh and check the new assets."
                )
            packages.record_review(edition, reviewer)

    def request(
        self, identifier: str, action: str, speed: float | None, outro: float | None
    ) -> dict:
        if action not in ACTIONS:
            raise ValueError("Unknown studio action")
        settings = self.settings(identifier)
        if action != "export":
            settings.update(
                speed=number(speed, 0.75, 1.5, "Speed"), outro_seconds=number(outro, 0, 15, "Outro")
            )
        request = {"settings": settings, "source": fingerprint(self.source(identifier))}
        if action == "export":
            request["edition"] = read_object(self.output / identifier / "latest.json")
        return request

    def plan(self, identifier: str, action: str, request: dict) -> str:
        settings = request["settings"]
        if action == "export":
            return "Package the currently selected full video and audio with title, description, tags and subtitles. No rendering; pace and outro controls do not affect export. The job stops if the edition changes before export. Review status stays attached to that edition."
        lines = ["Use the preserved narration; no Cloud generation or transcription requests."]
        try:
            directory = self.output / identifier
            latest = read_object(directory / "latest.json")
            edition = packages.relative_edition(directory, latest.get("audio"))
            state = read_object(edition / "production.json")
            valid = cache_valid(edition, state.get("fingerprint"), AUDIO_FILES)
            changed = [
                key
                for key, value in settings.items()
                if key != "video" and state.get("settings", {}).get(key) != value
            ]
            if not valid:
                lines.append(
                    "The latest audio is incomplete or changed; production will validate and repair the requested edition."
                )
            elif changed:
                lines.append(
                    "Sound changes: "
                    + ", ".join(changed)
                    + ". Finish audio and retime captions; an existing matching edition may be reused."
                )
            else:
                lines.append(
                    "The latest edition has matching sound settings. The worker verifies source, toolchain and cache hashes before reuse."
                )
        except (ValueError, OSError, TypeError, KeyError):
            lines.append("No usable local edition: finish audio and retime captions.")
        if action != "audio":
            lines.append(
                "Render a 10-second video preview."
                if action == "preview"
                else "Produce the full video and thumbnail."
            )
            lines.append(
                "The video engine verifies artwork, renderer, sound and caption identities before cache reuse."
            )
        lines.append(
            "Keep the published episode unchanged; new editions need listening and caption review."
        )
        return "\n\n".join(lines)

    def run(
        self,
        identifier: str,
        action: str,
        request: dict,
        directory: Path,
        emit: Callable[[str, str], None],
    ) -> str:
        if action not in ACTIONS:
            raise ValueError("Unknown studio action")
        if fingerprint(self.source(identifier)) != request["source"]:
            raise ValueError(
                "Episode source changed after this job was queued. Inspect a fresh plan."
            )
        config = directory / "settings.json"
        write_json(config, request["settings"])
        load_settings(
            config, identifier
        )  # Validate the immutable worker recipe before media writes.
        args = argparse.Namespace(
            episode=identifier,
            config=config,
            output_dir=self.output,
            audio_only=action == "audio",
            preview_seconds=10 if action == "preview" else None,
            audio_jobs=1,
            video_workers=None,
            browser_executable=None,
            upload_dir=None,
            metadata=None,
        )
        emit("preflight", "Checking episode source, recipe and installed tools")
        if action == "export":
            if read_object(self.output / identifier / "latest.json") != request["edition"]:
                raise ValueError(
                    "Completed edition changed after planning export. Inspect a fresh plan."
                )
            emit("export", "Verifying and packaging the selected full edition")
            packages.export(args, self.root)
            return str(self.root / "artifacts/uploads" / identifier)
        runner.produce(args, self.root)
        latest = read_object(self.output / identifier / "latest.json")
        kind = "audio" if action == "audio" else "preview" if action == "preview" else "video"
        return str(
            packages.relative_edition(self.output / identifier, latest[kind], video=kind != "audio")
        )
