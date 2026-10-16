"""History classification, never mutation or inferred media approval."""

from collections.abc import Iterable

from field_notes_studio.models import Job


def resolved_failures(jobs: Iterable[Job]) -> set[str]:
    """Repository snapshots are newest first. A later success resolves old failure prompts.

    Video includes audio, but preview/export do not establish full production.
    Keep original rows and errors for History; this only classifies next actions.
    """
    succeeded = set()
    resolved = set()
    for job in jobs:
        key = (job.episode, job.action)
        if job.status == "succeeded":
            succeeded.add(key)
            if job.action == "video":
                succeeded.add((job.episode, "audio"))
        elif job.status in {"failed", "interrupted", "cancelled"} and key in succeeded:
            resolved.add(job.identifier)
    return resolved
