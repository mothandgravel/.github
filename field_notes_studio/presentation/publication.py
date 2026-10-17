"""Release on one page: upload copy, files, the website step and the release record.

Everything needed to publish by hand sits on one scrolling page. Each copy field
shows its platform limit and its own Copy button; each file has a Copy path. Studio
never uploads, merges or checks a platform; the record is the reader's own note.
"""

import tkinter as tk
from datetime import date
from tkinter import font as tkfont
from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton, Tooltip
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


NO_LINK = "No note link for this episode."


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
        self.page = ScrollArea(self, padding=(12, 8, 12, 8))
        self.page.grid(row=0, column=0, sticky="nsew")
        content = self.page.content
        content.columnconfigure(0, weight=1)
        self.upload = ttk.Frame(content, style="Card.TFrame", padding=(14, 12))
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
        self._website_dialog()
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
            self.upload.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
            self.side.grid(row=0, column=1, sticky="nsew")
        else:
            self.upload.grid(row=0, column=0, columnspan=2, sticky="ew")
            self.side.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def _resize(self, event):
        self._layout(event.width >= 760)
        # Wrap from the page width, never from a card's own size: that fed back.
        left = (event.width - 12) * 2 // 3 if self.wide else event.width
        right = (event.width - 12) // 3 if self.wide else event.width
        for label in (self.basis, self.preflight, self.files.summary):
            label.configure(wraplength=max(200, left - 40))
        for label in (self.source, self.record_help, self.website_help):
            label.configure(wraplength=max(160, right - 40))
        if event.width != getattr(self, "fitted_width", None):
            self.fitted_width = event.width
            self.after_idle(self._fit_values)

    def _value_column_resized(self, event):
        # Refit only for a new width; restyling the labels must not refit again.
        if event.width != getattr(self, "value_width", None):
            self.value_width = event.width
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
            if self.details and not text and field == "Written note link":
                label.configure(text=NO_LINK, style="CardMuted.TLabel")
                continue
            if width > 20 and typeface.measure(text) > width:
                # Binary search keeps long descriptions cheap to fit.
                low, high = 0, len(text)
                while low < high:
                    middle = (low + high + 1) // 2
                    if typeface.measure(text[:middle] + "…") <= width:
                        low = middle
                    else:
                        high = middle - 1
                text = text[:low].rstrip() + "…"
            label.configure(text=text, style="Card.TLabel")

    def _upload_card(self, callbacks):
        card = self.upload
        heading = ttk.Frame(card, style="CardRow.TFrame")
        heading.grid(row=0, column=0, sticky="ew")
        ttk.Label(heading, text="1  Upload to YouTube", style="CardHeading.TLabel").pack(
            side="left"
        )
        self.refresh = ActionButton(
            heading,
            pictogram="refresh",
            text="Refresh",
            command=callbacks["release_refresh"],
            style="Small.TButton",
        )
        self.refresh.pack(side="right")
        self.edit_button = ActionButton(
            heading,
            pictogram="transcript",
            text="Edit title and description…",
            command=self.open_editor,
            style="Small.TButton",
        )
        self.edit_button.pack(side="right", padx=(0, 6))
        instruction = ttk.Label(
            card,
            text="Copy each field into the matching box in YouTube Studio.",
            style="CardMuted.TLabel",
        )
        instruction.grid(row=1, column=0, sticky="w", pady=(2, 6))
        # Where the copy comes from: a hover detail once loaded, visible while it is not.
        Tooltip(instruction, lambda: self.details.basis if self.details else "")
        fields = ttk.Frame(card, style="CardRow.TFrame")
        fields.grid(row=2, column=0, sticky="ew")
        fields.columnconfigure(1, weight=1)
        self.value_column = ttk.Frame(fields, style="CardRow.TFrame")
        self.value_column.grid(row=0, column=1, rowspan=len(FIELDS), sticky="nsew")
        self.values, self.measures, self.copy_buttons = {}, {}, {}
        for row, field in enumerate(FIELDS):
            ttk.Label(fields, text=field, style="CardNow.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=1
            )
            # A fixed one-character request keeps the column from following its text.
            value = ttk.Label(fields, text="", style="Card.TLabel", width=1)
            value.grid(row=row, column=1, sticky="ew", pady=1)
            meta = ttk.Label(fields, text="", style="CardMuted.TLabel")
            meta.grid(row=row, column=2, sticky="e", padx=12, pady=1)
            copy = ActionButton(
                fields,
                pictogram="copy",
                text="Copy",
                command=lambda f=field: self.copy(f),
                state="disabled",
                style="Small.TButton",
            )
            copy.grid(row=row, column=3, sticky="e", pady=1)
            self.values[field], self.measures[field], self.copy_buttons[field] = value, meta, copy
        self.value_column.lower()
        self.value_column.bind("<Configure>", self._value_column_resized)
        self.files = PackageFiles(card, callbacks, summary_master=card)
        self.files.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        bar = ttk.Frame(card, style="CardRow.TFrame")
        bar.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.actions = {}
        for key, label, pictogram, command, style in (
            ("upload", "Open YouTube Studio", "external", callbacks["youtube"], "Accent.TButton"),
            (
                "folder",
                "Open upload folder",
                "folder",
                lambda: callbacks["open"]("uploads"),
                "TButton",
            ),
        ):
            button = ActionButton(
                bar, pictogram=pictogram, text=label, command=command, style=style
            )
            button.pack(side="left", padx=(0, 6))
            self.actions[key] = button
        self.files.folder = self.actions["folder"]
        # Remaking the folder belongs with its files, beside Check files.
        self.actions["package"] = ActionButton(
            self.files.heading,
            pictogram="package",
            text="Make upload folder",
            command=callbacks["release_package"],
            style="Small.TButton",
        )
        self.actions["package"].pack(side="right", padx=(0, 6))
        self.files.summary.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        self.basis = ttk.Label(card, text="Loading upload copy…", style="CardSmall.TLabel")
        self.basis.grid(row=6, column=0, sticky="ew", pady=(2, 0))
        self.preflight = ttk.Label(
            card,
            text="Upload folder checks run here before anything is queued.",
            style="CardSmall.TLabel",
        )
        self.preflight.grid(row=7, column=0, sticky="ew")

    def _website_card(self):
        card = ttk.Frame(self.side, style="Card.TFrame", padding=(14, 12))
        card.grid(row=0, column=0, sticky="ew")
        ttk.Label(card, text="2  Website and podcast feed", style="CardHeading.TLabel").pack(
            anchor="w"
        )
        self.website_help = ttk.Label(
            card,
            text="Adds the finished audio to the note page and RSS, as a pull request.",
            style="CardMuted.TLabel",
            wraplength=300,
        )
        self.website_help.pack(anchor="w", pady=(2, 8))
        self.website_button = ActionButton(
            card,
            pictogram="package",
            text="Prepare website update…",
            command=self.open_website,
            style="Compact.TButton",
        )
        self.website_button.pack(anchor="w")
        ttk.Label(
            card, text="Today: terminal only (promote, publish)", style="CardWarn.TLabel"
        ).pack(anchor="w", pady=(8, 0))

    def _website_dialog(self):
        """The commands behind Prepare website update…; Studio runs neither of them."""
        window = self.website_window = tk.Toplevel(self)
        window.withdraw()
        window.title("Website and podcast feed")
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        window.bind("<Escape>", lambda _: window.withdraw())
        body = ttk.Frame(window, padding=18)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Prepare website update", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            body,
            text="Run these in a terminal in this checkout. promote adds the finished audio "
            "to the note page and RSS; publish pushes a pull request branch for you to merge. "
            "Studio does not run them yet.",
            style="Muted.TLabel",
            wraplength=460,
        ).pack(anchor="w", pady=(4, 10))
        self.commands = ttk.Label(body, text="", style="Mono.TLabel")
        self.commands.pack(anchor="w")
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(14, 0))
        self.copy_commands = ActionButton(
            actions,
            pictogram="copy",
            text="Copy commands",
            command=self.copy_website_commands,
        )
        self.copy_commands.pack(side="left")
        ttk.Button(actions, text="Close", command=window.withdraw).pack(side="right")

    def open_website(self):
        self.website_window.transient(self.winfo_toplevel())
        self.website_window.deiconify()
        self.website_window.lift()
        self.copy_commands.focus_set()

    def _record_card(self, callbacks):
        card = ttk.Frame(self.side, style="Card.TFrame", padding=(14, 12))
        card.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        card.columnconfigure(1, weight=1)
        self.record = card
        ttk.Label(card, text="3  Record where it went live", style="CardHeading.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        self.url, self.date = tk.StringVar(), tk.StringVar()
        self.url.trace_add("write", lambda *_: self.link_changed())
        self.date.trace_add("write", lambda *_: self.date_changed())
        ttk.Label(card, text="YouTube link", style="Card.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 3)
        )
        self.url_entry = ttk.Entry(card, textvariable=self.url, width=18)
        self.url_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(8, 3))
        ttk.Label(card, text="Published on", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=3
        )
        self.date_entry = ttk.Entry(card, textvariable=self.date, width=11)
        self.date_entry.grid(row=2, column=1, sticky="w", pady=3)
        self.today = ttk.Button(
            card,
            text="Use today",
            command=lambda: self.date.set(date.today().isoformat()),
            style="Small.TButton",
        )
        self.today.grid(row=2, column=2, sticky="e", padx=(6, 0), pady=3)
        self.defaults_button = ttk.Button(
            card,
            text="Use podcast details",
            command=self.use_defaults,
            state="disabled",
            style="Small.TButton",
        )
        self.defaults_button.grid(row=3, column=1, columnspan=2, sticky="w", pady=(3, 8))
        footer = ttk.Frame(card, style="CardRow.TFrame")
        footer.grid(row=4, column=0, columnspan=3, sticky="ew")
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
        self.source = ttk.Label(card, text="", style="CardSmall.TLabel", wraplength=300)
        self.source.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.record_help = ttk.Label(
            card,
            text="Studio never checks YouTube; this is your record of what you did.",
            style="CardMuted.TLabel",
            wraplength=300,
        )
        self.record_help.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(4, 0))

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
        self.basis.grid()
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
        self.basis.configure(text=details.basis)
        self.basis.grid_remove()
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
            hint = bool(self.details) and not available and field == "Written note link"
            # An empty link gets a plain hint instead of "0 characters" and a dead Copy.
            if hint:
                button.grid_remove()
            else:
                button.grid()
            self.measures[field].configure(
                text=measure(field, self._value(field)) if self.details and not hint else ""
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
