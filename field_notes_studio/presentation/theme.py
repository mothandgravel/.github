"""Moth & Gravel desktop palettes and widget styles.

Two named palettes share one set of roles. Paper (light) is the studio's identity;
Night follows the website's dark tokens. Colours are read from this module when a
widget is styled, so callers use ``theme.INK`` rather than importing a value once.
"""

import tkinter as tk
from tkinter import ttk

LIGHT = {
    "PAPER": "#f1eee7",
    "SURFACE": "#fffdf8",
    "INK": "#242827",
    "MUTED": "#626760",
    "BRASS": "#82632e",
    "DARK": "#202724",
    "LINE": "#d4cec1",
    "EDGE": "#b9b2a3",
    "SUCCESS": "#2e604c",
    "WARNING": "#865b23",
    "HOVER": "#e7e1d5",
    "PRESSED": "#ded7c9",
    "DISABLED": "#8a8c83",
    "ACCENT_FG": "#fffdf8",
    "ACCENT_ACTIVE": "#685025",
    "ACCENT_PRESSED": "#584422",
    "ACCENT_DISABLED": "#e2ded4",
    "SELECTED_FG": "#fffdf8",
    "ROW_SELECTED": "#202724",
    "ROW_SELECTED_FG": "#fffdf8",
    "ATTENTION": "#f4e8d5",
    "SUCCESS_BG": "#e4eee6",
}
NIGHT = {
    "PAPER": "#17191b",
    "SURFACE": "#202324",
    "INK": "#f1eee6",
    "MUTED": "#b5b3aa",
    "BRASS": "#d4b37c",
    "DARK": "#e7c89a",
    "LINE": "#3d4241",
    "EDGE": "#5a605e",
    "SUCCESS": "#8cc5a8",
    "WARNING": "#e3b06a",
    "HOVER": "#2a2e2f",
    "PRESSED": "#33383a",
    "DISABLED": "#83867f",
    "ACCENT_FG": "#17191b",
    "ACCENT_ACTIVE": "#e7c89a",
    "ACCENT_PRESSED": "#b8955b",
    "ACCENT_DISABLED": "#2a2e2f",
    "SELECTED_FG": "#17191b",
    "ROW_SELECTED": "#3a3f40",
    "ROW_SELECTED_FG": "#f1eee6",
    "ATTENTION": "#2c261c",
    "SUCCESS_BG": "#1f2b25",
}
PALETTES = {"light": LIGHT, "night": NIGHT}

NAME = "light"
PAPER = SURFACE = INK = MUTED = BRASS = DARK = LINE = EDGE = SUCCESS = WARNING = ""
HOVER = PRESSED = DISABLED = ACCENT_FG = ACCENT_ACTIVE = ACCENT_PRESSED = ""
ACCENT_DISABLED = SELECTED_FG = ROW_SELECTED = ROW_SELECTED_FG = ATTENTION = SUCCESS_BG = ""


def use(name: str) -> None:
    """Make a named palette current for every later colour lookup."""
    global NAME
    NAME = name if name in PALETTES else "light"
    globals().update(PALETTES[NAME])


use("light")


def color(role: str) -> str:
    """A palette role such as ``"INK"``, or a literal ``#rrggbb`` colour."""
    return role if role.startswith("#") else PALETTES[NAME][role]


def px(widget, value: int) -> int:
    """Pixels at the desktop's scale; ttk sizes given in pixels do not follow fonts."""
    return round(value * float(widget.tk.call("tk", "scaling")) / (96 / 72))


