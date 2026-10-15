"""Explicit human review of saved media; all file access stays in the service."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.scroll import ScrollArea


class Review(ttk.Frame):
    def __init__(self, parent, callbacks):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.scroller = ScrollArea(self, padding=12)
        self.scroller.grid(row=0, column=0, sticky="nsew")
        self.canvas = self.scroller.canvas
        content = self.scroller.content
        self.snapshot = None
        self.scope = tk.StringVar(value="Full video and audio")
        self.reviewer = tk.StringVar()
        self.audio_checked = tk.BooleanVar()
        self.captions_checked = tk.BooleanVar()
        self.video_checked = tk.BooleanVar()
        self.busy = False
        header = ttk.Frame(content)
        header.pack(fill="x")
        ttk.Label(header, text="Review saved edition", style="Heading.TLabel").pack(side="left")
        self.refresh = ActionButton(
            header,
            pictogram="refresh",
            text="Refresh edition",
            command=callbacks["refresh"],
            style="Compact.TButton",
        )
        self.refresh.pack(side="right")
        self.summary = ttk.Label(content, text="Loading edition…", wraplength=590)
        self.summary.pack(anchor="w", pady=8)
        content.bind(
            "<Configure>",
            lambda e: self.summary.configure(wraplength=max(250, e.width - 35)),
            add=True,
        )
        combo = ttk.Combobox(
            content,
            textvariable=self.scope,
            values=("Audio and captions", "Full video and audio"),
            state="readonly",
            width=24,
        )
        combo.pack(anchor="w", pady=(0, 8))
        combo.bind("<<ComboboxSelected>>", lambda _: callbacks["refresh"]())
        assets = ttk.Frame(content)
        assets.pack(fill="x", pady=(0, 8))
        self.asset_buttons = {}
        for label, kind in (
            ("Listen separately", "audio"),
            ("Check subtitles", "captions"),
            ("Watch video", "video"),
        ):
            button = ActionButton(
                assets,
                pictogram=kind,
                text=label,
                command=lambda k=kind: callbacks["open_review"](k),
                style="Compact.TButton",
            )
            button.pack(side="left", padx=(0, 6))
            self.asset_buttons[kind] = button
        self.review_help = ttk.Label(
            content,
            style="Muted.TLabel",
            wraplength=540,
            text="Watch with sound, check subtitles, approve once. Separate audio playback is optional.",
        )
        self.review_help.pack(anchor="w", pady=(0, 6))
        content.bind(
            "<Configure>",
            lambda e: self.review_help.configure(wraplength=max(250, e.width - 35)),
            add=True,
        )
        self.audio_check = ttk.Checkbutton(
            content, text="I listened to this saved audio", variable=self.audio_checked
        )
        self.video_check = ttk.Checkbutton(
            content,
            text="I watched and listened to the full episode",
            variable=self.video_checked,
            command=self.watched_episode,
        )
        self.captions_check = ttk.Checkbutton(
            content, text="I checked this episode's subtitles", variable=self.captions_checked
        )
        self.captions_check.pack(anchor="w")
        footer = ttk.Frame(self, padding=(16, 10))
        footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        ttk.Label(footer, text="Reviewed by").pack(side="left", padx=(0, 8))
        ttk.Entry(footer, textvariable=self.reviewer, width=20).pack(side="left")
        self.approve = ActionButton(
            footer,
            pictogram="review",
            text="Record approval",
            command=callbacks["approve"],
            style="Accent.TButton",
        )
        self.approve.pack(side="left", padx=8)
        for variable in (
            self.reviewer,
            self.audio_checked,
            self.captions_checked,
            self.video_checked,
        ):
            variable.trace_add("write", lambda *_: self.update_controls())
        self.update_controls()
        self.bind_navigation(content)

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
        return self.scope.get() == "Full video and audio"

    def clear(self, message="Loading edition…", *, loading=False):
        self.snapshot = None
        self.busy = False
        self.audio_checked.set(False)
        self.captions_checked.set(False)
        self.video_checked.set(False)
        self.summary.configure(text=message)
        self.refresh.configure(
            text="Checking…" if loading else "Refresh edition",
            state="disabled" if loading else "normal",
        )
        self.canvas.yview_moveto(0)
        self.update_controls()

    def load(self, snapshot):
        self.clear(snapshot.summary)
        if snapshot.identity:
            self.scope.set("Full video and audio" if snapshot.full_video else "Audio and captions")
        self.snapshot = snapshot
        self.update_controls()

    def update_controls(self):
        available = self.snapshot is not None and bool(self.snapshot.identity) and not self.busy
        for kind, button in self.asset_buttons.items():
            button.configure(
                state="normal" if available and getattr(self.snapshot, kind) else "disabled"
            )
        if self.full_video():
            self.audio_check.pack_forget()
            self.video_check.pack(anchor="w", before=self.captions_check)
            self.review_help.configure(
                text="Watch with sound, check subtitles, approve once. Separate audio playback is optional."
            )
        else:
            self.video_check.pack_forget()
            self.audio_check.pack(anchor="w", before=self.captions_check)
            self.review_help.configure(
                text="Audio-only review. For a video release, choose Full video and audio and approve that complete edition once."
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
            else "Record approval"
        )
        if self.busy:
            self.refresh.configure(state="disabled")
