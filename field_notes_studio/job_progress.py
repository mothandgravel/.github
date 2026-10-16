"""Read-only job milestones from journal evidence, never a media approval or an ETA."""

from __future__ import annotations

import re
from dataclasses import dataclass

from field_notes_studio.models import Job


@dataclass(frozen=True)
class Milestone:
    label: str
    state: str


@dataclass(frozen=True)
class JobProgress:
    title: str
    milestones: tuple[Milestone, ...]
    next_step: str


FLOWS = {
    "prepare": (("narration", "Narration"), ("captions", "Captions"), ("save", "Save recording")),
    "audio": (("audio", "Audio + captions"), ("save", "Save edition")),
    "video": (("audio", "Audio + captions"), ("video", "Full video"), ("save", "Save edition")),
    "preview": (
        ("audio", "Audio + captions"),
        ("video", "Video preview"),
        ("save", "Save preview"),
    ),
    "export": (("export", "Package files"), ("save", "Save package")),
}
TITLES = {
    "prepare": "Prepare recording",
    "audio": "Finish audio",
    "video": "Produce full episode",
    "preview": "Render preview",
    "export": "Export package",
}
NEXT = {
    "prepare": "Next: Produce episode. Narration and captions are saved; not yet a finished video.",
    "audio": "Next: review audio, or Produce episode for audio and full video together.",
    "video": "Next: Review full episode once, then export. Nothing has been published.",
    "preview": "Next: watch the preview, then Produce episode. A preview is not a full video.",
    "export": "Next: Check package files, then upload manually. Export is not publication.",
}
TERMINAL_STAGES = {"failed", "interrupted", "cancelled", "succeeded", "waiting"}


def progress_for(job: Job, events: list[dict], *, historical: bool = False) -> JobProgress:
    """Derive milestones only from completed events or this job's successful result.

    Later-stage activity alone does not prove earlier stages were saved. A loaded
    job journal describes that attempt, not the current validity of its artifacts.
    No parser reads progress out of provider messages or invents elapsed-time %s.
    """
    flow = FLOWS.get(job.action, (("work", "Work"), ("save", "Save output")))
    stages = [event.get("stage", "") for event in events]
    known = {key for key, _ in flow}
    done = {name.removesuffix("-complete") for name in stages if name.endswith("-complete")}
    at = job.stage
    if at in TERMINAL_STAGES:
        at = next((name for name in reversed(stages) if name not in TERMINAL_STAGES), "")
    chunk = re.fullmatch(r"narration-(\d+)-of-(\d+)(-complete)?", at)
    active = "narration" if chunk else at if at in known else ""
    if at.endswith("-complete"):
        # Do not declare the following worker stage active before it is observed.
        active = "save" if all(key in done for key in known - {"save"}) else ""
    if job.status == "waiting" and job.action == "prepare":
        active = "captions"
    if job.status == "succeeded":
        done = known
    milestones = []
    for key, label in flow:
        state = "Saved" if key in done else "Next"
        if key == active and key not in done:
            state = {
                "running": "Stopping" if job.cancel_requested else "Working",
                "failed": "Failed",
                "interrupted": "Uncertain",
                "cancelled": "Stopped",
                "waiting": "Waiting",
            }.get(job.status, "Next")
        if historical and state in {"Failed", "Uncertain", "Stopped"}:
            state = "History"
        milestones.append(Milestone(label, state))
    title = TITLES.get(job.action, "Saved job progress")
    if chunk and job.status != "succeeded":
        current, total = int(chunk[1]), int(chunk[2])
        if 0 < current <= total <= 10000:
            completed = {
                int(match[1])
                for name in stages
                if (match := re.fullmatch(r"narration-(\d+)-of-(\d+)-complete", name))
                and int(match[2]) == total
                and 0 < int(match[1]) <= total
            }
            unit = "chunk" if len(completed) == 1 else "chunks"
            title = f"Narration {current}/{total} · {len(completed)} {unit} saved in this job"
    if historical:
        next_step = "Historical attempt; a later job completed. No retry needed for this row."
    elif job.status == "succeeded":
        next_step = NEXT.get(job.action, "Next: inspect the saved output.")
    elif job.cancel_requested and job.status in {"queued", "running"}:
        next_step = "Stop requested. The current operation finishes first; saved work is retained."
    elif job.status == "waiting":
        next_step = "Next: Resume to check the saved caption operation. No new narration request."
    elif job.status in {"failed", "interrupted", "cancelled"}:
        next_step = (
            "Next: Inspect recovery. Keep saved chunks; another request needs fresh consent."
            if job.action == "prepare"
            else "Next: inspect History, then retry or check a fresh recipe. Saved work is retained."
        )
    elif job.status == "queued":
        next_step = (
            "Queued, not started. The worker runs one job at a time; closing this window is safe."
        )
    elif not active:
        next_step = "Checking or moving between stages. No completion estimate is available."
    elif job.action == "prepare" and active in {"narration", "captions"}:
        next_step = (
            "Waiting for the service; provider progress is unavailable. Saved chunks are retained."
        )
    else:
        next_step = "Working locally. Stages are not equal in duration; no completion estimate is available."
    return JobProgress(title, tuple(milestones), next_step)