def apply(root, name: str | None = None) -> None:
    if name is not None:
        use(name)
    root.configure(bg=PAPER)
    root.option_add("*Text.font", "{DejaVu Sans} 10")
    root.option_add("*Text.background", SURFACE)
    root.option_add("*Text.foreground", INK)
    root.option_add("*Text.insertBackground", INK)
    root.option_add("*Text.selectBackground", BRASS)
    root.option_add("*Text.selectForeground", ACCENT_FG)
    root.option_add("*Text.highlightThickness", 1)
    root.option_add("*Text.highlightBackground", LINE)
    root.option_add("*Text.highlightColor", BRASS)
    root.option_add("*Toplevel.background", PAPER)
    for widget_class in ("Menu", "TCombobox*Listbox"):
        root.option_add(f"*{widget_class}.background", SURFACE)
        root.option_add(f"*{widget_class}.foreground", INK)
        root.option_add(f"*{widget_class}.selectBackground", ROW_SELECTED)
        root.option_add(f"*{widget_class}.selectForeground", ROW_SELECTED_FG)
    root.option_add("*Menu.activeBackground", HOVER)
    root.option_add("*Menu.activeForeground", INK)
    root.option_add("*Menu.selectColor", BRASS)
    root.option_add("*Menu.disabledForeground", DISABLED)
    root.option_add("*Menu.relief", "raised")
    root.option_add("*Menu.borderWidth", 1)
    root.option_add("*Menu.activeBorderWidth", 0)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        ".",
        font=("DejaVu Sans", 10),
        background=PAPER,
        foreground=INK,
        troughcolor=PAPER,
        selectbackground=ROW_SELECTED,
        selectforeground=ROW_SELECTED_FG,
        fieldbackground=SURFACE,
        insertcolor=INK,
        bordercolor=LINE,
        lightcolor=PAPER,
        darkcolor=PAPER,
    )
    style.map(".", foreground=[("disabled", DISABLED)])
    style.configure("TFrame", background=PAPER)
    style.configure("TLabel", background=PAPER, foreground=INK)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Small.TLabel", foreground=MUTED, font=("DejaVu Sans", 9))
    style.configure("Title.TLabel", font=("DejaVu Serif", 23), foreground=INK)
    style.configure("Brand.TLabel", font=("DejaVu Sans", 10, "bold"), foreground=BRASS)
    style.configure("Studio.TLabel", font=("DejaVu Serif", 17), foreground=INK)
    style.configure("Heading.TLabel", font=("DejaVu Sans", 11, "bold"))
    style.configure("Legend.TLabel", font=("DejaVu Sans", 10, "bold"), foreground=INK)
    style.configure("Success.TLabel", foreground=SUCCESS)
    style.configure("Draft.TLabel", foreground=WARNING)
    style.configure("Mono.TLabel", font=("DejaVu Sans Mono", 9), foreground=MUTED)
    style.configure("Step.TLabel", foreground=MUTED, font=("DejaVu Sans", 10))
    style.configure("StepOn.TLabel", foreground=INK, font=("DejaVu Sans", 10, "bold"))
    # Cards and groups take their contrast from a drawn edge, never a flat fill alone.
    style.configure(
        "Card.TFrame", background=SURFACE, bordercolor=EDGE, relief="solid", borderwidth=1
    )
    style.configure("CardRow.TFrame", background=SURFACE, borderwidth=0, relief="flat")
    style.configure(
        "Attention.TFrame", background=ATTENTION, bordercolor=WARNING, relief="solid", borderwidth=1
    )
    for prefix, background in (("Card", SURFACE), ("Attention", ATTENTION)):
        style.configure(f"{prefix}.TLabel", background=background, foreground=INK)
        style.configure(f"{prefix}Muted.TLabel", background=background, foreground=MUTED)
        style.configure(
            f"{prefix}Small.TLabel",
            background=background,
            foreground=MUTED,
            font=("DejaVu Sans", 9),
        )
        style.configure(
            f"{prefix}Heading.TLabel",
            background=background,
            foreground=INK,
            font=("DejaVu Sans", 11, "bold"),
        )
        style.configure(f"{prefix}Ok.TLabel", background=background, foreground=SUCCESS)
        style.configure(f"{prefix}Warn.TLabel", background=background, foreground=WARNING)
        style.configure(
            f"{prefix}Now.TLabel",
            background=background,
            foreground=INK,
            font=("DejaVu Sans", 10, "bold"),
        )
    style.configure("CardBig.TLabel", background=SURFACE, foreground=INK, font=("DejaVu Serif", 15))
    style.configure(
        "CardBrass.TLabel", background=SURFACE, foreground=BRASS, font=("DejaVu Sans", 9, "bold")
    )
    style.configure("Brass.TLabel", foreground=BRASS, font=("DejaVu Sans", 9, "bold"))
    # Timeline states: the same size as their row text, brass for working and "you".
    style.configure(
        "CardState.TLabel", background=SURFACE, foreground=BRASS, font=("DejaVu Sans", 10, "bold")
    )
    style.configure(
        "CardMono.TLabel", background=SURFACE, foreground=MUTED, font=("DejaVu Sans Mono", 9)
    )
    style.configure(
        "TButton",
        padding=(12, 7),
        background=SURFACE,
        foreground=INK,
        bordercolor=EDGE,
        lightcolor=SURFACE,
        darkcolor=SURFACE,
        relief="raised",
        focuscolor=BRASS,
        focusthickness=2,
        anchor="center",
        width=-1,
    )
    style.map(
        "TButton",
        background=[("disabled", PAPER), ("pressed", PRESSED), ("active", HOVER)],
        lightcolor=[("disabled", PAPER), ("pressed", PRESSED), ("active", HOVER)],
        darkcolor=[("disabled", PAPER), ("pressed", PRESSED), ("active", HOVER)],
        foreground=[("disabled", DISABLED)],
        bordercolor=[("focus", BRASS)],
    )
    style.configure("Compact.TButton", padding=(8, 5))
    style.configure("Small.TButton", padding=(6, 3), font=("DejaVu Sans", 9))
    style.configure(
        "Accent.TButton",
        background=BRASS,
        foreground=ACCENT_FG,
        lightcolor=BRASS,
        darkcolor=BRASS,
        bordercolor=BRASS,
        focuscolor=ACCENT_FG,
    )
    accent = [
        ("disabled", ACCENT_DISABLED),
        ("pressed", ACCENT_PRESSED),
        ("active", ACCENT_ACTIVE),
    ]
    style.map(
        "Accent.TButton",
        background=accent,
        lightcolor=accent,
        darkcolor=accent,
        bordercolor=[("disabled", LINE), ("focus", ACCENT_PRESSED)],
        foreground=[("disabled", MUTED), ("!disabled", ACCENT_FG)],
    )
    style.configure(
        "Success.TButton",
        foreground=SUCCESS,
        background=SUCCESS_BG,
        lightcolor=SUCCESS_BG,
        darkcolor=SUCCESS_BG,
    )
    # Tools sit below the stage tabs; the open tool is marked by a brass edge.
    style.configure("Tool.TButton", padding=(8, 5))
    style.configure("ToolOn.TButton", padding=(8, 5), bordercolor=BRASS)
    style.map("ToolOn.TButton", bordercolor=[("focus", BRASS), ("!focus", BRASS)])
    style.configure("Placeholder.TLabel", background=SURFACE, foreground=MUTED)
    style.configure(
        "Tooltip.TLabel",
        background=SURFACE,
        foreground=INK,
        bordercolor=EDGE,
        relief="solid",
        borderwidth=1,
        font=("DejaVu Sans", 9),
    )
    # A segmented filter: the chosen segment is raised by an edge, not a flat fill alone.
    style.layout("Filter.TRadiobutton", style.layout("Toolbutton"))
    style.configure(
        "Filter.TRadiobutton",
        padding=(7, 3),
        background=PAPER,
        foreground=MUTED,
        bordercolor=PAPER,
        lightcolor=PAPER,
        darkcolor=PAPER,
        relief="solid",
        borderwidth=1,
        focuscolor=BRASS,
        font=("DejaVu Sans", 9),
    )
    style.map(
        "Filter.TRadiobutton",
        background=[("selected", SURFACE), ("active", HOVER)],
        lightcolor=[("selected", SURFACE), ("active", HOVER)],
        darkcolor=[("selected", SURFACE), ("active", HOVER)],
        foreground=[("selected", INK), ("active", INK)],
        bordercolor=[("selected", EDGE), ("focus", BRASS)],
    )
    style.configure(
        "TMenubutton",
        padding=(10, 6),
        width=-1,
        background=SURFACE,
        foreground=INK,
        bordercolor=EDGE,
        lightcolor=SURFACE,
        darkcolor=SURFACE,
        arrowcolor=INK,
        relief="raised",
    )
    style.map(
        "TMenubutton",
        background=[("pressed", PRESSED), ("active", HOVER)],
        lightcolor=[("pressed", PRESSED), ("active", HOVER)],
        darkcolor=[("pressed", PRESSED), ("active", HOVER)],
        bordercolor=[("focus", BRASS)],
    )
    style.configure(
        "TEntry",
        fieldbackground=SURFACE,
        foreground=INK,
        bordercolor=LINE,
        lightcolor=SURFACE,
        darkcolor=SURFACE,
        insertcolor=INK,
        padding=6,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", BRASS)],
        fieldbackground=[("readonly", PAPER), ("disabled", PAPER)],
    )
    style.configure(
        "TCombobox",
        fieldbackground=SURFACE,
        background=SURFACE,
        foreground=INK,
        bordercolor=LINE,
        lightcolor=SURFACE,
        darkcolor=SURFACE,
        arrowcolor=INK,
        insertcolor=INK,
        padding=5,
        arrowsize=12,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", SURFACE), ("disabled", PAPER)],
        bordercolor=[("focus", BRASS)],
        selectbackground=[("readonly", SURFACE)],
        selectforeground=[("readonly", INK)],
        arrowcolor=[("disabled", DISABLED)],
    )
    for name, background in (("TCheckbutton", PAPER), ("Card.TCheckbutton", SURFACE)):
        style.configure(name, background=background, foreground=INK, padding=(0, 3))
        style.configure(name, focuscolor=BRASS, focusthickness=1)
        style.map(name, background=[("active", background)], foreground=[("disabled", DISABLED)])
    style.configure(
        "TNotebook",
        background=PAPER,
        bordercolor=LINE,
        lightcolor=PAPER,
        darkcolor=PAPER,
        tabmargins=(0, 0, 0, 0),
    )
    for name, padding in (("TNotebook.Tab", (12, 7)), ("Workspace.TNotebook.Tab", (14, 7))):
        style.configure(
            name,
            padding=padding,
            background=PAPER,
            foreground=MUTED,
            bordercolor=LINE,
            lightcolor=PAPER,
            darkcolor=PAPER,
            focuscolor=BRASS,
        )
        # clam pads and expands the selected tab, so its label baseline jumped about
        # 5 px. Every tab keeps one size; the selected one is marked by fill and ink.
        style.map(
            name,
            padding=[("selected", padding)],
            expand=[("selected", (0, 0, 0, 0))],
            background=[("selected", DARK), ("active", HOVER)],
            foreground=[("selected", SELECTED_FG), ("active", INK)],
            lightcolor=[("selected", DARK)],
            darkcolor=[("selected", DARK)],
            bordercolor=[("selected", DARK)],
        )
    style.configure("TSeparator", background=LINE)
    style.configure("TPanedwindow", background=PAPER)
    style.configure("Sash", background=PAPER, lightcolor=LINE, darkcolor=LINE, bordercolor=PAPER)
    style.configure(
        "TScrollbar",
        background=LINE,
        troughcolor=PAPER,
        bordercolor=PAPER,
        lightcolor=LINE,
        darkcolor=LINE,
        arrowcolor=INK,
        arrowsize=10,
        gripcount=0,
    )
    style.map("TScrollbar", background=[("active", EDGE)])
    style.configure(
        "Treeview",
        background=SURFACE,
        fieldbackground=SURFACE,
        foreground=INK,
        rowheight=px(root, 34),
        bordercolor=LINE,
        lightcolor=SURFACE,
        darkcolor=SURFACE,
    )
    style.map(
        "Treeview",
        background=[("selected", ROW_SELECTED)],
        foreground=[("selected", ROW_SELECTED_FG)],
    )
    style.configure(
        "Treeview.Heading",
        background=PAPER,
        foreground=MUTED,
        padding=7,
        relief="flat",
        bordercolor=LINE,
        lightcolor=PAPER,
        darkcolor=PAPER,
    )
    style.map("Treeview.Heading", background=[("active", HOVER)])
    _checkbox(root, style)
    from field_notes_studio.presentation import icons

    icons.retheme(root)


