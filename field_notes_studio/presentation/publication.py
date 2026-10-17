"""Release on one page: upload copy, files, the website step and the release record.

Everything needed to publish by hand sits on one scrolling page. Each copy field
shows its platform limit and its own Copy button; each file has a Copy path. Studio
never uploads, merges or checks a platform; the record is the reader's own note.
"""

import tkinter as tk
from datetime import date
from tkinter import font as tkfont
from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.editors import PUBLISHING, Editor
from field_notes_studio.presentation.package_files import PackageFiles
from field_notes_studio.presentation.scroll import ScrollArea

FIELDS = {
    "Title": "title",
    "Description": "description",
    "Tags": "tags",
    "Hashtags": "hashtags",
    "Written note link": "written_url",
}


def measure(field, value):
    """Length against the platform limit the engine enforces, in its own units."""
    if field == "Title":
        return f"{len(value):,} / 100"
    if field == "Description":
        return f"{len((value + chr(10)).encode('utf-8')):,} / 5,000 bytes"
    if field == "Tags":
        tags = [tag for tag in value.split(", ") if tag]
        # YouTube counts separators and quotes around multiword tags.
        used = sum(len(tag) + (2 if " " in tag else 0) for tag in tags) + max(0, len(tags) - 1)
        return f"{used:,} / 500"
    if field == "Hashtags":
        return f"{len(value.split())} / 3 tags"
    return f"{len(value):,} characters"


