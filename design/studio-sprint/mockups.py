"""Static Tk mock windows for the studio design sprint.

Prototypes only: no engine, worker, repository, file or network access. They reuse the
studio's real ttk theme and stroke pictograms so the concepts are judged in the app's own
visual language. Render under any X display, for example a local Xvfb:

    DISPLAY=:93 python3 design/studio-sprint/mockups.py OUTPUT_DIR

Every value shown is a fixed illustration, not a measured price, provider state or
publication.
"""

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from field_notes_studio.presentation import theme  # noqa: E402
from field_notes_studio.presentation.icons import icon  # noqa: E402

NIGHT = {
    "PAPER": "#17191b",
    "SURFACE": "#202324",
    "INK": "#f1eee6",
    "MUTED": "#b5b3aa",
    "BRASS": "#d4b37c",
    "DARK": "#e7c89a",
    "LINE": "#3d4241",
    "SUCCESS": "#8cc5a8",
    "WARNING": "#e3b06a",
}


def palette(night):
    names = ("PAPER", "SURFACE", "INK", "MUTED", "BRASS", "DARK", "LINE", "SUCCESS", "WARNING")
    if night:
        return dict(NIGHT)
    return {name: getattr(theme, name) for name in names}


def style(root, night=False):
    """The shipped theme, plus the few styles the concepts introduce."""
    if night:
        for name, value in NIGHT.items():
            setattr(theme, name, value)
    theme.apply(root)
    p = palette(night)
    s = ttk.Style(root)
    if night:
        s.configure("Accent.TButton", foreground="#17191b")
        s.map("Accent.TButton", foreground=[("disabled", p["MUTED"]), ("!disabled", "#17191b")],
              background=[("active", "#e7c89a"), ("pressed", "#b8955b")])
        s.map("TNotebook.Tab", foreground=[("selected", "#17191b"), ("active", p["INK"])],
              background=[("selected", p["DARK"]), ("active", "#2a2e2f")])
        s.map("TButton", background=[("disabled", p["PAPER"]), ("active", "#2a2e2f")],
              foreground=[("disabled", "#7c7f78")])
        s.configure("TEntry", foreground=p["INK"], fieldbackground=p["SURFACE"],
                    insertcolor=p["INK"])
        s.configure("TNotebook", lightcolor=p["LINE"], darkcolor=p["LINE"], bordercolor=p["LINE"])
        s.map("Accent.TButton", background=[("disabled", "#2a2e2f"), ("active", "#e7c89a")])
        s.map("Treeview", background=[("selected", "#33383a")], foreground=[("selected", p["INK"])])
    s.configure("Box.TFrame", background=p["SURFACE"], bordercolor=p["LINE"], relief="solid",
                borderwidth=1)
    s.configure("Row.TFrame", background=p["SURFACE"], borderwidth=0, relief="flat")
    s.configure("TCheckbutton", indicatorbackground=p["SURFACE"], indicatorforeground=p["INK"])
    s.configure("AttRow.TFrame", background="#f6ead6" if not night else "#2c261c", borderwidth=0)
    s.configure("Card.TCheckbutton", background=p["SURFACE"], foreground=p["INK"],
                indicatorbackground=p["SURFACE"], indicatorforeground=p["INK"])
    s.configure("Card.TLabel", background=p["SURFACE"], foreground=p["INK"])
    s.configure("CardMuted.TLabel", background=p["SURFACE"], foreground=p["MUTED"])
    s.configure("CardHeading.TLabel", background=p["SURFACE"], foreground=p["INK"],
                font=("DejaVu Sans", 11, "bold"))
    s.configure("CardBig.TLabel", background=p["SURFACE"], foreground=p["INK"],
                font=("DejaVu Serif", 15))
    s.configure("CardOk.TLabel", background=p["SURFACE"], foreground=p["SUCCESS"])
    s.configure("CardWarn.TLabel", background=p["SURFACE"], foreground=p["WARNING"])
    s.configure("CardBrass.TLabel", background=p["SURFACE"], foreground=p["BRASS"],
                font=("DejaVu Sans", 10, "bold"))
    s.configure("Step.TLabel", foreground=p["MUTED"], font=("DejaVu Sans", 10))
    s.configure("StepOn.TLabel", foreground=p["INK"], font=("DejaVu Sans", 10, "bold"))
    s.configure("Small.TLabel", foreground=p["MUTED"], font=("DejaVu Sans", 9))
    s.configure("Warn.TLabel", foreground=p["WARNING"])
    s.configure("Ok.TLabel", foreground=p["SUCCESS"])
    s.configure("Mono.TLabel", font=("DejaVu Sans Mono", 9), foreground=p["MUTED"])
    s.configure("CardMono.TLabel", font=("DejaVu Sans Mono", 9), foreground=p["MUTED"],
                background=p["SURFACE"])
    s.configure("Attention.TFrame", background="#f6ead6" if not night else "#2c261c",
                bordercolor=p["WARNING"], relief="solid", borderwidth=1)
    s.configure("Attention.TLabel", background="#f6ead6" if not night else "#2c261c",
                foreground=p["INK"])
    s.configure("AttentionHead.TLabel", background="#f6ead6" if not night else "#2c261c",
                foreground=p["WARNING"], font=("DejaVu Sans", 11, "bold"))
    s.configure("AttentionMuted.TLabel", background="#f6ead6" if not night else "#2c261c",
                foreground=p["MUTED"])
    s.configure("Stage.TNotebook.Tab", padding=(14, 7))
    return p