def _checkbox(root, style) -> None:
    """Draw every checkbox from the studio's own indicator images.

    clam draws a cross for "selected" and a filled blue square for the tristate
    ("alternate") look of an unbound box, which readers took as already ticked.
    These images have exactly one unticked and one ticked appearance.
    """
    from field_notes_studio.presentation.icons import indicator

    if "Studio.Checkbutton.indicator" not in style.element_names():
        style.element_create(
            "Studio.Checkbutton.indicator",
            "image",
            indicator(root, "off"),
            ("disabled", "selected", indicator(root, "on-disabled")),
            ("disabled", indicator(root, "off-disabled")),
            ("selected", indicator(root, "on")),
            ("active", indicator(root, "off-active")),
            width=indicator(root, "off").width() + 8,
            sticky="w",
        )
    style.layout(
        "TCheckbutton",
        [
            (
                "Checkbutton.padding",
                {
                    "sticky": "nswe",
                    "children": [
                        ("Studio.Checkbutton.indicator", {"side": "left", "sticky": ""}),
                        (
                            "Checkbutton.focus",
                            {
                                "side": "left",
                                "sticky": "w",
                                "children": [("Checkbutton.label", {"sticky": "nswe"})],
                            },
                        ),
                    ],
                },
            )
        ],
    )


