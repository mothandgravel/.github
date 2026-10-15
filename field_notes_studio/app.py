"""Composition root: construct the Tk views and connect application callbacks."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from field_notes_studio.controller import Controller
from field_notes_studio.preparation_controller import PreparationController
from field_notes_studio.preparation_service import PreparationService
from field_notes_studio.presentation import theme
from field_notes_studio.presentation.preparation import PreparationWindow
from field_notes_studio.presentation.queue import ProductionQueue
from field_notes_studio.presentation.shelf import Shelf
from field_notes_studio.presentation.workspace import Workspace
from field_notes_studio.service import Studio


class Application:
    def __init__(self, root, directory: Path):
        self.root = root
        self.directory = directory
        self.preparation = None
        self.closed = False
        self.tick_handle = None
        self.poll_handle = None
        theme.apply(root)
        root.title("Moth & Gravel · Production studio")
        root.geometry("1280x920")
        root.minsize(1050, 760)
        main = ttk.Frame(root, padding=(24, 18))
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)
        ttk.Label(main, text="MOTH & GRAVEL  /  LOCAL PRODUCTION", style="Brand.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(main, text="Production studio", style="Studio.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 16)
        )
        self.prepare_button = ttk.Button(
            main, text="Prepare new notes…", command=self.open_preparation
        )
        self.prepare_button.grid(row=1, column=0, sticky="e", pady=(4, 16))
        self.controller = Controller(Studio(directory), self)
        body = ttk.Panedwindow(main, orient="horizontal")
        body.grid(row=2, column=0, sticky="nsew")
        self.shelf = Shelf(body, self.controller.select)
        self.workspace = Workspace(
            body,
            {
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
                "publication": self.controller.publication,
                "open": self.controller.open_output,
                "refresh": self.controller.refresh_review,
                "open_review": self.controller.open_review,
                "approve": self.controller.approve,
                "release_refresh": self.controller.refresh_release,
                "release_review": self.controller.release_review,
                "release_package": self.controller.prepare_package,
                "package_refresh": self.controller.refresh_package,
                "package_open": self.controller.open_package_file,
                "package_copy": self.controller.copy_package_path,
                "youtube": self.controller.open_publisher,
                "status": self.status,
            },
        )
        body.add(self.shelf, weight=1)
        body.add(self.workspace, weight=3)
        self.jobs = ProductionQueue(
            main,
            self.controller.stop,
            self.controller.retry,
            self.controller.job_detail,
            self.controller.history,
            self.controller.open_job_output,
            self.controller.review_job,
        )
        self.jobs.grid(row=3, column=0, sticky="ew")
        root.bind("<Configure>", self.resize)
        self.message = ttk.Label(
            main, text="Loading the episode shelf…", style="Muted.TLabel", wraplength=1150
        )
        self.message.grid(row=4, column=0, sticky="w", pady=(8, 0))
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.workspace.tabs.bind(
            "<<NotebookTabChanged>>", lambda _: self.controller.draft_changed(), add=True
        )
        self.workspace.publication.tabs.bind(
            "<<NotebookTabChanged>>", lambda _: self.controller.draft_changed(), add=True
        )
        self.shelf.query.trace_add("write", lambda *_: self.controller.draft_changed())
        self.controller.start()
        self.tick()
        self.poll()

    def open_preparation(self):
        if self.preparation is not None and not self.preparation.closed:
            self.preparation.view.window.lift()
            return
        self.preparation = PreparationController(
            PreparationService(self.directory), PreparationWindow(self.root)
        )

    def status(self, message):
        self.message.configure(text=message)

    def resize(self, event):
        if event.widget is self.root:
            self.jobs.tree.configure(height=1 if event.height < 850 else 2)
            self.jobs.detail.configure(wraplength=max(500, event.width - 70))
            self.message.configure(wraplength=max(500, event.width - 70))

    def tick(self):
        if not self.closed:
            self.controller.pump()
            self.tick_handle = self.root.after(50, self.tick)

    def poll(self):
        if not self.closed:
            self.controller.poll()
            self.poll_handle = self.root.after(1000, self.poll)

    def close(self):
        if self.closed:
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
