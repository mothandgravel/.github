"""Preparation navigation, explicit consent and local setup import prompts; no file IO."""

import tkinter as tk
from dataclasses import replace
from tkinter import filedialog, messagebox, ttk

from field_notes_studio.presentation.controls import Fieldset

JOURNEY = "1 Narrate the note → 2 Produce the episode → 3 Review once → 4 Release"


class PreparationWindow:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("Moth & Gravel · New episode from a note")
        self.window.geometry("1050x760")
        self.window.minsize(760, 580)
        self.window.transient(parent)
        self.items = {}
        self.snapshot = None
        self.loading = False
        self.queued_id = ""
        self.setup_directory = ""
        self.open_episode = lambda _: None
        self.open_job = lambda _: None
        main = ttk.Frame(self.window, padding=18)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)
        main.rowconfigure(6, weight=3)
        heading = ttk.Frame(main)
        heading.grid(row=0, column=0, sticky="ew")
        ttk.Label(heading, text="New episode from a note", style="Studio.TLabel").pack(side="left")
        self.setup_button = ttk.Button(heading, text="Import existing setup…")
        self.setup_button.pack(side="right")
        self.context = ttk.Label(
            main,
            text="Setup is local to this checkout, not your Git branch.",
            style="Muted.TLabel",
            wraplength=700,
        )
        self.context.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        self.journey = ttk.Label(
            main,
            text=JOURNEY,
            style="Muted.TLabel",
            wraplength=700,
        )
        self.journey.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        search = ttk.Frame(main)
        search.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="Find written note", style="Muted.TLabel").grid(
            row=0, column=0, padx=(0, 8)
        )
        self.query = tk.StringVar()
        self.search = ttk.Entry(search, textvariable=self.query)
        self.search.grid(row=0, column=1, sticky="ew")
        self.search.bind("<Escape>", lambda _: self.query.set(""))
        table = ttk.Frame(main)
        table.grid(row=4, column=0, sticky="nsew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            table,
            columns=("note", "title", "state"),
            show="headings",
            selectmode="browse",
            height=2,
        )
        for name, heading_text, width in (
            ("note", "Note", 65),
            ("title", "Written note", 420),
            ("state", "Next", 205),
        ):
            self.tree.heading(name, text=heading_text)
            self.tree.column(name, width=width, minwidth=60, stretch=name == "title")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        actions = ttk.Frame(main)
        actions.grid(row=5, column=0, sticky="ew", pady=8)
        self.refresh_button = ttk.Button(actions, text="Refresh notes")
        self.inspect_button = ttk.Button(
            actions, text="Check script · free, nothing is sent", state="disabled"
        )
        self.production_button = ttk.Button(
            actions, text="Open in production", state="disabled", command=self._open_production
        )
        self.job_button = ttk.Button(
            actions, text="Show job", state="disabled", command=self._open_job
        )
        for button in (
            self.refresh_button,
            self.inspect_button,
            self.production_button,
            self.job_button,
        ):
            button.pack(side="left", padx=(0, 6))
        tabs = ttk.Notebook(main)
        tabs.grid(row=6, column=0, sticky="nsew")
        self.plan = self._text(tabs, "Next step and request details")
        self.script = self._text(tabs, "Saved narration script")
        consent = ttk.Frame(main)
        consent.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        consent.columnconfigure(0, weight=1)
        # One labelled group holds every consent box, one box per line.
        self.consent = Fieldset(consent, "Your consent")
        self.consent.grid(row=0, column=0, sticky="w")
        self.authorized = tk.BooleanVar(value=False)
        self.authorization = ttk.Checkbutton(
            self.consent.body,
            text="Authorize the displayed Cloud work (charges may apply).",
            variable=self.authorized,
            command=lambda: self.busy(self.loading),
        )
        self.authorization.pack(anchor="w")
        self.queue_button = ttk.Button(
            consent, text="Queue narration", style="Accent.TButton", state="disabled"
        )
        self.queue_button.grid(row=0, column=1, sticky="se")
        self.recover_uncertain = tk.BooleanVar(value=False)
        self.recovery_consent = ttk.Checkbutton(
            self.consent.body,
            text="Also resend the uncertain chunk(s); I accept possible duplicate charges.",
            variable=self.recover_uncertain,
            command=lambda: self.busy(self.loading),
        )
        self.recovery_consent.pack(anchor="w")
        self.recovery_consent.pack_forget()
        # Past the spend guard: a separate, deliberate override with a logged reason.
        self.spend = ttk.Frame(self.consent.body)
        self.spend.columnconfigure(2, weight=1)
        self.spend_allowed = tk.BooleanVar(value=False)
        self.spend_override = ttk.Checkbutton(
            self.spend,
            text="Override the spend guard for one run; more charges are possible.",
            variable=self.spend_allowed,
            command=lambda: self.busy(self.loading),
        )
        self.spend_override.grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(self.spend, text="Reason (logged)", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", padx=(22, 8), pady=(4, 0)
        )
        self.spend_reason = tk.StringVar()
        self.spend_reason_entry = ttk.Entry(self.spend, textvariable=self.spend_reason)
        self.spend_reason_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(4, 0))
        self.spend_reason.trace_add("write", lambda *_: self.busy(self.loading))
        self.message = ttk.Label(main, style="Muted.TLabel", wraplength=700)
        self.message.grid(row=10, column=0, sticky="ew", pady=(8, 0))
        self.window.bind("<Configure>", self._resize, add=True)
        self.query.trace_add("write", lambda *_: self._render())
        self.clear("Loading written notes…")

    @staticmethod
    def _text(tabs, title):
        frame = ttk.Frame(tabs)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = tk.Text(frame, wrap="word", height=5, padx=12, pady=10, state="disabled")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        tabs.add(frame, text=title)
        return text

    @staticmethod
    def _put(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _resize(self, event):
        if event.widget is self.window:
            for label in (self.message, self.context, self.journey):
                label.configure(wraplength=max(400, event.width - 50))

    def connect(self, refresh, selected, inspect, close):
        self.refresh_button.configure(command=refresh)
        self.inspect_button.configure(command=inspect)
        self.tree.bind("<<TreeviewSelect>>", lambda _: selected())
        self.window.protocol("WM_DELETE_WINDOW", close)
        self.window.bind(
            "<Escape>", lambda event: close() if event.widget is not self.search else None
        )

    def connect_execution(self, submit):
        self.queue_button.configure(command=submit)

    def connect_setup(self, choose):
        self.setup_button.configure(command=choose)

    def connect_navigation(self, open_episode, open_job):
        self.open_episode, self.open_job = open_episode, open_job

    def choose_setup(self):
        return filedialog.askopenfilename(
            parent=self.window,
            title="Choose settings.json from your previous production checkout",
            filetypes=(("JSON setup", "*.json"),),
            initialdir=self.setup_directory,
        )

    def confirm_setup(self, summary):
        return messagebox.askyesno("Import existing setup locally?", summary, parent=self.window)

    def _open_production(self):
        item = self.items.get(self.selected())
        if item and item.state == "Ready for production":
            self.open_episode(item.episode)

    def _open_job(self):
        item = self.items.get(self.selected())
        identifier = self.queued_id or (item.job_id if item else "")
        if identifier:
            self.open_job(identifier)

    def queued(self, episode, identifier):
        # A completed submission must not leave this note's previous failure as
        # its visible next step. Do not change another selected note or its edits.
        for note, item in self.items.items():
            if item.episode != episode:
                continue
            item = replace(
                item,
                state="Queued",
                job_id=identifier,
                detail=(
                    f"{episode}: queued as job {identifier[:8]}. "
                    "Use Show job for current progress; do not queue another copy."
                ),
            )
            self.items[note] = item
            if self.tree.exists(note):
                self.tree.item(note, values=(item.note, item.title, item.state))
            if self.selected() == note:
                self._put(self.plan, item.detail)
            break
        self.queued_id = identifier
        self.job_button.configure(state="normal")
        self.message.configure(
            text=f"{episode} queued · {identifier[:8]}. Show job follows narration → captions → recording ready. Do not queue again."
        )

    def selected(self):
        selected = self.tree.selection()
        return selected[0] if selected else ""

    def reveal(self, note):
        self.query.set("")
        if self.tree.exists(note):
            self.tree.selection_set(note)
            self.tree.focus(note)
            self.tree.see(note)

    def clear(self, message=""):
        self.snapshot = None
        self.journey.configure(text=JOURNEY)
        self.authorized.set(False)
        self.recover_uncertain.set(False)
        self.recovery_consent.pack_forget()
        self.spend_allowed.set(False)
        self.spend_reason.set("")
        self.spend.pack_forget()
        self.queued_id = ""
        item = self.items.get(self.selected())
        detail = (
            item.detail
            if item
            else "Find a written note above. Check its script and setup, then allow the narration. A note is ready to produce once narration and captions are saved."
        )
        self._put(self.plan, detail)
        self._put(self.script, "")
        self.message.configure(
            text=message or (f"Note {item.note} · {item.state}. Details above." if item else detail)
        )
        self.busy(self.loading)

    def busy(self, value):
        self.loading = value
        self.refresh_button.configure(state="disabled" if value else "normal")
        self.setup_button.configure(state="disabled" if value else "normal")
        item = self.items.get(self.selected())
        eligible = item is not None and item.state not in {"Needs script", "Needs repair"}
        self.inspect_button.configure(state="normal" if eligible and not value else "disabled")
        ready = bool(
            self.snapshot
            and (self.snapshot.request_json or self.snapshot.recovery_json)
            and not value
        )
        recovering = bool(self.snapshot and self.snapshot.recovery_json)
        self.authorization.configure(state="normal" if ready else "disabled")
        self.recovery_consent.configure(state="normal" if ready and recovering else "disabled")
        guarded = bool(self.snapshot and getattr(self.snapshot, "spend_blocked", False))
        overridable = guarded and getattr(self.snapshot, "spend_overridable", False)
        self.spend_override.configure(state="normal" if ready and overridable else "disabled")
        self.spend_reason_entry.configure(
            state="normal" if ready and overridable and self.spend_allowed.get() else "disabled"
        )
        permitted = (
            ready
            and self.authorized.get()
            and (not recovering or self.recover_uncertain.get())
            and (
                not guarded
                or (
                    overridable
                    and self.spend_allowed.get()
                    and len(self.spend_reason.get().strip()) >= 8
                )
            )
        )
        self.queue_button.configure(
            state="normal" if permitted else "disabled",
            text="Queue recovery" if recovering else "Queue narration",
        )
        self.production_button.configure(
            state="normal"
            if item and item.state == "Ready for production" and not value
            else "disabled"
        )
        self.job_button.configure(
            state="normal"
            if not value and (self.queued_id or (item and item.job_id))
            else "disabled"
        )

    def _render(self):
        selected = self.selected()
        self.tree.delete(*self.tree.get_children())
        query = self.query.get().strip().casefold()
        for item in self.items.values():
            if query in f"{item.note} {item.episode} {item.title}".casefold():
                self.tree.insert(
                    "", "end", iid=item.note, values=(item.note, item.title, item.state)
                )
        if self.tree.exists(selected):
            self.tree.selection_set(selected)
            self.tree.see(selected)
        count = len(self.tree.get_children())
        self.clear(
            f"{count} of {len(self.items)} written notes. Search by title or number."
            if count
            else "0 written notes match. Clear the search or refresh this checkout's notes."
        )

    def show_catalog(self, items):
        self.items = {item.note: item for item in items}
        self._render()

    def show_snapshot(self, snapshot):
        if snapshot.note != self.selected():
            return
        self.snapshot = snapshot
        if snapshot.scope_summary:
            self.journey.configure(text=snapshot.scope_summary)
        self._put(self.plan, snapshot.summary)
        self._put(self.script, snapshot.script)
        self.authorized.set(False)
        self.recover_uncertain.set(False)
        self.spend_allowed.set(False)
        self.spend_reason.set("")
        if snapshot.recovery_json:
            self.recovery_consent.pack(anchor="w")
        else:
            self.recovery_consent.pack_forget()
        if getattr(snapshot, "spend_blocked", False):
            # The count and possible spend sit in the label itself, read before ticking.
            self.spend_override.configure(
                text=f"Override once ({snapshot.spend_label})."
                if snapshot.spend_overridable
                else f"Already overridden once in this window ({snapshot.spend_label})."
            )
            self.spend.pack(anchor="w", fill="x", pady=(2, 0))
        else:
            self.spend.pack_forget()
        self.busy(False)
        self.message.configure(
            text=(
                "Spend guard reached: this part was already overridden once in this window. "
                "Stop and wait; nothing can be queued for it now."
                if getattr(snapshot, "spend_blocked", False) and not snapshot.spend_overridable
                else "Spend guard reached: stop and wait. An override needs a logged reason."
                if getattr(snapshot, "spend_blocked", False)
                and (snapshot.request_json or snapshot.recovery_json)
                else "Recovery needs two confirmations. Completed audio is retained; uncertain resends can charge twice."
                if snapshot.recovery_json
                else "Script checked. Confirm the project and requests, give consent, then queue the narration."
                if snapshot.request_json
                else "Narration is blocked. Read the reason above; use Import existing setup or Show job as needed."
            )
        )

    def schedule(self, delay, callback):
        return self.window.after(delay, callback)

    def unschedule(self, handle):
        self.window.after_cancel(handle)

    def close(self):
        self.window.destroy()
