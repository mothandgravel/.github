"""The home work list: every episode and written note, grouped by who acts next.

Groups are "needs-you", "working" and "done". Written notes with no narration
script yet are counted separately ("not started"), so they never crowd the list.
Episode rows use the verified readiness cache, never a guess from file names:
a row whose inputs changed since the last check is verified again before it is
shown, unless the caller asks for the quick pass (then it reads "Check").
"""

from __future__ import annotations

from dataclasses import dataclass

GROUPS = ("needs-you", "working", "done")


@dataclass(frozen=True)
class WorkItem:
    identifier: str  # episode id, or "note:<number>" for a written note
    title: str
    state: str
    meta: str
    group: str
    glyph: str
    next: str
    verified: bool = True
    run: str = ""
    note: str = ""


@dataclass(frozen=True)
class WorkList:
    items: tuple[WorkItem, ...]
    not_started: int = 0

    def group(self, name: str) -> tuple[WorkItem, ...]:
        return tuple(item for item in self.items if item.group == name)


RUN_GLYPH = {
    "working": "produce",
    "review": "review",
    "paused": "health",
    "stopped": "stop",
    "ready": "package",
    "done": "check",
}
NEXT_GLYPH = {
    "Produce": "produce",
    "Review": "review",
    "Release": "package",
    "Working": "produce",
    "Done": "check",
    "In feed": "check",
    "Check": "health",
    "Repair": "health",
}


def first_line(text: str, limit: int = 90) -> str:
    line = (text or "").strip().split("\n", 1)[0]
    return line if len(line) <= limit else line[: limit - 1].rsplit(" ", 1)[0] + "…"


def build(studio, *, check: bool = True) -> WorkList:
    from field_notes_studio.preparation_service import PreparationService
    from field_notes_studio.readiness_cache import verified_next

    items: list[WorkItem] = []
    catalog = {episode.identifier: episode for episode in studio.catalog()}
    runs = {view.episode: view for view in studio.run_views()}
    for episode, view in runs.items():
        title = catalog[episode].title if episode in catalog else episode
        row = next((r for r in view.rows if r.key == view.current), None)
        items.append(
            WorkItem(
                episode,
                f"{episode} · {title}",
                view.headline,
                first_line(row.detail if row else view.detail),
                view.group,
                RUN_GLYPH.get(view.phase, "produce"),
                {"review": "Review", "ready": "Release", "done": "Done"}.get(view.phase, "Open"),
                run=view.identifier,
            )
        )
    rest = [identifier for identifier in catalog if identifier not in runs]
    for identifier, (label, verified, readiness) in verified_next(
        studio, rest, check=check
    ).items():
        episode = catalog[identifier]
        if label == "Produce" and episode.publication_url and not episode.publication_saved:
            label = "In feed"
        group = (
            "working"
            if label == "Working"
            else "done"
            if label in {"Done", "In feed"}
            else "needs-you"
        )
        state = readiness.title if readiness else "Not checked since files changed"
        meta = first_line(readiness.detail) if readiness else "Checking…"
        if label == "In feed":
            state, meta = "In the podcast feed", "No local version made in Studio"
        if label == "Done":
            state, meta = "Released", "Release record saved"
        items.append(
            WorkItem(
                identifier,
                f"{identifier} · {episode.title}",
                state,
                meta,
                group,
                NEXT_GLYPH.get(label, "health"),
                label,
                verified=verified,
            )
        )
    not_started = 0
    try:
        notes = PreparationService(studio.root).catalog()
    except (OSError, ValueError):
        # A checkout without the written-note catalog still lists its episodes.
        notes = []
    for item in notes:
        if item.episode and (item.episode in catalog or item.episode in runs):
            continue
        if item.state in {"Needs script"}:
            not_started += 1
            continue
        group, next_label, glyph = {
            "Queued": ("working", "Working", "produce"),
            "Preparing": ("working", "Working", "produce"),
            "Awaiting captions": ("working", "Working", "captions"),
            "Needs recovery": ("needs-you", "Recover", "health"),
            "Needs repair": ("needs-you", "Repair", "health"),
        }.get(item.state, ("needs-you", "Make", "transcript"))
        state = "Written; not narrated yet" if next_label == "Make" else item.state
        items.append(
            WorkItem(
                "note:" + item.note,
                f"{item.note} · {item.title}",
                state,
                first_line(item.detail),
                group,
                glyph,
                next_label,
                note=item.note,
            )
        )
    order = {name: index for index, name in enumerate(GROUPS)}
    items.sort(key=lambda item: (order[item.group], item.title), reverse=False)
    return WorkList(tuple(items), not_started)
