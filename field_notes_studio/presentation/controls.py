"""Labelled icon buttons with local, interruptible completion feedback."""

from tkinter import ttk

from field_notes_studio.presentation.icons import icon
from field_notes_studio.presentation.theme import MUTED, SURFACE


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
        color = SURFACE if self.cget("style") == "Accent.TButton" else None
        normal = icon(self, name, color) if color else icon(self, name)
        self.configure(image=(normal, "disabled", icon(self, name, MUTED)))

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
        self.set_icon("check")
        self.feedback_handle = self.after(1800, self.reset_feedback)

    def _destroyed(self, event):
        if event.widget is self and self.feedback_handle is not None:
            self.after_cancel(self.feedback_handle)
            self.feedback_handle = None
