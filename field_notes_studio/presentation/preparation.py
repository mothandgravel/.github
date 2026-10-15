"""Written-note discovery and read-only narration inspection; no engine or file access."""

import tkinter as tk
from tkinter import ttk


class PreparationWindow:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("Moth & Gravel · Prepare new notes")
        self.window.geometry("1050x760")
        self.window.minsize(760, 580)
        self.window.transient(parent)
        self.items = {}
        self.snapshot = None
        self.loading = False
        main = ttk.Frame(self.window, padding=18)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)
        main.rowconfigure(4, weight=2)
        ttk.Label(main, text="Prepare new notes", style="Studio.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            main,
            text="Written note → reviewed script → narration → captions → production",
            style="Muted.TLabel",
            wraplength=700,
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))
        table = ttk.Frame(main)
        table.grid(row=2, column=0, sticky="nsew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            table,
            columns=("note", "title", "state"),
            show="headings",
            selectmode="browse",
            height=7,
        )
        for name, heading, width in (
            ("note", "Note", 70),
            ("title", "Written edition", 450),
            ("state", "Local preparation", 200),
        ):
            self.tree.heading(name, text=heading)
            self.tree.column(name, width=width, minwidth=60, stretch=name == "title")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        actions = ttk.Frame(main)
        actions.grid(row=3, column=0, sticky="ew", pady=10)
        self.refresh_button = ttk.Button(actions, text="Refresh written notes")
        self.refresh_button.pack(side="left")
        self.inspect_button = ttk.Button(
            actions, text="Inspect script · no service request", state="disabled"
        )
        self.inspect_button.pack(side="left", padx=(8, 0))
        tabs = ttk.Notebook(main)
        tabs.grid(row=4, column=0, sticky="nsew")
        self.plan = self._text(tabs, "Preparation / next steps")
        self.script = self._text(tabs, "Saved narration script")
        self.message = ttk.Label(main, style="Muted.TLabel", wraplength=700)
        self.message.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        self.window.bind("<Configure>", self._resize, add=True)
        self.clear("Loading written notes…")

    @staticmethod
    def _text(tabs, title):
        frame = ttk.Frame(tabs)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = tk.Text(frame, wrap="word", height=9, padx=12, pady=10, state="disabled")
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
            self.message.configure(wraplength=max(400, event.width - 50))

    def connect(self, refresh, selected, inspect, close):
        self.refresh_button.configure(command=refresh)
        self.inspect_button.configure(command=inspect)
        self.tree.bind("<<TreeviewSelect>>", lambda _: selected())
        self.window.protocol("WM_DELETE_WINDOW", close)
        self.window.bind("<Escape>", lambda _: close())

    def selected(self):
        selected = self.tree.selection()
        return selected[0] if selected else ""

    def clear(self, message=""):
        self.snapshot = None
        item = self.items.get(self.selected())
        detail = (
            item.detail
            if item
            else "Select a written note, then inspect its saved narration script."
        )
        self._put(self.plan, detail)
        self._put(self.script, "")
        self.message.configure(text=message or detail)
        self.busy(self.loading)

    def busy(self, value):
        self.loading = value
        self.refresh_button.configure(state="disabled" if value else "normal")
        item = self.items.get(self.selected())
        eligible = item is not None and item.state not in {"Needs script", "Needs repair"}
        self.inspect_button.configure(state="normal" if eligible and not value else "disabled")

    def show_catalog(self, items):
        selected = self.selected()
        self.tree.delete(*self.tree.get_children())
        self.items = {item.note: item for item in items}
        for item in items:
            self.tree.insert("", "end", iid=item.note, values=(item.note, item.title, item.state))
        if selected in self.items:
            self.tree.selection_set(selected)
            self.tree.see(selected)
        self.clear(
            f"{len(items)} written notes. Catalog presence is not verified media or platform publication."
        )

    def show_snapshot(self, snapshot):
        if snapshot.note != self.selected():
            return
        self.snapshot = snapshot
        self._put(self.plan, snapshot.summary)
        self._put(self.script, snapshot.script)
        self.message.configure(
            text="Offline inspection complete. No narration or caption request was made; generation is not enabled here yet."
        )

    def schedule(self, delay, callback):
        return self.window.after(delay, callback)

    def unschedule(self, handle):
        self.window.after_cancel(handle)

    def close(self):
        self.window.destroy()
