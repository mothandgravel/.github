"""Searchable episode shelf."""

import tkinter as tk
from tkinter import ttk


class Shelf(ttk.Frame):
    def __init__(self, parent, select):
        super().__init__(parent, padding=(0, 0, 16, 0))
        self.episodes = []
        self.select = select
        ttk.Label(self, text="EPISODES", style="Heading.TLabel").pack(anchor="w", pady=(0, 10))
        self.query = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self.query)
        entry.pack(fill="x", pady=(0, 10))
        self.query.trace_add("write", lambda *_: self.render())
        region = ttk.Frame(self)
        region.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            region, columns=("publication",), show="tree headings", selectmode="browse"
        )
        self.tree.heading("#0", text="Field Note")
        self.tree.heading("publication", text="Link")
        self.tree.column("#0", width=240, minwidth=160)
        self.tree.column("publication", width=60, stretch=False)
        scrollbar = ttk.Scrollbar(region, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._selected)
        ttk.Label(
            self,
            text="Publication links are your records.\nProduction never uploads an episode.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=12)

    def load(self, episodes):
        self.episodes = episodes
        self.render()

    def render(self):
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        query = self.query.get().casefold()
        for episode in self.episodes:
            if query in f"{episode.identifier} {episode.title}".casefold():
                self.tree.insert(
                    "",
                    "end",
                    iid=episode.identifier,
                    text=episode.title,
                    values=("Saved" if episode.publication_url else "—",),
                )
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])

    def _selected(self, _event):
        selection = self.tree.selection()
        if selection:
            self.select(selection[0])