def button(parent, text, glyph=None, accent=False, state="normal", color=None):
    kwargs = {"text": text, "state": state}
    if glyph:
        p = palette(theme.PAPER == NIGHT["PAPER"])
        colour = color or (p["SURFACE"] if accent and theme.PAPER != NIGHT["PAPER"] else
                           "#17191b" if accent else p["INK"])
        kwargs.update(image=icon(parent, glyph, colour), compound="left")
    return ttk.Button(parent, style="Accent.TButton" if accent else "TButton", **kwargs)


def check(parent, value=False, **kwargs):
    """Bound to a variable so ttk does not draw its indeterminate (alternate) state."""
    variable = tk.BooleanVar(parent, value=value)
    widget = ttk.Checkbutton(parent, variable=variable, **kwargs)
    widget.variable = variable
    return widget


def glyph_label(parent, glyph, text, style_name, color):
    return ttk.Label(parent, text="  " + text, image=icon(parent, glyph, color), compound="left",
                     style=style_name)


def header(root, p, subtitle="LOCAL PRODUCTION"):
    top = ttk.Frame(root, padding=(24, 14, 24, 6))
    top.pack(fill="x")
    ttk.Label(top, text=f"MOTH & GRAVEL  /  {subtitle}", style="Brand.TLabel").pack(anchor="w")
    row = ttk.Frame(top)
    row.pack(fill="x")
    ttk.Label(row, text="Production studio", style="Studio.TLabel").pack(side="left")
    return row


def stepper(parent, p, steps, current, done=()):
    """Stage stepper: pictogram + text state, colour is never the only signal."""
    bar = ttk.Frame(parent)
    for index, (glyph, name, state) in enumerate(steps):
        if index:
            ttk.Label(bar, text="  ───  ", style="Step.TLabel").pack(side="left")
        on = index == current
        mark = "check" if index in done else glyph
        colour = p["SUCCESS"] if index in done else (p["BRASS"] if on else p["MUTED"])
        frame = ttk.Frame(bar)
        frame.pack(side="left")
        ttk.Label(frame, image=icon(frame, mark, colour)).pack(side="left", padx=(0, 6))
        ttk.Label(frame, text=name, style="StepOn.TLabel" if on else "Step.TLabel").pack(
            anchor="w")
        ttk.Label(frame, text=state, style="Small.TLabel").pack(anchor="w")
    return bar


def card(parent, padding=14):
    frame = ttk.Frame(parent, style="Box.TFrame", padding=padding)
    return frame


def checklist(parent, p, rows, style_prefix="Card"):
    for glyph, text, kind in rows:
        colour = {"ok": p["SUCCESS"], "warn": p["WARNING"], "todo": p["MUTED"],
                  "now": p["BRASS"]}[kind]
        mark = {"ok": "check", "warn": "health", "todo": "pending", "now": glyph}[kind]
        line = ttk.Frame(parent, style="Row.TFrame" if style_prefix == "Card" else "TFrame",
                         padding=0)
        line.configure(style="TFrame" if style_prefix != "Card" else "Row.TFrame")
        line.pack(fill="x", pady=2)
        ttk.Label(line, image=icon(line, mark, colour),
                  style=f"{style_prefix}.TLabel" if style_prefix == "Card" else "TLabel").pack(
            side="left", padx=(0, 8))
        ttk.Label(line, text=text,
                  style={"ok": "CardOk.TLabel", "warn": "CardWarn.TLabel",
                         "todo": "CardMuted.TLabel", "now": "CardHeading.TLabel"}[kind]
                  if style_prefix == "Card" else "TLabel").pack(side="left")


def shelf(parent, p, rows, selected=0, collection=True):
    side = ttk.Frame(parent, padding=(24, 6, 12, 0))
    ttk.Label(side, text="EPISODES", style="Heading.TLabel").pack(anchor="w")
    search = ttk.Frame(side)
    search.pack(fill="x", pady=(6, 6))
    entry = ttk.Entry(search)
    entry.insert(0, "Search title or number")
    entry.pack(fill="x")
    tree = ttk.Treeview(side, columns=("state",), show="headings", height=len(rows) + 1)
    tree.heading("#0", text="")
    tree.heading("state", text="")
    tree.configure(columns=("note", "state"))
    tree.heading("note", text="Episode", anchor="w")
    tree.heading("state", text="Next", anchor="w")
    tree.column("note", width=196, anchor="w")
    tree.column("state", width=92, anchor="w")
    for i, (title, state) in enumerate(rows):
        tree.insert("", "end", iid=str(i), values=(title, state))
    tree.selection_set(str(selected))
    tree.pack(fill="x")
    if collection:
        ttk.Label(side, text="Filter:  All · Needs me · Working · Done", style="Small.TLabel").pack(
            anchor="w", pady=(6, 0))
    return side


