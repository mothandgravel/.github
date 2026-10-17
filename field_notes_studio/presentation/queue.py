"""Durable job history and explicit cooperative stop controls."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.job_history import resolved_failures
from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.progress import ProgressStrip
from field_notes_studio.presentation.theme import SUCCESS, WARNING, set_text


class ProductionQueue(ttk.Frame):
    def __init__(self, parent, stop, retry, select, history, open_result, review):
        super().__init__(parent, padding=(0, 8, 0, 0))
        self.jobs = {}
        self.resolved = set()
        self.production_busy = False
        heading = ttk.Frame(self)
        heading.pack(fill="x", pady=(0, 4))
        heading.columnconfigure(0, weight=1)
        self.summary = ttk.Label(
            heading, text="Queue · no jobs yet", style="Muted.TLabel", wraplength=240
        )
        self.summary.grid(row=0, column=0, sticky="w")
        actions = ttk.Frame(heading)
        actions.grid(row=0, column=1, sticky="e")

        def fit_summary(event):
            self.summary.configure(wraplength=max(120, event.width - actions.winfo_reqwidth() - 12))

        heading.bind("<Configure>", fit_summary)
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
            self.progress.clear()
            self.update_controls()
            select()

        self.tree.bind("<<TreeviewSelect>>", selected)
        self.detail = ttk.Label(
            self,
            text="Inspect an episode's changes to start production. Jobs will appear here.",
            style="Muted.TLabel",
            wraplength=1050,
        )
        self.detail.pack(anchor="w", pady=(4, 2))
        self.progress = ProgressStrip(self)

    def production_working(self, value):
        self.production_busy = value
        self.update_controls()

    def selection(self):
        selected = self.tree.selection()
        return selected[0] if selected else None

    def update_controls(self):
        job = self.jobs.get(self.selection())
        conflicting = job and any(
            other.episode == job.episode
            and other.identifier != job.identifier
            and other.status in {"queued", "running", "waiting"}
            for other in self.jobs.values()
        )
        enabled = {
            "history": job is not None,
            "stop": bool(job and job.status in {"queued", "running"} and not job.cancel_requested),
            "retry": bool(
                job
                and job.status in {"failed", "interrupted", "cancelled", "waiting"}
                and not conflicting
                and job.identifier not in self.resolved
            ),
            "open": bool(job and job.status == "succeeded" and job.result),
            "review": bool(
                job
                and job.status == "succeeded"
                and job.action in {"audio", "video", "prepare"}
                and not (job.action == "prepare" and (self.production_busy or conflicting))
            ),
        }
        for name, button in self.buttons.items():
            button.configure(state="normal" if enabled[name] else "disabled")
        labels = {
            "audio": "Listen to audio",
            "preview": "Watch preview",
            "video": "Watch video",
            "export": "Open package",
            "prepare": "Open prepared files",
        }
        self.buttons["retry"].configure(
            text="Resume"
            if job and job.status == "waiting"
            else "Inspect recovery"
            if job and job.action == "prepare"
            else "Retry"
        )
        self.buttons["open"].configure(text=labels[job.action] if job else "Open output")
        self.buttons["review"].configure(
            text="Produce episode" if job and job.action == "prepare" else "Review latest"
        )
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
                self.progress.pack(fill="x", before=self.detail, pady=(5, 0))
        else:
            self.region.pack_forget()
            self.progress.pack_forget()
            self.progress.clear()
            self.detail.configure(
                text="Inspect an episode's changes to start production. Jobs will appear here."
            )
        selected = self.selection()
        self.jobs = {job.identifier: job for job in jobs}
        running = sum(job.status == "running" for job in jobs)
        queued = sum(job.status == "queued" for job in jobs)
        self.resolved = resolved_failures(jobs)
        attention = sum(
            job.status in {"failed", "interrupted", "waiting"}
            and job.identifier not in self.resolved
            for job in jobs
        )
        # Only non-zero counts, so the summary stays on one line beside the actions.
        counts = [
            f"{running} running" if running else "",
            f"{queued} queued" if queued else "",
            f"{attention} {'needs' if attention == 1 else 'need'} attention" if attention else "",
        ]
        self.summary.configure(
            text="Queue · " + (" · ".join(c for c in counts if c) or "nothing needs attention")
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
                    "waiting": "Awaiting captions",
                }.get(job.status, job.status)
            )
            stage = (
                job.stage.replace("narration-", "Narration ")
                .replace("-of-", "/")
                .replace("-complete", " saved")
            )
            if job.action == "prepare" and job.stage in {"failed", "interrupted", "cancelled"}:
                stage = "Inspect recovery"
            if job.action == "prepare" and job.status == "succeeded":
                status, stage = "Recording ready", "Next: Produce episode"
            historical = job.identifier in self.resolved
            if historical:
                status, stage = "Earlier attempt", "Later attempt completed"
            values = (
                job.episode,
                {
                    "prepare": "Prepare recording",
                    "video": "Full episode",
                    "audio": "Audio only",
                    "preview": "Video preview",
                    "export": "Export package",
                }.get(job.action, job.action),
                status,
                stage,
            )
            tags = (
                ("attention",)
                if job.status in {"failed", "interrupted", "waiting"} and not historical
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
