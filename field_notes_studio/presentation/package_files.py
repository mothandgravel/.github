"""Inspect checked upload assets and hand their paths to an external file picker."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton


def size_text(value):
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1000 or unit == "GB":
            return f"{value:,.1f} {unit}" if unit != "B" else f"{value} B"
        value /= 1000


class PackageFiles(ttk.Frame):
    def __init__(self, parent, callbacks):
        super().__init__(parent, padding=10)
        self.snapshot = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.summary = ttk.Label(
            self,
            text="Check the saved upload package to see its files.",
            wraplength=540,
            style="Muted.TLabel",
        )
        self.summary.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.tree = ttk.Treeview(
            self,
            columns=("purpose", "name", "size"),
            show="headings",
            selectmode="browse",
            height=3,
        )
        for name, title, width in (
            ("purpose", "Use", 170),
            ("name", "File", 200),
            ("size", "Size", 85),
        ):
            self.tree.heading(name, text=title, anchor="w")
            self.tree.column(name, width=width, minwidth=60, stretch=name != "size")
        self.tree.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self, command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _: self.selected())
        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=6)
        self.open = ActionButton(
            actions,
            pictogram="folder",
            text="Open file",
            command=callbacks["package_open"],
            state="disabled",
            style="Compact.TButton",
        )
        self.open.pack(side="left")
        self.copy = ActionButton(
            actions,
            pictogram="copy",
            text="Copy upload path",
            command=callbacks["package_copy"],
            state="disabled",
            style="Compact.TButton",
            width=19,
        )
        self.copy.pack(side="left", padx=6)
        self.folder = ActionButton(
            actions,
            pictogram="folder",
            text="Open folder",
            command=lambda: callbacks["open"]("uploads"),
            state="disabled",
            style="Compact.TButton",
        )
        self.folder.pack(side="left")
        self.refresh = ActionButton(
            actions,
            pictogram="refresh",
            text="Check files",
            command=callbacks["package_refresh"],
            style="Compact.TButton",
        )
        self.refresh.pack(side="right")
        self.path = tk.StringVar()
        ttk.Entry(self, textvariable=self.path, state="readonly").grid(
            row=3, column=0, columnspan=2, sticky="ew"
        )
        self.bind(
            "<Configure>", lambda e: self.summary.configure(wraplength=max(200, e.width - 24))
        )

    def selection(self):
        selected = self.tree.selection()
        return selected[0] if selected else None

    def selected(self):
        name = self.selection()
        asset = (
            next((asset for asset in self.snapshot.files if asset.name == name), None)
            if self.snapshot
            else None
        )
        self.path.set(asset.path if asset else "")
        self.copy.reset_feedback()
        self.folder.configure(
            state="normal" if self.snapshot and self.snapshot.identity else "disabled"
        )
        for button in (self.open, self.copy):
            button.configure(state="normal" if asset else "disabled")

    def clear(self, message="Check the saved upload package to see its files.", *, loading=False):
        self.snapshot = None
        self.tree.delete(*self.tree.get_children())
        self.summary.configure(text=message, style="Muted.TLabel")
        self.selected()
        self.refresh.configure(
            text="Checking…" if loading else "Check files",
            state="disabled" if loading else "normal",
        )

    def load(self, snapshot):
        previous = (
            self.selection()
            if self.snapshot and self.snapshot.episode == snapshot.episode
            else None
        )
        self.clear(snapshot.summary)
        self.snapshot = snapshot
        self.summary.configure(
            style="Success.TLabel"
            if snapshot.status == "ready"
            else "Muted.TLabel"
            if snapshot.status == "missing"
            else "Draft.TLabel"
        )
        for asset in snapshot.files:
            self.tree.insert(
                "", "end", iid=asset.name, values=(asset.purpose, asset.name, size_text(asset.size))
            )
        if snapshot.files:
            self.tree.selection_set(
                previous
                if previous is not None and self.tree.exists(previous)
                else snapshot.files[0].name
            )
        self.selected()

    def copied(self, path):
        self.clipboard_clear()
        self.clipboard_append(path)
        self.path.set(path)
        self.copy.complete("Path copied")