# ----------------------------------------------------------------------------------
# Concept A: polish in place
# ----------------------------------------------------------------------------------


def concept_a_main(root, p):
    row = header(root, p)
    button(row, "New episode from a note…", "transcript").pack(side="right")
    body = ttk.Frame(root)
    body.pack(fill="both", expand=True)
    left = shelf(body, p, [
        ("014 · Maritime study", "Prepare"),
        ("013 · The work outlives…", "Review"),
        ("012 · Coastal watch", "Release"),
        ("001 · Curiosity with calluses.", "Done"),
    ], selected=1)
    left.pack(side="left", fill="y")
    # Readiness card as an evidence checklist with one next action.
    ready = card(left)
    ready.pack(fill="x", pady=(16, 0))
    ttk.Label(ready, text="EPISODE 013", style="CardBrass.TLabel").pack(anchor="w")
    ttk.Label(ready, text="Ready for your review", style="CardBig.TLabel").pack(anchor="w",
                                                                                pady=(2, 8))
    checklist(ready, p, [
        ("audio", "Narration and captions saved", "ok"),
        ("video", "Full episode made · 14:32", "ok"),
        ("review", "Your review", "now"),
        ("package", "Upload package", "todo"),
        ("external", "Published", "todo"),
    ])
    ttk.Label(ready, text="Checked 11:06 · local files only", style="CardMuted.TLabel").pack(
        anchor="w", pady=(8, 8))
    button(ready, "Review full episode", "review", accent=True).pack(fill="x")

    main = ttk.Frame(body, padding=(12, 6, 24, 0))
    main.pack(side="left", fill="both", expand=True)
    ttk.Label(main, text="The work outlives the window", style="Title.TLabel").pack(anchor="w")
    ttk.Label(main, text="Episode 013  ·  AI narration, Moth & Gravel voice  ·  Show recipe: "
              "Field Notes standard (1 change)", style="Muted.TLabel").pack(anchor="w",
                                                                           pady=(2, 10))
    stepper(main, p, [("transcript", "Prepare", "Saved 20:47"),
                      ("produce", "Produce", "Saved 21:12"),
                      ("review", "Review", "Needs you"),
                      ("package", "Release", "Not started")], current=2, done=(0, 1)).pack(
        anchor="w", pady=(0, 12))
    stages = ttk.Notebook(main, style="Workspace.TNotebook")
    stages.pack(fill="both", expand=True)
    tab = ttk.Frame(stages, padding=16)
    for glyph, name in (("produce", "Produce"), ("review", "Review"), ("package", "Release")):
        frame = tab if name == "Review" else ttk.Frame(stages)
        stages.add(frame, text=f" {name}", image=icon(stages, glyph,
                   p["SURFACE"] if name == "Review" else p["MUTED"]), compound="left")
    stages.select(1)
    ttk.Label(tab, text="Watch the full episode once with sound, then check the subtitles.",
              style="TLabel").pack(anchor="w")
    actions = ttk.Frame(tab)
    actions.pack(anchor="w", pady=(10, 14))
    button(actions, "Watch full episode", "video").pack(side="left")
    button(actions, "Check subtitles", "captions").pack(side="left", padx=8)
    ttk.Label(actions, text="Opens your video player · 14:32", style="Small.TLabel").pack(
        side="left", padx=8)
    ttk.Label(tab, text="Before you approve", style="Heading.TLabel").pack(anchor="w")
    group = ttk.Frame(tab, padding=(0, 4))
    group.pack(fill="x")
    check(group, text="I watched and listened to the whole episode").pack(anchor="w",
                                                                                   pady=2)
    check(group, text="The subtitles match what is said").pack(anchor="w", pady=2)
    foot = ttk.Frame(tab)
    foot.pack(fill="x", pady=(14, 0))
    ttk.Label(foot, text="Reviewer").pack(side="left")
    name = ttk.Entry(foot, width=18)
    name.insert(0, "Perttu")
    name.pack(side="left", padx=8)
    ttk.Label(foot, text="remembered on this computer", style="Small.TLabel").pack(side="left")
    button(foot, "Approve this episode", "check", accent=True, state="disabled").pack(
        side="right")
    ttk.Label(tab, text="Approval belongs to these exact files. Changing pace, outro or sound "
              "makes a new edition that needs its own review.", style="Muted.TLabel",
              wraplength=640).pack(anchor="w", pady=(14, 0))
    tools = ttk.Frame(main)
    tools.pack(fill="x", pady=(8, 0))
    ttk.Label(tools, text="Tools", style="Small.TLabel").pack(side="left", padx=(0, 6))
    for glyph, label in (("transcript", "Transcript"), ("audio", "Sound"),
                         ("batch", "Several episodes"), ("health", "Setup check")):
        ttk.Button(tools, text=label, image=icon(tools, glyph, p["INK"]), compound="left",
                   style="Compact.TButton").pack(side="left", padx=(0, 4))
    status = ttk.Frame(root, padding=(24, 8, 24, 12))
    status.pack(fill="x")
    ttk.Separator(status).pack(fill="x", pady=(0, 8))
    line = ttk.Frame(status)
    line.pack(fill="x")
    glyph_label(line, "check", "Nothing running · last job: 013 full episode, saved 21:12",
                "Ok.TLabel", p["SUCCESS"]).pack(side="left")
    ttk.Button(line, text="Jobs (0)", image=icon(line, "history", p["INK"]), compound="left",
               style="Compact.TButton").pack(side="right")


