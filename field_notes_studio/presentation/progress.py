"""Compact, text-labelled milestones; no progress guessed from elapsed time."""

from tkinter import ttk

from field_notes_studio.presentation.icons import icon
from field_notes_studio.presentation.theme import BRASS, INK, MUTED, SUCCESS, WARNING

STATES = {
    "Saved": ("check", SUCCESS),
    "Working": ("produce", BRASS),
    "Waiting": ("history", WARNING),
    "Failed": ("stop", WARNING),
    "Uncertain": ("history", WARNING),
    "Stopped": ("stop", MUTED),
    "Stopping": ("stop", WARNING),
    "History": ("history", MUTED),
    "Next": ("pending", MUTED),
}


class ProgressStrip(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.snapshot = None
        self.cells = []
        for column in range(3):
            self.columnconfigure(column, weight=1, uniform="milestone")
            cell = ttk.Label(self, compound="left", style="Muted.TLabel", padding=(4, 3))
            cell.grid(row=0, column=column, sticky="ew", padx=(0, 8))
            self.cells.append(cell)
        self.bind("<Configure>", self._resize)

    def _resize(self, event):
        if event.widget is self:
            width = max(80, event.width // max(1, len(self.cells)) - 45)
            for cell in self.cells:
                cell.configure(wraplength=width)

    def clear(self):
        self.snapshot = None
        for cell in self.cells:
            cell.configure(text="", image="", foreground=INK)

    def show(self, snapshot):
        if self.snapshot == snapshot:
            return
        self.snapshot = snapshot
        for column, cell in enumerate(self.cells):
            if column >= len(snapshot.milestones):
                cell.grid_remove()
                continue
            cell.grid()
            milestone = snapshot.milestones[column]
            glyph, color = STATES[milestone.state]
            cell.configure(
                text=f"{milestone.label} · {milestone.state}",
                image=icon(self, glyph, color),
                foreground=color,
            )
