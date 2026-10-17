"""Read-only readiness/preflight adapter over existing media and release checks.

Slow media checks run on explicit refresh, selection and state transitions, never
on each queue poll. The returned value is a checked snapshot, not a durable grant.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
from pathlib import Path

from field_notes_audio.locks import RecordingBusy, run_lock
from field_notes_audio.production import packages, runner, sources
from field_notes_audio.production.config import audio_settings, validate_settings
from field_notes_audio.production.editions import fingerprint
from field_notes_audio.production.metadata import load_metadata, publishing_copy
from field_notes_audio.production.toolchain import inspect_audio_toolchain
from field_notes_audio.storage import digest_file, read_object
from field_notes_studio.readiness_models import Readiness, plain, technical


def recipe(pipeline, values: dict) -> dict:
    return validate_settings(copy.deepcopy(values), pipeline.root / "audio/production")


def source_check(pipeline, episode):
    entry = pipeline.source(episode)
    # The catalog validates provenance. Also check the preserved narration bytes,
    # rather than accepting a job result or a file's mere existence as readiness.
    for key, expected in {"audio": entry["audio_sha256"], **entry["files_sha256"]}.items():
        path = sources.media_path(pipeline.root, entry[key])
        if path.is_symlink() or digest_file(path) != expected:
            raise ValueError(f"Preserved {key} is missing or changed. Inspect preparation.")
    return entry


def copy_content(root, edition):
    config = load_metadata(root / "audio/production/publishing.json")
    settings = edition.state["settings"]
    credit = settings["music_credit"] if settings["music_mode"] != "none" else "No music."
    text = publishing_copy(config, edition.source, credit)
    return {
        "title.txt": text.title + "\n",
        "description.txt": text.description + "\n",
        "tags.txt": ", ".join(text.tags) + "\n",
        "hashtags.txt": " ".join(text.hashtags) + "\n",
    }


def preflight(pipeline, episode: str, action: str, request: dict) -> None:
    """Check only prerequisites for the requested action; never install anything."""
    entry = source_check(pipeline, episode)
    if fingerprint(entry) != request["source"]:
        raise ValueError("Source changed during preflight. Inspect again.")
    if action == "export":
        # Export needs saved/approved media and FFprobe, not Node or a renderer.
        with packages.locked_editions([entry], pipeline.output, full_video=True) as editions:
            edition = editions[0]
            if read_object(edition.directory / "latest.json") != request["edition"]:
                raise ValueError("Saved edition changed during preflight. Inspect export again.")
            if packages.review_status(edition, True) != "approved":
                raise ValueError(
                    "Review the full episode once before exporting its release package."
                )
            copy_content(pipeline.root, edition)
            uploads = pipeline.root / "artifacts/uploads"
            if uploads.exists():
                with run_lock(uploads, "export preflight"):
                    packages.check_upload_destinations(uploads, [entry])
        return
    recipe(pipeline, request["settings"])
    runner.preflight(
        pipeline.root,
        argparse.Namespace(audio_only=action == "audio", browser_executable=None),
    )
    if action != "audio":
        checked_assets(pipeline.root, entry)


def checked_assets(root, entry):
    from field_notes_audio.production.video import visual_assets

    assets = visual_assets(root, entry)
    for name, path in assets.items():
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Video artwork is missing or outside this checkout: {name}")
    return assets


def expected_video_identity(root, entry, edition, settings):
    """Read the existing renderer's content identity without requiring Node to export."""
    renderer = root / "video"
    code = {
        str(p.relative_to(renderer)): digest_file(p)
        for p in [
            *renderer.glob("*.mjs"),
            *renderer.glob("*.json"),
            *renderer.joinpath("src").rglob("*"),
        ]
        if p.is_file()
    }
    code["python-video"] = digest_file(Path(runner.__file__).parent / "video.py")
    state = read_object(edition / "production.json")
    return fingerprint(
        {
            "audio": state["fingerprint"],
            "master_sha256": digest_file(edition / "master.wav"),
            "cues_sha256": digest_file(edition / "cues.json"),
            "timeline": state["timeline_duration_seconds"],
            "assets": {
                name: digest_file(path) for name, path in checked_assets(root, entry).items()
            },
            "renderer": code,
            "video": settings["video"],
            "preview_seconds": None,
        }
    )


def expected_audio_identity(entry, settings):
    # Keep this aligned with produce_audio without changing the engine code/hash
    # and thereby invalidating every pre-existing recording for a UI-only change.
    toolchain = inspect_audio_toolchain()
    return fingerprint(
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
            "settings": audio_settings(settings),
            "implementation": dict(toolchain.implementation),
            "encoder": toolchain.encoder,
            "music_sha256": digest_file(Path(settings["music_file"]))
            if settings["music_file"]
            else None,
        }
    )


