"""Moth & Gravel desktop palette and widget styles."""

from tkinter import ttk

PAPER = "#f1eee7"
SURFACE = "#fffdf8"
INK = "#242827"
MUTED = "#626760"
BRASS = "#82632e"
DARK = "#202724"
LINE = "#d4cec1"
SUCCESS = "#2e604c"
WARNING = "#865b23"


def apply(root) -> None:
    root.configure(bg=PAPER)
    root.option_add("*Text.font", "{DejaVu Sans} 10")
    root.option_add("*Text.background", SURFACE)
    root.option_add("*Text.foreground", INK)
    root.option_add("*Text.selectBackground", BRASS)
    root.option_add("*Text.selectForeground", SURFACE)
    root.option_add("*Text.highlightThickness", 1)
    root.option_add("*Text.highlightBackground", LINE)
    root.option_add("*Text.highlightColor", BRASS)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=("DejaVu Sans", 10))
    style.configure("TFrame", background=PAPER)
    style.configure("TLabel", background=PAPER, foreground=INK)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Title.TLabel", font=("DejaVu Serif", 23), foreground=INK)
    style.configure("Brand.TLabel", font=("DejaVu Sans", 10, "bold"), foreground=BRASS)
    style.configure("Studio.TLabel", font=("DejaVu Serif", 17), foreground=INK)
    style.configure("Heading.TLabel", font=("DejaVu Sans", 11, "bold"))
    style.configure("Success.TLabel", foreground=SUCCESS)
    style.configure("Draft.TLabel", foreground=WARNING)
    style.configure(
        "TButton",
        padding=(12, 7),
        background=SURFACE,
        foreground=INK,
        bordercolor=LINE,
        lightcolor=SURFACE,
        darkcolor=SURFACE,
        relief="flat",
        focuscolor=BRASS,
        focusthickness=2,
        anchor="center",
        width=-1,
    )
    style.map(
        "TButton",
        background=[("disabled", PAPER), ("pressed", "#ded7c9"), ("active", "#e7e1d5")],
        foreground=[("disabled", "#93958c")],
        bordercolor=[("focus", BRASS)],
    )
    style.configure("Compact.TButton", padding=(8, 6))
    style.configure(
        "Accent.TButton",
        background=BRASS,
        foreground=SURFACE,
        lightcolor=BRASS,
        darkcolor=BRASS,
        bordercolor=BRASS,
    )
    style.map(
        "Accent.TButton",
        background=[("disabled", "#e2ded4"), ("pressed", "#584422"), ("active", "#685025")],
        foreground=[("disabled", MUTED), ("!disabled", SURFACE)],
    )
    style.configure("Success.TButton", foreground=SUCCESS, background="#e4eee6")
    style.configure("TEntry", fieldbackground=SURFACE, bordercolor=LINE, padding=6)
    style.map("TEntry", bordercolor=[("focus", BRASS)])
    style.configure(
        "TCombobox",
        fieldbackground=SURFACE,
        background=SURFACE,
        bordercolor=LINE,
        padding=5,
        arrowsize=12,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", SURFACE), ("disabled", PAPER)],
        bordercolor=[("focus", BRASS)],
        selectbackground=[("readonly", SURFACE)],
        selectforeground=[("readonly", INK)],
    )
    style.configure(
        "TCheckbutton", background=PAPER, foreground=INK, padding=(0, 2), focuscolor=BRASS
    )
    style.configure("TNotebook", background=PAPER, bordercolor=LINE, tabmargins=(0, 0, 0, 0))
    style.configure(
        "TNotebook.Tab",
        padding=(12, 7),
        background=PAPER,
        foreground=MUTED,
        bordercolor=LINE,
        lightcolor=PAPER,
        darkcolor=PAPER,
        focuscolor=BRASS,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", DARK), ("active", "#e7e1d5")],
        foreground=[("selected", SURFACE), ("active", INK)],
        lightcolor=[("selected", DARK)],
        darkcolor=[("selected", DARK)],
    )
    style.configure("TSeparator", background=LINE)
    style.configure(
        "TScrollbar",
        background=LINE,
        troughcolor=PAPER,
        bordercolor=PAPER,
        lightcolor=LINE,
        darkcolor=LINE,
        arrowsize=10,
        gripcount=0,
    )
    style.configure(
        "Treeview",
        background=SURFACE,
        fieldbackground=SURFACE,
        foreground=INK,
        rowheight=34,
        bordercolor=LINE,
        lightcolor=SURFACE,
        darkcolor=SURFACE,
    )
    style.map("Treeview", background=[("selected", DARK)], foreground=[("selected", SURFACE)])
    style.configure(
        "Treeview.Heading",
        background=PAPER,
        foreground=MUTED,
        padding=7,
        relief="flat",
        bordercolor=LINE,
    )


def set_text(widget, text: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")
