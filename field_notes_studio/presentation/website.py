"""Prepare website update: show exactly what will run, confirm, then stream it.

Values and callbacks only; the runner lives in ``field_notes_studio.website``.
The confirm button names its outcome ("Push branch for review") and is offered
only when the plan has no refusal. Nothing here merges anything.
"""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation import theme
from field_notes_studio.presentation.controls import ActionButton


class WebsiteDialog:
    def __init__(self, root, callbacks):
        self.callbacks = callbacks
        self.plan = None
        self.running = False
        self.window = window = tk.Toplevel(root)
        window.withdraw()
        window.title("Prepare website update · Moth & Gravel")
        window.minsize(theme.px(root, 640), theme.px(root, 480))
        window.geometry(f"{theme.px(root, 760)}x{theme.px(root, 600)}")
        window.protocol("WM_DELETE_WINDOW", self.close)
        window.bind("<Escape>", lambda _e: self.close())
        body = ttk.Frame(window, padding=18)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(4, weight=1)
        ttk.Label(
            body, text="MOTH & GRAVEL  /  WEBSITE AND PODCAST FEED", style="Brand.TLabel"
        ).grid(row=0, column=0, sticky="w")
        self.heading = ttk.Label(body, text="Prepare website update", style="Heading.TLabel")
        self.heading.grid(row=1, column=0, sticky="w", pady=(4, 2))
        self.summary = ttk.Label(body, text="Checking this checkout…", style="Muted.TLabel")
        self.summary.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        body.bind(
            "<Configure>",
            lambda e: self.summary.configure(wraplength=max(200, e.width - theme.px(body, 36))),
            add=True,
        )
        self.refusals = ttk.Frame(body, style="Attention.TFrame", padding=12)
        self.refusal_text = ttk.Label(self.refusals, style="Attention.TLabel")
        self.refusal_text.pack(anchor="w", fill="x")
        self.refusal_text.bind(
            "<Configure>", lambda e: self.refusal_text.configure(wraplength=max(200, e.width))
        )
        self.output = tk.Text(body, height=14, wrap="word", font=("DejaVu Sans Mono", 9))
        self.output.studio_colors = ("SURFACE", "INK")
        self.output.grid(row=4, column=0, sticky="nsew")
        theme.retheme(self.output)
        theme.set_text(self.output, "")
        actions = ttk.Frame(body)
        actions.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        self.copy_button = ActionButton(
            actions, pictogram="copy", text="Copy commands", command=self.copy
        )
        self.copy_button.pack(side="left")
        self.close_button = ttk.Button(actions, text="Close", command=self.close)
        self.close_button.pack(side="right")
        self.confirm_button = ActionButton(
            actions,
            pictogram="external",
            text="Push branch for review",
            style="Accent.TButton",
            command=self.confirm,
            state="disabled",
        )
        self.confirm_button.pack(side="right", padx=(0, 8))

    def open(self, root):
        self.window.transient(root)
        self.window.deiconify()
        self.window.lift()
        self.plan = None
        self.heading.configure(text="Prepare website update")
        self.summary.configure(text="Checking this checkout…")
        self.refusals.grid_remove()
        self.confirm_button.configure(state="disabled")
        theme.set_text(self.output, "")
        self.close_button.focus_set()

    def show(self, plan):
        """The dry run: the exact commands, the branch, the remote and every refusal."""
        self.plan = plan
        theme.set_text(self.output, plan.describe() if plan.commands else "")
        if plan.refusals:
            self.summary.configure(text="Nothing will run until these are fixed:")
            self.refusal_text.configure(text="\n".join("• " + r for r in plan.refusals))
            self.refusals.grid(row=3, column=0, sticky="ew", pady=(0, 10))
            self.confirm_button.configure(state="disabled")
            self.close_button.focus_set()
        else:
            self.summary.configure(
                text=f"This pushes the branch {plan.branch} to {plan.remote}. It never merges: "
                "you merge the pull request on GitHub."
            )
            self.refusals.grid_remove()
            self.confirm_button.configure(state="normal")
            self.confirm_button.focus_set()

    def confirm(self):
        if self.plan is None or self.running or self.plan.refusals:
            return
        self.running = True
        self.confirm_button.configure(state="disabled")
        self.close_button.configure(state="disabled")
        self.heading.configure(text="Running promote, then publish…")
        theme.set_text(self.output, "")
        self.callbacks["run"](self.plan)

    def line(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", text + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def finished(self, result):
        self.running = False
        self.close_button.configure(state="normal")
        self.heading.configure(
            text="Branch pushed for review" if result.ok else "Website update stopped"
        )
        self.summary.configure(text=result.summary)
        if not result.ok:
            self.refusal_text.configure(text=result.summary)
            self.refusals.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.close_button.focus_set()

    def copy(self):
        if not self.plan or not self.plan.commands:
            return
        self.window.clipboard_clear()
        self.window.clipboard_append(
            "\n".join("python3 " + " ".join(c[1:]) for c in self.plan.commands)
        )
        self.copy_button.complete()

    def close(self):
        if self.running:
            return
        self.window.withdraw()
