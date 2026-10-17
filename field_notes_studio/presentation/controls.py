"""Labelled icon buttons with local, interruptible completion feedback, and groups."""

from tkinter import ttk

from field_notes_studio.presentation.icons import icon


class ActionButton(ttk.Button):
    def __init__(self, parent, *, pictogram, **options):
        super().__init__(parent, compound="left", **options)
        self.feedback_handle = None
        self.default_text = options.get("text", "")
        self.default_style = options.get("style", "TButton")
        self.pictogram = pictogram
        self.reset_feedback()
        self.bind("<Destroy>", self._destroyed, add=True)

    def set_icon(self, name):
        self.pictogram_now = name
        accent = self.cget("style") == "Accent.TButton"
        self.configure(
            image=(
                icon(self, name, "ACCENT_FG" if accent else "INK"),
                "disabled",
                icon(self, name, "MUTED" if accent else "DISABLED"),
            )
        )

    def set_style(self, style):
        """Change emphasis (for example to or from the brass primary) and its glyph colour."""
        self.default_style = style
        self.configure(style=style)
        self.set_icon(getattr(self, "pictogram_now", self.pictogram))

    def reset_feedback(self, text=None):
        if self.feedback_handle is not None:
            self.after_cancel(self.feedback_handle)
            self.feedback_handle = None
        if text is not None:
            self.default_text = text
        self.configure(text=self.default_text, style=self.default_style)
        self.set_icon(self.pictogram)

    def complete(self, text="Copied"):
        self.reset_feedback()
        self.configure(text=text, style="Success.TButton")
        self.configure(image=icon(self, "check", "SUCCESS"))
        self.feedback_handle = self.after(1800, self.reset_feedback)

    def _destroyed(self, event):
        if event.widget is self and self.feedback_handle is not None:
            self.after_cancel(self.feedback_handle)
            self.feedback_handle = None


class Fieldset(ttk.Frame):
    """A labelled group of related controls: a legend-like heading above its members.

    Members are packed into ``self.body`` one per line, vertically, so each box has
    exactly one clear label of its own (NN/g checkbox guidance).
    """

    def __init__(self, parent, legend, *, style="TFrame", legend_style="Legend.TLabel", **kw):
        super().__init__(parent, style=style, **kw)
        self.legend = ttk.Label(self, text=legend, style=legend_style)
        self.legend.pack(anchor="w")
        self.body = ttk.Frame(self, style=style, padding=(2, 2, 0, 0))
        self.body.pack(fill="x")


class Tooltip:
    """A small hover note for detail that should not crowd the page (ids, full titles).

    ``text`` is a callable so the note always shows current content; an empty
    string shows nothing.
    """

    def __init__(self, widget, text):
        self.widget, self.text, self.window, self.handle = widget, text, None, None
        widget.bind("<Enter>", self._schedule, add=True)
        widget.bind("<Motion>", self._schedule, add=True)
        widget.bind("<Leave>", self.hide, add=True)
        widget.bind("<ButtonPress>", self.hide, add=True)

    def _schedule(self, event):
        self.hide()
        self.position = event.x_root + 12, event.y_root + 16
        self.handle = self.widget.after(450, self.show)

    def show(self):
        import tkinter as tk

        self.handle = None
        text = self.text()
        if not text or not self.widget.winfo_exists():
            return
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry("+{}+{}".format(*self.position))
        ttk.Label(
            self.window, text=text, style="Tooltip.TLabel", padding=(8, 4), wraplength=420
        ).pack()

    def hide(self, _event=None):
        if self.handle is not None:
            self.widget.after_cancel(self.handle)
            self.handle = None
        if self.window is not None:
            self.window.destroy()
            self.window = None