class Publication(ttk.Frame):
    def __init__(self, parent, callbacks):
        super().__init__(parent)
        self.callbacks = callbacks
        self.details = None
        self.filling = False
        self.date_edited = False
        self.loaded_url = ""
        self.episode = None
        self.current_episode = None
        self.defaults = ("", "")
        self.written_url = ""
        self.drafts = {}
        self.metadata_draft = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.page = ScrollArea(self, padding=(14, 12, 14, 14))
        self.page.grid(row=0, column=0, sticky="nsew")
        content = self.page.content
        content.columnconfigure(0, weight=1)
        self.preflight = ttk.Label(
            content,
            text="Upload folder checks run here before anything is queued.",
            style="Muted.TLabel",
            wraplength=540,
        )
        self.preflight.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.upload = ttk.Frame(content, style="Card.TFrame", padding=14)
        self.upload.columnconfigure(0, weight=1)
        self.side = ttk.Frame(content)
        self.side.columnconfigure(0, weight=1)
        self.wide = None
        self._upload_card(callbacks)
        self._website_card()
        self._record_card(callbacks)
        content.bind("<Configure>", self._resize, add=True)
        self._layout(True)
        self.editor_window = tk.Toplevel(self)
        self.editor_window.withdraw()
        self.editor_window.title("Title and description · this episode")
        self.editor_window.geometry("720x620")
        self.editor_window.protocol("WM_DELETE_WINDOW", self.close_editor)
        self.editor_window.bind("<Escape>", lambda _: self.close_editor())
        self.editor = Editor(
            self.editor_window,
            PUBLISHING,
            callbacks["draft"],
            "Episode changes combine with the show's usual copy. Save, then make the upload "
            "folder again to include them.",
            save=callbacks["metadata_save"],
            reload=callbacks["metadata_reload"],
        )
        self.editor.pack(fill="both", expand=True)
        ttk.Button(self.editor_window, text="Close", command=self.close_editor).pack(
            anchor="e", padx=10, pady=(0, 10)
        )
        self.page.bind_navigation()

    # Layout -----------------------------------------------------------------------

    def _layout(self, wide):
        if wide == self.wide:
            return
        self.wide = wide
        self.upload.grid_forget()
        self.side.grid_forget()
        content = self.page.content
        # A uniform group fixes the split, so wrapped text never widens a column.
        content.columnconfigure(0, weight=2 if wide else 1, uniform="release" if wide else "")
        content.columnconfigure(1, weight=1 if wide else 0, uniform="release" if wide else "")
        if wide:
            self.upload.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
            self.side.grid(row=1, column=1, sticky="nsew")
        else:
            self.upload.grid(row=1, column=0, columnspan=2, sticky="ew")
            self.side.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def _resize(self, event):
        self._layout(event.width >= 760)
        self.preflight.configure(wraplength=max(220, event.width - 30))
        if event.width != getattr(self, "fitted_width", None):
            self.fitted_width = event.width
            self.after_idle(self._fit_values)

    def _fit_values(self):
        """Ellipsize each copy preview to its row; Copy always copies the full text."""
        if not self.winfo_exists():
            return
        width = self.value_column.winfo_width()
        typeface = tkfont.Font(
            font=ttk.Style(self).lookup("Card.TLabel", "font") or "TkDefaultFont"
        )
        for field, label in self.values.items():
            text = (self._value(field) if self.details else "").split("\n", 1)[0]
            if width > 20 and typeface.measure(text) > width:
                while text and typeface.measure(text + "…") > width:
                    text = text[:-1]
                text = text.rstrip() + "…"
            label.configure(text=text)

    def _upload_card(self, callbacks):
        card = self.upload
        ttk.Label(card, text="1  Upload to YouTube", style="CardHeading.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.basis = ttk.Label(
            card,
            text="Loading upload copy…",
            style="CardMuted.TLabel",
            wraplength=520,
        )
        self.basis.grid(row=1, column=0, sticky="ew", pady=(2, 10))
        fields = ttk.Frame(card, style="CardRow.TFrame")
        fields.grid(row=2, column=0, sticky="ew")
        fields.columnconfigure(1, weight=1)
        self.value_column = ttk.Frame(fields, style="CardRow.TFrame")
        self.value_column.grid(row=0, column=1, rowspan=len(FIELDS), sticky="nsew")
        self.values, self.measures, self.copy_buttons = {}, {}, {}
        for row, field in enumerate(FIELDS):
            ttk.Label(fields, text=field, style="CardNow.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=4
            )
            # A fixed one-character request keeps the column from following its text.
            value = ttk.Label(fields, text="", style="Card.TLabel", width=1)
            value.grid(row=row, column=1, sticky="ew", pady=4)
            meta = ttk.Label(fields, text="", style="CardMuted.TLabel")
            meta.grid(row=row, column=2, sticky="e", padx=12, pady=4)
            copy = ActionButton(
                fields,
                pictogram="copy",
                text="Copy",
                command=lambda f=field: self.copy(f),
                state="disabled",
                style="Compact.TButton",
            )
            copy.grid(row=row, column=3, sticky="e", pady=2)
            self.values[field], self.measures[field], self.copy_buttons[field] = value, meta, copy
        self.value_column.lower()
        self.value_column.bind("<Configure>", lambda _: self.after_idle(self._fit_values))
        card.bind(
            "<Configure>",
            lambda e: self.basis.configure(wraplength=max(200, e.width - 30)),
            add=True,
        )
        edit = ttk.Frame(card, style="CardRow.TFrame")
        edit.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        self.edit_button = ActionButton(
            edit,
            pictogram="transcript",
            text="Edit title and description…",
            command=self.open_editor,
            style="Compact.TButton",
        )
        self.edit_button.pack(side="left")
        self.refresh = ActionButton(
            edit,
            pictogram="refresh",
            text="Refresh",
            command=callbacks["release_refresh"],
            style="Compact.TButton",
        )
        self.refresh.pack(side="right")
        ttk.Separator(card).grid(row=4, column=0, sticky="ew", pady=12)
        self.files = PackageFiles(card, callbacks)
        self.files.grid(row=5, column=0, sticky="ew")
        bar = ttk.Frame(card, style="CardRow.TFrame")
        bar.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        self.actions = {}
        for key, label, pictogram, command in (
            ("upload", "Open YouTube Studio", "external", callbacks["youtube"]),
            ("folder", "Open upload folder", "folder", lambda: callbacks["open"]("uploads")),
            ("package", "Make upload folder", "package", callbacks["release_package"]),
        ):
            button = ActionButton(bar, pictogram=pictogram, text=label, command=command)
            button.pack(side="left", padx=(0, 6))
            self.actions[key] = button
        self.files.folder = self.actions["folder"]

    def _website_card(self):
        card = ttk.Frame(self.side, style="Card.TFrame", padding=14)
        card.grid(row=0, column=0, sticky="ew")
        ttk.Label(card, text="2  Website and podcast feed", style="CardHeading.TLabel").pack(
            anchor="w"
        )
        self.website_help = ttk.Label(
            card,
            text="Adds the finished audio to the note page and the RSS feed, as a pull "
            "request you merge. For now this step runs in a terminal:",
            style="CardMuted.TLabel",
            wraplength=300,
        )
        self.website_help.pack(anchor="w", pady=(2, 6))
        self.commands = ttk.Label(card, text="", style="CardMono.TLabel", wraplength=300)
        self.commands.pack(anchor="w")
        self.copy_commands = ActionButton(
            card,
            pictogram="copy",
            text="Copy commands",
            command=self.copy_website_commands,
            style="Compact.TButton",
        )
        self.copy_commands.pack(anchor="w", pady=(8, 0))

    def _record_card(self, callbacks):
        card = ttk.Frame(self.side, style="Card.TFrame", padding=14)
        card.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        card.columnconfigure(2, weight=1)
        self.record = card
        ttk.Label(card, text="3  Record where it went live", style="CardHeading.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        self.source = ttk.Label(card, text="", style="CardMuted.TLabel", wraplength=300)
        self.source.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(2, 8))
        self.url, self.date = tk.StringVar(), tk.StringVar()
        self.url.trace_add("write", lambda *_: self.link_changed())
        self.date.trace_add("write", lambda *_: self.date_changed())
        ttk.Label(card, text="Published link", style="Card.TLabel").grid(
            row=2, column=0, columnspan=3, sticky="w"
        )
        self.url_entry = ttk.Entry(card, textvariable=self.url, width=24)
        self.url_entry.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(2, 6))
        ttk.Label(card, text="Published on", style="Card.TLabel").grid(
            row=4, column=0, columnspan=3, sticky="w"
        )
        self.date_entry = ttk.Entry(card, textvariable=self.date, width=12)
        self.date_entry.grid(row=5, column=0, sticky="w", pady=(2, 6))
        self.today = ttk.Button(
            card,
            text="Use today",
            command=lambda: self.date.set(date.today().isoformat()),
            style="Compact.TButton",
        )
        self.today.grid(row=5, column=1, sticky="w", padx=(6, 0), pady=(2, 6))
        self.defaults_button = ttk.Button(
            card,
            text="Use podcast details",
            command=self.use_defaults,
            state="disabled",
            style="Compact.TButton",
        )
        self.defaults_button.grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 10))
        footer = ttk.Frame(card, style="CardRow.TFrame")
        footer.grid(row=7, column=0, columnspan=3, sticky="ew")
        self.save = ActionButton(
            footer,
            pictogram="save",
            text="Save release record",
            command=callbacks["publication"],
            style="Accent.TButton",
        )
        self.save.pack(anchor="w")
        self.record_status = ttk.Label(footer, text="", style="CardMuted.TLabel")
        self.record_status.pack(anchor="w", pady=(4, 0))
        self.record_help = ttk.Label(
            card,
            text="Studio never checks YouTube; this is your record of what you did. Use "
            "today only for a release published today.",
            style="CardMuted.TLabel",
            wraplength=300,
        )
        self.record_help.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        card.bind(
            "<Configure>",
            lambda e: [
                label.configure(wraplength=max(200, e.width - 30))
                for label in (self.source, self.record_help, self.website_help, self.commands)
            ],
            add=True,
        )

    # Editor window ------------------------------------------------------------------

    def open_editor(self):
        self.editor_window.transient(self.winfo_toplevel())
        self.editor_window.deiconify()
        self.editor_window.lift()
        self.editor.form.canvas.focus_set()

    def close_editor(self):
        self.editor_window.withdraw()

    def editor_visible(self):
        return self.editor_window.state() != "withdrawn"

    # Episode state ------------------------------------------------------------------

    def load_episode(self, episode):
        self.current_episode = episode
        self.episode = episode.identifier
        self.written_url = episode.written_url
        self.defaults = (episode.podcast_url, episode.podcast_date)
        self.commands.configure(
            text=f"python3 -m field_notes_audio promote {episode.identifier}\n"
            "python3 -m field_notes_audio publish"
        )
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
                "Draft details restored for this episode. Save to record the actual release."
                if draft
                else episode.publication_source or "No release recorded yet."
            )
        )
        self.save.configure(state="normal")
        self.save.reset_feedback()
        self.record_status.configure(
            text="Unsaved changes"
            if draft
            else "Saved locally"
            if episode.publication_saved
            else "Catalog suggestion"
            if any(self.defaults)
            else "Not recorded",
            style="Draft.TLabel"
            if draft
            else "CardOk.TLabel"
            if episode.publication_saved
            else "CardMuted.TLabel",
        )
        self.defaults_button.configure(state="normal" if any(self.defaults) else "disabled")
        self.render_copy()

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
        self.editor.loaded = False
        self.editor.enable(False)
        self.editor.save.configure(state="disabled")
        self.metadata_draft = {}
        self.episode = None
        self.written_url = ""
        self.clear()
        self.filling = True
        self.url.set("")
        self.date.set("")
        self.filling = False
        self.source.configure(text="Loading release details…")
        self.save.configure(state="disabled")
        self.save.reset_feedback()
        self.record_status.configure(text="")
        self.defaults_button.configure(state="disabled")
        self.files.clear()

    def files_visible(self):
        """The upload files load lazily, once Release is on screen."""
        notebook = self.nametowidget(self.winfo_parent())
        return notebook.select() == str(self)

    def clear(self, message="Loading upload copy…", *, loading=True):
        self.details = None
        self.basis.configure(text=message)
        for field in FIELDS:
            self.copy_buttons[field].reset_feedback()
            self.copy_buttons[field].configure(state="disabled")
            self.measures[field].configure(text="")
            self.values[field].configure(text="")
        self.refresh.configure(
            text="Refreshing…" if loading else "Refresh",
            state="disabled" if loading else "normal",
        )

    def load_details(self, details):
        self.details = details
        self.basis.configure(
            text=details.basis + " Copy each field into the matching box in YouTube Studio."
        )
        self.refresh.configure(text="Refresh", state="normal")
        self.render_copy()

    def _value(self, field):
        if field == "Written note link":
            return self.written_url
        return getattr(self.details, FIELDS[field]) if self.details else ""

    def render_copy(self):
        for field in FIELDS:
            button = self.copy_buttons[field]
            button.reset_feedback()
            available = bool(self.details) and bool(self._value(field))
            button.configure(state="normal" if available else "disabled")
            self.measures[field].configure(
                text=measure(field, self._value(field)) if self.details else ""
            )
        self._fit_values()

    def copy(self, field):
        if self.details:
            value = self._value(field)
            self.clipboard_clear()
            self.clipboard_append(value)
            for other, button in self.copy_buttons.items():
                if other != field:
                    button.reset_feedback()
            self.copy_buttons[field].complete()
            self.callbacks["status"](field + " copied. Paste it into the upload form.")

    def copy_website_commands(self):
        self.clipboard_clear()
        self.clipboard_append(self.commands.cget("text"))
        self.copy_commands.complete()
        self.callbacks["status"](
            "Website commands copied. Run them in a terminal in this checkout; Studio ran nothing."
        )

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
            self.callbacks["draft"]()

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