def inspect(pipeline, episode: str, settings: dict) -> Readiness:
    """Verify source, saved edition/review and package copy, preserving partial evidence."""
    stages = [
        "Recording: unchecked",
        "Full episode: unchecked",
        "Review: unchecked",
        "Package: unchecked",
    ]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def result(action, title, detail, evidence=None, error=None, context=""):
        return Readiness(
            episode,
            action,
            title,
            plain(error, context) if error is not None else detail,
            tuple(stages),
            fingerprint(evidence) if evidence else "",
            checked_at=stamp,
            technical=technical(error) if error is not None else "",
        )

    try:
        desired = recipe(pipeline, settings)
        entry = source_check(pipeline, episode)
        stages[0] = "Recording: verified"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return result("repair", "Inputs need attention", "", error=exc, context="inputs")

    evidence = {"source": fingerprint(entry), "recipe": desired}
    pointer = pipeline.output / episode / "latest.json"
    if not pointer.exists():
        stages[1:] = ["Full episode: not produced", "Review: not yet", "Package: not yet"]
        return result(
            "produce",
            "Ready to produce",
            "One job finishes audio, captions, full video and thumbnail.",
            evidence,
        )
    try:
        with packages.locked_editions([entry], pipeline.output, full_video=True) as editions:
            edition = editions[0]
            evidence["edition"] = pipeline.review_identity(edition)
            stages[1] = "Full episode: verified"
            approved = packages.review_status(edition, True) == "approved"
            evidence["approved"] = approved
            stages[2] = "Review: approved" if approved else "Review: needed"
            # The saved edition may be entirely valid but not match the edited recipe.
            # Never carry its approval to that pending recipe or relabel it as damaged.
            rendered = read_object(edition.video / "render.json")
            differences = [
                key
                for key, value in audio_settings(desired).items()
                if edition.state["settings"].get(key) != value
            ]
            differences.extend(
                "video." + key
                for key in ("width", "height", "fps")
                if rendered.get(key) != desired["video"][key]
            )
            if (
                not differences
                and expected_audio_identity(entry, desired) != edition.state["fingerprint"]
            ):
                differences.append("audio source, music bytes or processing implementation")
            if (
                not differences
                and expected_video_identity(pipeline.root, entry, edition.audio, desired)
                != read_object(edition.video / "production.json")["fingerprint"]
            ):
                differences.append("video recipe, artwork or renderer")
            if differences:
                stages[1] = "Full episode: saved; draft differs"
                return result(
                    "produce",
                    "Draft differs from saved episode",
                    "Changed: "
                    + ", ".join(differences)
                    + ". Existing media and approval stay intact.",
                    evidence,
                )
            if not approved:
                return result(
                    "review",
                    "Ready for one full review",
                    "Watch and listen, check subtitles, then approve the exact saved edition.",
                    evidence,
                )
            try:
                expected_copy = copy_content(pipeline.root, edition)
            except (OSError, ValueError) as exc:
                return result(
                    "repair", "Publishing copy needs attention", "", evidence, exc, "copy"
                )
            evidence["copy"] = expected_copy
    except RecordingBusy as exc:
        return result("check", "Saved files are in use", "", evidence, exc, "busy")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        stages[1] = "Full episode: unavailable"
        return result("produce", "Full edition needs production", "", evidence, exc, "edition")

    try:
        package = pipeline.package_snapshot(episode)
        evidence["package"] = package.identity
        stages[3] = "Package: " + package.status
        if package.status != "ready":
            return result("export", "Export the reviewed episode", package.summary, evidence)
        directory = pipeline.root / "artifacts/uploads" / episode
        with run_lock(directory.parent, "readiness package"):
            _, manifest = pipeline._upload_manifest(episode)
            if fingerprint(manifest) != package.identity:
                raise ValueError("Package changed while checking. Refresh readiness.")
            if any(
                (directory / name).read_text(encoding="utf-8") != text
                for name, text in expected_copy.items()
            ):
                stages[3] = "Package: upload copy changed"
                return result(
                    "export",
                    "Upload package needs refreshing",
                    "Full episode remains approved. Export to include the current saved title, description and tags.",
                    evidence,
                )
        # Recheck cheap pointers/config after slow file verification. Each action
        # will repeat its own checks, so this card never serves as authorization.
        if fingerprint(pipeline.source(episode)) != evidence["source"]:
            raise ValueError("Source changed while checking. Refresh readiness.")
        if read_object(pointer).get("video") != str(edition.video.relative_to(edition.directory)):
            raise ValueError("Edition changed while checking. Refresh readiness.")
        if copy_content(pipeline.root, edition) != expected_copy:
            raise ValueError("Publishing settings changed while checking. Refresh readiness.")
        stages[3] = "Package: current and verified"
        return result(
            "package",
            "Ready for manual upload",
            "Media, full review and upload copy match. Publication on an external platform is not verified.",
            evidence,
        )
    except RecordingBusy as exc:
        return result("check", "Package check is waiting", "", evidence, exc, "busy")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        stages[3] = "Package: needs attention"
        return result("export", "Refresh the upload package", "", evidence, exc, "package")