def concept_a_release(root, p):
    row = header(root, p)
    button(row, "New episode from a note…", "transcript").pack(side="right")
    main = ttk.Frame(root, padding=(24, 6, 24, 0))
    main.pack(fill="both", expand=True)
    ttk.Label(main, text="The work outlives the window", style="Title.TLabel").pack(anchor="w")
    stepper(main, p, [("transcript", "Prepare", "Saved"), ("produce", "Produce", "Saved"),
                      ("review", "Review", "Approved by Perttu"),
                      ("package", "Release", "Package ready")], current=3,
            done=(0, 1, 2)).pack(anchor="w", pady=(8, 12))
    cols = ttk.Frame(main)
    cols.pack(fill="both", expand=True)
    left = card(cols)
    left.pack(side="left", fill="both", expand=True, padx=(0, 12))
    ttk.Label(left, text="1  Upload to YouTube", style="CardHeading.TLabel").pack(anchor="w")
    ttk.Label(left, text="Copy each field into the matching box in YouTube Studio.",
              style="CardMuted.TLabel").pack(anchor="w", pady=(2, 10))
    for label, value, meta in (
        ("Title", "The work outlives the window | Moth & Gravel Field Notes", "57 / 100"),
        ("Description", "A local production studio grew out of a pipeline…",
         "1,412 / 5,000 bytes"),
        ("Tags", "podcast production, tkinter, local-first, field notes", "212 / 500"),
    ):
        f = ttk.Frame(left, style="Row.TFrame")
        f.pack(fill="x", pady=4)
        ttk.Label(f, text=label, style="CardHeading.TLabel", width=12).pack(side="left")
        ttk.Label(f, text=value, style="Card.TLabel", width=46).pack(side="left")
        ttk.Label(f, text=meta, style="CardMuted.TLabel", width=17).pack(side="left")
        ttk.Button(f, text="Copy", image=icon(f, "copy", p["INK"]), compound="left",
                   style="Compact.TButton").pack(side="right")
    ttk.Label(left, text="Files", style="CardHeading.TLabel").pack(anchor="w", pady=(14, 4))
    for glyph, label, name, size in (("video", "Video", "episode.mp4", "123.5 MB"),
                                     ("folder", "Thumbnail", "thumbnail.png", "212 KB"),
                                     ("captions", "Subtitles", "captions.srt", "18 KB")):
        f = ttk.Frame(left, style="Row.TFrame")
        f.pack(fill="x", pady=3)
        ttk.Label(f, image=icon(f, glyph, p["INK"]), style="Card.TLabel").pack(side="left")
        ttk.Label(f, text=f"  {label}", style="Card.TLabel", width=12).pack(side="left")
        ttk.Label(f, text=name, style="CardMono.TLabel", width=20).pack(side="left")
        ttk.Label(f, text=size, style="CardMuted.TLabel", width=10).pack(side="left")
        ttk.Button(f, text="Copy path", image=icon(f, "copy", p["INK"]), compound="left",
                   style="Compact.TButton").pack(side="right")
    bar = ttk.Frame(left, style="Row.TFrame")
    bar.pack(fill="x", pady=(14, 0))
    button(bar, "Open YouTube Studio", "external", accent=True).pack(side="left")
    button(bar, "Open package folder", "folder").pack(side="left", padx=8)
    ttk.Label(left, text="Package checked 21:40 · matches the approved edition",
              style="CardOk.TLabel").pack(anchor="w", pady=(10, 0))

    right = ttk.Frame(cols)
    right.pack(side="left", fill="y")
    web = card(right)
    web.pack(fill="x")
    ttk.Label(web, text="2  Website and podcast feed", style="CardHeading.TLabel").pack(
        anchor="w")
    ttk.Label(web, text="Adds the finished audio to the note page\nand RSS, as a pull request.",
              style="CardMuted.TLabel").pack(anchor="w", pady=(2, 8))
    button(web, "Prepare website update…", "package").pack(anchor="w")
    ttk.Label(web, text="Today: terminal only (promote, publish)", style="CardWarn.TLabel").pack(
        anchor="w", pady=(8, 0))
    rec = card(right)
    rec.pack(fill="x", pady=(12, 0))
    ttk.Label(rec, text="3  Record where it went live", style="CardHeading.TLabel").pack(
        anchor="w")
    for label, value in (("YouTube link", "Paste after publishing"),
                         ("Published on", "2026-10-17")):
        f = ttk.Frame(rec, style="Row.TFrame")
        f.pack(fill="x", pady=4)
        ttk.Label(f, text=label, style="Card.TLabel", width=13).pack(side="left")
        e = ttk.Entry(f, width=24)
        e.insert(0, value)
        e.pack(side="left")
    links = ttk.Frame(rec, style="Row.TFrame")
    links.pack(fill="x", pady=(2, 8))
    ttk.Button(links, text="Use today", style="Compact.TButton").pack(side="left")
    button(rec, "Save release record", "save", accent=True, state="disabled").pack(anchor="w")
    ttk.Label(rec, text="Studio never checks YouTube; this is your\nrecord of what you did.",
              style="CardMuted.TLabel").pack(anchor="w", pady=(8, 0))


