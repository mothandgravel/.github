"""Explicit show-recipe selection, creation and update; no persistence in widgets."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from field_notes_studio.presentation.theme import set_text


class RecipeWindow:
    def __init__(self, parent, apply, save, reload, undo):
        self.window = tk.Toplevel(parent)
        self.window.title("Show recipes · current episode only")
        self.window.geometry("760x470")
        self.window.minsize(680, 420)
        self.window.transient(parent)
        self.items = {}
        self.identity = ""
        self.choice = tk.StringVar()
        main = ttk.Frame(self.window, padding=16)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)
        ttk.Label(main, text="Named show recipes", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            main,
            text="Apply changes only to this episode's draft. Other episodes, queued jobs and approvals stay unchanged.",
            style="Muted.TLabel",
            wraplength=620,
        ).grid(row=1, column=0, sticky="w", pady=8)
        toolbar = ttk.Frame(main)
        toolbar.grid(row=2, column=0, sticky="ew")
        self.select = ttk.Combobox(toolbar, textvariable=self.choice, state="readonly", width=28)
        self.select.pack(side="left")
        self.apply = ttk.Button(toolbar, text="Apply to episode", command=apply, state="disabled")
        self.apply.pack(side="left", padx=8)
        ttk.Button(toolbar, text="Reload recipes", command=reload).pack(side="left")
        region = ttk.Frame(main)
        region.grid(row=3, column=0, sticky="nsew", pady=8)
        region.columnconfigure(0, weight=1)
        region.rowconfigure(0, weight=1)
        self.diff = tk.Text(region, wrap="word", height=9, state="disabled", padx=12, pady=10)
        self.diff.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(region, command=self.diff.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.diff.configure(yscrollcommand=scroll.set)
        bottom = ttk.Frame(main)
        bottom.grid(row=4, column=0, sticky="w")
        self.save_new = ttk.Button(
            bottom, text="Save current as…", command=lambda: self.ask_save(save, False)
        )
        self.save_new.pack(side="left")
        self.update = ttk.Button(
            bottom,
            text="Update selected…",
            command=lambda: self.ask_save(save, True),
            state="disabled",
        )
        self.update.pack(side="left", padx=8)
        self.undo = ttk.Button(bottom, text="Undo apply", command=undo, state="disabled")
        self.undo.pack(side="left")
        self.message = ttk.Label(
            main, text="Loading recipes…", style="Muted.TLabel", wraplength=620
        )
        self.message.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        self.select.bind("<<ComboboxSelected>>", lambda _: self.show_difference())
        self.current = {}
        self.episode = None
        self.valid_selection = True
        self.window.bind("<Escape>", lambda _: self.window.destroy())

    def alive(self):
        return bool(self.window.winfo_exists())

    def load(self, data, identity, current, reference):
        self.identity, self.current = identity, current
        self.items = {item["name"]: (key, item) for key, item in data["recipes"].items()}
        self.select.configure(values=tuple(sorted(self.items, key=str.casefold)))
        if self.choice.get() not in self.items:
            self.choice.set(
                reference.get("name", "") if reference.get("name") in self.items else ""
            )
        selected = self.items.get(self.choice.get())
        changed = (
            selected
            and selected[0] == reference.get("id")
            and selected[1]["settings"] != reference.get("settings")
        )
        self.message.configure(
            text="Library recipe changed; this episode keeps its captured version until you Apply explicitly."
            if changed
            else "Choose a recipe to inspect differences. Save creates a local show recipe, not a production job."
        )
        self.show_difference()

    def show_difference(self):
        # Diff formatter is supplied by the coordinator, not an engine import.
        item = self.items.get(self.choice.get())
        self.apply.configure(state="normal" if item and self.valid_selection else "disabled")
        self.update.configure(state="normal" if item and self.valid_selection else "disabled")
        if hasattr(self, "difference"):
            set_text(
                self.diff, self.difference(item[1]["settings"] if item else None, self.current)
            )

    def ask_save(self, save, update):
        item = self.items.get(self.choice.get())
        if update:
            if item and messagebox.askokcancel(
                "Update show recipe",
                "Update this named recipe from the current episode? Other episode drafts and queued jobs will not change.",
                parent=self.window,
            ):
                save(self.choice.get(), item[0])
        else:
            name = simpledialog.askstring(
                "Name this recipe", "Show recipe name:", parent=self.window
            )
            if name is not None:
                save(name, None)
