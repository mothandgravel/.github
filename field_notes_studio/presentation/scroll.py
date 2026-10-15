"""Scrollable form content with keyboard focus reveal and a fixed parent footer."""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation.theme import PAPER


class ScrollArea(ttk.Frame):
    def __init__(self, parent, padding=16):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, height=180, highlightthickness=0, background=PAPER)
        scrollbar = ttk.Scrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.content = ttk.Frame(self.canvas, padding=padding)
        window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind(
            "<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))

    def bind_navigation(self, widget=None):
        widget = self.content if widget is None else widget
        widget.bind(
            "<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        )
        widget.bind("<Button-4>", lambda _: self.canvas.yview_scroll(-1, "units"))
        widget.bind("<Button-5>", lambda _: self.canvas.yview_scroll(1, "units"))
        widget.bind("<FocusIn>", lambda _: self.reveal(widget))
        for child in widget.winfo_children():
            self.bind_navigation(child)

    def reveal(self, widget):
        if not str(widget).startswith(str(self.canvas) + "."):
            return
        top = widget.winfo_rooty() - self.canvas.winfo_rooty() + self.canvas.canvasy(0)
        bottom = top + widget.winfo_height()
        visible = self.canvas.canvasy(0)
        height = self.canvas.winfo_height()
        region = self.canvas.bbox("all")
        if region and region[3] > height:
            if top < visible:
                self.canvas.yview_moveto(top / region[3])
            elif bottom > visible + height:
                self.canvas.yview_moveto((bottom - height) / region[3])
