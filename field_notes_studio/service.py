"""Application use cases; orchestration without widget access or media processing."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from field_notes_studio.pipeline import Pipeline
from field_notes_studio.processes import launch_worker, open_path
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
                publication_url=publications.get(episode.identifier, ("", ""))[0],
                publication_date=publications.get(episode.identifier, ("", ""))[1],
            )
            for episode in self.pipeline.catalog()
        ]

    def plan(self, episode: str, action: str, speed: float, outro: float) -> tuple[dict, str]:
        request = self.pipeline.request(episode, action, speed, outro)
        return request, self.pipeline.plan(episode, action, request)

    def settings(self, episode: str) -> dict:
        settings = self.pipeline.settings(episode)
        for job in self.repository.jobs():
            if job.episode == episode and job.action != "export":
                saved = json.loads(job.request)["settings"]
                settings.update(speed=saved["speed"], outro_seconds=saved["outro_seconds"])
                break
        return settings

    def retry(self, identifier: str) -> str:
        job = self.repository.get(identifier)
        if job.status not in {"failed", "interrupted", "cancelled"}:
            raise ValueError("Only failed, interrupted or stopped jobs can be retried")
        return self.submit(job.episode, job.action, json.loads(job.request))

    def submit(self, episode: str, action: str, request: dict) -> str:
        # Spawn before persisting; if process creation fails no orphan request is queued.
        launch_worker(self.root)
        return self.repository.submit(episode, action, request)

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
            date.fromisoformat(published)
        self.repository.publication(episode, url.strip(), published.strip())

    def open_output(self, episode: str, kind: str) -> None:
        open_path(self.pipeline.output_path(episode, kind))
