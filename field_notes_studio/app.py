"""Composition root: construct the Tk views and connect application callbacks."""

from __future__ import annotations

import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from field_notes_studio import appearance
from field_notes_studio.controller import Controller
from field_notes_studio.make_flow import MakeFlow
from field_notes_studio.preparation_controller import PreparationController
from field_notes_studio.preparation_service import PreparationService
from field_notes_studio.presentation import theme
from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.icons import icon
from field_notes_studio.presentation.make_episode import RunPanel, WorkListView
from field_notes_studio.presentation.preparation import PreparationWindow
from field_notes_studio.presentation.queue import ProductionQueue
from field_notes_studio.presentation.readiness import ReadinessCard
from field_notes_studio.presentation.shelf import Shelf
from field_notes_studio.presentation.workspace import Workspace
from field_notes_studio.service import Studio

SHORTCUTS = (
    ("Work list", "Ctrl+H", "<Control-h>"),
    ("Make episode from a note…", "Ctrl+N", "<Control-n>"),
    ("Do the next step", "Ctrl+Enter", "<Control-Return>"),
    ("Search episodes", "Ctrl+F", "<Control-f>"),
    ("Go to Produce", "Ctrl+1", "<Control-Key-1>"),
    ("Go to Review", "Ctrl+2", "<Control-Key-2>"),
    ("Go to Release", "Ctrl+3", "<Control-Key-3>"),
    ("Show or hide jobs", "Ctrl+J", "<Control-j>"),
)
APPEARANCE_RECHECK_SECONDS = 20


