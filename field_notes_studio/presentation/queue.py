"""Durable job history and explicit cooperative stop controls."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.models import TERMINAL
from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.theme import SUCCESS, WARNING, set_text


class ProductionQueue(ttk.Frame):
    def __init__(self, parent, stop, retry, select, history, open_result, review):
        super().__init__(parent, padding=(0, 16, 0, 0))
        self.jobs = {}
        heading = ttk.Frame(self)
        heading.pack(fill="x", pady=(0, 8))
        self.summary = ttk.Label(heading, text="Queue · no jobs yet", style="Muted.TLabel")
        self.summary.pack(side="left")
        actions = ttk.Frame(heading)
        actions.pack(side="right")
        self.buttons = {}
        for name, label, command, pictogram in (
            ("open", "Open output", open_result, "folder"),
            ("review", "Review latest", review, "review"),
            ("history", "History", history, "history"),
            ("retry", "Retry", retry, "refresh"),
            ("stop", "Stop", stop, "stop"),
        ):
            button = ActionButton(
                actions,
                pictogram=pictogram,
                text=label,
                command=command,
                state="disabled",
                style="Compact.TButton",
            )
            button.pack(side="left", padx=(6, 0))
            self.buttons[name] = button
        region = self.region = ttk.Frame(self)
        self.tree = ttk.Treeview(
            region,
            columns=("episode", "action", "status", "stage"),
            show="headings",
            height=2,
            selectmode="browse",
        )
        for name, width in [("episode", 130), ("action", 100), ("status", 130), ("stage", 230)]:
            self.tree.heading(name, text=name.title(), anchor="w")
            self.tree.column(name, width=width)
        scrollbar = ttk.Scrollbar(region, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.tag_configure("attention", background="#f4e8d5", foreground=WARNING)
        self.tree.tag_configure("complete", foreground=SUCCESS)

        def selected(_event):
            self.update_controls()
            select()

        self.tree.bind("<<TreeviewSelect>>", selected)
        self.detail = ttk.Label(
            self,
            text="Inspect an episode's changes to start production. Jobs will appear here.",
            style="Muted.TLabel",
            wraplength=1050,
        )
        self.detail.pack(anchor="w", pady=8)

    def selection(self):
        selected = self.tree.selection()
        return selected[0] if selected else None

    def update_controls(self):
        job = self.jobs.get(self.selection())
        conflicting = job and any(
            other.episode == job.episode and other.status not in TERMINAL
            for other in self.jobs.values()
        )
        enabled = {
            "history": job is not None,
            "stop": bool(job and job.status not in TERMINAL and not job.cancel_requested),
            "retry": bool(
                job and job.status in {"failed", "interrupted", "cancelled"} and not conflicting
            ),
            "open": bool(job and job.status == "succeeded" and job.result),
            "review": bool(job and job.status == "succeeded" and job.action in {"audio", "video"}),
        }
        for name, button in self.buttons.items():
            button.configure(state="normal" if enabled[name] else "disabled")
        labels = {
            "audio": "Listen to audio",
            "preview": "Watch preview",
            "video": "Watch video",
            "export": "Open package",
        }
        self.buttons["open"].configure(text=labels[job.action] if job else "Open output")
        self.buttons["open"].set_icon(
            {"audio": "audio", "preview": "video", "video": "video", "export": "package"}.get(
                job.action if job else "", "folder"
            )
        )

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
        if jobs:
            if not self.jobs:
                self.detail.configure(
                    text="Select a job to inspect its recipe, status and saved output."
                )
            if not self.region.winfo_manager():
                self.region.pack(fill="x", before=self.detail)
        else:
            self.region.pack_forget()
            self.detail.configure(
                text="Inspect an episode's changes to start production. Jobs will appear here."
            )
        selected = self.selection()
        self.jobs = {job.identifier: job for job in jobs}
        running = sum(job.status == "running" for job in jobs)
        queued = sum(job.status == "queued" for job in jobs)
        attention = sum(job.status in {"failed", "interrupted"} for job in jobs)
        self.summary.configure(
            text=f"Queue · {running} running · {queued} queued · {attention} need attention"
            if jobs
            else "Queue · no jobs yet"
        )
        ids = {job.identifier for job in jobs}
        for identifier in self.tree.get_children():
            if identifier not in ids:
                self.tree.delete(identifier)
        for job in reversed(jobs):
            status = (
                "stop requested"
                if job.cancel_requested and job.status in {"queued", "running"}
                else {
                    "succeeded": "Complete",
                    "failed": "Failed",
                    "interrupted": "Interrupted",
                    "cancelled": "Stopped",
                    "queued": "Queued",
                    "running": "Working",
                }.get(job.status, job.status)
            )
            values = (job.episode, job.action, status, job.stage)
            tags = (
                ("attention",)
                if job.status in {"failed", "interrupted"}
                else ("complete",)
                if job.status == "succeeded"
                else ()
            )
            if self.tree.exists(job.identifier):
                if self.tree.item(job.identifier, "values") != values:
                    self.tree.item(job.identifier, values=values, tags=tags)
            else:
                self.tree.insert("", 0, iid=job.identifier, values=values, tags=tags)
        if (not selected or selected not in ids) and jobs:
            self.tree.selection_set(jobs[0].identifier)
        self.update_controls()
