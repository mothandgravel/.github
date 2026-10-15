"""A guided handoff with generated upload copy and sourced publication defaults."""

import tkinter as tk
from datetime import date
from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.package_files import PackageFiles
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
        self.episode = None
        self.defaults = ("", "")
        self.drafts = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        actions = ttk.Frame(self, padding=(10, 8))
        actions.grid(row=0, column=0, sticky="ew")
        self.actions = {}
        for key, label, callback in (
            ("review", "1. Review video", callbacks["release_review"]),
            ("package", "2. Inspect package", callbacks["release_package"]),
            ("upload", "3. YouTube Studio", callbacks["youtube"]),
        ):
            button = ActionButton(
                actions,
                text=label,
                command=callback,
                pictogram={"review": "review", "package": "package", "upload": "external"}[key],
                style="Accent.TButton" if key == "upload" else "Compact.TButton",
            )
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
        self.copy_button = ActionButton(
            toolbar,
            pictogram="copy",
            text="Copy title",
            command=self.copy,
            state="disabled",
            width=16,
        )
        self.copy_button.pack(side="left", padx=6)
        self.refresh = ActionButton(
            toolbar, pictogram="refresh", text="Refresh", command=callbacks["release_refresh"]
        )
        self.refresh.pack(side="right")
        self.measure = ttk.Label(copy, text="", style="Muted.TLabel")
        self.measure.grid(row=3, column=0, columnspan=2, sticky="w", pady=(5, 0))
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
        self.save = ActionButton(
            footer,
            pictogram="save",
            text="Save publication record",
            command=callbacks["publication"],
            style="Accent.TButton",
            width=24,
        )
        self.save.pack(side="left")
        self.record_status = ttk.Label(footer, text="", style="Muted.TLabel")
        self.record_status.pack(side="left", padx=12)
        self.form.bind_navigation()
        self.files = PackageFiles(self.tabs, callbacks)
        self.tabs.add(self.files, text="Package files")
        self.tabs.bind(
            "<<NotebookTabChanged>>",
            lambda _: callbacks["package_refresh"]() if self.files_visible() else None,
        )
        copy.bind("<Configure>", lambda e: self.basis.configure(wraplength=max(200, e.width - 24)))
        content.bind(
            "<Configure>",
            lambda e: self.source.configure(wraplength=max(200, e.width - 24)),
            add=True,
        )

    def load_episode(self, episode):
        self.episode = episode.identifier
        self.defaults = (episode.podcast_url, episode.podcast_date)
        self.filling = True
        draft = self.drafts.get(self.episode)
        if draft is None:
            self.url.set(episode.publication_url)
            self.date.set(episode.publication_date)
            self.loaded_url = episode.publication_url
            self.date_edited = False
        else:
            url, published, self.loaded_url, self.date_edited = draft
            self.url.set(url)
            self.date.set(published)
        self.filling = False
        self.source.configure(
            text=(
                "Unsaved details kept for this episode. Save before closing Studio."
                if draft
                else episode.publication_source or "No publication details recorded yet."
            )
        )
        self.save.configure(state="normal")
        self.save.reset_feedback()
        self.record_status.configure(
            text="Unsaved changes"
            if draft
            else "Saved locally"
            if episode.publication_saved
            else "Catalog suggestion",
            style="Draft.TLabel"
            if draft
            else "Success.TLabel"
            if episode.publication_saved
            else "Muted.TLabel",
        )
        self.defaults_button.configure(state="normal" if any(self.defaults) else "disabled")

    def record_saved(self, episode, url, published):
        draft = self.drafts.get(episode.identifier)
        if draft is not None and draft[:2] == (url, published):
            del self.drafts[episode.identifier]
        if self.episode == episode.identifier and (self.url.get(), self.date.get()) == (
            url,
            published,
        ):
            self.load_episode(episode)
            self.save.complete("Saved")

    def loading_episode(self):
        self.episode = None
        self.clear()
        self.filling = True
        self.url.set("")
        self.date.set("")
        self.filling = False
        self.source.configure(text="Loading publication details…")
        self.save.configure(state="disabled")
        self.save.reset_feedback()
        self.record_status.configure(text="")
        self.defaults_button.configure(state="disabled")
        self.files.clear()

    def files_visible(self):
        return self.tabs.select() == str(self.files)

    def clear(self, message="Loading upload copy…", *, loading=True):
        self.details = None
        self.basis.configure(text=message)
        self.copy_button.configure(state="disabled")
        self.copy_button.reset_feedback()
        self.measure.configure(text="")
        self.refresh.configure(
            text="Refreshing…" if loading else "Refresh",
            state="disabled" if loading else "normal",
        )
        set_text(self.text, "")

    def load_details(self, details):
        self.details = details
        self.basis.configure(text=details.basis)
        self.refresh.configure(text="Refresh", state="normal")
        self.render_copy()

    def render_copy(self):
        self.copy_button.reset_feedback("Copy " + self.field.get().lower())
        if self.details:
            value = getattr(self.details, FIELDS[self.field.get()])
            set_text(self.text, value)
            self.copy_button.configure(state="normal")
            self.measure.configure(
                text=f"{len(value):,} characters · {self.field.get().lower()} for the upload form"
            )

    def copy(self):
        if self.details:
            self.clipboard_clear()
            self.clipboard_append(getattr(self.details, FIELDS[self.field.get()]))
            self.copy_button.complete()
            self.callbacks["status"](self.field.get() + " copied. Paste it into the upload form.")

    def use_defaults(self):
        if self.episode is not None and any(self.defaults):
            self.filling = True
            self.url.set(self.defaults[0])
            self.date.set(self.defaults[1])
            self.loaded_url = self.defaults[0]
            self.date_edited = False
            self.filling = False
            self.source.configure(
                text="Podcast catalog in this checkout; review and save this record."
            )
            self.remember()

    def remember(self):
        if self.episode is not None:
            self.save.reset_feedback()
            self.record_status.configure(text="Unsaved changes", style="Draft.TLabel")
            self.drafts[self.episode] = (
                self.url.get(),
                self.date.get(),
                self.loaded_url,
                self.date_edited,
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
        self.remember()

    def date_changed(self):
        if not self.filling:
            self.date_edited = True
            self.source.configure(text="Unsaved release details. Save to keep this record.")
            self.remember()
