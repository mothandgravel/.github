"""Persistent episode overview; values and callbacks only, no media/file access."""

from tkinter import ttk

from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.readiness_models import LABELS


class ReadinessCard(ttk.Frame):
    def __init__(self, parent, act, refresh):
        super().__init__(parent, padding=(0, 10, 16, 0))
        self.snapshot = None
        self.columnconfigure(0, weight=1)
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="EPISODE READINESS", style="Heading.TLabel").pack(side="left")
        ttk.Button(header, text="Check", command=refresh, width=7).pack(side="right")
        self.title = ttk.Label(
            self, text="Choose a recording", style="Heading.TLabel", wraplength=270
        )
        self.title.grid(row=1, column=0, sticky="ew", pady=(6, 3))
        evidence = ttk.Frame(self)
        evidence.grid(row=2, column=0, sticky="ew")
        evidence.columnconfigure(0, weight=1)
        self.stages = ttk.Label(evidence, text="", style="Muted.TLabel", wraplength=270)
        self.stages.grid(row=0, column=0, sticky="ew")
        # Exception text stays behind an explicit disclosure, never in the headline.
        self.details_button = ttk.Button(
            evidence, text="▸ Details", command=self.toggle_details, style="Toolbutton"
        )
        self.detail = ttk.Label(self, text="", style="Muted.TLabel", wraplength=270)
        self.detail.grid(row=3, column=0, sticky="ew", pady=(4, 5))
        self.details_shown = False
        self.details = ttk.Label(self, text="", style="Muted.TLabel", wraplength=270)
        self.primary = ActionButton(
            self,
            text="Check readiness",
            pictogram="search",
            command=act,
            style="Accent.TButton",
            state="disabled",
        )
        self.primary.grid(row=5, column=0, sticky="ew")
        self.bind("<Configure>", self._resize)

    def _resize(self, event):
        for label in (self.title, self.detail, self.details):
            label.configure(wraplength=max(180, event.width - 20))
        self.width = event.width
        self._wrap_stages()

    def _wrap_stages(self):
        # Stage lines are short; leave room for the Details toggle only while shown.
        reserve = 110 if self.snapshot and self.snapshot.technical else 20
        self.stages.configure(wraplength=max(150, getattr(self, "width", 290) - reserve))

    def toggle_details(self):
        self.details_shown = not self.details_shown
        self._show_details()

    def _show_details(self):
        self._wrap_stages()
        technical = self.snapshot.technical if self.snapshot else ""
        if not technical:
            self.details_shown = False
            self.details_button.grid_remove()
            self.details.grid_remove()
            return
        self.details_button.grid(row=0, column=1, sticky="ne", padx=(6, 0))
        # A disclosure triangle keeps the width constant when toggled.
        self.details_button.configure(text=("▾ " if self.details_shown else "▸ ") + "Details")
        if self.details_shown:
            self.details.configure(text="Technical detail: " + technical)
            self.details.grid(row=4, column=0, sticky="ew", pady=(0, 5))
        else:
            self.details.grid_remove()

    def invalidate(self, text="Check the edited recipe against saved media.", enabled=True):
        self.snapshot = None
        self._show_details()
        self.primary.set_icon("search")
        self.title.configure(text="Readiness needs checking")
        self.stages.configure(text="")
        self.detail.configure(text=text)
        self.primary.configure(text="Check readiness", state="normal" if enabled else "disabled")

    def working(self):
        self.snapshot = None
        self._show_details()
        self.primary.set_icon("search")
        self.title.configure(text="Checking episode…")
        self.stages.configure(text="Source · media · review · upload copy")
        self.detail.configure(text="Checking local evidence; no service request.")
        self.primary.configure(text="Checking…", state="disabled")

    def show(self, snapshot):
        self.snapshot = snapshot
        self.details_shown = False
        self._show_details()
        self.primary.set_icon(
            {
                "produce": "produce",
                "review": "review",
                "export": "package",
                "package": "folder",
                "job": "history",
                "health": "health",
                "repair": "health",
            }.get(snapshot.action, "search")
        )
        self.title.configure(text=snapshot.title)
        self.stages.configure(text="\n".join(snapshot.stages))
        # Detailed blockers go beside Produce/Export; keep the overview compact.
        detail = snapshot.detail if len(snapshot.detail) <= 190 else snapshot.detail[:187] + "…"
        if snapshot.checked_at:
            detail += "\nChecked " + snapshot.checked_at.replace("T", " ").replace("+00:00", " UTC")
        self.detail.configure(text=detail)
        self.primary.configure(text=LABELS[snapshot.action], state="normal")
