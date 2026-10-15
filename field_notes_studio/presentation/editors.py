"""Scrollable, labelled editors; raw text can be checkpointed before validation."""

import tkinter as tk
from tkinter import filedialog, ttk

from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.scroll import ScrollArea

SOUND = (
    ("intro_seconds", "Intro · seconds (0–15)"),
    ("music_overlap_seconds", "Music overlap · seconds (0–3)"),
    ("music_gain_db", "Music level · dB (−40–0)"),
    ("target_lufs", "Loudness · LUFS (−24–−14)"),
    ("true_peak_db", "Peak ceiling · dB (−3–−1)"),
    ("music_mode", "Music · motif / file / none"),
    ("music_file", "Custom music file"),
    ("music_credit", "Music credit and license"),
)
PUBLISHING = (
    ("title", "Episode title · 100 characters"),
    ("description", "Episode summary · 4,000 characters"),
    ("tags", "Additional episode tags · comma separated"),
    ("hashtags", "Additional hashtags · space separated"),
    ("show_title", "Show template · title"),
    ("show_description", "Show template · description"),
    ("shared_tags", "Show template · shared tags"),
    ("shared_hashtags", "Show template · shared hashtags"),
)


class Editor(ttk.Frame):
    def __init__(self, parent, fields, changed, explanation, save=None, reload=None):
        super().__init__(parent)
        self.values = {}
        self.widgets = {}
        self.filling = False
        self.baseline = ""
        self.loaded = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.message = ttk.Label(
            self, text=explanation, wraplength=540, style="Muted.TLabel", padding=10
        )
        self.message.grid(row=0, column=0, sticky="ew")
        self.bind(
            "<Configure>", lambda e: self.message.configure(wraplength=max(200, e.width - 24))
        )
        self.form = ScrollArea(self, padding=10)
        self.form.grid(row=1, column=0, sticky="nsew")
        for name, label in fields:
            ttk.Label(self.form.content, text=label).pack(anchor="w", pady=(8, 2))
            variable = self.values[name] = tk.StringVar()
            variable.trace_add("write", lambda *_: None if self.filling else changed())
            if name in {"description", "show_description", "music_credit"}:
                widget = tk.Text(
                    self.form.content,
                    height=4 if name != "music_credit" else 2,
                    wrap="word",
                    relief="flat",
                    padx=6,
                    pady=5,
                    undo=True,
                )
                variable.trace_add("write", lambda *_, v=variable, w=widget: self.update_text(v, w))
                widget.bind("<<Modified>>", lambda _, v=variable, w=widget: self.update_value(v, w))
            elif name == "music_mode":
                widget = ttk.Combobox(
                    self.form.content,
                    textvariable=variable,
                    values=("motif", "file", "none"),
                    state="readonly",
                )
            else:
                widget = ttk.Entry(self.form.content, textvariable=variable)
            widget.pack(fill="x")
            self.widgets[name] = widget
            if name == "music_file":
                ttk.Button(
                    self.form.content, text="Choose music file…", command=self.choose_music
                ).pack(anchor="w", pady=4)
        if save:
            footer = ttk.Frame(self, padding=10)
            footer.grid(row=2, column=0, sticky="ew")
            self.save = ActionButton(
                footer,
                text="Save publishing settings",
                pictogram="save",
                command=save,
                style="Accent.TButton",
                state="disabled",
            )
            self.save.pack(side="left")
            ActionButton(
                footer, text="Reload saved settings", pictogram="refresh", command=reload
            ).pack(side="left", padx=6)
        self.form.bind_navigation()
        if save:
            self.enable(False)

    @staticmethod
    def update_text(variable, widget):
        value = variable.get()
        if value != widget.get("1.0", "end-1c"):
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", value)
            widget.edit_modified(False)

    @staticmethod
    def update_value(variable, widget):
        if widget.edit_modified():
            widget.edit_modified(False)
            value = widget.get("1.0", "end-1c")
            if value != variable.get():
                variable.set(value)

    def enable(self, enabled):
        for name, widget in self.widgets.items():
            widget.configure(
                state="readonly"
                if enabled and name == "music_mode"
                else "normal"
                if enabled
                else "disabled"
            )

    def choose_music(self):
        path = filedialog.askopenfilename(
            parent=self, title="Choose music with permission to publish"
        )
        if path:
            self.values["music_file"].set(path)
            self.values["music_mode"].set("file")

    def raw(self):
        return {
            name: self.widgets[name].get("1.0", "end-1c")
            if isinstance(self.widgets[name], tk.Text)
            else value.get()
            for name, value in self.values.items()
        }

    def fill(self, values):
        self.filling = True
        for name, variable in self.values.items():
            variable.set("" if values.get(name) is None else str(values.get(name, "")))
        self.filling = False
        self.loaded = True
        self.enable(True)

    def sound(self):
        raw = self.raw()
        try:
            for name, _ in SOUND[:5]:
                raw[name] = float(raw[name])
        except ValueError:
            raise ValueError("Sound timing and levels must be numbers") from None
        if raw["music_mode"] != "file":
            raw["music_file"] = None
        return raw

    def snapshot(self):
        return {"baseline": self.baseline, "values": self.raw()} if self.loaded else {}

    def load(self, snapshot):
        self.baseline = snapshot["baseline"]
        self.fill(snapshot["values"])
        self.save.configure(state="normal")
