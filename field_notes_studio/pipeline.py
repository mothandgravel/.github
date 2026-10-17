"""Anti-corruption adapter: the only studio module that calls production APIs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import re
import subprocess
import tempfile
from collections.abc import Callable
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

from field_notes_audio import site
from field_notes_audio.locks import RecordingBusy, run_lock
from field_notes_audio.production import packages, runner, sources
from field_notes_audio.production.config import load_settings, number, validate_settings
from field_notes_audio.production.editions import AUDIO_FILES, cache_valid, fingerprint
from field_notes_audio.production.metadata import load_metadata, publishing_copy
from field_notes_audio.storage import digest_file, read_object, write_json
from field_notes_studio.models import (
    ACTIONS,
    Episode,
    PackageFile,
    PackageSnapshot,
    ReleaseDetails,
    ReviewSnapshot,
)

PACKAGE_MEDIA = {
    "episode.mp4": "Video",
    "thumbnail.png": "Thumbnail",
    "captions.srt": "Subtitles · SRT",
    "captions.vtt": "Subtitles · VTT",
    "episode.mp3": "Podcast audio",
    "transcript.txt": "Transcript",
}


class Pipeline:
    def __init__(self, root: Path):
        self.root = root
        self.output = root / "artifacts/production"

    def entries(self) -> list[dict]:
        return sources.load_entries(self.root)

    def catalog(self) -> list[Episode]:
        episodes = []
        for entry in self.entries():
            link, published = self.publication_defaults(entry)
            episodes.append(
                Episode(
                    entry["id"],
                    entry["title"],
                    entry["duration_seconds"],
                    sources.media_path(self.root, entry["transcript"]).read_text(encoding="utf-8"),
                    link,
                    published,
                    (
                        "Private narrated note; not published or reviewed."
                        if entry.get("local_prepared")
                        else "Podcast catalog in this checkout; external platforms have not been checked."
                    ),
                    podcast_url=link,
                    podcast_date=published,
                    written_url=site.DOMAIN
                    + (
                        "/notes/" + entry["slug"] if entry.get("slug") else "/notes/#listen-archive"
                    ),
                )
            )
        return episodes

    def stage_hints(self) -> dict[str, str]:
        """A cheap next-step hint per episode from saved pointers, without hashing media.

        "Produce" when no full version is saved, "Review" until a review record
        says approved, then "Release". Catalog episodes with a podcast destination
        and no local version are "In feed". Readiness re-verifies everything.
        """
        hints = {}
        for entry in self.entries():
            identifier = entry["id"]
            pointer = self.output / identifier / "latest.json"
            try:
                if not pointer.is_file():
                    link, _ = self.publication_defaults(entry)
                    hints[identifier] = "In feed" if link else "Produce"
                    continue
                latest = read_object(pointer)
                audio = (self.output / identifier / str(latest.get("audio", ""))).resolve()
                if not audio.is_relative_to((self.output / identifier).resolve()):
                    raise ValueError("Saved version pointer leaves the episode folder")
                review = audio / "review.json"
                approved = review.is_file() and read_object(review).get("status") == "approved"
                hints[identifier] = "Release" if approved and latest.get("video") else "Review"
            except (OSError, ValueError, TypeError):
                hints[identifier] = "Check"
        return hints

    @staticmethod
    def publication_defaults(entry: dict) -> tuple[str, str]:
        if entry.get("local_prepared"):
            return "", ""
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
                message = "Saved upload text changed. Make the upload folder again to repair it."
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
                "Saved upload folder text (checksummed). Make the upload folder again to apply later changes; approval stays in Review.",
            )
        config = load_metadata(self.root / "audio/production/publishing.json")
        settings = self.settings(identifier)
        basis = "Draft copy from the show's publishing settings. Produce the episode to confirm its music credit."
        if (self.output / identifier / "latest.json").exists():
            with packages.locked_editions([entry], self.output, full_video=False) as editions:
                settings = editions[0].state["settings"]
                basis = (
                    "Copy from the show's publishing settings and the saved audio's music credit."
                )
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

    def metadata_editor(self, identifier: str) -> dict:
        path = self.root / "audio/production/publishing.json"
        (self.root / "artifacts/studio/publishing").mkdir(parents=True, exist_ok=True)
        with run_lock(self.root / "artifacts/studio/publishing", "publishing settings"):
            config = load_metadata(path)
            baseline = digest_file(path)
        entry = self.source(identifier)
        override = config["episodes"].get(identifier, {})
        values = {
            "title": override.get("title", entry["title"]),
            "description": override.get("description", entry["description"]),
            "tags": ", ".join(override.get("tags", [])),
            "hashtags": " ".join(override.get("hashtags", [])),
            "show_title": config["show"]["title"],
            "show_description": config["show"]["description"],
            "shared_tags": ", ".join(config["shared_tags"]),
            "shared_hashtags": " ".join(config["shared_hashtags"]),
        }
        return {"baseline": baseline, "values": values}

    def health(self) -> str:
        lines = []

        def preflight(audio_only, name):
            try:
                runner.preflight(
                    self.root, argparse.Namespace(audio_only=audio_only, browser_executable=None)
                )
                lines.append(f"{name} checks: ready")
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                lines.append(f"{name} checks: {exc}")

        preflight(True, "Audio")
        preflight(False, "Full video")
        try:
            load_metadata(self.root / "audio/production/publishing.json")
            for entry in self.entries():
                self.settings(entry["id"])
            lines.append("Production and publishing settings: valid")
        except (OSError, ValueError) as exc:
            lines.append(f"Settings: {exc}")
        return "\n".join(lines)

    def save_metadata(self, identifier: str, snapshot: dict) -> dict:
        """Validate the whole template before atomically replacing shared settings."""
        path = self.root / "audio/production/publishing.json"
        with run_lock(self.root / "artifacts/studio/publishing", "publishing settings"):
            if digest_file(path) != snapshot["baseline"]:
                raise ValueError(
                    "Publishing settings changed elsewhere. Reload saved settings, then reapply your edits."
                )
            config = copy.deepcopy(load_metadata(path))
            values = snapshot["values"]
            config["show"] = {
                "title": values["show_title"],
                "description": values["show_description"],
            }
            config["shared_tags"] = [
                item.strip() for item in values["shared_tags"].split(",") if item.strip()
            ]
            config["shared_hashtags"] = values["shared_hashtags"].split()
            config["episodes"][identifier] = {
                "title": values["title"],
                "description": values["description"],
                "tags": [item.strip() for item in values["tags"].split(",") if item.strip()],
                "hashtags": values["hashtags"].split(),
            }
            with tempfile.TemporaryDirectory() as temporary:
                candidate = Path(temporary) / "publishing.json"
                write_json(candidate, config)
                validated = load_metadata(candidate)
                # Shared template edits must remain exportable for every episode.
                entries = self.entries()
                if not any(entry["id"] == identifier for entry in entries):
                    entries = [*entries, self.source(identifier)]
                for entry in entries:
                    source = site.source_entry(entry)
                    settings = self.settings(source["id"])
                    publishing_copy(
                        validated,
                        source,
                        settings["music_credit"]
                        if settings["music_mode"] != "none"
                        else "No music.",
                    )
            if digest_file(path) != snapshot["baseline"]:
                raise ValueError(
                    "Publishing settings changed during validation. Reload saved settings before saving again."
                )
            write_json(path, validated)
            # Return the identity of this write while still owning the lock. Reading
            # again after release could attach another window's identity to our text.
            return {"baseline": digest_file(path), "values": dict(values)}

    def _upload_manifest(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier
        ):
            raise ValueError("Choose a prepared episode")
        directory = self.root / "artifacts/uploads" / identifier
        path = directory / "upload.json"
        manifest = read_object(path)
        if (
            directory.is_symlink()
            or path.is_symlink()
            or type(manifest.get("schema_version")) is not int
            or manifest["schema_version"] != 1
            or manifest.get("episode") != identifier
            or not isinstance(manifest.get("files"), dict)
            or set(manifest["files"]) != packages.UPLOAD_FILES
            or not isinstance(manifest.get("review_status"), str)
            or manifest["review_status"] not in {"pending", "approved"}
            or not isinstance(manifest.get("fingerprint"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", manifest["fingerprint"])
            or type(manifest.get("default_playback_rate")) is not int
            or manifest["default_playback_rate"] != 1
        ):
            raise ValueError("The upload folder is damaged. Make the upload folder again.")
        return directory, manifest

    def package_snapshot(self, identifier: str) -> PackageSnapshot:
        entry = self.source(identifier)
        uploads = self.root / "artifacts/uploads"
        if not (uploads / identifier / "upload.json").exists():
            return PackageSnapshot(
                identifier,
                "",
                "missing",
                "No upload folder yet. Produce and review the full episode, then choose Make upload folder.",
            )
        with ExitStack() as stack:
            edition, problem = None, ""
            try:
                edition = stack.enter_context(
                    packages.locked_editions([entry], self.output, full_video=True)
                )[0]
            except RecordingBusy:
                raise  # Temporary ownership is not an unverifiable portable edition.
            except (ValueError, OSError) as exc:
                problem = str(exc)
            # Same lock order as export: production first, then upload files.
            with run_lock(uploads, "upload package check"):
                directory, manifest = self._upload_manifest(identifier)
                if not packages.upload_valid(directory, manifest["fingerprint"]):
                    raise ValueError(
                        "Upload files are missing or changed. Make the upload folder again."
                    )
                files = tuple(
                    PackageFile(
                        name, purpose, (directory / name).stat().st_size, str(directory / name)
                    )
                    for name, purpose in PACKAGE_MEDIA.items()
                )
                status, summary = (
                    "unverified",
                    "Files checked; the current version is unavailable: " + problem,
                )
                if edition is not None:
                    expected = {
                        name: edition.state["files"][name]
                        for name in PACKAGE_MEDIA
                        if name not in {"episode.mp4", "thumbnail.png"}
                    }
                    expected.update(
                        {
                            name: edition.video_state["files"][name]
                            for name in ("episode.mp4", "thumbnail.png")
                        }
                    )
                    current = (
                        manifest.get("audio_fingerprint") == edition.state["fingerprint"]
                        and manifest.get("video_fingerprint") == edition.video_state["fingerprint"]
                        and all(
                            manifest["files"][name] == value for name, value in expected.items()
                        )
                    )
                    if not current:
                        status, summary = (
                            "stale",
                            "This upload folder holds an older or different version. Make the upload folder again for the latest media.",
                        )
                    elif packages.review_status(edition, True) != "approved":
                        status, summary = (
                            "review",
                            "Files match the saved version, but its review is pending. Review the full episode, then make the upload folder again.",
                        )
                    elif manifest["review_status"] != "approved":
                        status, summary = (
                            "stale",
                            "The full episode is approved; make the upload folder again to include that approval.",
                        )
                    else:
                        status, summary = (
                            "ready",
                            "Files checked · current full version · approved. Ready to upload by hand; Studio does not check the platform.",
                        )
                link, published = self.publication_defaults(entry)
                details = ReleaseDetails(
                    *(
                        (directory / name).read_text(encoding="utf-8").removesuffix("\n")
                        for name in ("title.txt", "description.txt", "tags.txt", "hashtags.txt")
                    ),
                    link,
                    published,
                    "Saved upload folder text (checksummed). Media and review status is shown under Files.",
                )
                return PackageSnapshot(
                    identifier, fingerprint(manifest), status, summary, files, details
                )

    def package_file(self, snapshot: PackageSnapshot, name: str) -> Path:
        if not snapshot.identity or name not in PACKAGE_MEDIA:
            raise ValueError("Choose a checked upload file first")
        try:
            with run_lock(self.root / "artifacts/uploads", "upload package check"):
                directory, manifest = self._upload_manifest(snapshot.episode)
                path = directory / name
                if (
                    fingerprint(manifest) != snapshot.identity
                    or path.is_symlink()
                    or digest_file(path) != manifest["files"][name]
                ):
                    raise ValueError(
                        "The upload folder changed after checking. Check the files again before copying a path."
                    )
                return path
        except OSError as exc:
            raise ValueError(
                "Upload files are unavailable. Check the files again before copying a path."
            ) from exc

    def preflight(self, identifier, action, request):
        from field_notes_studio.readiness import preflight
        from field_notes_studio.readiness_models import ReadinessBusy

        try:
            preflight(self, identifier, action, request)
        except RecordingBusy as exc:
            raise ReadinessBusy(str(exc)) from exc

    def spend_summary(self, identifier: str) -> str:
        """One line about uncertain paid attempts for a failure view; empty when none."""
        from field_notes_audio import spend_guard

        return spend_guard.summary_line(self.root / "artifacts/audio", identifier)

    def readiness(self, identifier, settings):
        from field_notes_studio.readiness import inspect

        return inspect(self, identifier, settings)

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
                "",
                "No saved version yet. Produce episode makes audio, captions, full video and thumbnail together.",
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
                    f"Saved version: {edition.audio.name} · {settings['speed']:g}× pace · "
                    f"{settings['outro_seconds']:g}s outro\n"
                )
                if status == "approved":
                    detail += (
                        "Approved. Next: make the upload folder."
                        if full_video
                        else "Approved. For YouTube, produce and review the full episode, then make the upload folder."
                    )
                else:
                    detail += (
                        "Watch and listen to the full episode, check its subtitles, then approve all three at once."
                        if full_video
                        else "Listen to the audio, check its subtitles, then approve."
                    )
                return ReviewSnapshot(
                    self.review_identity(edition),
                    detail,
                    str(edition.audio / "episode.mp3"),
                    str(edition.audio / "captions.srt"),
                    str(edition.video / "episode.mp4") if edition.video else "",
                    full_video,
                    approved=status == "approved",
                )
        except (ValueError, OSError) as exc:
            return ReviewSnapshot("", f"Review unavailable: {exc}")

    def approve(self, identifier: str, expected: ReviewSnapshot, reviewer: str) -> None:
        if not expected.identity:
            raise ValueError("Load a finished version before reviewing it")
        with packages.locked_editions(
            [self.source(identifier)],
            self.output,
            expected.full_video,
            inspect_video=expected.full_video,
        ) as editions:
            edition = editions[0]
            if self.review_identity(edition) != expected.identity:
                raise ValueError(
                    "The version changed while you were reviewing. Check again and review the new files."
                )
            if not expected.full_video and packages.review_status(edition) == "approved":
                # An optional audio-only recheck must not erase the existing fuller
                # approval for these exact audio bytes. The identity is checked above.
                return
            packages.record_review(edition, reviewer)

    def request(
        self,
        identifier: str,
        action: str,
        speed: float | None,
        outro: float | None,
        sound: dict | None = None,
        recipe: dict | None = None,
    ) -> dict:
        if action not in ACTIONS:
            raise ValueError("Unknown studio action")
        settings = (
            copy.deepcopy(recipe)
            if recipe is not None and action != "export"
            else self.settings(identifier)
        )
        if action != "export":
            if sound is not None:
                allowed = {
                    "intro_seconds",
                    "music_overlap_seconds",
                    "music_gain_db",
                    "target_lufs",
                    "true_peak_db",
                    "music_mode",
                    "music_file",
                    "music_credit",
                }
                if sound.keys() - allowed:
                    raise ValueError("Unknown sound control")
                settings.update(sound)
            settings.update(
                speed=number(speed, 0.75, 1.5, "Speed"), outro_seconds=number(outro, 0, 15, "Outro")
            )
            validate_settings(settings, self.root / "audio/production")
        request = {"settings": settings, "source": fingerprint(self.source(identifier))}
        if action == "export":
            request["edition"] = read_object(self.output / identifier / "latest.json")
        return request

    def plan(self, identifier: str, action: str, request: dict) -> str:
        settings = request["settings"]
        if action == "export":
            return "Make the upload folder from the saved full video and audio, with title, description, tags and subtitles. Nothing is rendered; pace and outro do not apply. The job stops if the version changes first. The approval stays with that version."
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
                    "The latest audio is incomplete or changed; production checks and repairs it for this version."
                )
            elif changed:
                lines.append(
                    "Sound changes: "
                    + ", ".join(changed)
                    + ". Finish audio and retime captions; an existing matching edition may be reused."
                )
            else:
                lines.append(
                    "The latest version has the same sound settings. The background producer checks the note, tools and saved files before reusing them."
                )
        except (ValueError, OSError, TypeError, KeyError):
            lines.append("No usable saved version: finish audio and retime captions.")
        if action != "audio":
            lines.append(
                "Render a 10-second video preview."
                if action == "preview"
                else "Produce the full video and thumbnail."
            )
            lines.append(
                "The video engine verifies artwork, renderer, sound and caption identities before cache reuse."
            )
        lines.append("The published episode stays unchanged; a new version needs its own review.")
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
        emit("preflight", "Checking the note, its show settings and installed tools")
        if action == "export":
            if read_object(self.output / identifier / "latest.json") != request["edition"]:
                raise ValueError(
                    "The finished version changed after this plan was checked. Check the plan again."
                )
            emit("export", "Checking the full version and making its upload folder")
            packages.export(args, self.root, expected_edition=request["edition"])
            return str(self.root / "artifacts/uploads" / identifier)
        runner.produce(args, self.root)
        latest = read_object(self.output / identifier / "latest.json")
        kind = "audio" if action == "audio" else "preview" if action == "preview" else "video"
        return str(
            packages.relative_edition(self.output / identifier, latest[kind], video=kind != "audio")
        )
