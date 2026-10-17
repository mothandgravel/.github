"""Several episodes at once: an explicit checklist and an all-or-nothing checked plan."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton, Fieldset
from field_notes_studio.presentation.scroll import ScrollArea
from field_notes_studio.presentation.theme import set_text

OUTPUTS = {
    "video": "full episodes",
    "audio": "audio and captions only",
    "preview": "10-second video previews",
    "export": "upload folders",
}


class Batch(ttk.Frame):
    def __init__(self, parent, inspect, submit, changed):
        super().__init__(parent, padding=10)
        self.changed = changed
        self.choices = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.explanation = ttk.Label(
            self,
            text="Choose episodes, then check each one's saved settings. Nothing is queued "
            "until every chosen episode passes its checks.",
            wraplength=540,
            style="Muted.TLabel",
        )
        self.explanation.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.form = ScrollArea(self, padding=4)
        self.form.grid(row=1, column=0, sticky="nsew")
        self.summary = tk.Text(
            self, height=2, wrap="word", state="disabled", relief="flat", padx=8, pady=6
        )
        self.summary.grid(row=2, column=0, sticky="ew", pady=8)
        footer = ttk.Frame(self)
        footer.grid(row=3, column=0, sticky="ew")
        ActionButton(
            footer, text="Check chosen episodes", pictogram="search", command=inspect
        ).pack(side="left")
        self.queue = ActionButton(
            footer,
            text="Queue checked episodes",
            pictogram="queue",
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
        group = Fieldset(self.form.content, "Episodes to include")
        group.pack(fill="x")
        for episode in episodes:
            value = self.choices[episode.identifier] = tk.BooleanVar(
                value=episode.identifier in previous
            )
            ttk.Checkbutton(
                group.body,
                text=f"{episode.identifier} · {episode.title}",
                variable=value,
                command=self.changed,
            ).pack(anchor="w", pady=2)
        self.form.bind_navigation()

    def selection(self):
        return [identifier for identifier, value in self.choices.items() if value.get()]

    def output(self, action):
        self.explanation.configure(
            text=f"Makes: {OUTPUTS.get(action, action)}. Choose episodes, then check each "
            "one's saved settings. Nothing is queued until every chosen episode passes."
        )

    def show(self, message, ready=False):
        set_text(self.summary, message)
        self.queue.configure(state="normal" if ready else "disabled")
