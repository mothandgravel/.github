"""Explicit human review of saved media; all file access stays in the service."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton, Fieldset, Tooltip
from field_notes_studio.presentation.scroll import ScrollArea

FULL = "Full video and audio"
AUDIO = "Audio and captions"


class Review(ttk.Frame):
    def __init__(self, parent, callbacks):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.scroller = ScrollArea(self, padding=(16, 14, 16, 6))
        self.scroller.grid(row=0, column=0, sticky="nsew")
        self.canvas = self.scroller.canvas
        content = self.scroller.content
        self.snapshot = None
        self.scope = tk.StringVar(value=FULL)
        self.reviewer = tk.StringVar()
        self.audio_checked = tk.BooleanVar()
        self.captions_checked = tk.BooleanVar()
        self.video_checked = tk.BooleanVar()
        self.busy = False
        header = ttk.Frame(content)
        header.pack(fill="x")
        self.review_help = ttk.Label(
            header,
            text="Watch the full episode once with sound, then check the subtitles.",
            wraplength=540,
        )
        self.review_help.pack(side="left", anchor="w")
        # The episode card holds the one "Check again"; this one is kept for state only.
        self.refresh = ActionButton(
            header, pictogram="refresh", text="Check again", command=callbacks["refresh"]
        )
        assets = ttk.Frame(content)
        assets.pack(fill="x", pady=(10, 4))
        self.asset_buttons = {}
        for label, kind in (
            ("Watch full episode", "video"),
            ("Check subtitles", "captions"),
            ("Listen to audio only", "audio"),
        ):
            button = ActionButton(
                assets,
                pictogram=kind,
                text=label,
                command=lambda k=kind: callbacks["open_review"](k),
            )
            button.pack(side="left", padx=(0, 6))
            self.asset_buttons[kind] = button
        self.media = ttk.Label(assets, text="", style="Small.TLabel")
        self.media.pack(side="left", padx=(6, 0))
        self.summary = ttk.Label(
            content, text="Loading version…", style="Muted.TLabel", wraplength=590
        )
        self.summary.pack(anchor="w", pady=(6, 12))
        Tooltip(
            self.summary,
            lambda: f"Version id {self.snapshot.version}"
            if self.snapshot and self.snapshot.version
            else "",
        )
        self.checks = Fieldset(content, "Before you approve")
        self.checks.pack(fill="x")
        self.audio_check = ttk.Checkbutton(
            self.checks.body,
            text="I listened to the whole saved audio",
            variable=self.audio_checked,
        )
        self.video_check = ttk.Checkbutton(
            self.checks.body,
            text="I watched and listened to the whole episode",
            variable=self.video_checked,
            command=self.watched_episode,
        )
        self.captions_check = ttk.Checkbutton(
            self.checks.body,
            text="The subtitles match what is said",
            variable=self.captions_checked,
        )
        self.captions_check.pack(anchor="w")
        footer = ttk.Frame(content)
        footer.pack(fill="x", pady=(12, 0))
        footer.columnconfigure(3, weight=1)
        ttk.Label(footer, text="Reviewer").grid(row=0, column=0, padx=(0, 8))
        self.reviewer_entry = ttk.Entry(footer, textvariable=self.reviewer, width=20)
        self.reviewer_entry.grid(row=0, column=1)
        self.remembered = ttk.Label(footer, text="", style="Small.TLabel")
        self.remembered.grid(row=0, column=2, padx=8, sticky="w")
        self.approve = ActionButton(
            footer,
            pictogram="check",
            text="Approve this episode",
            command=callbacks["approve"],
            style="Accent.TButton",
        )
        self.approve.grid(row=0, column=4, sticky="e")
        scope = ttk.Frame(content)
        scope.pack(fill="x", pady=(18, 0))
        ttk.Label(scope, text="What you are approving", style="Muted.TLabel").pack(side="left")
        combo = self.scope_control = ttk.Combobox(
            scope, textvariable=self.scope, values=(FULL, AUDIO), state="readonly", width=22
        )
        combo.pack(side="left", padx=8)
        combo.bind("<<ComboboxSelected>>", lambda _: callbacks["refresh"]())
        self.note = ttk.Label(
            content,
            text="Approval belongs to these exact files. Changing pace, outro or sound makes "
            "a new version that needs its own review.",
            style="Muted.TLabel",
            wraplength=590,
        )
        self.note.pack(anchor="w", pady=(12, 0))
        content.bind("<Configure>", self._resize, add=True)
        for variable in (
            self.reviewer,
            self.audio_checked,
            self.captions_checked,
            self.video_checked,
        ):
            variable.trace_add("write", lambda *_: self.update_controls())
        self.update_controls()
        self.bind_navigation(content)

    def _resize(self, event):
        width = max(250, event.width - 40)
        for label in (self.summary, self.note):
            label.configure(wraplength=width)
        self.review_help.configure(wraplength=max(200, width - 140))

    def remember(self, name):
        """Fill the reviewer remembered on this computer; never any of the ticks."""
        if name and not self.reviewer.get().strip():
            self.reviewer.set(name)
        self.remembered.configure(text="remembered on this computer" if name else "")

    def watched_episode(self):
        # Only this explicit, labelled user action confirms both watching AND listening.
        # Loading snapshots or changing scope never manufactures either confirmation.
        if self.full_video():
            self.audio_checked.set(self.video_checked.get())

    def bind_navigation(self, widget):
        self.scroller.bind_navigation(widget)

    def reveal(self, widget):
        self.scroller.reveal(widget)

    def full_video(self):
        return self.scope.get() == FULL

    def clear(self, message="Loading version…", *, loading=False):
        self.snapshot = None
        self.busy = False
        self.audio_checked.set(False)
        self.captions_checked.set(False)
        self.video_checked.set(False)
        self.summary.configure(text=message)
        self.refresh.configure(
            text="Checking…" if loading else "Check again",
            state="disabled" if loading else "normal",
        )
        self.canvas.yview_moveto(0)
        self.update_controls()

    def load(self, snapshot):
        lines = snapshot.summary.splitlines()
        # The status line is the subtitle's job; here the version line is what matters.
        self.clear(
            "\n".join(lines[1:2]) if snapshot.identity and len(lines) > 1 else snapshot.summary
        )
        if snapshot.identity:
            self.scope.set(FULL if snapshot.full_video else AUDIO)
        self.snapshot = snapshot
        self.update_controls()

    def update_controls(self):
        available = self.snapshot is not None and bool(self.snapshot.identity) and not self.busy
        duration = int(self.snapshot.duration) if self.snapshot and self.snapshot.duration else 0
        player = "video" if self.full_video() else "audio"
        self.media.configure(
            text=f"Opens your {player} player · {duration // 60}:{duration % 60:02d}"
            if available and duration
            else f"Opens your {player} player"
            if available
            else ""
        )
        for kind, button in self.asset_buttons.items():
            button.configure(
                state="normal" if available and getattr(self.snapshot, kind) else "disabled"
            )
        if self.full_video():
            self.audio_check.pack_forget()
            self.video_check.pack(anchor="w", before=self.captions_check)
            self.review_help.configure(
                text="Watch the full episode once with sound, then check the subtitles."
            )
        else:
            self.video_check.pack_forget()
            self.audio_check.pack(anchor="w", before=self.captions_check)
            self.review_help.configure(
                text="Audio-only review. For a video release, choose Full video and audio "
                "and approve that whole version once."
            )
        ready = (
            available
            and not self.snapshot.approved
            and self.reviewer.get().strip()
            and self.audio_checked.get()
            and self.captions_checked.get()
            and (not self.full_video() or self.video_checked.get())
        )
        self.approve.configure(state="normal" if ready else "disabled")
        self.approve.configure(
            text="Recording…"
            if self.busy
            else "Approved"
            if available and self.snapshot.approved
            else "Approve this episode"
        )
        if self.busy:
            self.refresh.configure(state="disabled")
