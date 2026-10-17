"""Episode stages and tools; callbacks express user intent.

Produce, Review and Release are the stages, in one notebook with one primary
action each. Transcript, Sound, Several episodes and Setup check are tools: they
open in the same space from the tools row and leave the tab strip when closed.
"""

import copy
import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.batch import Batch
from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.editors import SOUND, Editor
from field_notes_studio.presentation.icons import icon
from field_notes_studio.presentation.publication import Publication
from field_notes_studio.presentation.review import Review
from field_notes_studio.presentation.stepper import Stepper
from field_notes_studio.presentation.theme import set_text

OUTPUTS = {
    "video": "Full episode (usual)",
    "audio": "Audio and captions only",
    "preview": "First 10 seconds of video",
    "export": "Upload folder only",
}
OUTPUT_HELP = {
    "video": "Full episode: audio, subtitles, full video and thumbnail in one job. "
    "You review it once before making the upload folder.",
    "audio": "Audio and captions only, as MP3 and subtitles with no video. "
    "An alternative, not a step before the full episode.",
    "preview": "Renders the first 10 seconds of video to check its look.",
    "export": "Makes the upload folder from the approved full episode, with title, "
    "description, tags and subtitles.",
}


class Workspace(ttk.Frame):
    def __init__(self, parent, callbacks):
        super().__init__(parent, padding=(12, 0, 0, 0))
        self.callbacks = callbacks
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        self.title = ttk.Label(self, text="Choose an episode", style="Title.TLabel", wraplength=720)
        self.title.grid(row=0, column=0, sticky="w")
        self.subtitle = ttk.Label(
            self, text="AI-narrated · local versions", style="Muted.TLabel", wraplength=650
        )
        self.subtitle.grid(row=1, column=0, sticky="w", pady=(2, 10))
        self.bind("<Configure>", self._resize, add=True)
        self.stepper = Stepper(self, self.navigate)
        self.stepper.grid(row=2, column=0, sticky="w", pady=(0, 12))
        self.speed = tk.StringVar(value="1.15")
        self.outro = tk.StringVar(value="5")
        self.action = tk.StringVar(value="video")
        self.output_label = tk.StringVar(value=OUTPUTS["video"])
        self.production_base = {}
        self.show_recipe = {}
        self.production_busy = False
        self.has_episode = False
        self.last_stage = 0
        tabs = self.tabs = ttk.Notebook(self, style="Workspace.TNotebook")
        tabs.grid(row=3, column=0, sticky="nsew")
        self._produce_tab(tabs, callbacks)
        self.review = Review(tabs, callbacks)
        tabs.add(self.review, text="Review")
        self.publication = Publication(tabs, callbacks)
        tabs.add(self.publication, text="Release")
        self.transcript = self._text_tab(tabs, "Transcript")
        self.sound = Editor(
            tabs,
            SOUND,
            callbacks["changed"],
            "Pace and outro are on Produce. Custom music needs a file and a licence credit.",
        )
        self.recipe_info = ttk.Label(
            self.sound.form.content,
            text="Usual show settings",
            style="Muted.TLabel",
            wraplength=520,
        )
        first = self.sound.form.content.winfo_children()[0]
        self.recipe_info.pack(anchor="w", fill="x", before=first, pady=(0, 4))
        self.recipe_button = ttk.Button(
            self.sound.form.content, text="Show settings…", command=callbacks["recipes"]
        )
        self.recipe_button.pack(anchor="w", before=first, pady=(0, 8))
        self.sound.bind(
            "<Configure>",
            lambda e: self.recipe_info.configure(wraplength=max(200, e.width - 35)),
            add=True,
        )
        tabs.add(self.sound, text="Sound")
        self.batch = Batch(
            tabs, callbacks["batch_inspect"], callbacks["batch_submit"], callbacks["batch_changed"]
        )
        tabs.add(self.batch, text="Several episodes")
        self.batch.output(self.action.get())
        self._health_tab(tabs, callbacks)
        self.stages = (self.plan.master, self.review, self.publication)
        self.tools = {
            str(self.transcript.master): ("transcript", "Transcript"),
            str(self.sound): ("audio", "Sound"),
            str(self.batch): ("episodes", "Several episodes"),
            str(self.health.master): ("health", "Setup check"),
        }
        for tab, glyph in (
            (self.plan.master, "produce"),
            (self.review, "review"),
            (self.publication, "package"),
            (self.transcript.master, "transcript"),
            (self.sound, "audio"),
            (self.batch, "episodes"),
            (self.health.master, "health"),
        ):
            tabs.tab(
                tab,
                compound="left",
                image=(icon(self, glyph, "MUTED"), "selected", icon(self, glyph, "SELECTED_FG")),
            )
        tools = self.tools_row = ttk.Frame(self)
        tools.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(tools, text="Tools", style="Small.TLabel").pack(side="left", padx=(0, 6))
        self.tool_buttons = {}
        for path, (glyph, label) in self.tools.items():
            button = ActionButton(
                tools,
                pictogram=glyph,
                text=label,
                style="Tool.TButton",
                command=lambda p=path: self.toggle_tool(p),
            )
            button.pack(side="left", padx=(0, 4))
            self.tool_buttons[path] = button
        self.empty_state = ttk.Frame(self, style="Card.TFrame", padding=24)
        self.empty_title = ttk.Label(self.empty_state, text="", style="CardHeading.TLabel")
        self.empty_title.pack(anchor="w")
        self.empty_text = ttk.Label(
            self.empty_state, text="", style="CardMuted.TLabel", wraplength=560
        )
        self.empty_text.pack(anchor="w", pady=(6, 12))
        self.empty_action = ActionButton(self.empty_state, pictogram="transcript", text="")
        self.empty_action.pack(anchor="w")
        self.url, self.date = self.publication.url, self.publication.date
        tabs.bind("<<NotebookTabChanged>>", lambda _: self._tab_changed(), add=True)
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
        self.output_guidance()
        self._tab_changed()
        self.episode_available(False)

    def _resize(self, event):
        if event.widget is self:
            self.title.configure(wraplength=max(250, event.width - 20))
            self.subtitle.configure(wraplength=max(250, event.width - 20))
            self.empty_text.configure(wraplength=max(250, event.width - 80))

    def _produce_tab(self, tabs, callbacks):
        frame = ttk.Frame(tabs, padding=(16, 12, 16, 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(5, weight=1)
        tabs.add(frame, text="Produce")
        self.intro = ttk.Label(
            frame,
            text="Make the full episode: audio, captions, video and thumbnail in one job.",
            wraplength=640,
        )
        self.intro.grid(row=0, column=0, columnspan=2, sticky="w")
        controls = self.controls = ttk.Frame(frame)
        controls.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        for column, (label, variable, values) in enumerate(
            [
                ("Pace ×", self.speed, ("0.75", "1", "1.15", "1.25", "1.5")),
                ("Outro seconds", self.outro, ("0", "2", "5", "8", "10", "15")),
            ]
        ):
            box = ttk.Frame(controls)
            box.grid(row=0, column=column, sticky="w", padx=(0, 18))
            ttk.Label(box, text=label, style="Muted.TLabel").pack(side="left", padx=(0, 8))
            combo = ttk.Combobox(box, textvariable=variable, values=values, width=8)
            combo.pack(side="left")
            setattr(self, "speed_control" if label == "Pace ×" else "outro_control", combo)
            variable.trace_add("write", lambda *_: callbacks["changed"]())
        buttons = self.production_buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.full_episode = ActionButton(
            buttons,
            pictogram="produce",
            text="Produce episode",
            command=callbacks["produce_episode"],
            state="disabled",
        )
        self.full_episode.pack(side="left")
        self.more_button = ActionButton(
            buttons,
            pictogram="more",
            text="More options…",
            command=self.toggle_more,
            style="Compact.TButton",
        )
        self.more_button.pack(side="left", padx=(8, 0))
        more = self.more = ttk.Frame(frame, style="Card.TFrame", padding=12)
        output = ttk.Frame(more, style="CardRow.TFrame")
        output.pack(fill="x")
        ttk.Label(output, text="Make instead", style="Card.TLabel").pack(side="left")
        self.output_control = ttk.Combobox(
            output,
            textvariable=self.output_label,
            values=tuple(OUTPUTS.values()),
            state="readonly",
            width=26,
        )
        self.output_control.pack(side="left", padx=8)
        self.output_control.bind(
            "<<ComboboxSelected>>",
            lambda _: self.action.set(
                next(k for k, v in OUTPUTS.items() if v == self.output_label.get())
            ),
        )
        self.output_help = ttk.Label(more, text="", style="CardMuted.TLabel", wraplength=560)
        self.output_help.pack(anchor="w", pady=(6, 8))
        steps = ttk.Frame(more, style="CardRow.TFrame")
        steps.pack(fill="x")
        self.inspect_button = ActionButton(
            steps,
            pictogram="search",
            text="Check plan",
            command=callbacks["plan"],
            style="Compact.TButton",
        )
        self.inspect_button.pack(side="left")
        self.produce = ActionButton(
            steps,
            pictogram="queue",
            text="Queue checked plan",
            command=callbacks["submit"],
            style="Compact.TButton",
            state="disabled",
        )
        self.produce.pack(side="left", padx=6)
        self.outputs = ttk.Frame(steps, style="CardRow.TFrame")
        self.outputs.pack(side="right")
        for label, kind in (("Version folder", "folder"), ("Upload folder", "uploads")):
            ActionButton(
                self.outputs,
                pictogram="folder",
                text=label,
                style="Compact.TButton",
                command=lambda k=kind: callbacks["open"](k),
            ).pack(side="left", padx=(6, 0))
        self.action.trace_add("write", lambda *_: self.output_guidance())
        self.guidance = ttk.Label(frame, text="", style="Muted.TLabel", wraplength=640)
        self.guidance.grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 8))
        text = tk.Text(
            frame, wrap="word", padx=14, pady=12, relief="flat", height=6, state="disabled"
        )
        scrollbar = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=5, column=0, sticky="nsew", pady=(0, 14))
        scrollbar.grid(row=5, column=1, sticky="ns", pady=(0, 14))
        self.plan = text
        frame.bind(
            "<Configure>",
            lambda e: [
                label.configure(wraplength=max(250, e.width - 40))
                for label in (self.intro, self.guidance, self.output_help)
            ],
            add=True,
        )

    def _health_tab(self, tabs, callbacks):
        frame = ttk.Frame(tabs, padding=(0, 10, 0, 0))
        tabs.add(frame, text="Setup check")
        self.health_actions = ttk.Frame(frame, padding=(12, 0, 12, 8))
        self.health_actions.pack(fill="x")
        ActionButton(
            self.health_actions,
            pictogram="refresh",
            text="Check setup",
            command=callbacks["health"],
        ).pack(side="left")
        ActionButton(
            self.health_actions,
            pictogram="worker",
            text="Start or restart background producer",
            command=callbacks["worker_restart"],
        ).pack(side="left", padx=6)
        text = tk.Text(
            frame, wrap="word", padx=18, pady=16, relief="flat", height=10, state="disabled"
        )
        scrollbar = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        self.health = text
        tabs.bind(
            "<<NotebookTabChanged>>",
            lambda _: callbacks["health"]() if tabs.select() == str(frame) else None,
            add=True,
        )

    def toggle_more(self, show=None):
        show = not self.more.winfo_ismapped() if show is None else show
        if show:
            self.more.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
            self.more_button.reset_feedback("Fewer options")
        else:
            self.more.grid_remove()
            self.more_button.reset_feedback("More options…")

    def preflight_status(self, message, action="video"):
        short = message if len(message) <= 78 else message[:75] + "…"
        if action != "export":
            self.guidance.configure(text="Checks · " + short)
        if action in {"export", "both"}:
            self.publication.preflight.configure(text="Upload folder · " + short)
            # The idle "not checked" note is noise on Release; blockers and results show.
            if message.startswith("Not checked"):
                self.publication.preflight.grid_remove()
            else:
                self.publication.preflight.grid()

    def effective_recipe(self):
        values = copy.deepcopy(self.production_base)
        values.update(self.sound.sound())
        values.update(speed=float(self.speed.get()), outro_seconds=float(self.outro.get()))
        return values

    def draft_conflict(self, visible):
        if visible:
            self.conflict.grid(row=5, column=0, sticky="ew")
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
        self.show_stages()
        self.title.configure(text=episode.title)
        self.subtitle.configure(
            text=f"{episode.identifier} · {episode.duration / 60:.1f} min · AI-narrated"
        )
        self.speed.set(f"{settings['speed']:g}")
        self.outro.set(f"{settings['outro_seconds']:g}")
        self.sound.fill(settings)
        self.publication.load_episode(episode)
        set_text(self.transcript, episode.transcript)
        set_text(self.plan, "Check your changes before queueing a version.")

    def show_plan(self, text, ready=False):
        set_text(self.plan, text)
        self.produce.configure(state="normal" if ready and not self.production_busy else "disabled")

    def episode_available(self, value):
        self.has_episode = value
        state = "normal" if value else "disabled"
        for widget in (self.speed_control, self.outro_control, self.inspect_button):
            widget.configure(state=state)
        self.output_control.configure(state="readonly" if value else "disabled")
        self.recipe_button.configure(state=state)
        if value:
            self.output_guidance()
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

    def show_empty(self, title, text, action=None, command=None, *, heading=None):
        """Replace the stages with one sentence and at most one button."""
        self.tabs.grid_remove()
        self.tools_row.grid_remove()
        self.empty_state.grid(row=3, column=0, sticky="new")
        self.title.configure(text=heading or title)
        self.empty_title.configure(text=title)
        self.empty_text.configure(text=text)
        if action and command:
            self.empty_action.reset_feedback(action)
            self.empty_action.configure(command=command)
            self.empty_action.pack(anchor="w")
        else:
            self.empty_action.pack_forget()
        self.stepper.grid_remove()
        self.episode_available(False)

    def compact(self, value):
        self.compacted = value
        if value:
            self.intro.grid_remove()
        else:
            self.intro.grid()
        if value or self.empty_state.winfo_manager():
            self.stepper.grid_remove()
        else:
            self.stepper.grid()

    def show_stages(self):
        if self.empty_state.winfo_manager():
            self.empty_state.grid_remove()
            self.tabs.grid()
            self.tools_row.grid()
            self.compact(getattr(self, "compacted", False))

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
            if key in {"speed", "outro", "action"} and (key != "action" or value in OUTPUTS):
                getattr(self, key).set(value)
        if draft.get("publication"):
            self.publication.drafts[self.publication.episode] = tuple(draft["publication"])
            self.publication.load_episode(self.publication.current_episode)

    def output_guidance(self):
        action = self.action.get()
        if hasattr(self, "batch"):
            self.batch.output(action)
        self.output_label.set(OUTPUTS.get(action, action))
        self.output_help.configure(text=OUTPUT_HELP.get(action, ""))
        self.guidance.configure(
            text=""
            if action == "video"
            else "Other output selected: " + OUTPUTS[action] + ". Use Check plan, then Queue."
        )
        if action != "video" and hasattr(self, "more"):
            self.toggle_more(True)
        state = "disabled" if action == "export" or not self.has_episode else "normal"
        self.speed_control.configure(state=state)
        self.outro_control.configure(state=state)

    def show_review(self):
        self.tabs.select(self.review)

    def navigate(self, index):
        """Stepper: 0 opens preparation, 1–3 select Produce, Review or Release."""
        if index == 0:
            self.callbacks.get("prepare", lambda: None)()
        elif not self.empty_state.winfo_manager():
            self.tabs.select(self.stages[index - 1])

    def select_stage(self, index):
        if not self.empty_state.winfo_manager():
            self.tabs.select(self.stages[index])

    def toggle_tool(self, path):
        if self.tabs.select() == path:
            self.tabs.select(self.stages[self.last_stage])
        else:
            self.tabs.select(path)

    def tool_open(self):
        return self.tabs.select() in self.tools

    def _tab_changed(self):
        selected = self.tabs.select()
        for path in self.tools:
            if path != selected and self.tabs.tab(path, "state") != "hidden":
                self.tabs.hide(path)
        for path, button in self.tool_buttons.items():
            button.set_style("ToolOn.TButton" if path == selected else "Tool.TButton")
        for index, stage in enumerate(self.stages):
            if str(stage) == selected:
                self.last_stage = index
        release = selected == str(self.publication)
        if release:
            # Release checks its upload folder lazily, only once it is on screen.
            self.callbacks["package_refresh"]()
        # Release takes the whole width and height, as in the approved one-page design.
        for widget in (self.subtitle, self.tools_row):
            if release or (widget is self.tools_row and self.empty_state.winfo_manager()):
                widget.grid_remove()
            else:
                widget.grid()
        self.callbacks.get("stage", lambda _release: None)(release)

    def show_plan_tab(self):
        self.tabs.select(self.plan.master)