# ----------------------------------------------------------------------------------
# Concept B: one-shot "Make episode"
# ----------------------------------------------------------------------------------


def concept_b_preflight(root, p):
    root.configure(bg=p["PAPER"])
    wrap = ttk.Frame(root, padding=(28, 20, 28, 20))
    wrap.pack(fill="both", expand=True)
    ttk.Label(wrap, text="MOTH & GRAVEL  /  MAKE EPISODE", style="Brand.TLabel").pack(anchor="w")
    ttk.Label(wrap, text="Make Field Note 014 into an episode", style="Title.TLabel").pack(
        anchor="w", pady=(4, 2))
    ttk.Label(wrap, text="Maritime study  ·  1,964 words  ·  script checked 10:02  ·  "
              "show recipe: Field Notes standard", style="Muted.TLabel").pack(anchor="w")
    cols = ttk.Frame(wrap)
    cols.pack(fill="both", expand=True, pady=(16, 0))
    plan = card(cols)
    plan.pack(side="left", fill="both", expand=True, padx=(0, 14))
    ttk.Label(plan, text="What will happen", style="CardHeading.TLabel").pack(anchor="w",
                                                                              pady=(0, 8))
    for glyph, step, detail, tag, kind in (
        ("audio", "Narrate", "3 parts with the cloud voice", "Paid", "warn"),
        ("captions", "Caption", "Timed subtitles from the narration", "Paid", "warn"),
        ("produce", "Finish sound", "Pace 1.15×, motif intro and 5 s outro, −16 LUFS",
         "Local", "ok"),
        ("video", "Make video", "Full video and thumbnail", "Local", "ok"),
        ("review", "Your review", "Watch once, check subtitles, approve", "You", "now"),
        ("package", "Upload package", "Made automatically after you approve", "Local", "ok"),
    ):
        line = ttk.Frame(plan, style="Row.TFrame")
        line.pack(fill="x", pady=5)
        ttk.Label(line, image=icon(line, glyph, p["INK"]), style="Card.TLabel").pack(
            side="left", padx=(0, 10))
        ttk.Label(line, text=step, style="CardHeading.TLabel", width=13).pack(side="left")
        ttk.Label(line, text=detail, style="Card.TLabel", width=44).pack(side="left")
        ttk.Label(line, text=tag, style={"warn": "CardWarn.TLabel", "ok": "CardOk.TLabel",
                                         "now": "CardBrass.TLabel"}[kind]).pack(side="right")
    ttk.Label(plan, text="Reused if already saved: narration parts, captions, sound and video.",
              style="CardMuted.TLabel").pack(anchor="w", pady=(10, 0))
    ttk.Label(plan, text="About 25 minutes of waiting in total; you can close Studio meanwhile.",
              style="CardMuted.TLabel").pack(anchor="w")
    ttk.Label(plan, text="Change recipe…   ·   See request details…", style="CardBrass.TLabel"
              ).pack(anchor="w", pady=(10, 0))

    money = card(cols)
    money.pack(side="left", fill="y")
    ttk.Label(money, text="Cloud spending", style="CardHeading.TLabel").pack(anchor="w")
    for label, value in (("Project", "mothandgravel-audio"), ("Estimate", "about $0.12"),
                         ("Spend guard", "stop after 2 failed attempts"),
                         ("", "on any part, then ask me")):
        f = ttk.Frame(money, style="Row.TFrame")
        f.pack(fill="x", pady=3)
        ttk.Label(f, text=label, style="CardMuted.TLabel", width=12).pack(side="left")
        ttk.Label(f, text=value, style="Card.TLabel").pack(side="left")
    ttk.Label(money, text="Estimate is from the script length.\nFailed attempts may still be "
              "billed;\nStudio never retries on its own.", style="CardMuted.TLabel").pack(
        anchor="w", pady=(10, 12))
    check(money, style="Card.TCheckbutton",
                    text="Allow paid narration and captions\nfor this episode").pack(
        anchor="w")
    foot = ttk.Frame(wrap)
    foot.pack(fill="x", pady=(16, 0))
    ttk.Button(foot, text="Cancel").pack(side="left")
    button(foot, "Make episode", "produce", accent=True, state="disabled").pack(side="right")
    ttk.Label(foot, text="Nothing is published. You approve before any upload package is made.",
              style="Muted.TLabel").pack(side="right", padx=14)


