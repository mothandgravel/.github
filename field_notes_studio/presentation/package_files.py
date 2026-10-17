"""Checked upload files, one row each, with a Copy path for the browser's file picker."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.icons import icon

GLYPHS = {
    "episode.mp4": "video",
    "thumbnail.png": "folder",
    "captions.srt": "captions",
    "captions.vtt": "captions",
    "episode.mp3": "audio",
    "transcript.txt": "transcript",
}


def size_text(value):
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1000 or unit == "GB":
            return f"{value:,.1f} {unit}" if unit != "B" else f"{value} B"
        value /= 1000


class PackageFiles(ttk.Frame):
    def __init__(self, parent, callbacks, summary_master=None):
        super().__init__(parent, style="CardRow.TFrame")
        self.callbacks = callbacks
        self.snapshot = None
        self.copy_buttons = {}
        self.columnconfigure(0, weight=1)
        heading = self.heading = ttk.Frame(self, style="CardRow.TFrame")
        heading.grid(row=0, column=0, sticky="ew")
        ttk.Label(heading, text="Files", style="CardHeading.TLabel").pack(side="left")
        self.refresh = ActionButton(
            heading,
            pictogram="refresh",
            text="Check files",
            command=callbacks["package_refresh"],
            style="Small.TButton",
        )
        self.refresh.pack(side="right")
        self.rows = ttk.Frame(self, style="CardRow.TFrame")
        self.rows.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        for column, weight in ((0, 0), (1, 0), (2, 1), (3, 0), (4, 0)):
            self.rows.columnconfigure(column, weight=weight)
        # The checked-status line can sit elsewhere in the card, below its actions.
        self.summary = ttk.Label(
            summary_master or self, text="", style="CardMuted.TLabel", wraplength=520
        )
        if summary_master is None:
            self.summary.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.path = tk.StringVar()
        if summary_master is None:
            self.bind(
                "<Configure>",
                lambda e: self.summary.configure(wraplength=max(200, e.width - 10)),
                add=True,
            )

    def error(self, message):
        self.summary.configure(text=message, style="CardWarn.TLabel")

    def _render(self):
        for child in self.rows.winfo_children():
            child.destroy()
        self.copy_buttons = {}
        files = self.snapshot.files if self.snapshot else ()
        for row, asset in enumerate(files):
            ttk.Label(
                self.rows, image=icon(self, GLYPHS.get(asset.name, "folder")), style="Card.TLabel"
            ).grid(row=row, column=0, padx=(0, 8), pady=1)
            ttk.Label(self.rows, text=asset.purpose, style="Card.TLabel").grid(
                row=row, column=1, sticky="w", padx=(0, 12)
            )
            ttk.Label(self.rows, text=asset.name, style="CardMono.TLabel").grid(
                row=row, column=2, sticky="w"
            )
            ttk.Label(self.rows, text=size_text(asset.size), style="CardMuted.TLabel").grid(
                row=row, column=3, sticky="e", padx=12
            )
            button = ActionButton(
                self.rows,
                pictogram="copy",
                text="Copy path",
                command=lambda n=asset.name: self.callbacks["package_copy"](n),
                style="Small.TButton",
            )
            button.grid(row=row, column=4, sticky="e", pady=1)
            self.copy_buttons[asset.name] = button

    def working(self, name):
        for asset, button in self.copy_buttons.items():
            button.reset_feedback()
            button.configure(state="disabled")
            if asset == name:
                button.configure(text="Copying…")

    def ready(self):
        for button in self.copy_buttons.values():
            button.reset_feedback()
            button.configure(state="normal")

    def clear(self, message="Check the saved upload folder to see its files.", *, loading=False):
        self.snapshot = None
        self._render()
        self.summary.configure(text=message, style="CardMuted.TLabel")
        self.path.set("")
        self.refresh.configure(
            text="Checking…" if loading else "Check files",
            state="disabled" if loading else "normal",
        )

    def load(self, snapshot):
        self.clear(snapshot.summary)
        self.snapshot = snapshot
        self.summary.configure(
            style="CardOk.TLabel"
            if snapshot.status == "ready"
            else "CardMuted.TLabel"
            if snapshot.status == "missing"
            else "CardWarn.TLabel"
        )
        self._render()

    def copied(self, name, path):
        self.ready()
        self.clipboard_clear()
        self.clipboard_append(path)
        self.path.set(path)
        if name in self.copy_buttons:
            self.copy_buttons[name].complete("Path copied")
