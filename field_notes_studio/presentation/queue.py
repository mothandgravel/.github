"""Durable job history and explicit cooperative stop controls."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.theme import set_text


class ProductionQueue(ttk.Frame):
    def __init__(self, parent, stop, retry, select, history):
        super().__init__(parent, padding=(0, 16, 0, 0))
        heading = ttk.Frame(self)
        heading.pack(fill="x", pady=(0, 8))
        ttk.Label(heading, text="PRODUCTION QUEUE", style="Heading.TLabel").pack(side="left")
        ttk.Button(heading, text="Job history", command=history).pack(side="right", padx=8)
        ttk.Button(heading, text="Request stop", command=stop).pack(side="right")
        ttk.Button(heading, text="Retry selected job", command=retry).pack(side="right", padx=8)
        region = ttk.Frame(self)
        region.pack(fill="x")
        self.tree = ttk.Treeview(
            region,
            columns=("episode", "action", "status", "stage"),
            show="headings",
            height=2,
            selectmode="browse",
        )
        for name, width in [("episode", 130), ("action", 100), ("status", 130), ("stage", 230)]:
            self.tree.heading(name, text=name.title())
            self.tree.column(name, width=width)
        scrollbar = ttk.Scrollbar(region, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda _event: select())
        self.detail = ttk.Label(
            self,
            text="Completed editions remain available after a stop. Running stages finish before a stop takes effect.",
            style="Muted.TLabel",
            wraplength=1050,
        )
        self.detail.pack(anchor="w", pady=8)

    def selection(self):
        selected = self.tree.selection()
        return selected[0] if selected else None

    def show_history(self, job, events):
        window = tk.Toplevel(self)
        window.title(f"{job.episode} · {job.action} · Job history")
        window.geometry("820x480")
        text = tk.Text(window, wrap="word", padx=20, pady=20, relief="flat")
        text.pack(fill="both", expand=True)
        entries = [f"{job.episode} · {job.action} · {job.status}", job.error or job.result]
        entries.extend(
            f"{event['time']} · {event['stage']}\n{event['message']}" for event in events
        )
        set_text(text, "\n\n".join(entries))

    def render(self, jobs):
        selected = self.selection()
        ids = {job.identifier for job in jobs}
        for identifier in self.tree.get_children():
            if identifier not in ids:
                self.tree.delete(identifier)
        for job in reversed(jobs):
            status = (
                "stop requested"
                if job.cancel_requested and job.status in {"queued", "running"}
                else job.status
            )
            values = (job.episode, job.action, status, job.stage)
            if self.tree.exists(job.identifier):
                if self.tree.item(job.identifier, "values") != values:
                    self.tree.item(job.identifier, values=values)
            else:
                self.tree.insert("", 0, iid=job.identifier, values=values)
        if not selected and jobs:
            self.tree.selection_set(jobs[0].identifier)