def timeline(parent, p, rows):
    for glyph, name, state, detail, kind in rows:
        line = ttk.Frame(parent, style="Row.TFrame")
        line.pack(fill="x", pady=4)
        colour = {"ok": p["SUCCESS"], "run": p["BRASS"], "todo": p["MUTED"],
                  "warn": p["WARNING"], "you": p["BRASS"]}[kind]
        mark = {"ok": "check", "todo": "pending", "warn": "health"}.get(kind, glyph)
        ttk.Label(line, image=icon(line, mark, colour), style="Card.TLabel").pack(
            side="left", padx=(0, 10))
        ttk.Label(line, text=name, style="CardHeading.TLabel", width=14).pack(side="left")
        ttk.Label(line, text=state, width=14, style={
            "ok": "CardOk.TLabel", "run": "CardBrass.TLabel", "todo": "CardMuted.TLabel",
            "warn": "CardWarn.TLabel", "you": "CardBrass.TLabel"}[kind]).pack(side="left")
        ttk.Label(line, text=detail, style="CardMuted.TLabel").pack(side="left")


def concept_b_progress(root, p):
    row = header(root, p, "MAKE EPISODE")
    ttk.Button(row, text="Hide", style="Compact.TButton").pack(side="right")
    wrap = ttk.Frame(root, padding=(24, 6, 24, 18))
    wrap.pack(fill="both", expand=True)
    ttk.Label(wrap, text="Field Note 014 · Maritime study", style="Title.TLabel").pack(anchor="w")
    ttk.Label(wrap, text="Started 10:04 · you can close Studio; the worker keeps going",
              style="Muted.TLabel").pack(anchor="w", pady=(2, 12))
    box = card(wrap, padding=18)
    box.pack(fill="x")
    timeline(box, p, [
        ("audio", "Narrate", "Saved", "3 of 3 parts · 10:04 – 10:11", "ok"),
        ("captions", "Caption", "Saved", "Checked against narration · 10:13", "ok"),
        ("produce", "Finish sound", "Saved", "−16.1 LUFS · peak −1.2 dBTP · 10:14", "ok"),
        ("video", "Make video", "Working", "Rendering · 4 min elapsed · 6–9 min on this computer before", "run"),
        ("review", "Your review", "Next", "We will tell you when it is ready", "todo"),
        ("package", "Upload package", "After review", "Local, automatic once approved", "todo"),
    ])
    note = ttk.Frame(wrap)
    note.pack(fill="x", pady=(14, 0))
    check(note, text="Show a desktop notification when my review is needed").pack(
        side="left")
    ttk.Button(note, text="Stop after this step", image=icon(note, "stop", p["INK"]),
               compound="left").pack(side="right")


