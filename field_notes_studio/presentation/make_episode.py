"""Make episode views: the work list home, the pre-flight summary and the run timeline.

Values and callbacks only. The summary shows what the person consents to: the
paid steps with their estimate, the local steps, what is reused for free, and the
spend guard with every uncertain attempt. The one confirm is the tick plus
Make episode; it is never offered while the summary has a blocker.
"""

import tkinter as tk
from tkinter import ttk

from field_notes_studio.presentation import theme
from field_notes_studio.presentation.controls import ActionButton
from field_notes_studio.presentation.icons import icon
from field_notes_studio.presentation.scroll import ScrollArea

TAGS = {
    "paid": ("Paid", "CardWarn.TLabel"),
    "local": ("Local", "CardOk.TLabel"),
    "you": ("You", "CardBrass.TLabel"),
    "reused": ("Reused · free", "CardOk.TLabel"),
}
GLYPHS = {
    "narrate": "audio",
    "caption": "captions",
    "sound": "produce",
    "video": "video",
    "review": "review",
    "package": "package",
}
ROW_STATE_STYLES = {
    "ok": "CardOk.TLabel",
    "run": "CardState.TLabel",
    "todo": "CardMuted.TLabel",
    "warn": "CardWarn.TLabel",
    "you": "CardState.TLabel",
}
# What the status bar says while a run's step is working.
RUNNING_VERBS = {
    "narrate": "Narrating",
    "caption": "Captioning",
    "sound": "Finishing the sound for",
    "video": "Making the video for",
    "package": "Making the upload folder for",
}


def run_activity(view, title):
    """One status-bar line for a run: what is running, or who acts next."""
    row = next((r for r in view.rows if r.kind == "run"), None)
    if view.group == "working" and row is not None:
        elapsed = row.detail.split(" elapsed", 1)[0] if " elapsed" in row.detail else ""
        text = f"{RUNNING_VERBS.get(row.key, 'Working on')} {title}"
        return ("produce", "BRASS", text + (f" · {elapsed}" if elapsed else ""))
    if view.group == "working":
        return ("history", "BRASS", f"{title} · {view.headline}")
    if view.group == "needs-you":
        return ("health" if view.phase == "paused" else "review", "WARNING", f"{title} needs you")
    return ("check", "SUCCESS", f"{title} · {view.headline}")


ROW_COLORS = {"ok": "SUCCESS", "run": "BRASS", "todo": "MUTED", "warn": "WARNING", "you": "BRASS"}
GROUP_TITLES = {"needs-you": "Needs you", "working": "Working", "done": "Done"}


def money(value):
    if value is None:
        return "no local estimate"
    if value < 0.01:
        return "under $0.01"
    return f"about ${value:.2f}"


class Link(ttk.Label):
    """A brass text action that is a real focusable control (Enter or Space activates)."""

    def __init__(self, parent, text, command, style="CardBrass.TLabel"):
        super().__init__(parent, text=text, style=style, cursor="hand2", takefocus=True)
        self.command = command
        for sequence in ("<Button-1>", "<Return>", "<space>"):
            self.bind(sequence, lambda _e: self.command())
        self.bind("<FocusIn>", lambda _e: self.configure(text="› " + text))
        self.bind("<FocusOut>", lambda _e: self.configure(text=text))


# -- Work list home -----------------------------------------------------------------------