def retheme(widget) -> None:
    """Recolour classic Tk widgets, which do not follow ttk styles, recursively.

    A Text may carry ``studio_colors = (background_role, foreground_role)``.
    Any widget may define ``retheme()`` for colours it sets itself.
    """
    if isinstance(widget, tk.Text):
        background, foreground = getattr(widget, "studio_colors", ("SURFACE", "INK"))
        widget.configure(
            background=color(background),
            foreground=color(foreground),
            insertbackground=INK,
            selectbackground=BRASS,
            selectforeground=ACCENT_FG,
            highlightbackground=LINE,
            highlightcolor=BRASS,
        )
    elif isinstance(widget, tk.Canvas):
        widget.configure(background=color(getattr(widget, "studio_background", "PAPER")))
    elif isinstance(widget, tk.Menu):
        widget.configure(
            background=SURFACE,
            foreground=INK,
            activebackground=HOVER,
            activeforeground=INK,
            selectcolor=BRASS,
            disabledforeground=DISABLED,
        )
    elif isinstance(widget, tk.Toplevel | tk.Tk):
        widget.configure(background=PAPER)
    hook = getattr(widget, "retheme", None)
    if callable(hook):
        hook()
    for child in widget.winfo_children():
        retheme(child)


def set_text(widget, text: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")
