"""Composition root: construct the Tk views and connect application callbacks."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from field_notes_studio.controller import Controller
from field_notes_studio.presentation import theme
from field_notes_studio.presentation.queue import ProductionQueue
from field_notes_studio.presentation.shelf import Shelf
from field_notes_studio.presentation.workspace import Workspace
from field_notes_studio.service import Studio


class Application:
    def __init__(self, root, directory: Path):
        self.root = root
        self.closed = False
        self.tick_handle = None
        self.poll_handle = None
        theme.apply(root)
        root.title("Moth & Gravel · Production studio")
        root.geometry("1280x920")
        root.minsize(1050, 760)
        main = ttk.Frame(root, padding=24)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)
        ttk.Label(main, text="MOTH & GRAVEL", style="Heading.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(main, text="Production studio", style="Title.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 20)
        )
        self.controller = Controller(Studio(directory), self)
        body = ttk.Panedwindow(main, orient="horizontal")
        body.grid(row=2, column=0, sticky="nsew")
        self.shelf = Shelf(body, self.controller.select)
        self.workspace = Workspace(
            body,
            {
                "changed": self.controller.changed,
                "plan": self.controller.inspect,
                "submit": self.controller.submit,
                "publication": self.controller.publication,
                "open": self.controller.open_output,
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
        )
        self.jobs.grid(row=3, column=0, sticky="ew")
        self.message = ttk.Label(
            main, text="Loading the episode shelf…", style="Muted.TLabel", wraplength=1150
        )
        self.message.grid(row=4, column=0, sticky="w", pady=(8, 0))
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.controller.start()
        self.tick()
        self.poll()

    def status(self, message):
        self.message.configure(text=message)

    def tick(self):
        if not self.closed:
            self.controller.pump()
            self.tick_handle = self.root.after(50, self.tick)

    def poll(self):
        if not self.closed:
            self.controller.poll()
            self.poll_handle = self.root.after(1000, self.poll)

    def close(self):
        self.closed = True
        for handle in (self.tick_handle, self.poll_handle):
            if handle is not None:
                self.root.after_cancel(handle)
        self.controller.close()
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
