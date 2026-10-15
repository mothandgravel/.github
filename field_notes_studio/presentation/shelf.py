"""Searchable episode shelf."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.icons import icon


class Shelf(ttk.Frame):
    def __init__(self, parent, select):
        super().__init__(parent, padding=(0, 0, 16, 0))
        self.episodes = []
        self.current = None
        self.select = select
        ttk.Label(self, text="EPISODES", style="Heading.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(
            self,
            text="Search by title or note number",
            image=icon(self, "search"),
            compound="left",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 4))
        self.query = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self.query)
        entry.pack(fill="x", pady=(0, 10))
        entry.bind("<Escape>", lambda _: self.query.set(""))
        self.query.trace_add("write", lambda *_: self.render())
        region = ttk.Frame(self)
        region.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            region, columns=("publication",), show="tree headings", selectmode="browse"
        )
        self.tree.heading("#0", text="Field Note")
        self.tree.heading("publication", text="Link")
        self.tree.heading("#0", anchor="w")
        self.tree.column("#0", width=240, minwidth=160)
        self.tree.column("publication", width=60, stretch=False)
        scrollbar = ttk.Scrollbar(region, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._selected)
        self.count = ttk.Label(self, text="Loading episodes…", style="Muted.TLabel")
        self.count.pack(anchor="w", pady=(8, 0))
        ttk.Label(
            self,
            text="Catalog links fill automatically.\nSaved records take precedence.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 0))

    def load(self, episodes):
        self.episodes = episodes
        self.render()

    def reveal(self, identifier):
        if not self.tree.exists(identifier):
            self.query.set("")
        if self.tree.exists(identifier):
            self.current = identifier
            self.tree.selection_set(identifier)
            self.tree.focus(identifier)
            self.tree.see(identifier)

    def render(self):
        selected = self.tree.selection() or ((self.current,) if self.current else ())
        self.tree.delete(*self.tree.get_children())
        query = self.query.get().casefold()
        for episode in self.episodes:
            if query in f"{episode.identifier} {episode.title}".casefold():
                self.tree.insert(
                    "",
                    "end",
                    iid=episode.identifier,
                    text=episode.title,
                    values=(
                        ("Saved" if episode.publication_saved else "Feed")
                        if episode.publication_url
                        else "—",
                    ),
                )
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])
        count = len(self.tree.get_children())
        self.count.configure(
            text=(
                f"{count} of {len(self.episodes)} episodes"
                if count
                else "No matches. Try another title or note number."
                if query
                else "No prepared episodes yet."
            ),
            wraplength=260,
        )

    def _selected(self, _event):
        selection = self.tree.selection()
        if selection:
            self.current = selection[0]
            self.select(selection[0])
