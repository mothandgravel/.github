"""Persistent episode overview: an evidence checklist with one next action.

Values and callbacks only, no media or file access. The checklist restates the
checked snapshot in plain words; it never adds evidence the snapshot lacks.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.icons import icon
from field_notes_studio.readiness_models import LABELS

# Plain-language labels for the next action; the readiness model keeps its own ids.
ACTION_LABELS = {
    **LABELS,
    "export": "Make upload folder",
    "package": "Open upload folder",
    "health": "See what blocks it",
    "repair": "See what blocks it",
}
TITLES = {
    "Ready to produce": "Ready to make the full episode",
    "Draft differs from saved episode": "Your settings differ from the saved version",
    "Ready for one full review": "Ready for your review",
    "Export the reviewed episode": "Approved · make the upload folder",
    "Upload package needs refreshing": "Upload folder needs refreshing",
    "Package needs refreshing": "Upload folder needs refreshing",
    "Refresh the upload package": "Upload folder needs refreshing",
    "Ready for manual upload": "Ready to upload",
    "Full edition needs production": "Full episode needs making again",
    "Package check is waiting": "Upload folder check is waiting",
}
GLYPHS = {
    "produce": "produce",
    "review": "review",
    "export": "package",
    "package": "folder",
    "job": "history",
    "health": "health",
    "repair": "health",
}
NEEDS_REFRESH = {"upload copy changed", "needs attention", "stale", "unverified", "review"}
# Plain wording for the fixed explanations a checked snapshot carries.
DETAILS = {
    "One job finishes audio, captions, full video and thumbnail.": "One job makes the audio, "
    "captions, full video and thumbnail.",
    "Watch and listen, check subtitles, then approve the exact saved edition.": "Watch and "
    "listen once, check the subtitles, then approve this exact version.",
    "Full episode remains approved. Export to include the current saved title, description "
    "and tags.": "The full episode stays approved. Make the upload folder again to include "
    "the current title, description and tags.",
    "Media, full review and upload copy match. Publication on an external platform is not "
    "verified.": "Files, approval and upload text match. Studio does not check YouTube.",
}


@dataclass(frozen=True)
class Step:
    """One stage of the episode: glyph, label, a state in words and its kind."""

    glyph: str
    label: str
    state: str
    kind: str  # "done", "now", "warn" or "todo"


def parse_stages(stages):
    values = {}
    for line in stages:
        name, _, value = line.partition(":")
        values[name.strip()] = value.strip()
    return values


def journey(snapshot, published=False):
    """Prepare · Produce · Review · Release for the stepper, from one checked snapshot."""
    if snapshot is None:
        return (
            Step("transcript", "Prepare", "Narrated", "done"),
            Step("produce", "Produce", "Not checked", "todo"),
            Step("review", "Review", "Not checked", "todo"),
            Step("package", "Release", "Not checked", "todo"),
        )
    stages = parse_stages(snapshot.stages)
    recording = stages.get("Recording", "")
    episode = stages.get("Full episode", "")
    review = stages.get("Review", "")
    package = stages.get("Package", "")
    if recording == "verified":
        prepare = Step("transcript", "Prepare", "Saved", "done")
    elif snapshot.action == "repair":
        prepare = Step("transcript", "Prepare", "Needs attention", "warn")
    else:
        prepare = Step("transcript", "Prepare", "Narrated", "done")
    if episode == "verified":
        produce = Step("produce", "Produce", "Made", "done")
    elif episode.startswith("saved; draft differs"):
        produce = Step("produce", "Produce", "Settings changed", "warn")
    elif episode == "unavailable":
        produce = Step("produce", "Produce", "Make again", "warn")
    elif episode == "not produced":
        produce = Step("produce", "Produce", "Next", "now")
    else:
        produce = Step("produce", "Produce", "Not checked", "todo")
    if review == "approved":
        reviewed = Step("review", "Review", "Approved", "done")
    elif review == "needed" and produce.kind == "done":
        reviewed = Step("review", "Review", "Needs you", "now")
    else:
        reviewed = Step("review", "Review", "Not yet", "todo")
    if published:
        release = Step("package", "Release", "Recorded", "done")
    elif reviewed.kind != "done":
        release = Step("package", "Release", "Not started", "todo")
    elif package == "current and verified":
        release = Step("package", "Release", "Ready to upload", "now")
    elif package in NEEDS_REFRESH:
        release = Step("package", "Release", "Refresh upload folder", "now")
    else:
        release = Step("package", "Release", "Next", "now")
    return prepare, produce, reviewed, release


def checklist(snapshot, published=False):
    """Card rows as (glyph, text, kind); kind is ok, now, warn or todo."""
    if snapshot is None:
        return (
            ("audio", "Narration and captions", "todo"),
            ("video", "Full episode", "todo"),
            ("review", "Your review", "todo"),
            ("package", "Upload folder", "todo"),
            ("external", "Published", "todo"),
        )
    prepare, produce, review, release = journey(snapshot, published)
    package = parse_stages(snapshot.stages).get("Package", "")
    recording = (
        ("audio", "Narration and captions saved", "ok")
        if prepare.state == "Saved"
        else ("audio", "Narration and captions need attention", "warn")
        if prepare.kind == "warn"
        else ("audio", "Narration and captions", "todo")
    )
    episode = {
        "Made": ("video", "Full episode made", "ok"),
        "Settings changed": ("video", "Full episode differs from your settings", "warn"),
        "Make again": ("video", "Full episode needs making again", "warn"),
        "Next": ("video", "Make the full episode", "now"),
    }.get(produce.state, ("video", "Full episode", "todo"))
    approval = (
        ("review", "Approved", "ok")
        if review.kind == "done"
        else ("review", "Your review", "now" if review.kind == "now" else "todo")
    )
    if package == "current and verified":
        folder = ("package", "Upload folder ready", "ok")
    elif package in NEEDS_REFRESH:
        folder = ("package", "Upload folder needs refreshing", "warn")
    elif release.kind == "now":
        folder = ("package", "Make the upload folder", "now")
    else:
        folder = ("package", "Upload folder", "todo")
    record = (
        ("external", "Release recorded", "ok") if published else ("external", "Published", "todo")
    )
    return recording, episode, approval, folder, record


def episode_label(identifier):
    match = re.fullmatch(r"note-(\d+)", identifier or "")
    return f"FIELD NOTE {match[1]}" if match else (identifier or "").upper()


def checked_text(stamp):
    try:
        moment = datetime.fromisoformat(stamp).astimezone()
    except (TypeError, ValueError):
        return ""
    today = moment.date() == datetime.now().astimezone().date()
    return "Checked " + moment.strftime("%H:%M" if today else "%d %b %H:%M") + " · local files"


ROW_STYLES = {
    "ok": ("check", "SUCCESS", "CardOk.TLabel"),
    "now": (None, "BRASS", "CardNow.TLabel"),
    "warn": ("health", "WARNING", "CardWarn.TLabel"),
    "todo": ("pending", "MUTED", "CardMuted.TLabel"),
}


class ReadinessCard(ttk.Frame):
    def __init__(self, parent, act, refresh, *, published=None, changed=None):
        super().__init__(parent, style="Card.TFrame", padding=12)
        self.snapshot = None
        self.act = act
        self.override = None
        self.published = published or (lambda _episode: False)
        self.changed = changed or (lambda _snapshot: None)
        self.columnconfigure(0, weight=1)
        header = ttk.Frame(self, style="CardRow.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        self.episode = ttk.Label(header, text="", style="CardBrass.TLabel")
        self.episode.pack(side="left")
        self.check = ttk.Button(header, text="Check again", command=refresh, style="Small.TButton")
        self.check.pack(side="right")
        self.title = ttk.Label(
            self, text="Choose an episode", style="CardBig.TLabel", wraplength=270
        )
        self.title.grid(row=1, column=0, sticky="ew", pady=(2, 6))
        self.rows = ttk.Frame(self, style="CardRow.TFrame")
        self.rows.grid(row=2, column=0, sticky="ew")
        self.row_widgets = []
        for _ in range(5):
            line = ttk.Frame(self.rows, style="CardRow.TFrame")
            line.pack(fill="x")
            glyph = ttk.Label(line, style="Card.TLabel")
            glyph.pack(side="left", padx=(0, 8))
            text = ttk.Label(line, style="CardMuted.TLabel")
            text.pack(side="left")
            self.row_widgets.append((glyph, text))
        evidence = ttk.Frame(self, style="CardRow.TFrame")
        evidence.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        evidence.columnconfigure(0, weight=1)
        self.detail = ttk.Label(evidence, text="", style="CardMuted.TLabel", wraplength=270)
        self.detail.grid(row=0, column=0, sticky="ew")
        # Exception text stays behind an explicit disclosure, never in the headline.
        self.details_button = ttk.Button(
            evidence, text="▸ Details", command=self.toggle_details, style="Small.TButton"
        )
        self.details_shown = False
        self.details = ttk.Label(self, text="", style="CardSmall.TLabel", wraplength=270)
        self.checked = ttk.Label(self, text="", style="CardSmall.TLabel")
        self.checked.grid(row=5, column=0, sticky="w", pady=(4, 8))
        self.primary = ActionButton(
            self,
            text="Check readiness",
            pictogram="search",
            command=self._invoke,
            style="Accent.TButton",
            state="disabled",
        )
        self.primary.grid(row=6, column=0, sticky="ew")
        self.bind("<Configure>", self._resize)
        self._rows(None)

    def _invoke(self):
        (self.override or self.act)()

    def _resize(self, event):
        if event.widget is self:
            for label in (self.title, self.details):
                label.configure(wraplength=max(180, event.width - 32))
            self.width = event.width
            self._wrap_detail()
            self.checked.configure(wraplength=max(120, event.width - 32))

    def _wrap_detail(self):
        # Leave room for the Details toggle only while it is shown.
        reserve = 120 if self.snapshot and self.snapshot.technical else 32
        self.detail.configure(wraplength=max(150, getattr(self, "width", 290) - reserve))

    def toggle_details(self):
        self.details_shown = not self.details_shown
        self._show_details()

    def _show_details(self):
        self._wrap_detail()
        technical = self.snapshot.technical if self.snapshot else ""
        if not technical:
            self.details_shown = False
            self.details_button.grid_remove()
            self.details.grid_remove()
            return
        self.details_button.grid(row=0, column=1, sticky="ne", padx=(6, 0))
        # A disclosure triangle keeps the width constant when toggled.
        self.details_button.configure(text=("▾ " if self.details_shown else "▸ ") + "Details")
        if self.details_shown:
            self.details.configure(text="Technical detail: " + technical)
            self.details.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        else:
            self.details.grid_remove()

    def _rows(self, snapshot, published=False):
        for (glyph, text, kind), (image, label) in zip(
            checklist(snapshot, published), self.row_widgets, strict=True
        ):
            mark, color, style = ROW_STYLES[kind]
            image.configure(image=icon(image, mark or glyph, color))
            label.configure(text=text, style=style)

    def invalidate(self, text="Check your edited settings against the saved files.", enabled=True):
        self.snapshot = None
        self.override = None
        self._show_details()
        self.primary.set_icon("search")
        self.title.configure(text="Needs checking")
        self._rows(None)
        self.detail.configure(text=text)
        self.checked.configure(text="")
        self.check.configure(state="normal" if enabled else "disabled")
        self.primary.configure(text="Check readiness", state="normal" if enabled else "disabled")
        self.changed(None)

    def working(self):
        self.snapshot = None
        self.override = None
        self._show_details()
        self.primary.set_icon("search")
        self.title.configure(text="Checking episode…")
        self.detail.configure(text="Checking saved files on this computer; no service request.")
        self.checked.configure(text="")
        self.primary.configure(text="Checking…", state="disabled")

    def empty(self, label, title, detail, action=None, command=None):
        """No narrated episode selected: one sentence and, at most, one action."""
        self.snapshot = None
        self.override = command
        self._show_details()
        self.episode.configure(text=label)
        self.title.configure(text=title)
        self._rows(None)
        self.detail.configure(text=detail)
        self.checked.configure(text="")
        self.check.configure(state="disabled")
        self.primary.set_icon("transcript")
        self.primary.configure(
            text=action or "Check readiness", state="normal" if command else "disabled"
        )
        self.changed(None)

    def show(self, snapshot):
        self.snapshot = snapshot
        self.override = None
        self.details_shown = False
        self._show_details()
        published = bool(self.published(snapshot.episode))
        self.primary.set_icon(GLYPHS.get(snapshot.action, "search"))
        self.episode.configure(text=episode_label(snapshot.episode))
        self.title.configure(text=TITLES.get(snapshot.title, snapshot.title))
        self._rows(snapshot, published)
        # Detailed blockers go beside Produce/Release; keep the overview compact.
        detail = DETAILS.get(snapshot.detail, snapshot.detail)
        detail = detail if len(detail) <= 130 else detail[:127].rsplit(" ", 1)[0] + "…"
        self.detail.configure(text=detail)
        self.checked.configure(text=checked_text(snapshot.checked_at))
        self.check.configure(state="normal")
        self.primary.configure(text=ACTION_LABELS[snapshot.action], state="normal")
        self.changed(snapshot)
