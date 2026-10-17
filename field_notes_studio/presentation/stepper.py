"""Prepare · Produce · Review · Release: where this episode is, in words and pictograms.

Colour is never the only signal: each step shows a pictogram (a tick once done)
and a state word. Steps are navigation, not actions; nothing here starts work.
"""

from tkinter import ttk

from field_notes_studio.presentation.icons import icon
from field_notes_studio.presentation.readiness import journey

KIND_COLORS = {"done": "SUCCESS", "now": "BRASS", "warn": "WARNING", "todo": "MUTED"}


class Stepper(ttk.Frame):
    def __init__(self, parent, navigate=None):
        super().__init__(parent)
        self.navigate = navigate or (lambda _stage: None)
        self.cells = []
        self.steps = journey(None)
        for index in range(4):
            if index:
                ttk.Label(self, text="───", style="Step.TLabel").grid(
                    row=0, column=index * 2 - 1, rowspan=2, padx=10
                )
            cell = ttk.Frame(self, cursor="hand2")
            cell.grid(row=0, column=index * 2, sticky="w")
            glyph = ttk.Label(cell)
            glyph.grid(row=0, column=0, rowspan=2, padx=(0, 6))
            name = ttk.Label(cell, style="Step.TLabel")
            name.grid(row=0, column=1, sticky="w")
            state = ttk.Label(cell, style="Small.TLabel")
            state.grid(row=1, column=1, sticky="w")
            for widget in (cell, glyph, name, state):
                widget.bind("<Button-1>", lambda _e, i=index: self.navigate(i))
            self.cells.append((glyph, name, state))
        self.show(self.steps)

    def show(self, steps, current=None):
        """Render four steps; ``current`` is the stage the reader is looking at."""
        self.steps = tuple(steps)
        if current is None:
            current = next(
                (i for i, step in enumerate(self.steps) if step.kind in {"now", "warn"}), None
            )
        for index, (step, (glyph, name, state)) in enumerate(
            zip(self.steps, self.cells, strict=True)
        ):
            mark = "check" if step.kind == "done" else step.glyph
            glyph.configure(image=icon(glyph, mark, KIND_COLORS[step.kind]))
            name.configure(
                text=step.label, style="StepOn.TLabel" if index == current else "Step.TLabel"
            )
            state.configure(text=step.state)

    def retheme(self):
        self.show(self.steps)

    def summary(self):
        """The stepper as one sentence, for tests and the status line."""
        return " · ".join(f"{step.label}: {step.state}" for step in self.steps)
