"""Moth & Gravel desktop palette and widget styles."""

from tkinter import ttk

PAPER = "#eee9df"
SURFACE = "#faf7f0"
INK = "#242827"
MUTED = "#626760"
BRASS = "#82632e"
DARK = "#202724"


def apply(root) -> None:
    root.configure(bg=PAPER)
    root.option_add("*Text.font", "{DejaVu Sans} 10")
    root.option_add("*Text.background", SURFACE)
    root.option_add("*Text.foreground", INK)
    root.option_add("*Text.selectBackground", BRASS)
    root.option_add("*Text.selectForeground", SURFACE)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=("DejaVu Sans", 10))
    style.configure("TFrame", background=PAPER)
    style.configure("TLabel", background=PAPER, foreground=INK)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Title.TLabel", font=("DejaVu Serif", 23), foreground=INK)
    style.configure("Heading.TLabel", font=("DejaVu Sans", 11, "bold"))
    style.configure("TButton", padding=(12, 7), background=SURFACE, foreground=INK)
    style.configure("Accent.TButton", background=BRASS, foreground=SURFACE)
    style.map("Accent.TButton", background=[("active", "#685025")])
    style.configure(
        "Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=INK, rowheight=32
    )
    style.map("Treeview", background=[("selected", DARK)], foreground=[("selected", SURFACE)])
    style.configure("Treeview.Heading", background=PAPER, foreground=MUTED, padding=7)


def set_text(widget, text: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")
