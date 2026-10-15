"""Episode controls and review surfaces; callbacks express user intent."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.icons import icon
from field_notes_studio.presentation.publication import Publication
from field_notes_studio.presentation.review import Review
from field_notes_studio.presentation.theme import SURFACE, set_text


class Workspace(ttk.Frame):
    def __init__(self, parent, callbacks):
        super().__init__(parent, padding=(8, 0))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(5, weight=1)
        self.title = ttk.Label(self, text="Choose an episode", style="Title.TLabel", wraplength=720)
        self.title.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.bind(
            "<Configure>", lambda event: self.title.configure(wraplength=max(250, event.width - 20))
        )
        self.subtitle = ttk.Label(
            self, text="AI-narrated · local review editions", style="Muted.TLabel", wraplength=650
        )
        self.bind(
            "<Configure>",
            lambda e: self.subtitle.configure(wraplength=max(250, e.width - 20)),
            add=True,
        )
        self.subtitle.grid(row=1, column=0, sticky="w", pady=(0, 12))
        controls = self.controls = ttk.Frame(self)
        controls.grid(row=2, column=0, sticky="ew")
        self.speed = tk.StringVar(value="1.15")
        self.outro = tk.StringVar(value="5")
        self.action = tk.StringVar(value="audio")
        for column, (label, variable, values) in enumerate(
            [
                ("Pace ×", self.speed, ("0.75", "1", "1.15", "1.25", "1.5")),
                ("Outro seconds", self.outro, ("0", "2", "5", "8", "10", "15")),
                ("Output", self.action, ("audio", "preview", "video", "export")),
            ]
        ):
            box = ttk.Frame(controls)
            box.grid(row=0, column=column, sticky="w", padx=(0, 18))
            ttk.Label(box, text=label, style="Muted.TLabel").pack(anchor="w")
            combo = ttk.Combobox(
                box,
                textvariable=variable,
                values=values,
                width=13,
                state="readonly" if label == "Output" else "normal",
            )
            combo.pack(anchor="w", pady=5)
            if label != "Output":
                setattr(self, "speed_control" if label == "Pace ×" else "outro_control", combo)
            variable.trace_add("write", lambda *_: callbacks["changed"]())
        buttons = self.production_buttons = ttk.Frame(self)
        buttons.grid(row=3, column=0, sticky="ew", pady=(10, 16))
        ActionButton(
            buttons, pictogram="search", text="Inspect changes", command=callbacks["plan"]
        ).pack(side="left")
        self.produce = ActionButton(
            buttons,
            pictogram="produce",
            text="Queue production",
            command=callbacks["submit"],
            style="Accent.TButton",
            state="disabled",
        )
        self.produce.pack(side="left", padx=8)
        self.guidance = ttk.Label(self, text="", style="Muted.TLabel", wraplength=650)
        self.guidance.grid(row=4, column=0, sticky="w", pady=(0, 10))
        self.action.trace_add("write", lambda *_: self.output_guidance())
        self.output_guidance()
        tabs = self.tabs = ttk.Notebook(self)
        tabs.grid(row=5, column=0, sticky="nsew")
        self.plan = self._text_tab(tabs, "Produce")
        self.review = Review(tabs, callbacks)
        tabs.add(self.review, text="Review")
        self.publication = Publication(tabs, callbacks)
        tabs.add(self.publication, text="Release")
        self.transcript = self._text_tab(tabs, "Transcript")
        for tab, glyph in (
            (self.plan.master, "produce"),
            (self.review, "review"),
            (self.publication, "package"),
            (self.transcript.master, "transcript"),
        ):
            tabs.tab(
                tab,
                compound="left",
                image=(icon(self, glyph), "selected", icon(self, glyph, SURFACE)),
            )
        self.url, self.date = self.publication.url, self.publication.date
        tabs.bind("<<NotebookTabChanged>>", lambda _: self.layout_stage())
        self.publication.tabs.bind(
            "<<NotebookTabChanged>>", lambda _: self.layout_stage(), add=True
        )
        outputs = self.outputs = ttk.Frame(self)
        outputs.grid(row=6, column=0, sticky="ew", pady=(14, 0))
        for label, kind in [
            ("Edition folder", "folder"),
            ("Upload package", "uploads"),
        ]:
            ActionButton(
                outputs,
                pictogram="folder" if kind == "folder" else "package",
                text=label,
                command=lambda k=kind: callbacks["open"](k),
            ).pack(side="left", padx=(0, 7))
        self.layout_stage()

    @staticmethod
    def _text_tab(tabs, title):
        frame = ttk.Frame(tabs)
        tabs.add(frame, text=title)
        text = tk.Text(
            frame, wrap="word", padx=18, pady=16, relief="flat", height=10, state="disabled"
        )
        scrollbar = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        return text

    def load(self, episode, settings):
        self.title.configure(text=episode.title)
        self.subtitle.configure(
            text=f"{episode.identifier} · {episode.duration / 60:.1f} min · AI-narrated"
        )
        self.speed.set(f"{settings['speed']:g}")
        self.outro.set(f"{settings['outro_seconds']:g}")
        self.publication.load_episode(episode)
        set_text(self.transcript, episode.transcript)
        set_text(self.plan, "Inspect your changes before queueing an edition.")

    def show_plan(self, text, ready=False):
        set_text(self.plan, text)
        self.produce.configure(state="normal" if ready else "disabled")

    def output_guidance(self):
        messages = {
            "audio": "Audio → finish an MP3 and subtitles. Then open Review to listen and approve.",
            "preview": "Preview → render the first 10 seconds to check the video style.",
            "video": "Video → render the full episode and thumbnail. Then review the full video.",
            "export": "Export → package the saved full edition with title, description, tags and subtitles.",
        }
        self.guidance.configure(text=messages[self.action.get()])
        state = "disabled" if self.action.get() == "export" else "normal"
        self.speed_control.configure(state=state)
        self.outro_control.configure(state=state)

    def show_review(self):
        self.tabs.select(self.review)

    def layout_stage(self):
        producing = self.tabs.select() == str(self.plan.master)
        for widget in (self.controls, self.production_buttons, self.guidance):
            if producing:
                widget.grid()
            else:
                widget.grid_remove()
        if self.tabs.select() == str(self.publication) and self.publication.files_visible():
            self.outputs.grid_remove()
        else:
            self.outputs.grid()

    def show_plan_tab(self):
        self.tabs.select(self.plan.master)
