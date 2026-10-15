"""An explicit episode checklist and inspected, all-or-nothing batch handoff."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.scroll import ScrollArea
from field_notes_studio.presentation.theme import set_text


class Batch(ttk.Frame):
    def __init__(self, parent, inspect, submit, changed):
        super().__init__(parent, padding=10)
        self.changed = changed
        self.choices = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.explanation = ttk.Label(
            self,
            text="Choose episodes, then inspect each saved draft recipe. Output follows Produce. Nothing queues until the complete batch passes inspection.",
            wraplength=540,
            style="Muted.TLabel",
        )
        self.explanation.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.form = ScrollArea(self, padding=4)
        self.form.grid(row=1, column=0, sticky="nsew")
        self.summary = tk.Text(
            self, height=3, wrap="word", state="disabled", relief="flat", padx=8, pady=8
        )
        self.summary.grid(row=2, column=0, sticky="ew", pady=8)
        footer = ttk.Frame(self)
        footer.grid(row=3, column=0, sticky="ew")
        ActionButton(
            footer, text="Inspect selected episodes", pictogram="search", command=inspect
        ).pack(side="left")
        self.queue = ActionButton(
            footer,
            text="Queue inspected batch",
            pictogram="produce",
            command=submit,
            state="disabled",
            style="Accent.TButton",
        )
        self.queue.pack(side="left", padx=6)

    def load(self, episodes):
        previous = set(self.selection())
        for child in self.form.content.winfo_children():
            child.destroy()
        self.choices = {}
        for episode in episodes:
            value = self.choices[episode.identifier] = tk.BooleanVar(
                value=episode.identifier in previous
            )
            ttk.Checkbutton(
                self.form.content,
                text=f"{episode.identifier} · {episode.title}",
                variable=value,
                command=self.changed,
            ).pack(anchor="w", pady=4)
        self.form.bind_navigation()

    def selection(self):
        return [identifier for identifier, value in self.choices.items() if value.get()]

    def output(self, action):
        self.explanation.configure(
            text=f"Output: {action}. Choose episodes, then inspect each saved draft recipe. Queueing requires the complete batch to pass inspection."
        )

    def show(self, message, ready=False):
        set_text(self.summary, message)
        self.queue.configure(state="normal" if ready else "disabled")
