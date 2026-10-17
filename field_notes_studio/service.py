"""Application use cases; orchestration without widget access or media processing."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from field_notes_studio.health import restart, tool_status, worker_status
from field_notes_studio.job_history import resolved_failures
from field_notes_studio.models import ReviewSnapshot
from field_notes_studio.pipeline import Pipeline
from field_notes_studio.preparation_jobs import PreparationJobs
from field_notes_studio.processes import launch_worker, open_path, open_publisher, upload_path
from field_notes_studio.repository import Repository


class Studio:
    def __init__(self, root: Path):
        self.root = root
        self.repository = Repository(root / "artifacts/studio/studio.sqlite3")
        self.pipeline = Pipeline(root)

    def catalog(self):
        publications = self.repository.publications()
        return [
            replace(
                episode,
                publication_url=publications.get(
                    episode.identifier, (episode.publication_url, episode.publication_date)
                )[0],
                publication_date=publications.get(
                    episode.identifier, (episode.publication_url, episode.publication_date)
                )[1],
                publication_source=(
                    "Your saved release record"
                    if episode.identifier in publications
                    else episode.publication_source
                ),
                publication_saved=episode.identifier in publications,
            )
            for episode in self.pipeline.catalog()
        ]

    def health(self) -> str:
        worker = worker_status(self.repository)
        return worker["message"] + "\n\n" + self.pipeline.health() + "\n\n" + tool_status(self.root)

    def restart_worker(self):
        return restart(self.repository, self.root)

    def open_draft_recovery(self):
        directory = self.repository.path.parent / "draft-recovery"
        directory.mkdir(parents=True, exist_ok=True)
        open_path(directory)

    def plan(
        self,
        episode: str,
        action: str,
        speed: float | None,
        outro: float | None,
        sound: dict | None = None,
        recipe: dict | None = None,
    ) -> tuple[dict, str]:
        request = self.pipeline.request(episode, action, speed, outro, sound, recipe)
        return request, self.pipeline.plan(episode, action, request)

    def checked_plan(self, episode, action, speed, outro, sound=None, recipe=None):
        request, summary = self.plan(episode, action, speed, outro, sound, recipe)
        self.pipeline.preflight(episode, action, request)
        return request, "Preflight passed for this action.\n\n" + summary

    def spend_summary(self, episode: str) -> str:
        return self.pipeline.spend_summary(episode)

    def readiness(self, episode, settings):
        from field_notes_studio.readiness_models import (
            Readiness,
            ReadinessBusy,
            plain,
            technical,
        )

        def active():
            return next(
                (
                    j
                    for j in self.repository.jobs()
                    if j.episode == episode and j.status in {"queued", "running", "waiting"}
                ),
                None,
            )

        job = active()
        if job is None:
            value = self.pipeline.readiness(episode, settings)
            job = active()
            if job is None:
                if value.action in {"produce", "export"}:
                    action = "video" if value.action == "produce" else "export"
                    try:
                        request = self.pipeline.request(
                            episode,
                            action,
                            settings.get("speed"),
                            settings.get("outro_seconds"),
                            recipe=settings,
                        )
                        self.pipeline.preflight(episode, action, request)
                    except ReadinessBusy as exc:
                        value = replace(
                            value,
                            action="check",
                            title="Files are in use",
                            detail=plain(exc, "busy"),
                            technical=technical(exc),
                        )
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        value = replace(
                            value,
                            action="health",
                            title="Preflight needs attention",
                            detail=plain(exc, "preflight"),
                            technical=technical(exc),
                        )
                # A different window may have queued this episode during preflight.
                job = active()
                if job is None:
                    return value
        return Readiness(
            episode,
            "job",
            "Episode work is " + job.status,
            "Follow the existing job; do not queue another copy. Saved media and review are checked when the job finishes.",
            job=job.identifier,
        )

    def settings(self, episode: str) -> dict:
        settings = self.pipeline.settings(episode)
        saved = self.repository.latest_recipe(episode)
        if saved is not None:
            settings.update(saved)
        return settings

    def retry(self, identifier: str) -> str:
        job = self.repository.get(identifier)
        if job.status not in {"failed", "interrupted", "cancelled", "waiting"}:
            raise ValueError("Only failed, interrupted or stopped jobs can be retried")
        if identifier in resolved_failures(self.repository.jobs()):
            raise ValueError(
                "A later attempt completed. Use the ready episode instead of retrying this historical failure."
            )
        request = json.loads(job.request)
        if job.action == "prepare":
            if request.get("spend_override"):
                raise ValueError(
                    "A spend-limit override covers one run only. Inspect preparation again and "
                    "confirm a new override if you still accept the possible charge."
                )
            if request.get("uncertain_chunks"):
                raise ValueError(
                    "Inspect preparation recovery again. A previous resend authorization cannot authorize another attempt."
                )
            PreparationJobs(self.root).validate(request)
            if job.status == "waiting":
                launch_worker(self.root)
                return self.repository.resume_preparation(identifier)
        return self.submit(job.episode, job.action, request)

    def submit(self, episode: str, action: str, request: dict) -> str:
        # Spawn before persisting; if process creation fails no orphan request is queued.
        launch_worker(self.root)
        return self.repository.submit(episode, action, request)

    def batch_plan(self, identifiers: list[str], action: str):
        if not identifiers or len(identifiers) > 32:
            raise ValueError("Choose 1–32 episodes to inspect")
        plans, summaries = [], []
        for identifier in identifiers:
            settings = self.settings(identifier)
            draft = self.repository.state("draft:" + identifier)
            recipe = draft.get("recipe", {})
            speed = float(recipe.get("speed", settings["speed"])) if action != "export" else None
            outro = (
                float(recipe.get("outro", settings["outro_seconds"]))
                if action != "export"
                else None
            )
            sound = (
                draft.get(
                    "sound",
                    {
                        key: settings[key]
                        for key in (
                            "intro_seconds",
                            "music_overlap_seconds",
                            "music_gain_db",
                            "target_lufs",
                            "true_peak_db",
                            "music_mode",
                            "music_file",
                            "music_credit",
                        )
                    },
                )
                if action != "export"
                else None
            )
            if sound:
                sound = dict(sound)
                for key in (
                    "intro_seconds",
                    "music_overlap_seconds",
                    "music_gain_db",
                    "target_lufs",
                    "true_peak_db",
                ):
                    sound[key] = float(sound[key])
                if sound["music_mode"] != "file":
                    sound["music_file"] = None
            request, summary = self.checked_plan(
                identifier, action, speed, outro, sound, draft.get("production_base")
            )
            plans.append((identifier, action, request))
            summaries.append(f"{identifier} · {action}\n{summary}")
        return plans, "\n\n".join(summaries)

    def submit_batch(self, plans):
        launch_worker(self.root)
        return self.repository.submit_batch(plans)

    def publication(self, episode: str, url: str, published: str) -> None:
        url, published = url.strip(), published.strip()
        if url:
            parts = urlsplit(url)
            if (
                parts.scheme not in {"https", "http"}
                or not parts.hostname
                or parts.username
                or parts.password
            ):
                raise ValueError("Publication URL must be an http(s) link without credentials")
        if published:
            try:
                if date.fromisoformat(published).isoformat() != published:
                    raise ValueError
            except ValueError:
                raise ValueError(
                    "Publication date must be a real date in YYYY-MM-DD format"
                ) from None
        self.repository.publication(episode, url.strip(), published.strip())

    def open_output(self, episode: str, kind: str) -> None:
        open_path(self.pipeline.output_path(episode, kind))

    def release_details(self, episode: str):
        return self.pipeline.release_details(episode)

    def metadata_editor(self, episode: str):
        return self.pipeline.metadata_editor(episode)

    def save_metadata(self, episode: str, snapshot: dict):
        return self.pipeline.save_metadata(episode, snapshot)

    def package_snapshot(self, episode: str):
        return self.pipeline.package_snapshot(episode)

    def open_package_file(self, snapshot, name: str) -> None:
        open_path(self.pipeline.package_file(snapshot, name))

    def package_upload_path(self, snapshot, name: str) -> str:
        return upload_path(self.pipeline.package_file(snapshot, name))

    def open_publisher(self) -> None:
        open_publisher()

    def open_job_output(self, identifier: str) -> None:
        """Open the selected job's durable result, rather than a moving latest pointer."""
        job = self.repository.get(identifier)
        if job.status != "succeeded" or not job.result:
            raise ValueError("Choose a completed job with saved output")
        directory = Path(job.result).resolve()
        expected = (
            self.root
            / "artifacts"
            / (
                "studio/prepared"
                if job.action == "prepare"
                else "uploads"
                if job.action == "export"
                else "production"
            )
        )
        if not directory.is_relative_to(expected.resolve()):
            raise ValueError("Saved job output is outside the production directory")
        filename = {
            "audio": "episode.mp3",
            "preview": "episode.mp4",
            "video": "episode.mp4",
            "export": "",
            "prepare": "",
        }[job.action]
        open_path(directory / filename if filename else directory)

    def review_snapshot(self, episode: str, full_video: bool = False) -> ReviewSnapshot:
        return self.pipeline.review_snapshot(episode, full_video)

    def approve(self, episode: str, snapshot: ReviewSnapshot, reviewer: str) -> None:
        self.pipeline.approve(episode, snapshot, reviewer)

    def open_review(self, snapshot: ReviewSnapshot, kind: str) -> None:
        path = {"audio": snapshot.audio, "captions": snapshot.captions, "video": snapshot.video}[
            kind
        ]
        if not snapshot.identity or not path:
            raise ValueError("Load a completed edition for this review first")
        open_path(Path(path))
