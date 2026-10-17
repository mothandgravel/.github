"""Durable job history and explicit cooperative stop controls."""

import re
import tkinter as tk
from tkinter import ttk

from field_notes_studio.job_history import resolved_failures
from field_notes_studio.presentation import theme
from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.progress import ProgressStrip
from field_notes_studio.presentation.theme import set_text

ACTIONS = {
    "prepare": "Narration and captions",
    "video": "Full episode",
    "audio": "Audio only",
    "preview": "Video preview",
    "export": "Upload folder",
}
STAGES = {
    "queued": "Waiting for its turn",
    "running": "Starting",
    "narration": "Narrating",
    "captions": "Making captions",
    "audio": "Finishing audio and captions",
    "video": "Making the video",
    "export": "Making the upload folder",
    "save": "Saving",
    "succeeded": "Finished",
    "failed": "Stopped by a problem",
    "interrupted": "Interrupted",
    "cancelled": "Stopped on request",
    "waiting": "Waiting for captions",
}
SAVED = {
    "narration": "Narration saved",
    "captions": "Captions saved",
    "audio": "Audio and captions saved",
    "video": "Video saved",
    "export": "Upload folder saved",
    "save": "Saved",
}


def stage_sentence(stage):
    """A raw journal stage id as a short sentence a reader can act on."""
    part = re.fullmatch(r"narration-(\d+)-of-(\d+)(-complete)?", stage or "")
    if part:
        return (
            f"Part {part[1]} of {part[2]} saved"
            if part[3]
            else (f"Narrating part {part[1]} of {part[2]}")
        )
    stage = stage or ""
    if stage.endswith("-complete"):
        name = stage.removesuffix("-complete")
        return SAVED.get(name, name.replace("-", " ").capitalize() + " saved")
    return STAGES.get(stage, (stage or "").replace("-", " ").replace("_", " ").capitalize())


class ProductionQueue(ttk.Frame):
    def __init__(self, parent, stop, retry, select, history, open_result, review):
        super().__init__(parent, padding=(0, 8, 0, 0))
        self.jobs = {}
        self.resolved = set()
        self.on_render = lambda: None
        self.production_busy = False
        heading = ttk.Frame(self)
        heading.pack(fill="x", pady=(0, 4))
        heading.columnconfigure(0, weight=1)
        self.summary = ttk.Label(
            heading, text="Jobs · none yet", style="Muted.TLabel", wraplength=240
        )
        # The status bar shows this summary in one line; the panel keeps it for history.
        actions = ttk.Frame(heading)
        actions.grid(row=1, column=0, sticky="w")
        heading.bind(
            "<Configure>", lambda e: self.summary.configure(wraplength=max(200, e.width - 10))
        )
        self.buttons = {}
        for name, label, command, pictogram in (
            ("open", "Open result", open_result, "folder"),
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
                style="Small.TButton",
            )
            button.pack(side="left", padx=(0, 6))
            self.buttons[name] = button
        region = self.region = ttk.Frame(self)
        self.tree = ttk.Treeview(
            region,
            columns=("episode", "action", "status", "stage"),
            show="headings",
            height=2,
            selectmode="browse",
        )
        for name, title, width in [
            ("episode", "Episode", 130),
            ("action", "What", 150),
            ("status", "Status", 130),
            ("stage", "Where it is", 260),
        ]:
            self.tree.heading(name, text=title, anchor="w")
            self.tree.column(name, width=width)
        scrollbar = ttk.Scrollbar(region, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.retheme()

        def selected(_event):
            self.progress.clear()
            self.update_controls()
            select()

        self.tree.bind("<<TreeviewSelect>>", selected)
        self.detail = ttk.Label(
            self,
            text="No jobs yet. Produce episode starts one; jobs appear here.",
            style="Muted.TLabel",
            wraplength=1050,
        )
        self.detail.pack(anchor="w", pady=(4, 2))
        self.progress = ProgressStrip(self)
        self.bind(
            "<Configure>",
            lambda e: self.detail.configure(wraplength=max(300, e.width - 10))
            if e.widget is self
            else None,
            add=True,
        )

    def retheme(self):
        self.tree.tag_configure("attention", background=theme.ATTENTION, foreground=theme.WARNING)
        self.tree.tag_configure("complete", foreground=theme.SUCCESS)

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
            "export": "Open upload folder",
            "prepare": "Open narration files",
        }
        self.buttons["retry"].configure(
            text="Resume"
            if job and job.status == "waiting"
            else "Check recovery"
            if job and job.action == "prepare"
            else "Retry"
        )
        self.buttons["open"].configure(text=labels[job.action] if job else "Open result")
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
        window.title(f"{job.episode} · {ACTIONS.get(job.action, job.action)} · Job history")
        window.geometry("820x480")
        text = tk.Text(window, wrap="word", padx=20, pady=20, relief="flat")
        text.pack(fill="both", expand=True)
        entries = [
            f"{job.episode} · {ACTIONS.get(job.action, job.action)} · {job.status}",
            job.error or job.result,
        ]
        entries.extend(
            f"{event['time']} · {stage_sentence(event['stage'])} ({event['stage']})\n"
            f"{event['message']}"
            for event in events
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
            self.detail.configure(text="No jobs yet. Produce episode starts one; jobs appear here.")
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
        parts = [
            f"{count} {label}"
            for count, label in (
                (running, "running"),
                (queued, "waiting"),
                (attention, "needs you" if attention == 1 else "need you"),
            )
            if count
        ]
        self.summary.configure(
            text="Jobs · " + (" · ".join(parts) if parts else "nothing running")
            if jobs
            else "Jobs · none yet"
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
                    "waiting": "Waiting for captions",
                }.get(job.status, job.status)
            )
            stage = stage_sentence(job.stage)
            if job.status in {"failed", "interrupted", "cancelled"}:
                if job.stage in {"queued", "running", "starting"}:
                    stage = "Stopped before it started"
                elif job.stage not in STAGES:
                    stage = "Stopped: " + stage[:1].lower() + stage[1:]
            if job.action == "prepare" and job.stage in {"failed", "interrupted", "cancelled"}:
                stage = "Next: check recovery"
            if job.action == "prepare" and job.status == "succeeded":
                status, stage = "Narrated", "Next: Produce episode"
            historical = job.identifier in self.resolved
            if historical:
                status, stage = "Earlier attempt", "Later attempt completed"
            values = (job.episode, ACTIONS.get(job.action, job.action), status, stage)
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
        self.on_render()