def concept_b_incident(root, p):
    row = header(root, p, "MAKE EPISODE")
    ttk.Button(row, text="Hide", style="Compact.TButton").pack(side="right")
    wrap = ttk.Frame(root, padding=(24, 6, 24, 18))
    wrap.pack(fill="both", expand=True)
    ttk.Label(wrap, text="Field Note 014 · Maritime study", style="Title.TLabel").pack(anchor="w")
    ttk.Label(wrap, text="Paused 12:41 · nothing is running · nothing will be sent until you "
              "choose", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))
    alert = ttk.Frame(wrap, style="Attention.TFrame", padding=16)
    alert.pack(fill="x")
    ttk.Label(alert, text="The narration service is failing, so Studio paused",
              style="AttentionHead.TLabel").pack(anchor="w")
    ttk.Label(alert, text="Part 3 of 3 failed three times in a row: a gateway error, a cancelled "
              "request and no reply. Parts 1 and 2 are saved and safe. The spend guard "
              "stopped further attempts.",
              style="Attention.TLabel", wraplength=1000).pack(anchor="w", pady=(4, 10))
    table = ttk.Treeview(alert, columns=("when", "result", "waited", "billing"), show="headings",
                         height=3)
    for col, label, width in (("when", "Attempt", 150), ("result", "What came back", 380),
                              ("waited", "Waited", 110), ("billing", "Billing", 260)):
        table.heading(col, text=label, anchor="w")
        table.column(col, width=width, anchor="w")
    for values in (
        ("1 · 10:07", "502 Bad Gateway from the service", "4 min 0 s", "Unknown; may be billed"),
        ("2 · 11:02", "499 Request cancelled before reply", "2 min 11 s", "Unknown; may be billed"),
        ("3 · 11:39", "No reply within the 10-minute limit", "10 min 0 s",
         "Unknown; may be billed"),
    ):
        table.insert("", "end", values=values)
    table.pack(fill="x")
    ttk.Label(alert, text="Up to 3 uncertain attempts × about $0.04 = at most about $0.12 extra. "
              "Check actual charges in the Cloud billing console.",
              style="AttentionMuted.TLabel").pack(anchor="w", pady=(8, 12))
    acts = ttk.Frame(alert, style="AttRow.TFrame")
    acts.pack(fill="x")
    button(acts, "Try part 3 once more…", "refresh", accent=True).pack(side="left")
    button(acts, "Pause until I come back", "stop").pack(side="left", padx=8)
    button(acts, "Open billing console", "external").pack(side="left")
    button(acts, "Copy diagnostics", "copy").pack(side="right")
    ttk.Label(wrap, text="Try once more asks for duplicate-charge consent for part 3 only, and "
              "counts against the same spend guard as the terminal command.",
              style="Muted.TLabel").pack(anchor="w", pady=(12, 10))
    box = card(wrap)
    box.pack(fill="x")
    timeline(box, p, [
        ("audio", "Narrate", "Paused", "2 of 3 parts saved · part 3: provider failing", "warn"),
        ("captions", "Caption", "Waiting", "Starts after narration", "todo"),
        ("produce", "Finish sound", "Waiting", "Local", "todo"),
        ("video", "Make video", "Waiting", "Local", "todo"),
    ])


def concept_c_review(root, p):
    row = header(root, p)
    button(row, "New episode from a note…", "transcript").pack(side="right")
    wrap = ttk.Frame(root, padding=(24, 4, 24, 0))
    wrap.pack(fill="both", expand=True)
    ttk.Label(wrap, text="Review · The work outlives the window", style="Title.TLabel").pack(
        anchor="w")
    player = card(wrap, padding=10)
    player.pack(fill="x", pady=(10, 10))
    ttk.Button(player, text="Play", image=icon(player, "produce", p["INK"]), compound="left",
               style="Compact.TButton").pack(side="left")
    ttk.Label(player, text="  03:42 / 14:32", style="CardHeading.TLabel").pack(side="left")
    bar = tk.Canvas(player, height=30, width=760, bg=p["SURFACE"], highlightthickness=0)
    bar.pack(side="left", padx=14)
    bar.create_line(0, 15, 760, 15, fill=p["LINE"], width=4)
    bar.create_line(0, 15, 194, 15, fill=p["BRASS"], width=4)
    for x, colour in ((120, p["WARNING"]), (430, p["WARNING"]), (612, p["SUCCESS"])):
        bar.create_rectangle(x - 2, 4, x + 2, 26, fill=colour, outline="")
    for x, t in ((0, "Narration 1"), (262, "Narration 2"), (520, "Narration 3")):
        bar.create_text(x + 4, 28, text=t, anchor="sw", fill=p["MUTED"], font=("DejaVu Sans", 7))
    ttk.Label(player, text="Audio plays in Studio",
              style="CardMuted.TLabel").pack(side="left")
    cols = ttk.Frame(wrap)
    cols.pack(fill="both", expand=True)
    script = card(cols, padding=0)
    script.pack(side="left", fill="both", expand=True, padx=(0, 12))
    tree = ttk.Treeview(script, columns=("time", "text", "flag"), show="headings", height=13)
    for col, label, width in (("time", "Time", 70), ("text", "What is said (caption)", 640),
                              ("flag", "Your note", 150)):
        tree.heading(col, text=label, anchor="w")
        tree.column(col, width=width, anchor="w")
    rows = (
        ("03:21", "The window closes, and the job keeps its place in the queue.", ""),
        ("03:27", "A worker that survives the window has to say what it knows.", ""),
        ("03:34", "Not what it hopes. What it knows.", ""),
        ("03:42", "Tee-kay-inter gave us a desktop without a build step.", "Pronunciation"),
        ("03:49", "Every stage writes a small journal entry before it moves on.", ""),
        ("03:55", "So when the lights go out, the journal still remembers.", ""),
        ("04:02", "Retry is a new job with the same recipe, not a resend.", "Caption typo"),
        ("04:10", "That distinction costs a sentence and saves a bill.", ""),
        ("04:16", "The review belongs to the bytes, not to the button.", ""),
        ("04:23", "Change the outro and the approval stays with the old file.", ""),
    )
    for i, values in enumerate(rows):
        tree.insert("", "end", iid=str(i), values=values)
    tree.selection_set("3")
    tree.pack(fill="both", expand=True)
    side = card(cols)
    side.pack(side="left", fill="y")
    ttk.Label(side, text="Selected line · 03:42", style="CardHeading.TLabel").pack(anchor="w")
    ttk.Label(side, text="“Tee-kay-inter gave us a desktop\nwithout a build step.”",
              style="Card.TLabel").pack(anchor="w", pady=(6, 10))
    for glyph, text in (("produce", "Play from here"), ("captions", "Fix caption text"),
                        ("audio", "Re-narrate this part… (paid)")):
        ttk.Button(side, text=text, image=icon(side, glyph, p["INK"]), compound="left").pack(
            fill="x", pady=3)
    ttk.Separator(side).pack(fill="x", pady=12)
    ttk.Label(side, text="2 notes to resolve", style="CardWarn.TLabel").pack(anchor="w")
    ttk.Label(side, text="Pronunciation at 03:42\nCaption typo at 04:02",
              style="CardMuted.TLabel").pack(anchor="w", pady=(4, 12))
    ttk.Label(side, text="Watched to the end: 14:32 of 14:32", style="CardOk.TLabel").pack(
        anchor="w")
    button(side, "Approve episode", "check", accent=True, state="disabled").pack(fill="x",
                                                                                 pady=(10, 0))
    ttk.Label(side, text="Resolve or dismiss notes first.", style="CardMuted.TLabel").pack(
        anchor="w", pady=(6, 0))


