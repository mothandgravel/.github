"""The episode shelf: every written note, what comes next, and a Needs me filter.

Narrated episodes and written notes that are not narrated yet share one list, so
the shelf is the single front door. The Next column is a quick hint from saved
files and jobs; the episode card's check is the evidence.
"""

import re
import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.controls import Tooltip
from field_notes_studio.presentation.theme import px

FILTERS = ("All", "Needs me", "Working", "Done")
# "Check" is a version whose saved pointer could not be read: someone should look.
NEEDS_ME = {"Prepare", "Produce", "Review", "Release", "Recover", "Resume", "Repair", "Check"}
WORKING = {"Working"}
DONE = {"Done", "In feed"}
# Preparation states for written notes that are not narrated yet.
NOTE_NEXT = {
    "Queued": "Working",
    "Preparing": "Working",
    "Awaiting captions": "Resume",
    "Needs recovery": "Recover",
    "Needs script": "Needs script",
    "Needs repair": "Repair",
}


def note_number(text):
    match = re.search(r"(\d+)", text or "")
    return int(match[1]) if match else -1


def matches(next_step, choice):
    return (
        choice == "All"
        or (choice == "Needs me" and next_step in NEEDS_ME)
        or (choice == "Working" and next_step in WORKING)
        or (choice == "Done" and next_step in DONE)
    )


class Shelf(ttk.Frame):
    def __init__(self, parent, select, select_note=None):
        super().__init__(parent, padding=(0, 0, 12, 0))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)
        self.episodes = []
        self.notes = []
        self.hints = {}
        self.current = None
        self.restoring = None
        self.select = select
        self.select_note = select_note or (lambda _item: None)
        ttk.Label(self, text="EPISODES", style="Heading.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        self.query = tk.StringVar()
        self.search = ttk.Entry(self, textvariable=self.query)
        self.search.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.search.bind("<Escape>", lambda _: self.query.set(""))
        self.placeholder = ttk.Label(
            self.search, text="Search title or number   Ctrl+F", style="Placeholder.TLabel"
        )
        self.placeholder.bind("<Button-1>", lambda _: self.search.focus_set())
        for event in ("<FocusIn>", "<FocusOut>"):
            self.search.bind(event, lambda _: self._placeholder(), add=True)
        self.query.trace_add("write", lambda *_: (self._placeholder(), self.render()))
        self.filter = tk.StringVar(value="All")
        filters = ttk.Frame(self)
        filters.grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.filter_buttons = {}
        for name in FILTERS:
            button = ttk.Radiobutton(
                filters,
                text=name,
                value=name,
                variable=self.filter,
                style="Filter.TRadiobutton",
                command=self.render,
            )
            button.pack(side="left", padx=(0, 2))
            self.filter_buttons[name] = button
        region = ttk.Frame(self)
        region.grid(row=4, column=0, sticky="nsew")
        self.tree = ttk.Treeview(
            region, columns=("episode", "next"), show="headings", selectmode="browse"
        )
        self.tree.heading("episode", text="Episode", anchor="w")
        self.tree.heading("next", text="Next", anchor="w")
        self.tree.column("episode", width=px(self, 222), minwidth=px(self, 140))
        self.tree.column("next", width=px(self, 66), minwidth=px(self, 60), stretch=False)
        Tooltip(self.tree, self._hovered)
        scrollbar = ttk.Scrollbar(region, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._selected)
        self.count = ttk.Label(self, text="Loading episodes…", style="Small.TLabel")
        self.count.grid(row=5, column=0, sticky="w", pady=(6, 10))
        self.bind(
            "<Configure>",
            lambda e: self.count.configure(wraplength=max(160, e.width - 20)),
            add=True,
        )
        self._placeholder()

    def _hovered(self):
        """The full title of the row under the pointer, for titles the column cuts."""
        y = self.tree.winfo_pointery() - self.tree.winfo_rooty()
        row = self.tree.identify_row(y)
        return self.tree.set(row, "episode") if row else ""

    def _placeholder(self):
        if self.query.get() or self.focus_get() is self.search:
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=7, rely=0.5, anchor="w")

    def load(self, episodes, hints=None):
        self.episodes = episodes
        if hints is not None:
            self.hints = dict(hints)
        self.render()

    def load_notes(self, notes):
        """Written notes from the preparation catalog; narrated ones are already rows."""
        self.notes = list(notes)
        self.render()

    def load_hints(self, hints):
        self.hints = dict(hints)
        self.render()

    def note(self, iid):
        return next((item for item in self.notes if "note:" + item.note == iid), None)

    def rows(self):
        """(iid, label, next, order) for every episode and unprepared written note."""
        prepared = {episode.identifier for episode in self.episodes}
        numbers = {item.episode: note_number(item.note) for item in self.notes if item.episode}
        rows = []
        for position, episode in enumerate(self.episodes):
            number = numbers.get(episode.identifier, note_number(episode.identifier))
            next_step = self.hints.get(episode.identifier) or (
                "In feed" if episode.publication_url and not episode.publication_saved else "Check"
            )
            if episode.publication_saved:
                next_step = "Done"
            rows.append(
                (
                    episode.identifier,
                    f"{episode.identifier} · {episode.title}",
                    next_step,
                    (number, -position),
                )
            )
        for item in self.notes:
            if item.episode and item.episode in prepared:
                continue
            rows.append(
                (
                    "note:" + item.note,
                    f"{item.note} · {item.title}",
                    NOTE_NEXT.get(item.state, "Prepare"),
                    (note_number(item.note), 0),
                )
            )
        return sorted(rows, key=lambda row: row[3], reverse=True)

    def reveal(self, identifier):
        if not self.tree.exists(identifier):
            self.query.set("")
            self.filter.set("All")
            self.render()
        if self.tree.exists(identifier):
            self.current = identifier
            self.tree.selection_set(identifier)
            self.tree.focus(identifier)
            self.tree.see(identifier)

    def render(self):
        selected = self.tree.selection() or ((self.current,) if self.current else ())
        self.tree.delete(*self.tree.get_children())
        query = self.query.get().casefold()
        choice = self.filter.get()
        rows = self.rows()
        for iid, label, next_step, _ in rows:
            if query in label.casefold() and matches(next_step, choice):
                self.tree.insert("", "end", iid=iid, values=(label, next_step))
        if selected and self.tree.exists(selected[0]):
            # Restoring the highlight after a refresh is not a person choosing a row:
            # its <<TreeviewSelect>> arrives later and must not re-select an episode.
            self.restoring = selected[0]
            self.tree.selection_set(selected[0])
            self.after_idle(self._restored)
        count = len(self.tree.get_children())
        waiting = sum(matches(row[2], "Needs me") for row in rows)
        if count:
            text = f"{count} of {len(rows)} notes · {waiting} need you"
        elif query or choice != "All":
            text = "Nothing matches. Clear the search or choose All."
        elif not rows:
            text = "No notes yet. Write a note, then choose New episode from a note…"
        else:
            text = ""
        self.count.configure(text=text)

    def _restored(self):
        self.restoring = None

    def _selected(self, _event):
        selection = self.tree.selection()
        if not selection:
            return
        if getattr(self, "restoring", None) == selection[0]:
            return
        self.current = selection[0]
        item = self.note(selection[0])
        if item is not None:
            self.select_note(item)
        else:
            self.select(selection[0])
