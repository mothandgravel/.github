"""A guided handoff with generated upload copy and sourced publication defaults."""

import tkinter as tk
from datetime import date
from tkinter import ttk

from field_notes_studio.presentation.scroll import ScrollArea
from field_notes_studio.presentation.theme import set_text

FIELDS = {"Title": "title", "Description": "description", "Tags": "tags", "Hashtags": "hashtags"}


class Publication(ttk.Frame):
    def __init__(self, parent, callbacks):
        super().__init__(parent)
        self.callbacks = callbacks
        self.details = None
        self.filling = False
        self.date_edited = False
        self.loaded_url = ""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        actions = ttk.Frame(self, padding=(10, 8))
        actions.grid(row=0, column=0, sticky="ew")
        self.actions = {}
        for key, label, callback in (
            ("review", "1. Review full video", callbacks["release_review"]),
            ("package", "2. Inspect package", callbacks["release_package"]),
            ("upload", "3. YouTube Studio", callbacks["youtube"]),
        ):
            button = ttk.Button(actions, text=label, command=callback, style="Compact.TButton")
            button.pack(side="left", padx=(0, 6))
            self.actions[key] = button
        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=1, column=0, sticky="nsew")
        copy = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(copy, text="Upload details")
        copy.columnconfigure(0, weight=1)
        copy.rowconfigure(2, weight=1)
        self.basis = ttk.Label(
            copy, text="Loading upload copy…", wraplength=540, style="Muted.TLabel"
        )
        self.basis.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        toolbar = ttk.Frame(copy)
        toolbar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.field = tk.StringVar(value="Title")
        ttk.Combobox(
            toolbar, textvariable=self.field, values=tuple(FIELDS), state="readonly", width=15
        ).pack(side="left")
        self.copy_button = ttk.Button(
            toolbar, text="Copy title", command=self.copy, state="disabled"
        )
        self.copy_button.pack(side="left", padx=6)
        ttk.Button(toolbar, text="Refresh details", command=callbacks["release_refresh"]).pack(
            side="right"
        )
        self.text = tk.Text(
            copy, wrap="word", height=4, padx=10, pady=8, relief="flat", state="disabled"
        )
        self.text.grid(row=2, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(copy, command=self.text.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)
        self.field.trace_add("write", lambda *_: self.render_copy())
        record = ttk.Frame(self.tabs)
        record.columnconfigure(0, weight=1)
        record.rowconfigure(0, weight=1)
        self.tabs.add(record, text="Publication record")
        self.form = ScrollArea(record, padding=8)
        self.form.grid(row=0, column=0, sticky="nsew")
        content = self.form.content
        self.source = ttk.Label(content, text="", style="Muted.TLabel", wraplength=540)
        self.source.pack(anchor="w", pady=(0, 4))
        self.url, self.date = tk.StringVar(), tk.StringVar()
        self.url.trace_add("write", lambda *_: self.link_changed())
        self.date.trace_add("write", lambda *_: self.date_changed())
        links = ttk.Frame(content)
        links.pack(fill="x", pady=(0, 2))
        ttk.Label(links, text="Episode link", width=18).pack(side="left")
        self.url_entry = ttk.Entry(links, textvariable=self.url)
        self.url_entry.pack(side="left", fill="x", expand=True)
        dates = ttk.Frame(content)
        dates.pack(fill="x")
        ttk.Label(dates, text="Date · YYYY-MM-DD", width=18).pack(side="left")
        self.date_entry = ttk.Entry(dates, textvariable=self.date, width=13)
        self.date_entry.pack(side="left")
        ttk.Button(
            dates,
            text="Today",
            command=lambda: self.date.set(date.today().isoformat()),
            style="Compact.TButton",
        ).pack(side="left", padx=6)
        self.defaults_button = ttk.Button(
            dates,
            text="Use podcast details",
            command=self.use_defaults,
            state="disabled",
            style="Compact.TButton",
        )
        self.defaults_button.pack(side="left")
        ttk.Label(
            content,
            text="The podcast date follows the catalog timestamp's timezone. For a YouTube release, replace the link and date with that release's details.",
            style="Muted.TLabel",
            wraplength=540,
        ).pack(anchor="w", pady=(6, 0))
        footer = ttk.Frame(record, padding=(10, 6))
        footer.grid(row=1, column=0, sticky="ew")
        self.save = ttk.Button(
            footer, text="Save publication record", command=callbacks["publication"]
        )
        self.save.pack(side="left")
        self.form.bind_navigation()
        copy.bind("<Configure>", lambda e: self.basis.configure(wraplength=max(200, e.width - 24)))
        content.bind(
            "<Configure>",
            lambda e: self.source.configure(wraplength=max(200, e.width - 24)),
            add=True,
        )

    def load_episode(self, episode):
        self.filling = True
        self.url.set(episode.publication_url)
        self.date.set(episode.publication_date)
        self.loaded_url = episode.publication_url
        self.date_edited = False
        self.filling = False
        self.source.configure(
            text=episode.publication_source or "No publication details recorded yet."
        )
        self.save.configure(state="normal")

    def loading_episode(self):
        self.clear()
        self.filling = True
        self.url.set("")
        self.date.set("")
        self.filling = False
        self.source.configure(text="Loading publication details…")
        self.save.configure(state="disabled")

    def clear(self, message="Loading upload copy…"):
        self.details = None
        self.basis.configure(text=message)
        self.copy_button.configure(state="disabled")
        self.defaults_button.configure(state="disabled")
        set_text(self.text, "")

    def load_details(self, details):
        self.details = details
        self.basis.configure(text=details.basis)
        self.defaults_button.configure(state="normal")
        self.render_copy()

    def render_copy(self):
        self.copy_button.configure(text="Copy " + self.field.get().lower())
        if self.details:
            set_text(self.text, getattr(self.details, FIELDS[self.field.get()]))
            self.copy_button.configure(state="normal")

    def copy(self):
        if self.details:
            self.clipboard_clear()
            self.clipboard_append(getattr(self.details, FIELDS[self.field.get()]))
            self.callbacks["status"](self.field.get() + " copied. Paste it into the upload form.")

    def use_defaults(self):
        if self.details:
            self.filling = True
            self.url.set(self.details.podcast_url)
            self.date.set(self.details.podcast_date)
            self.loaded_url = self.details.podcast_url
            self.date_edited = False
            self.filling = False
            self.source.configure(
                text="Podcast catalog in this checkout; review and save this record."
            )

    def link_changed(self):
        if self.filling:
            return
        if self.url.get() != self.loaded_url and not self.date_edited:
            # A podcast date does not establish a YouTube video's publication date.
            self.filling = True
            self.date.set("")
            self.filling = False
        self.source.configure(text="Unsaved link. Enter this release's actual date, then save.")

    def date_changed(self):
        if not self.filling:
            self.date_edited = True
            self.source.configure(text="Unsaved release details. Save to keep this record.")