class Application:
    def __init__(self, root, directory: Path):
        self.root = root
        self.directory = directory
        self.preparation = None
        self.closed = False
        self.tick_handle = None
        self.poll_handle = None
        self.jobs_open = False
        self.attention = 0
        self.message_text = ""
        self.appearance_checked = 0.0
        studio = Studio(directory)
        try:
            self.preferences = studio.preferences()
        except Exception:
            self.preferences = {}
        forced = os.environ.get("STUDIO_APPEARANCE", "")
        self.appearance = tk.StringVar(
            value=forced
            if forced in appearance.CHOICES
            else self.preferences.get("appearance", "system")
        )
        self.system_dark = self.preferences.get("system_dark")
        theme.apply(root, appearance.resolve(self.appearance.get(), self.system_dark))
        root.title("Moth & Gravel · Production studio")
        root.geometry("1280x920")
        root.minsize(1050, 760)
        main = self.main = ttk.Frame(root, padding=(24, 8, 24, 0))
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)
        self.brand = ttk.Label(
            main, text="MOTH & GRAVEL  /  LOCAL PRODUCTION", style="Brand.TLabel"
        )
        self.brand.grid(row=0, column=0, sticky="w")
        ttk.Label(main, text="Production studio", style="Studio.TLabel").grid(
            row=1, column=0, sticky="w", pady=(0, 4)
        )
        header = ttk.Frame(main)
        header.grid(row=0, column=0, rowspan=2, sticky="e")
        self.view_name = "home"
        self.home_button = ActionButton(
            header,
            pictogram="episodes",
            text="Work list",
            command=self.show_home,
            style="Compact.TButton",
        )
        # B's front door: one summary, one confirm. The step-by-step Prepare window
        # stays in the Menu as the expert path.
        self.prepare_button = ActionButton(
            header,
            pictogram="produce",
            text="Make episode from a note…",
            command=self.make_episode,
            style="Accent.TButton",
        )
        self.episodes_button = ActionButton(
            header,
            pictogram="menu",
            text="Show episodes",
            command=self.toggle_episodes,
            style="Compact.TButton",
        )
        self.release_focused = False
        self.episodes_shown = False
        self.prepare_button.pack(side="left")
        self.menu_button = ttk.Menubutton(
            header, text="Menu", image=icon(header, "menu"), compound="left"
        )
        self.menu_button.pack(side="left", padx=(8, 0))
        self.notes_service = None
        self.controller = Controller(studio, self)
        self.flow = MakeFlow(self.controller, self)
        body = self.body = ttk.Panedwindow(main, orient="horizontal")
        body.grid(row=2, column=0, sticky="nsew")
        self.home = WorkListView(main, {"open": self.flow.open_item})
        self.run_panel = RunPanel(
            main,
            {
                "hide": self.show_home,
                "stop": self.flow.stop,
                "next": self.flow.next,
                "recover": self.flow.recover,
                "billing": self.flow.billing,
                "notify": self.flow.set_notify,
                "close": self.flow.close,
            },
        )
        self.shelf = Shelf(body, self.controller.select, self.controller.select_note)
        self.readiness = ReadinessCard(
            self.shelf,
            self.controller.episode_controls.act,
            self.controller.episode_controls.refresh,
            published=self.published,
            changed=self.readiness_changed,
        )
        self.readiness.grid(row=6, column=0, sticky="ew", pady=(0, 12))
        self.workspace = Workspace(
            body,
            {
                "recipes": self.controller.episode_controls.open_recipes,
                "changed": self.controller.changed,
                "draft": self.controller.draft_changed,
                "metadata_save": self.controller.save_metadata,
                "metadata_reload": lambda: self.controller.load_metadata(discard=True),
                "batch_inspect": self.controller.inspect_batch,
                "batch_submit": self.controller.submit_batch,
                "batch_changed": self.controller.batch_changed,
                "health": self.controller.health,
                "worker_restart": self.controller.restart_worker,
                "draft_reload": lambda: self.controller.resolve_draft(False),
                "draft_keep": lambda: self.controller.resolve_draft(True),
                "draft_recovery": self.controller.open_draft_recovery,
                "plan": self.controller.inspect,
                "submit": self.controller.submit,
                "produce_episode": self.controller.production.start,
                "publication": self.controller.publication,
                "open": self.controller.open_output,
                "refresh": self.controller.refresh_review,
                "open_review": self.controller.open_review,
                "approve": self.controller.approve,
                "release_refresh": self.controller.refresh_release,
                "release_review": self.controller.release_review,
                "release_package": self.controller.prepare_package,
                "package_refresh": self.controller.refresh_package,
                "package_copy": self.controller.copy_package_path,
                "youtube": self.controller.open_publisher,
                "website": self.open_website,
                "status": self.status,
                "prepare": self.prepare_selected,
                "stage": self.release_focus,
            },
        )
        # The shelf keeps its width; the stages take any extra space.
        body.add(self.shelf, weight=0)
        body.add(self.workspace, weight=1)
        self.sash_placed = False
        body.bind("<Configure>", self._place_sash, add=True)
        # Jobs open under the stages, so the shelf and its card keep their height.
        self.jobs = ProductionQueue(
            self.workspace,
            self.controller.stop,
            self.controller.retry,
            self.controller.job_detail,
            self.controller.history,
            self.controller.open_job_output,
            self.controller.review_job,
        )
        self.jobs.on_render = self.jobs_rendered
        self.release_focus(self.workspace.tabs.select() == str(self.workspace.publication))
        ttk.Separator(main).grid(row=4, column=0, sticky="ew", pady=(8, 0))
        bar = self.status_bar = ttk.Frame(main, padding=(0, 6, 0, 8))
        bar.grid(row=5, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        self.activity = ttk.Label(bar, text="Nothing running", compound="left")
        self.activity.grid(row=0, column=0, sticky="w")
        self.message = ttk.Label(bar, text="", style="Muted.TLabel")
        self.message.grid(row=0, column=1, sticky="ew", padx=(12, 12))
        self.jobs_button = ActionButton(
            bar,
            pictogram="history",
            text="Jobs (0)",
            command=self.toggle_jobs,
            style="Compact.TButton",
        )
        self.jobs_button.grid(row=0, column=2, sticky="e")
        self.jobs_rendered()
        self.status("Loading the episode shelf…")
        root.bind("<Configure>", self.resize)
        self._menu()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.workspace.tabs.bind(
            "<<NotebookTabChanged>>", lambda _: self.controller.draft_changed(), add=True
        )
        self.shelf.query.trace_add("write", lambda *_: self.controller.draft_changed())
        root.bind("<FocusIn>", lambda _: self.check_appearance(), add=True)
        self.flow.notify = bool(self.preferences.get("notify"))
        self.run_panel.notify.set(self.flow.notify)
        self.controller.start()
        self.show_view("home")
        self.check_appearance(force=True)
        self.tick()
        self.poll()

    # Header menu, shortcuts and appearance ------------------------------------------

    def _menu(self):
        menu = self.menu = tk.Menu(self.menu_button, tearoff=False)
        commands = {
            "<Control-h>": self.show_home,
            "<Control-n>": self.make_episode,
            "<Control-Return>": self.next_step,
            "<Control-f>": self.focus_search,
            "<Control-Key-1>": lambda: self.workspace.select_stage(0),
            "<Control-Key-2>": lambda: self.workspace.select_stage(1),
            "<Control-Key-3>": lambda: self.workspace.select_stage(2),
            "<Control-j>": self.toggle_jobs,
        }
        for index, (label, accelerator, sequence) in enumerate(SHORTCUTS):
            if index in {2, 4, 7}:
                menu.add_separator()
            menu.add_command(label=label, accelerator=accelerator, command=commands[sequence])
            self.root.bind(sequence, lambda event, c=commands[sequence]: self.shortcut(event, c))
        menu.add_separator()
        # The expert path: today's screens, unchanged.
        menu.add_command(
            label="Episodes and stages (expert)", command=lambda: self.show_view("episodes")
        )
        menu.add_command(
            label="Prepare a note step by step…", command=lambda: self.open_preparation()
        )
        menu.add_separator()
        self.appearance_menu = tk.Menu(menu, tearoff=False)
        for value, label in (
            ("system", "Match this computer"),
            ("light", "Paper (light)"),
            ("night", "Night"),
        ):
            self.appearance_menu.add_radiobutton(
                label=label,
                value=value,
                variable=self.appearance,
                command=self.appearance_chosen,
            )
        menu.add_cascade(label="Appearance", menu=self.appearance_menu)
        menu.add_command(
            label="Setup check", command=lambda: self.workspace.toggle_tool(self._health_tab())
        )
        self.menu_button.configure(menu=menu)
        self._appearance_label()

    def _health_tab(self):
        return str(self.workspace.health.master)

    def _appearance_label(self):
        detected = (
            "not detected" if self.system_dark is None else "Night" if self.system_dark else "Paper"
        )
        self.appearance_menu.entryconfigure(0, label=f"Match this computer ({detected})")

    def appearance_chosen(self):
        self.apply_appearance()
        self.controller.task(
            lambda: self.controller.studio.remember(appearance=self.appearance.get()),
            lambda _: None,
        )

    def apply_appearance(self):
        name = appearance.resolve(self.appearance.get(), self.system_dark)
        if name != theme.NAME:
            theme.apply(self.root, name)
            theme.retheme(self.root)
        self._appearance_label()

    def check_appearance(self, force=False):
        """Ask the desktop for its light or dark setting, off the UI thread."""
        if self.closed or os.environ.get("STUDIO_APPEARANCE"):
            return
        if self.appearance.get() != "system" and not force:
            return
        now = time.monotonic()
        if not force and now - self.appearance_checked < APPEARANCE_RECHECK_SECONDS:
            return
        self.appearance_checked = now
        mailbox = self.controller.mailbox

        def probe():
            try:
                value = appearance.system_prefers_dark()
            except Exception:
                value = None
            mailbox.put((self.system_appearance, value, None, None))

        threading.Thread(target=probe, name="studio-appearance", daemon=True).start()

    def system_appearance(self, dark):
        if self.closed or dark is None and self.system_dark is None:
            if not self.closed:
                self._appearance_label()
            return
        changed = dark != self.system_dark
        self.system_dark = dark
        self.apply_appearance()
        if changed and dark is not None:
            self.controller.task(
                lambda: self.controller.studio.remember(system_dark=dark), lambda _: None
            )

    # Views: the work list (home), a Make episode run, and the expert episodes view ------

    def show_view(self, name):
        """Show one of the three views; the expert view keeps all its state."""
        self.view_name = name
        for widget in (self.home, self.run_panel, self.body):
            widget.grid_remove()
        {"home": self.home, "run": self.run_panel, "episodes": self.body}[name].grid(
            row=2, column=0, sticky="nsew"
        )
        self.brand.configure(
            text="MOTH & GRAVEL  /  " + ("MAKE EPISODE" if name == "run" else "LOCAL PRODUCTION")
        )
        self.home_button.reset_feedback("Hide" if name == "run" else "Work list")
        self.home_button.pack_forget()
        self.episodes_button.pack_forget()
        self.prepare_button.set_style("Accent.TButton" if name == "home" else "TButton")
        if name == "run":
            self.prepare_button.pack_forget()
        elif not self.prepare_button.winfo_manager():
            self.prepare_button.pack(side="left", before=self.menu_button)
        if name != "home":
            self.home_button.pack(side="left", padx=(0, 8), before=self.menu_button)
            if self.prepare_button.winfo_manager():
                self.home_button.pack_configure(before=self.prepare_button)
        if name == "episodes" and self.release_focused:
            self.release_focus(True)
        if name != "run":
            self.run_activity = None
        if name == "home":
            self.flow.refresh_work()
        if name != "episodes" and self.jobs_open:
            self.toggle_jobs(False)

    def show_home(self):
        self.show_view("home")
        self.home.focus_first()

    def show_episode(self, identifier, stage=None):
        self.show_view("episodes")
        if identifier in self.controller.episodes:
            self.shelf.reveal(identifier)
            self.controller.select(identifier)
        if stage is not None:
            self.workspace.select_stage(stage)

    def make_episode(self):
        self.flow.choose()

    def open_website(self, episode):
        self.flow.open_website(episode)

    def next_step(self):
        if self.view_name != "episodes":
            return
        primary = self.readiness.primary
        if primary.instate(["!disabled"]):
            primary.invoke()

    def focus_search(self):
        if self.view_name != "episodes":
            self.show_view("episodes")
        self.shelf.search.focus_set()
        self.shelf.search.select_range(0, "end")

    def release_focus(self, release):
        """Release gets the full width; the shelf and card return on the other stages."""
        if not hasattr(self, "jobs"):
            return  # Construction: the panes are added afterwards.
        self.release_focused = release
        if not release:
            self.episodes_shown = False
        self._shelf_visible(not release or self.episodes_shown)
        if release:
            self.episodes_button.reset_feedback(
                "Hide episodes" if self.episodes_shown else "Show episodes"
            )
            self.episodes_button.pack(side="left", padx=(0, 8), before=self.prepare_button)
        else:
            self.episodes_button.pack_forget()

    def toggle_episodes(self):
        self.episodes_shown = not self.episodes_shown
        self.release_focus(self.release_focused)

    def _shelf_visible(self, visible):
        panes = [str(pane) for pane in self.body.panes()]
        if visible and str(self.shelf) not in panes:
            self.body.insert(0, self.shelf, weight=0)
            self.root.after_idle(self._set_sash)
        elif not visible and str(self.shelf) in panes:
            self.body.forget(self.shelf)

    def _set_sash(self):
        # The shelf pane may be gone again (Release restored or a quick toggle).
        if len(self.body.panes()) > 1:
            self.body.sashpos(0, theme.px(self.root, 316))

    def shortcut(self, event, command):
        """Run a menu shortcut, except Ctrl+Enter while typing in an editable text box."""
        if (
            event.keysym == "Return"
            and isinstance(event.widget, tk.Text)
            and str(event.widget.cget("state")) == "normal"
        ):
            return None
        command()
        return "break"

    def _place_sash(self, event):
        """Give the shelf room for its filters and Next column on first layout."""
        if not self.sash_placed and event.width > 1:
            self.sash_placed = True
            self.root.after_idle(self._set_sash)

    # Jobs panel and status bar --------------------------------------------------------

    def toggle_jobs(self, show=None):
        show = not self.jobs_open if show is None else show
        if show and self.view_name != "episodes":
            # The job list lives under the stages, on the expert view.
            self.show_view("episodes")
        self.jobs_open = show
        if show:
            self.jobs.grid(row=6, column=0, sticky="ew")
        else:
            self.jobs.grid_remove()
        self.jobs_button.set_style("ToolOn.TButton" if show else "Compact.TButton")
        self._compact()

    def _compact(self):
        """On a short window with jobs open, the jobs list borrows the stepper's row."""
        short = self.root.winfo_height() < 850
        self.workspace.compact(self.jobs_open and short)

    def run_status(self, view, title):
        """On the timeline the status bar describes that run, not the shelf."""
        from field_notes_studio.presentation.make_episode import run_activity

        self.run_activity = run_activity(view, title.split(" · ", 1)[0])
        self.jobs_rendered()
        # The timeline already says the producer keeps going; the bar names the step.
        self.status("" if view.group == "working" else view.headline)

    def jobs_rendered(self):
        jobs = list(self.jobs.jobs.values())
        running = [job for job in jobs if job.status == "running"]
        queued = [job for job in jobs if job.status == "queued"]
        attention = sum(
            job.status in {"failed", "interrupted", "waiting"}
            and job.identifier not in self.jobs.resolved
            for job in jobs
        )
        if attention:
            glyph, color, style = "health", "WARNING", "Draft.TLabel"
            text = "1 job needs you" if attention == 1 else f"{attention} jobs need you"
        elif running:
            job = running[0]
            glyph, color, style = "produce", "BRASS", "TLabel"
            text = f"Working · {job.episode} · " + self.jobs.tree.set(job.identifier, "stage")
            if queued:
                text += f" · {len(queued)} waiting"
        elif queued:
            glyph, color, style = "history", "BRASS", "TLabel"
            text = f"{len(queued)} waiting for the background producer"
        else:
            glyph, color, style = "check", "SUCCESS", "Success.TLabel"
            text = "Nothing running"
        run = getattr(self, "run_activity", None)
        if self.view_name == "run" and run is not None:
            glyph, color, text = run
            style = {"WARNING": "Draft.TLabel", "SUCCESS": "Success.TLabel"}.get(color, "TLabel")
        self.activity.configure(
            text=" " + text, image=icon(self.activity, glyph, color), style=style
        )
        count = len(running) + len(queued) + attention
        self.jobs_button.reset_feedback(f"Jobs ({count})")
        if attention > self.attention:
            # A job that needs a person always opens the jobs list.
            self.toggle_jobs(True)
        self.attention = attention

    def status(self, message):
        self.message_text = message
        self._fit_message()

    def _fit_message(self):
        width = self.message.winfo_width()
        text = " ".join(self.message_text.split())
        typeface = tkfont.Font(
            font=ttk.Style(self.root).lookup("TLabel", "font") or "TkDefaultFont"
        )
        if width > 40 and typeface.measure(text) > width:
            while text and typeface.measure(text + "…") > width:
                text = text[: max(0, len(text) - max(1, len(text) // 20))]
            text = text.rstrip() + "…"
        self.message.configure(text=text)

    def resize(self, event):
        if event.widget is self.root:
            self.jobs.tree.configure(height=1 if event.height < 850 else 2)
            self._compact()
            self.root.after_idle(self._fit_message)

    # Preparation ----------------------------------------------------------------------

    def notes(self):
        if self.notes_service is None:
            self.notes_service = PreparationService(self.directory)
        return self.notes_service

    def published(self, episode):
        item = self.controller.episodes.get(episode)
        return bool(item and item.publication_saved)

    def readiness_changed(self, snapshot):
        from field_notes_studio.presentation.readiness import journey

        published = bool(snapshot and self.published(snapshot.episode))
        self.workspace.stepper.show(journey(snapshot, published))

    def prepare_selected(self):
        note = self.shelf.note(self.shelf.current or "")
        self.open_preparation(note=note.note if note else "")

    def open_preparation(self, *, note="", query=""):
        if self.preparation is not None and not self.preparation.closed:
            self.preparation.view.window.lift()
            if not self.preparation.busy:
                # Apply navigation after the fresh catalog arrives. Revealing a
                # row first schedules selection events that can stale the read.
                self.preparation.target_note = note
                self.preparation.target_query = query
                self.preparation.refresh()
            elif note:
                self.preparation.view.reveal(note)
            elif query:
                self.preparation.view.query.set(query)
            return
        view = PreparationWindow(self.root)
        view.setup_directory = str(
            self.directory.parent.parent
            if self.directory.name == ".github"
            else self.directory.parent
        )
        view.context.configure(text=f"Working checkout: {self.directory}")
        view.connect_navigation(self.open_prepared, self.show_preparation_job)
        self.preparation = PreparationController(
            PreparationService(self.directory), view, note=note, query=query
        )

    def open_prepared(self, episode):
        self.controller.open_prepared(episode)

    def show_preparation_job(self, identifier):
        self.preparation.close()

        def loaded(jobs):
            self.jobs.render(jobs)
            self.toggle_jobs(True)
            if self.jobs.tree.exists(identifier):
                self.jobs.tree.selection_set(identifier)
                self.jobs.tree.see(identifier)
                self.controller.job_detail()

        self.controller.task(self.controller.studio.repository.jobs, loaded)

    # Lifecycle ------------------------------------------------------------------------

    def tick(self):
        if not self.closed:
            self.controller.pump()
            self.tick_handle = self.root.after(50, self.tick)

    def poll(self):
        if not self.closed:
            self.controller.poll()
            self.polls = getattr(self, "polls", 0) + 1
            if self.view_name == "run":
                self.flow.reload_run()
            elif self.view_name == "home" and self.polls % 3 == 0:
                self.flow.refresh_work()
            self.poll_handle = self.root.after(1000, self.poll)

    def close(self):
        if self.closed:
            return
        website = getattr(self.flow, "website", None)
        if website is not None and website.running:
            self.status("The website update is still running. Studio closes when it finishes.")
            return
        try:
            self.controller.close()
        except Exception as exc:
            self.status(
                f"Draft save failed: {exc}. Studio stays open so you can recover your edits."
            )
            return
        self.closed = True
        if self.preparation is not None:
            self.preparation.close()
        for handle in (self.tick_handle, self.poll_handle):
            if handle is not None:
                self.root.after_cancel(handle)
        self.root.destroy()


def run(directory: Path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise ValueError(
            "No desktop display is available. Run in WSLg or a Linux desktop session."
        ) from exc
    Application(root, directory)
    root.mainloop()