class WorkListView(ttk.Frame):
    """Episodes and notes grouped by who acts next; each row opens where it belongs."""

    def __init__(self, parent, callbacks):
        super().__init__(parent)
        self.callbacks = callbacks
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.scroll = ScrollArea(self, padding=(0, 0, 8, 12))
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.scroll.canvas.bind("<Configure>", lambda _e: self._scrollbar(), add=True)
        self.content = self.scroll.content
        self.content.columnconfigure(0, weight=1)
        self.done_open = False
        self.work = None
        self.rows = {}
        self.status = ttk.Label(self.content, text="Loading the work list…", style="Muted.TLabel")
        self.status.grid(row=0, column=0, sticky="w", pady=(12, 0))

    def load(self, work):
        """Render a WorkList; rows keep their order: Needs you, Working, Done."""
        self.work = work
        for child in self.content.winfo_children():
            child.destroy()
        self.rows = {}
        row = 0
        for group in ("needs-you", "working"):
            items = work.group(group)
            heading = GROUP_TITLES[group].upper()
            ttk.Label(self.content, text=heading, style="Heading.TLabel").grid(
                row=row, column=0, sticky="w", pady=(14 if row else 4, 4)
            )
            row += 1
            if not items:
                ttk.Label(
                    self.content,
                    text="Nothing needs you right now."
                    if group == "needs-you"
                    else "Nothing is running. Closing Studio never stops work in progress.",
                    style="Muted.TLabel",
                ).grid(row=row, column=0, sticky="w", pady=(0, 2))
                row += 1
            for item in items:
                self._card(item).grid(row=row, column=0, sticky="ew", pady=3)
                row += 1
        done = work.group("done")
        bar = ttk.Frame(self.content)
        bar.grid(row=row, column=0, sticky="ew", pady=(14, 4))
        ttk.Label(bar, text=f"DONE · {len(done)} episodes", style="Heading.TLabel").pack(
            side="left"
        )
        if done:
            self.done_button = ttk.Button(
                bar,
                text="Hide" if self.done_open else "Show",
                style="Small.TButton",
                command=self.toggle_done,
            )
            self.done_button.pack(side="left", padx=(10, 0))
        row += 1
        if self.done_open:
            for item in done:
                self._card(item).grid(row=row, column=0, sticky="ew", pady=3)
                row += 1
        if work.not_started:
            ttk.Label(
                self.content,
                text=f"{work.not_started} written notes have no narration script yet; "
                "they are not listed.",
                style="Small.TLabel",
            ).grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.scroll.bind_navigation()
        self.after_idle(self._scrollbar)

    def _scrollbar(self):
        """Show the scrollbar only when the list is taller than the window."""
        self.update_idletasks()
        needed = self.content.winfo_reqheight() > self.scroll.canvas.winfo_height()
        if needed:
            self.scroll.scrollbar.grid()
        else:
            self.scroll.scrollbar.grid_remove()
            self.scroll.canvas.yview_moveto(0)

    def focus_first(self):
        if self.rows:
            next(iter(self.rows.values())).focus_set()

    def toggle_done(self):
        self.done_open = not self.done_open
        if self.work is not None:
            self.load(self.work)

    def _card(self, item):
        card = ttk.Frame(self.content, style="Card.TFrame", padding=(10, 8))
        card.columnconfigure(2, weight=1, uniform="cols")
        card.columnconfigure(3, weight=1, uniform="cols")
        card.columnconfigure(1, weight=1, uniform="cols")
        colour = (
            "WARNING" if item.glyph == "health" else "BRASS" if item.group == "needs-you" else "INK"
        )
        ttk.Label(card, image=icon(card, item.glyph, colour), style="Card.TLabel").grid(
            row=0, column=0, padx=(4, 12)
        )
        ttk.Label(card, text=item.title, style="CardHeading.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        state = item.state if item.verified else item.state + " · checking…"
        ttk.Label(card, text=state, style="Card.TLabel").grid(row=0, column=2, sticky="w")
        ttk.Label(card, text=item.meta, style="CardMuted.TLabel").grid(row=0, column=3, sticky="w")
        button = ttk.Button(
            card,
            text="Make episode…" if item.next == "Make" else "Open",
            style="Compact.TButton",
            command=lambda: self.callbacks["open"](item),
        )
        button.grid(row=0, column=4, sticky="e", padx=(8, 0))
        for label in card.winfo_children()[1:4]:
            label.bind("<Configure>", lambda e, w=label: w.configure(wraplength=e.width))
        card.bind("<Double-Button-1>", lambda _e: self.callbacks["open"](item))
        self.rows[item.identifier] = button
        return card


# -- Pre-flight summary -----------------------------------------------------------------


class PreflightDialog:
    """What will happen, what it may cost, and the single consent."""

    def __init__(self, root, callbacks):
        self.callbacks = callbacks
        self.plan = None
        self.window = window = tk.Toplevel(root)
        window.title("Make episode · Moth & Gravel")
        window.transient(root)
        window.minsize(theme.px(root, 900), theme.px(root, 560))
        window.geometry(f"{theme.px(root, 1180)}x{theme.px(root, 640)}")
        window.protocol("WM_DELETE_WINDOW", self.cancel)
        window.bind("<Escape>", lambda _e: self.cancel())
        wrap = self.wrap = ttk.Frame(window, padding=(28, 20, 28, 20))
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(3, weight=1)
        ttk.Label(wrap, text="MOTH & GRAVEL  /  MAKE EPISODE", style="Brand.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.title = ttk.Label(wrap, text="Checking the note…", style="Title.TLabel")
        self.title.grid(row=1, column=0, sticky="w", pady=(4, 2))
        self.subtitle = ttk.Label(wrap, text="", style="Muted.TLabel")
        self.subtitle.grid(row=2, column=0, sticky="w")
        cols = ttk.Frame(wrap)
        cols.grid(row=3, column=0, sticky="nsew", pady=(16, 0))
        cols.columnconfigure(0, weight=1)
        cols.rowconfigure(0, weight=1)
        self.plan_card = ttk.Frame(cols, style="Card.TFrame", padding=14)
        self.plan_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.plan_card.columnconfigure(2, weight=1)
        self.money_card = ttk.Frame(cols, style="Card.TFrame", padding=14)
        self.money_card.grid(row=0, column=1, sticky="ns")
        self.allowed = tk.BooleanVar(value=False)
        foot = ttk.Frame(wrap)
        foot.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        foot.columnconfigure(1, weight=1)
        self.cancel_button = ttk.Button(foot, text="Cancel", command=self.cancel)
        self.cancel_button.grid(row=0, column=0, sticky="w")
        self.note = ttk.Label(
            foot,
            text="Nothing is published. You approve before any upload package is made.",
            style="Muted.TLabel",
        )
        self.note.grid(row=0, column=1, sticky="e", padx=14)
        self.make_button = ActionButton(
            foot,
            pictogram="produce",
            text="Make episode",
            style="Accent.TButton",
            command=self.confirm,
            state="disabled",
        )
        self.make_button.grid(row=0, column=2, sticky="e")
        window.bind("<Control-Return>", lambda _e: self.confirm())
        self.loading("Checking the note, its saved work and the spend guard…")

    def loading(self, message):
        self.plan = None
        for card in (self.plan_card, self.money_card):
            for child in card.winfo_children():
                child.destroy()
        ttk.Label(self.plan_card, text=message, style="CardMuted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.make_button.configure(state="disabled")

    def failed(self, message):
        self.loading("")
        self.title.configure(text="This note can't be made yet")
        for child in self.plan_card.winfo_children():
            child.destroy()
        ttk.Label(
            self.plan_card, text=message, style="Card.TLabel", wraplength=theme.px(self.window, 640)
        ).grid(row=0, column=0, sticky="w")
        Link(self.plan_card, "More options…", self.callbacks["expert"]).grid(
            row=1, column=0, sticky="w", pady=(12, 0)
        )
        self.cancel_button.focus_set()

    def show(self, plan):
        self.plan = plan
        self.allowed.set(False)
        name = f"Field Note {plan.note}" if plan.note else plan.title or plan.episode
        self.title.configure(text=f"Make {name} into an episode")
        details = [plan.title] if plan.note and plan.title else []
        if plan.words:
            details.append(f"{plan.words:,} words")
        details.append(f"checked {plan.checked_at}")
        details.append(f"show settings: {plan.recipe_label}")
        self.subtitle.configure(text="  ·  ".join(details))
        for card in (self.plan_card, self.money_card):
            for child in card.winfo_children():
                child.destroy()
        self._plan_card(plan)
        self._money_card(plan)
        self.update_button()
        (self.consent if plan.paid and not plan.blockers else self.make_button).focus_set()

    def _plan_card(self, plan):
        card = self.plan_card
        ttk.Label(card, text="What will happen", style="CardHeading.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )
        for index, step in enumerate(plan.steps, start=1):
            ttk.Label(
                card, image=icon(card, GLYPHS.get(step.key, "produce")), style="Card.TLabel"
            ).grid(row=index, column=0, sticky="w", padx=(0, 10), pady=5)
            ttk.Label(card, text=step.name, style="CardHeading.TLabel").grid(
                row=index, column=1, sticky="w", padx=(0, 12)
            )
            detail = ttk.Label(card, text=step.detail, style="Card.TLabel")
            detail.grid(row=index, column=2, sticky="ew")
            detail.bind("<Configure>", lambda e, w=detail: w.configure(wraplength=e.width))
            text, style = TAGS[step.kind]
            ttk.Label(card, text=text, style=style).grid(row=index, column=3, sticky="e")
        row = len(plan.steps) + 1
        reused = (
            "Reused if already saved: " + ", ".join(plan.reused) + "; no charge."
            if plan.reused
            else "Reused if already saved: narration parts, captions, sound and video."
        )
        ttk.Label(card, text=reused, style="CardMuted.TLabel").grid(
            row=row, column=0, columnspan=4, sticky="w", pady=(10, 0)
        )
        ttk.Label(card, text=self.callbacks["waiting"](plan), style="CardMuted.TLabel").grid(
            row=row + 1, column=0, columnspan=4, sticky="w"
        )
        links = ttk.Frame(card, style="CardRow.TFrame")
        links.grid(row=row + 2, column=0, columnspan=4, sticky="w", pady=(10, 0))
        Link(links, "Change show settings…", self.callbacks["settings"]).pack(side="left")
        ttk.Label(links, text="   ·   ", style="CardMuted.TLabel").pack(side="left")
        Link(links, "See request details…", self.callbacks["expert"]).pack(side="left")
        if plan.blockers:
            alert = ttk.Frame(card, style="Attention.TFrame", padding=12)
            alert.grid(row=row + 3, column=0, columnspan=4, sticky="ew", pady=(12, 0))
            ttk.Label(alert, text="Can't start yet", style="AttentionHeading.TLabel").pack(
                anchor="w"
            )
            for blocker in plan.blockers:
                ttk.Label(
                    alert,
                    text=blocker,
                    style="Attention.TLabel",
                    wraplength=theme.px(card, 620),
                ).pack(anchor="w", pady=(4, 0))

    def _money_card(self, plan):
        card = self.money_card
        ttk.Label(card, text="Cloud spending", style="CardHeading.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        spend = plan.spend
        rows = [
            ("Project", plan.project or "none needed"),
            ("Estimate", plan.estimate_text),
            ("Spend guard", f"stop after {spend.part_limit} failed attempts"),
            ("", f"on any part, {spend.episode_limit} per episode,"),
            ("", f"in {spend.window_hours:g} h, then ask me"),
            (
                "Right now",
                f"{spend.episode_window} uncertain attempt"
                + ("" if spend.episode_window == 1 else "s")
                + " recorded",
            ),
        ]
        for index, (label, value) in enumerate(rows, start=1):
            ttk.Label(card, text=label, style="CardMuted.TLabel").grid(
                row=index, column=0, sticky="w", padx=(0, 12), pady=3
            )
            ttk.Label(
                card,
                text=value,
                style="CardWarn.TLabel"
                if label == "Right now" and spend.episode_window
                else "Card.TLabel",
            ).grid(row=index, column=1, sticky="w")
        row = len(rows) + 1
        for attempt in spend.attempts[-3:]:
            ttk.Label(
                card,
                text=f"{attempt.when} · {attempt.part} · {attempt.detail} · billing unknown",
                style="CardSmall.TLabel",
            ).grid(row=row, column=0, columnspan=2, sticky="w")
            row += 1
        ttk.Label(
            card,
            text="Estimate is from the script length; captions\nhave no local price. "
            "Failed attempts may still be\nbilled; Studio never retries on its own.",
            style="CardMuted.TLabel",
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 12))
        self.consent = ttk.Checkbutton(
            card,
            text="Allow paid narration and captions\nfor this episode",
            variable=self.allowed,
            style="Card.TCheckbutton",
            command=self.update_button,
        )
        if plan.paid and not plan.blockers:
            self.consent.grid(row=row + 1, column=0, columnspan=2, sticky="w")
        elif not plan.paid:
            ttk.Label(
                card,
                text="Nothing paid: narration and\ncaptions are already saved.",
                style="CardOk.TLabel",
            ).grid(row=row + 1, column=0, columnspan=2, sticky="w")

    def update_button(self):
        plan = self.plan
        ready = plan is not None and not plan.blockers and (not plan.paid or self.allowed.get())
        self.make_button.configure(state="normal" if ready else "disabled")

    def confirm(self):
        if str(self.make_button["state"]) != "normal" or self.plan is None:
            return
        self.make_button.configure(state="disabled")
        self.callbacks["confirm"](self.plan, self.allowed.get() if self.plan.paid else False)

    def cancel(self):
        if self.window.winfo_exists():
            self.window.destroy()
        self.callbacks.get("closed", lambda: None)()


# -- Run timeline -------------------------------------------------------------------------


class RunPanel(ttk.Frame):
    """Progress across every stage, with measured times; the failure ledger on a pause."""

    def __init__(self, parent, callbacks):
        super().__init__(parent)
        self.callbacks = callbacks
        self.view = None
        self.columnconfigure(0, weight=1)
        self.title = ttk.Label(self, text="", style="Title.TLabel")
        self.title.grid(row=0, column=0, sticky="w")
        self.subtitle = ttk.Label(self, text="", style="Muted.TLabel")
        self.subtitle.grid(row=1, column=0, sticky="w", pady=(2, 12))
        self.alert = ttk.Frame(self, style="Attention.TFrame", padding=(16, 12))
        self.alert.columnconfigure(0, weight=1)
        self.alert_title = ttk.Label(self.alert, style="AttentionHeading.TLabel")
        self.alert_title.grid(row=0, column=0, sticky="w")
        self.alert_text = ttk.Label(self.alert, style="Attention.TLabel")
        self.alert_text.grid(row=1, column=0, sticky="ew", pady=(4, 10))
        # Wrap to the panel, not to the label's own (text-driven) width.
        self.alert.bind(
            "<Configure>",
            lambda e: self.alert_text.configure(wraplength=max(200, e.width - theme.px(self, 36))),
            add=True,
        )
        self.ledger = ttk.Treeview(
            self.alert, columns=("when", "result", "estimate", "billing"), show="headings", height=3
        )
        for column, label, width in (
            ("when", "Attempt", 150),
            ("result", "What came back", 380),
            ("estimate", "Estimate", 140),
            ("billing", "Billing", 240),
        ):
            self.ledger.heading(column, text=label, anchor="w")
            self.ledger.column(column, width=theme.px(self, width), anchor="w")
        self.ledger.grid(row=2, column=0, sticky="ew")
        self.ledger_note = ttk.Label(self.alert, style="AttentionMuted.TLabel")
        self.ledger_note.grid(row=3, column=0, sticky="w", pady=(8, 12))
        actions = ttk.Frame(self.alert, style="Attention.TFrame", padding=0)
        actions.configure(borderwidth=0)
        actions.grid(row=4, column=0, sticky="ew")
        self.retry_button = ActionButton(
            actions,
            pictogram="refresh",
            text="Try once more…",
            style="Accent.TButton",
            command=lambda: self.callbacks["recover"](self.view),
        )
        self.retry_button.pack(side="left")
        ActionButton(
            actions,
            pictogram="stop",
            text="Pause until I come back",
            command=self.callbacks["hide"],
        ).pack(side="left", padx=8)
        ActionButton(
            actions,
            pictogram="external",
            text="Open billing console",
            command=self.callbacks["billing"],
        ).pack(side="left")
        self.copy_button = ActionButton(
            actions,
            pictogram="copy",
            text="Copy diagnostics",
            command=self.copy_diagnostics,
        )
        self.copy_button.pack(side="right")
        self.hint_row = ttk.Frame(self)
        self.hint_row.columnconfigure(0, weight=1)
        self.alert_hint = ttk.Label(self.hint_row, style="Muted.TLabel")
        self.alert_hint.grid(row=0, column=0, sticky="w")
        self.close_link = Link(
            self.hint_row,
            "Close this run",
            lambda: self.callbacks["close"](self.view),
            style="Brass.TLabel",
        )
        self.close_link.grid(row=0, column=1, sticky="e")
        self.box = ttk.Frame(self, style="Card.TFrame", padding=18)
        self.box.grid(row=4, column=0, sticky="ew")
        self.box.columnconfigure(3, weight=1)
        self.cells = []
        for index in range(6):
            glyph = ttk.Label(self.box, style="Card.TLabel")
            glyph.grid(row=index, column=0, padx=(0, 10), pady=4, sticky="w")
            name = ttk.Label(self.box, style="CardHeading.TLabel", width=14)
            name.grid(row=index, column=1, sticky="w")
            state = ttk.Label(self.box, style="CardMuted.TLabel", width=14)
            state.grid(row=index, column=2, sticky="w")
            detail = ttk.Label(self.box, style="CardMuted.TLabel")
            detail.grid(row=index, column=3, sticky="w")
            self.cells.append((glyph, name, state, detail))
        # What this episode has cost so far: a local estimate, never shown as a bill.
        self.cost = ttk.Label(self, style="Muted.TLabel")
        self.cost.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        self.bind(
            "<Configure>",
            lambda e: self.cost.configure(wraplength=max(200, e.width - 8)),
            add=True,
        )
        foot = self.foot = ttk.Frame(self)
        foot.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        self.notify = tk.BooleanVar(value=False)
        self.notify_box = ttk.Checkbutton(
            foot,
            text="Show a desktop notification when my review is needed",
            variable=self.notify,
            command=lambda: self.callbacks["notify"](self.notify.get()),
        )
        self.notify_box.pack(side="left")
        self.primary = ActionButton(
            foot,
            pictogram="review",
            text="Review full episode",
            style="Accent.TButton",
            command=lambda: self.callbacks["next"](self.view),
        )
        self.stop_button = ActionButton(
            foot,
            pictogram="stop",
            text="Stop after this step",
            command=lambda: self.callbacks["stop"](self.view),
        )
        self.stop_button.pack(side="right")

    def show(self, view, title, attempts=(), diagnostics="", cost=""):
        self.view = view
        self.cost.configure(text=cost)
        self.diagnostics = diagnostics
        self.title.configure(text=title)
        if view.group == "working":
            state = f"Started {view.started} · you can close Studio; the background producer keeps going"
        elif view.phase == "paused":
            state = "Paused · nothing is running · nothing will be sent until you choose"
        elif view.phase == "stopped":
            state = "Stopped between steps · nothing is running"
        else:
            state = f"Started {view.started} · {view.headline}"
        self.subtitle.configure(text=state)
        failed = view.phase == "paused" and any(r.kind == "warn" for r in view.rows)
        if failed:
            # The ledger's own actions replace the footer, so the minimum window fits.
            self._alert(view, attempts)
            self.foot.grid_remove()
        else:
            self.alert.grid_remove()
            self.hint_row.grid_remove()
            self.foot.grid()
        for (glyph, name, state_label, detail), row in zip(self.cells, view.rows, strict=False):
            mark = {"ok": "check", "todo": "pending", "warn": "health"}.get(
                row.kind, GLYPHS.get(row.key, "produce")
            )
            glyph.configure(image=icon(glyph, mark, ROW_COLORS[row.kind]))
            name.configure(text=row.name)
            state_label.configure(text=row.state, style=ROW_STATE_STYLES[row.kind])
            detail.configure(text=row.detail)
        self.primary.pack_forget()
        label = {
            "review": ("review", "Review full episode"),
            "ready": ("package", "Open Release"),
            "done": ("package", "Open Release"),
            "stopped": ("produce", "Continue"),
        }.get(view.phase)
        if label:
            self.primary.pictogram = label[0]
            self.primary.reset_feedback(label[1])
            self.primary.pack(side="right", padx=(8, 0))
        running = view.group == "working"
        if running:
            self.stop_button.pack(side="right")
        else:
            self.stop_button.pack_forget()
        self.stop_button.configure(state="disabled" if view.stop_after else "normal")
        self.stop_button.reset_feedback(
            "Stops after this step" if view.stop_after else "Stop after this step"
        )

    def _alert(self, view, attempts):
        self.alert.grid(row=2, column=0, sticky="ew")
        self.alert_title.configure(
            text="The narration service is failing, so Studio paused" if attempts else view.headline
        )
        self.alert_text.configure(text=view.detail)
        self.ledger.delete(*self.ledger.get_children())
        if attempts:
            self.ledger.grid()
            for index, attempt in enumerate(attempts, start=1):
                self.ledger.insert(
                    "",
                    "end",
                    values=(
                        f"{index} · {attempt.when}",
                        f"{attempt.part}: {attempt.detail}",
                        attempt.estimate,
                        "Unknown; may be billed",
                    ),
                )
            self.ledger.configure(height=min(4, max(1, len(attempts))))
            part = attempts[-1].part
            self.retry_button.reset_feedback(f"Try {part} once more…")
            self.ledger_note.configure(
                text=f"Up to {len(attempts)} uncertain attempt(s); possible spend is shown per "
                "attempt. Check actual charges in the Cloud billing console."
            )
            self.ledger_note.grid()
        else:
            self.ledger.grid_remove()
            self.ledger_note.grid_remove()
            self.retry_button.reset_feedback(
                "Run this step again (free)" if view.retry_free else "Check recovery…"
            )
        self.alert_hint.configure(
            text="This step is local: running it again costs nothing."
            if view.retry_free
            else "Try once more asks for duplicate-charge consent for that part only, and "
            "counts against the same spend guard as the terminal command."
        )
        self.hint_row.grid(row=3, column=0, sticky="ew", pady=(8, 8))

    def copy_diagnostics(self):
        self.clipboard_clear()
        self.clipboard_append(self.diagnostics or "")
        self.copy_button.complete()


# -- Choosing what to make ------------------------------------------------------------------


class NoteChooser:
    """Pick a written note (or a narrated episode) to make; nothing is checked yet."""

    def __init__(self, root, items, choose):
        self.items = {item.identifier: item for item in items}
        self.choose = choose
        self.window = window = tk.Toplevel(root)
        window.title("Make episode from a note · Moth & Gravel")
        window.transient(root)
        window.geometry(f"{theme.px(root, 640)}x{theme.px(root, 460)}")
        window.minsize(theme.px(root, 480), theme.px(root, 320))
        window.bind("<Escape>", lambda _e: window.destroy())
        body = ttk.Frame(window, padding=18)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        ttk.Label(body, text="Make episode from a note", style="Heading.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            body,
            text="Choose a note. The next page shows what will happen and what it may cost "
            "before anything starts.",
            style="Muted.TLabel",
            wraplength=theme.px(root, 580),
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))
        self.tree = ttk.Treeview(body, columns=("note", "state"), show="headings", height=8)
        self.tree.heading("note", text="Note", anchor="w")
        self.tree.heading("state", text="Where it is", anchor="w")
        self.tree.column("note", width=theme.px(root, 340))
        self.tree.column("state", width=theme.px(root, 200))
        for item in items:
            self.tree.insert("", "end", iid=item.identifier, values=(item.title, item.state))
        self.tree.grid(row=2, column=0, sticky="nsew")
        self.tree.bind("<Double-Button-1>", lambda _e: self.go())
        self.tree.bind("<Return>", lambda _e: self.go())
        foot = ttk.Frame(body)
        foot.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Button(foot, text="Cancel", command=window.destroy).pack(side="left")
        self.next_button = ActionButton(
            foot,
            pictogram="produce",
            text="Check what will happen…",
            style="Accent.TButton",
            command=self.go,
        )
        self.next_button.pack(side="right")
        if items:
            first = items[0].identifier
            self.tree.selection_set(first)
            self.tree.focus(first)
            self.tree.focus_set()
        else:
            ttk.Label(
                body,
                text="No note is waiting. Write a note and its narration script first.",
                style="Muted.TLabel",
            ).grid(row=4, column=0, sticky="w", pady=(8, 0))
            self.next_button.configure(state="disabled")

    def go(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = self.items[selection[0]]
        self.window.destroy()
        self.choose(item)
