"""Episode controls and review surfaces; callbacks express user intent."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.theme import set_text


class Workspace(ttk.Frame):
    def __init__(self, parent, callbacks):
        super().__init__(parent, padding=(8, 0))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)
        self.title = ttk.Label(self, text="Choose an episode", style="Title.TLabel", wraplength=720)
        self.title.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.bind(
            "<Configure>", lambda event: self.title.configure(wraplength=max(250, event.width - 20))
        )
        self.subtitle = ttk.Label(
            self, text="AI-narrated · local review editions", style="Muted.TLabel"
        )
        self.subtitle.grid(row=1, column=0, sticky="w", pady=(0, 16))
        controls = ttk.Frame(self)
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
            variable.trace_add("write", lambda *_: callbacks["changed"]())
        buttons = ttk.Frame(self)
        buttons.grid(row=3, column=0, sticky="ew", pady=(10, 16))
        ttk.Button(buttons, text="Inspect changes", command=callbacks["plan"]).pack(side="left")
        self.produce = ttk.Button(
            buttons,
            text="Queue production",
            command=callbacks["submit"],
            style="Accent.TButton",
            state="disabled",
        )
        self.produce.pack(side="left", padx=8)
        tabs = ttk.Notebook(self)
        tabs.grid(row=4, column=0, sticky="nsew")
        self.plan = self._text_tab(tabs, "Rebuild plan")
        self.transcript = self._text_tab(tabs, "Transcript")
        publishing = ttk.Frame(tabs, padding=15)
        tabs.add(publishing, text="Publication")
        ttk.Label(
            publishing, text="Record an episode you already published.", style="Heading.TLabel"
        ).pack(anchor="w", pady=(0, 16))
        self.url = tk.StringVar()
        self.date = tk.StringVar()
        ttk.Label(publishing, text="Episode URL").pack(anchor="w")
        ttk.Entry(publishing, textvariable=self.url).pack(fill="x", pady=(5, 12))
        ttk.Label(publishing, text="Publication date · YYYY-MM-DD (optional)").pack(anchor="w")
        ttk.Entry(publishing, textvariable=self.date).pack(fill="x", pady=(5, 12))
        ttk.Button(
            publishing, text="Save publication record", command=callbacks["publication"]
        ).pack(anchor="w")
        ttk.Label(
            publishing,
            text="A saved URL records publication; a completed job records production.\nA new edition does not replace the published one.",
            style="Muted.TLabel",
            wraplength=600,
        ).pack(anchor="w", pady=16)
        outputs = ttk.Frame(self)
        outputs.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        for label, kind in [
            ("Listen", "audio"),
            ("Check subtitles", "captions"),
            ("Edition folder", "folder"),
            ("Upload package", "uploads"),
        ]:
            ttk.Button(outputs, text=label, command=lambda k=kind: callbacks["open"](k)).pack(
                side="left", padx=(0, 7)
            )

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
        self.url.set(episode.publication_url)
        self.date.set(episode.publication_date)
        set_text(self.transcript, episode.transcript)
        set_text(self.plan, "Inspect your changes before queueing an edition.")

    def show_plan(self, text, ready=False):
        set_text(self.plan, text)
        self.produce.configure(state="normal" if ready else "disabled")
