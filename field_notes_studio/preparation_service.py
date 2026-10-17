"""Preparation use cases; explicit authorization is separate from offline inspection."""

import json
from dataclasses import replace

from field_notes_studio.preparation_jobs import PreparationJobs
from field_notes_studio.preparation_setup import import_setup, preview_setup
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
        latest = {}
        for job in jobs:
            if job.action == "prepare":
                latest.setdefault(job.episode, job)
        ready = self.adapter.ready_episodes()
        values = []
        for item in self.adapter.preparation.catalog():
            job = active.get(item.episode)
            if job is not None:
                state = {
                    "queued": "Queued",
                    "running": "Preparing",
                    "waiting": "Awaiting captions",
                }[job.status]
                item = replace(
                    item,
                    state=state,
                    job_id=job.identifier,
                    detail=(
                        f"{item.episode}: {state}. "
                        + (
                            "Use Resume in the main queue to check the saved caption operation. No new narration."
                            if job.status == "waiting"
                            else "Use Show job to follow progress. Do not queue another copy."
                        )
                    ),
                )
            elif item.episode in ready:
                item = replace(
                    item,
                    state="Ready for production",
                    detail="Narration and captions are ready. Open in production, then Produce episode for audio and video together. Review and publication remain separate.",
                )
            elif (job := latest.get(item.episode)) and job.status in {
                "failed",
                "interrupted",
                "cancelled",
            }:
                item = replace(
                    item,
                    state="Needs recovery",
                    job_id=job.identifier,
                    detail=(
                        f"Job history from the last refresh · {job.identifier[:8]} · created {job.created}\n"
                        f"{item.episode}: {job.status} at {job.stage}. {job.error}\n"
                        + (
                            spend + "\n"
                            if (spend := self.adapter.spend_summary(item.episode))
                            else ""
                        )
                        + "This is a saved job result, not a fresh read of the narration receipts. "
                        "Refresh notes for current job state, or inspect script / recovery for current receipts. "
                        "Do not delete receipts or restart the whole episode; stop and wait before any paid retry."
                    ),
                )
            values.append(item)
        return sorted(values, key=lambda item: int(item.note), reverse=True)

    def preview_setup(self, path):
        return preview_setup(path)

    def import_setup(self, preview):
        if any(job.status in {"queued", "running", "waiting"} for job in self.repository.jobs()):
            raise ValueError(
                "Finish or resolve the saved work before importing setup. Existing jobs are unchanged."
            )
        import_setup(self.root, preview)

    def inspect(self, note):
        snapshot = self.adapter.inspect(note)
        if any(
            job.episode == snapshot.episode and job.status in {"queued", "running", "waiting"}
            for job in self.repository.jobs()
        ):
            return replace(
                snapshot,
                request_json="",
                recovery_json="",
                recovery_summary="",
                summary=snapshot.summary
                + "\n\nThis episode already has active or waiting preparation. Use its main-queue controls; no second job will be queued.",
            )
        return snapshot

    def submit(
        self,
        snapshot,
        authorized: bool,
        *,
        recover_uncertain: bool = False,
        spend_override: str | None = None,
    ):
        captured = snapshot.recovery_json if recover_uncertain is True else snapshot.request_json
        if type(recover_uncertain) is not bool or authorized is not True or not captured:
            raise ValueError(
                "Inspect preparation and explicitly authorize the captured service requests first"
            )
        request = json.loads(captured)
        if bool(request.get("uncertain_chunks")) != recover_uncertain:
            raise ValueError("Uncertain recovery needs separate explicit consent")
        if snapshot.note != request["note"] or snapshot.episode != request["episode"]:
            raise ValueError("Preparation selection changed")
        if snapshot.spend_blocked and spend_override is None:
            raise ValueError(
                "The spend guard blocks more paid work for this episode. Stop and wait, or "
                "tick the override and give a reason; nothing was queued."
            )
        if spend_override is not None:
            if not snapshot.spend_blocked:
                raise ValueError("No spend-limit override is needed for this preparation")
            request["spend_override"] = {
                "reason": spend_override,
                "acknowledged": snapshot.spend_count,
            }
        self.adapter.validate_recovery(request)
        launch_worker(self.root)
        return self.repository.submit(snapshot.episode, "prepare", request)