def concept_b_home(root, p):
    """B's Studio home: the shelf becomes a work list grouped by who acts next."""
    row = header(root, p)
    button(row, "Make episode from a note…", "produce", accent=True).pack(side="right")
    wrap = ttk.Frame(root, padding=(24, 6, 24, 18))
    wrap.pack(fill="both", expand=True)
    for heading, rows in (
        ("Needs you", [("review", "013 · The work outlives the window", "Review full episode",
                        "Made 21:12 · 14:32", True),
                       ("health", "014 · Maritime study", "Narration paused · provider failing",
                        "Spend guard stopped part 3", True)]),
        ("Working", [("video", "012 · Coastal watch", "Making video · 4 min elapsed",
                      "Review next", False)]),
        ("Ready to publish", [("package", "011 · Specimen return", "Upload package checked",
                               "Not yet recorded as published", False)]),
    ):
        ttk.Label(wrap, text=heading.upper(), style="Heading.TLabel").pack(anchor="w",
                                                                           pady=(12, 4))
        for glyph, title, state, meta, act in rows:
            c = card(wrap, padding=10)
            c.pack(fill="x", pady=3)
            colour = p["WARNING"] if glyph == "health" else p["BRASS"] if act else p["INK"]
            ttk.Label(c, image=icon(c, glyph, colour), style="Card.TLabel").pack(
                side="left", padx=(4, 12))
            ttk.Label(c, text=title, style="CardHeading.TLabel", width=34).pack(side="left")
            ttk.Label(c, text=state, style="Card.TLabel", width=36).pack(side="left")
            ttk.Label(c, text=meta, style="CardMuted.TLabel").pack(side="left")
            ttk.Button(c, text="Open", style="Compact.TButton").pack(side="right")
    ttk.Label(wrap, text="DONE · 10 episodes", style="Heading.TLabel").pack(anchor="w",
                                                                           pady=(14, 0))


SCREENS = {
    "a-review-polished": (concept_a_main, (1280, 860), False),
    "a-review-polished-night": (concept_a_main, (1280, 860), True),
    "a-release-one-page": (concept_a_release, (1280, 760), False),
    "b-home-work-list": (concept_b_home, (1280, 700), False),
    "b-make-episode-preflight": (concept_b_preflight, (1180, 620), False),
    "b-progress-timeline": (concept_b_progress, (1180, 560), False),
    "b-provider-failure-spend-guard": (concept_b_incident, (1180, 760), False),
    "c-transcript-review": (concept_c_review, (1280, 700), False),
}


def grab(root, path):
    root.event_generate("<Motion>", warp=True, x=root.winfo_width() - 2, y=root.winfo_height() - 2)
    root.update()
    subprocess.run(["ffmpeg", "-v", "error", "-f", "x11grab", "-draw_mouse", "0",
                    "-video_size", f"{root.winfo_width()}x{root.winfo_height()}",
                    "-i", f"{os.environ['DISPLAY']}+{root.winfo_rootx()},{root.winfo_rooty()}",
                    "-frames:v", "1", "-update", "1", "-y", str(path)], check=True, timeout=15)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[2:])
    for name, (build, (w, h), night) in SCREENS.items():
        if only and name not in only:
            continue
        # Fresh interpreter per screen keeps palettes independent.
        if os.environ.get("MOCK_CHILD") != name:
            subprocess.run([sys.executable, __file__, str(out), name], check=True,
                           env={**os.environ, "MOCK_CHILD": name})
            continue
        root = tk.Tk()
        root.geometry(f"{w}x{h}+0+0")
        p = style(root, night)
        build(root, p)
        root.update()
        root.after(300)
        grab(root, out / f"{name}.png")
        root.destroy()


if __name__ == "__main__":
    main()
