"""Preparation use cases; explicit authorization is separate from offline inspection."""

import json
from dataclasses import replace

from field_notes_studio.preparation_jobs import PreparationJobs
from field_notes_studio.processes import launch_worker
from field_notes_studio.repository import Repository


class PreparationService:
    def __init__(self, root):
        self.root = root
        self.adapter = PreparationJobs(root)
        self.repository = Repository(root / "artifacts/studio/studio.sqlite3")

    def catalog(self):
        jobs = self.repository.jobs()
        active = {
            job.episode: job for job in jobs if job.status in {"queued", "running", "waiting"}
        }
        values = []
        for item in self.adapter.preparation.catalog():
            job = active.get(item.episode)
            if job is not None:
                item = replace(
                    item,
                    state="Preparation " + job.status,
                    detail=f"{item.episode} has saved {job.status} work. Use the main queue for its status, history and Resume.",
                )
            values.append(item)
        return values

    def inspect(self, note):
        snapshot = self.adapter.inspect(note)
        if any(
            job.episode == snapshot.episode and job.status in {"queued", "running", "waiting"}
            for job in self.repository.jobs()
        ):
            return replace(
                snapshot,
                request_json="",
                summary=snapshot.summary
                + "\n\nThis episode already has active or waiting preparation. Use its main-queue controls; no second job will be queued.",
            )
        return snapshot

    def submit(self, snapshot, authorized: bool):
        if authorized is not True or not snapshot.request_json:
            raise ValueError(
                "Inspect preparation and explicitly authorize the captured service requests first"
            )
        request = json.loads(snapshot.request_json)
        if snapshot.note != request["note"] or snapshot.episode != request["episode"]:
            raise ValueError("Preparation selection changed")
        self.adapter.validate(request)
        launch_worker(self.root)
        return self.repository.submit(snapshot.episode, "prepare", request)
