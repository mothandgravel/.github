"""Episode controls and review surfaces; callbacks express user intent."""

import copy
import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.batch import Batch
from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.editors import SOUND, Editor
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
        self.action = tk.StringVar(value="video")
        self.production_base = {}
        self.show_recipe = {}
        self.production_busy = False
        self.has_episode = False
        for column, (label, variable, values) in enumerate(
            [
                ("Pace ×", self.speed, ("0.75", "1", "1.15", "1.25", "1.5")),
                ("Outro seconds", self.outro, ("0", "2", "5", "8", "10", "15")),
                ("Output", self.action, ("audio", "preview", "video", "export")),
            ]
        ):
            box = ttk.Frame(controls)
            box.grid(row=0, column=column, sticky="w", padx=(0, 18))
            ttk.Label(
                box, text="Optional output" if label == "Output" else label, style="Muted.TLabel"
            ).pack(anchor="w")
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
        self.full_episode = ActionButton(
            buttons,
            pictogram="produce",
            text="Produce episode",
            command=callbacks["produce_episode"],
            style="Compact.TButton",
            state="disabled",
        )
        self.full_episode.pack(side="left", before=buttons.winfo_children()[0], padx=(0, 8))
        self.produce = ActionButton(
            buttons,
            pictogram="produce",
            text="Queue inspected output",
            command=callbacks["submit"],
            style="Compact.TButton",
            state="disabled",
        )
        self.produce.pack(side="left", padx=8)
        self.guidance = ttk.Label(self, text="", style="Muted.TLabel", wraplength=650)
        self.guidance.grid(row=4, column=0, sticky="w", pady=(0, 10))
        self.action.trace_add("write", lambda *_: self.output_guidance())
        self.output_guidance()
        tabs = self.tabs = ttk.Notebook(self, style="Workspace.TNotebook")
        tabs.grid(row=5, column=0, sticky="nsew")
        self.plan = self._text_tab(tabs, "Produce")
        self.review = Review(tabs, callbacks)
        tabs.add(self.review, text="Review")
        self.publication = Publication(tabs, callbacks)
        tabs.add(self.publication, text="Release")
        self.transcript = self._text_tab(tabs, "Transcript")
        self.sound = Editor(
            tabs,
            SOUND,
            callbacks["changed"],
            "Pace and outro are in Produce. Inspect changes before queueing. Custom music needs a file and license credit.",
        )
        self.recipe_info = ttk.Label(
            self.sound.form.content,
            text="Configured defaults",
            style="Muted.TLabel",
            wraplength=520,
        )
        first = self.sound.form.content.winfo_children()[0]
        self.recipe_info.pack(anchor="w", fill="x", before=first, pady=(0, 4))
        self.recipe_button = ttk.Button(
            self.sound.form.content, text="Show recipes / overrides…", command=callbacks["recipes"]
        )
        self.recipe_button.pack(anchor="w", before=first, pady=(0, 8))
        self.sound.bind(
            "<Configure>",
            lambda e: self.recipe_info.configure(wraplength=max(200, e.width - 35)),
            add=True,
        )
        tabs.add(self.sound, text="Audio")
        self.batch = Batch(
            tabs, callbacks["batch_inspect"], callbacks["batch_submit"], callbacks["batch_changed"]
        )
        tabs.add(self.batch, text="Batch")
        self.batch.output(self.action.get())
        self.health = self._text_tab(tabs, "Health")
        tabs.bind(
            "<<NotebookTabChanged>>",
            lambda _: callbacks["health"]() if tabs.select() == str(self.health.master) else None,
            add=True,
        )
        for tab, glyph in (
            (self.plan.master, "produce"),
            (self.review, "review"),
            (self.publication, "package"),
            (self.transcript.master, "transcript"),
            (self.sound, "audio"),
            (self.batch, "batch"),
            (self.health.master, "health"),
        ):
            tabs.tab(
                tab,
                compound="left",
                image=(icon(self, glyph), "selected", icon(self, glyph, SURFACE)),
            )
        self.url, self.date = self.publication.url, self.publication.date
        tabs.bind("<<NotebookTabChanged>>", lambda _: self.layout_stage(), add=True)
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
        self.health_actions = ttk.Frame(self)
        ActionButton(
            self.health_actions,
            pictogram="refresh",
            text="Check health",
            command=callbacks["health"],
        ).pack(side="left", padx=4)
        ActionButton(
            self.health_actions,
            pictogram="produce",
            text="Start / restart worker",
            command=callbacks["worker_restart"],
        ).pack(side="left")
        self.layout_stage()
        self.conflict = ttk.Frame(self, padding=(0, 8))
        ttk.Label(
            self.conflict,
            text="Newer draft in another window · your recovery copy is saved",
            style="Draft.TLabel",
        ).pack(anchor="w")
        actions = ttk.Frame(self.conflict)
        actions.pack(anchor="w", pady=(4, 0))
        for label, callback in (
            ("Load saved draft", "draft_reload"),
            ("Keep my draft", "draft_keep"),
            ("Open recovery copies", "draft_recovery"),
        ):
            ActionButton(
                actions,
                pictogram="save"
                if callback == "draft_keep"
                else "folder"
                if callback == "draft_recovery"
                else "refresh",
                text=label,
                command=callbacks[callback],
            ).pack(side="left", padx=(0, 6))

    def preflight_status(self, message, action="video"):
        short = message if len(message) <= 78 else message[:75] + "…"
        if action != "export":
            self.guidance.configure(text="Preflight · " + short)
        if action in {"export", "both"}:
            self.publication.preflight.configure(text="Export · " + short)

    def effective_recipe(self):
        values = copy.deepcopy(self.production_base)
        values.update(self.sound.sound())
        values.update(speed=float(self.speed.get()), outro_seconds=float(self.outro.get()))
        return values

    def draft_conflict(self, visible):
        if visible:
            self.conflict.grid(row=7, column=0, sticky="ew")
        else:
            self.conflict.grid_remove()

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
        self.production_base = copy.deepcopy(settings)
        self.show_recipe = {}
        self.title.configure(text=episode.title)
        self.subtitle.configure(
            text=f"{episode.identifier} · {episode.duration / 60:.1f} min · AI-narrated"
        )
        self.speed.set(f"{settings['speed']:g}")
        self.outro.set(f"{settings['outro_seconds']:g}")
        self.sound.fill(settings)
        self.publication.load_episode(episode)
        set_text(self.transcript, episode.transcript)
        set_text(self.plan, "Inspect your changes before queueing an edition.")

    def show_plan(self, text, ready=False):
        set_text(self.plan, text)
        self.produce.configure(state="normal" if ready and not self.production_busy else "disabled")

    def episode_available(self, value):
        self.has_episode = value
        self.production_working(self.production_busy)

    def production_working(self, value):
        self.production_busy = value
        self.full_episode.configure(
            state="normal" if self.has_episode and not value else "disabled",
            text="Checking episode…" if value else "Produce episode",
        )
        if value:
            self.produce.configure(state="disabled")

    def show_health(self, message):
        set_text(self.health, message)

    def draft(self):
        publication = self.publication
        return {
            "production_base": copy.deepcopy(self.production_base),
            "show_recipe": copy.deepcopy(self.show_recipe),
            "recipe": {
                "speed": self.speed.get(),
                "outro": self.outro.get(),
                "action": self.action.get(),
            },
            "publication": publication.drafts.get(publication.episode),
            "sound": self.sound.raw(),
            "metadata": publication.editor.snapshot() or publication.metadata_draft,
        }

    def restore(self, draft):
        if isinstance(draft.get("production_base"), dict) and draft["production_base"]:
            self.production_base = copy.deepcopy(draft["production_base"])
        self.show_recipe = copy.deepcopy(draft.get("show_recipe", {}))
        if draft.get("sound"):
            self.sound.fill(draft["sound"])
        self.publication.metadata_draft = draft.get("metadata", {})
        for key, value in draft.get("recipe", {}).items():
            if key in {"speed", "outro", "action"} and (
                key != "action" or value in {"audio", "preview", "video", "export"}
            ):
                getattr(self, key).set(value)
        if draft.get("publication"):
            self.publication.drafts[self.publication.episode] = tuple(draft["publication"])
            self.publication.load_episode(self.publication.current_episode)

    def output_guidance(self):
        if hasattr(self, "batch"):
            self.batch.output(self.action.get())
        messages = {
            "audio": "Audio only → MP3 and subtitles; no video. This is an alternative, not a prerequisite.",
            "preview": "Preview → render the first 10 seconds to check the video style.",
            "video": "Full episode → audio, retimed captions, full video and thumbnail, in one job.",
            "export": "Export → package the saved full edition with title, description, tags and subtitles.",
        }
        self.guidance.configure(
            text=(
                "Full episode: audio, subtitles, full video and thumbnail. Review once before export."
                if self.action.get() == "video"
                else "Produce episode includes audio + video. Optional output: "
                + messages[self.action.get()]
            )
        )
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
        health = self.tabs.select() == str(self.health.master)
        release_editor = self.tabs.select() == str(
            self.publication
        ) and self.publication.tabs.select() == str(self.publication.editor)
        if (
            producing
            or health
            or release_editor
            or self.tabs.select() == str(self.review)
            or self.tabs.select() in {str(self.sound), str(self.batch)}
            or (self.tabs.select() == str(self.publication) and self.publication.files_visible())
        ):
            self.outputs.grid_remove()
        else:
            self.outputs.grid()
        if health:
            self.health_actions.grid(row=6, column=0, sticky="ew", pady=(14, 0))
        else:
            self.health_actions.grid_remove()

    def show_plan_tab(self):
        self.tabs.select(self.plan.master)
