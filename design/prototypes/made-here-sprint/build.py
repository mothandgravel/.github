#!/usr/bin/env python3
"""Build the Made here sprint prototypes.

Unpublished: everything is written under design/prototypes/made-here-sprint/, outside
docs/, so GitHub Pages never serves it. Home variants are generated from the live
docs/index.html with one inserted section each, so the surrounding home stays exact.
Serve the repository root (python3 -m http.server 8790) and open
/design/prototypes/made-here-sprint/.
"""
from __future__ import annotations

import html
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOCS = ROOT / "docs"

# ---------------------------------------------------------------- the body of work
# One studio, one body of work. Product names stay; no organisation names appear.
STATUS = {
    "production": "In production for our own work",
    "playable": "Playable today",
    "prototype": "Prototype",
    "study": "Study",
    "internal": "Internal tool",
}

THINGS = [
    dict(key="docket", name="Decision Docket", status="production",
         what="A workspace for the decisions and evidence behind software work. Our own tool, in production for our own work.",
         note="Shown with synthetic captures only. The real workspace holds private work.",
         asks=["how-old", "take-back", "green-light"], links=[("Try the same week in two shapes", "toy:week")]),
    dict(key="cybergrid", name="Cyber Grid", status="playable",
         what="A daily logic puzzle: visit every node once, in jumps. Each day’s board is checked for a route before anyone plays it.",
         asks=["green-light"], links=[("Ask whether a board can be finished", "toy:grid"), ("Play Cyber Grid", "ext:https://cyber-grid-164542994548.europe-north1.run.app/")]),
    dict(key="raivari", name="Raivari", status="prototype",
         what="The framework under our maritime study and Coastal watch.",
         asks=["how-old"], links=[("The maritime study", "docs:specimens/maritime-study/"), ("Coastal watch", "docs:specimens/coastal-watch/")]),
    dict(key="ajo", name="Ajo", status="prototype",
         what="Checked plans for agents, with their execution recorded. A lost reply is not a no.",
         asks=["take-back", "green-light"], links=[("The saved simulator case", "docs:index.html#specimen-ajo")]),
    dict(key="skystack", name="SkyStack Builder", status="prototype",
         what="An island builder for Windows. One intended gesture should come back with one undo.",
         asks=["take-back"], links=[("Field note 008", "docs:notes/008-one-undo.html"), ("Try one undo", "toy:stamp")]),
    dict(key="geaidnu", name="Geaidnu", status="prototype",
         what="A calm cockpit for work in progress. A finished task is not yet a proven one.",
         asks=["green-light"], links=[("Field note 005", "docs:notes/005-green-light.html")]),
    dict(key="liveconnect", name="LiveConnect", status="study",
         what="A streaming study, parked. The connection came back; did the picture?",
         asks=["how-old"], links=[("Specimen 004", "docs:specimens/connected-to-what/")]),
    dict(key="buggy", name="Kitronik buggy", status="study",
         what="A small robot in a cardboard arena, and the maps it leaves behind.",
         asks=["how-old"], links=[("Whose map?", "docs:specimens/whose-map/")]),
    dict(key="rpc", name="raivari-rpc", status="study",
         what="An exploration of host and agent. An agent may ask; the host decides.",
         asks=["take-back"], links=[]),
    dict(key="flutter", name="flutter-test-rs", status="prototype",
         what="A Flutter test runner that minds the machine it runs on.",
         asks=["green-light"], links=[]),
    dict(key="paja", name="paja", status="internal",
         what="Spare machines on one network, building together.",
         asks=["take-back", "green-light"], links=[]),
    dict(key="studio", name="Field Notes studio", status="production",
         what="The desktop workbench that makes the recordings of these notes.",
         asks=["window"], links=[("Field note 013", "docs:notes/013-work-outlives-the-window.html")]),
]
BY_KEY = {t["key"]: t for t in THINGS}

INVESTIGATIONS = [
    dict(slug="how-old", n="01", q="How old is what I’m seeing?", short="How old is it?",
         lead="A picture keeps looking current after its source has gone quiet. A mark stays on the chart. A reading stays on the dial. We keep asking how a screen should carry the age of what it shows.",
         things=["raivari", "liveconnect", "docket", "buggy"],
         notes=[("012", "The picture stays.", "012-the-picture-stays.html"), ("014", "Enough light to read by.", "014-enough-light-to-read-by.html"), ("006", "A map should leave room for doubt.", "006-map-leaves-room.html"), ("007", "Fast signals. Slow eyes.", "007-fast-signals.html")],
         specimens=[("005", "Coastal watch", "specimens/coastal-watch/"), ("006", "The maritime study", "specimens/maritime-study/"), ("004", "LiveConnect", "specimens/connected-to-what/"), ("003", "Whose map?", "specimens/whose-map/")],
         toy="week", toy_title="The same week, in two shapes.",
         toy_lead="Six fictional items from a Decision Docket-style recap. Each carries the revision it was captured at. Change the shape and watch what the drawing implies about time.",
         toy_scope="Authored, fictional items. Not a capture of any real workspace, and not the product’s interface.",
         distinction=("The source. Its capture. Its age.", "A captured revision is a fixed point. The screen should say when it was taken, and never let a newer-looking picture lend it time it does not have.")),
    dict(slug="take-back", n="02", q="Did it happen, and can I take it back?", short="Did it happen?",
         lead="A press disappears. A reply never comes. A whole staircase goes down in one click. The work may already be done, and the way back has to match the thing someone believed they did.",
         things=["ajo", "skystack", "docket", "rpc", "paja"],
         notes=[("008", "A whole staircase. One undo.", "008-one-undo.html"), ("005", "A green light should mean something.", "005-green-light.html"), ("004", "A control should stay where you left it.", "004-controls-stay-put.html")],
         specimens=[("001", "Ajo / a missing reply", "index.html#specimen-ajo"), ("002", "SkyStack / the thing you just tried", "index.html#specimen-skystack")],
         toy="stamp", toy_title="One gesture. One undo.",
         toy_lead="Place a stamp on a small island. Every cell is checked before anything is spent. A placement becomes one entry in history, and Undo either takes the whole thing back or says plainly that it could not.",
         toy_scope="A rules sketch written from the source study in Field Note 008. No game code, art or assets; not a capture of SkyStack Builder.",
         distinction=("The action. Its reply. The way back.", "A missing answer does not mean nothing happened. An undo that cannot find what it placed should keep its record, not guess.")),
    dict(slug="green-light", n="03", q="What does a green light promise?", short="What does green promise?",
         lead="Running. Passing. Finished. Each small light answers a different question, and the colour travels more easily than the meaning. We keep asking what a signal lets someone stop worrying about.",
         things=["geaidnu", "flutter", "docket", "cybergrid"],
         notes=[("005", "A green light should mean something.", "005-green-light.html"), ("013", "The work outlives the window.", "013-work-outlives-the-window.html")],
         specimens=[("001", "Ajo / a missing reply", "index.html#specimen-ajo")],
         toy="grid", toy_title="Can this board be finished?",
         toy_lead="Cyber Grid checks every daily board for a route before anyone plays it. Here is that check on a smaller board. Place obstacles, then ask. Shrink the search budget and watch “not found” stop meaning “no”.",
         toy_scope="A 5 × 5 reduction using the game’s jump rule and route search, restyled. The game itself plays on a larger board.",
         distinction=("The observation. The conclusion.", "A search that ran out of budget has not found a no. A route the reader can check is worth more than a tick.")),
    dict(slug="window", n="04", q="What survives closing the window?", short="What survives?",
         lead="An episode is rendering. You close its window. When you come back, what should still be there, and what should ask for your attention again?",
         things=["studio", "docket"],
         notes=[("013", "The work outlives the window.", "013-work-outlives-the-window.html")],
         specimens=[], toy=None, forming=True,
         distinction=("The view. The work. The record.", "The window may disappear. The job, its recipe and its review should not.")),
]
INV = {i["slug"]: i for i in INVESTIGATIONS}
CORE = [i for i in INVESTIGATIONS if not i.get("forming")]

TOYS = {
    "stamp": ("One gesture. One undo.", "SkyStack Builder", "take-back"),
    "grid": ("Can this board be finished?", "Cyber Grid", "green-light"),
    "week": ("The same week, two shapes.", "Decision Docket", "how-old"),
}

# ---------------------------------------------------------------- helpers
e = html.escape


def rel(page: Path, target: Path) -> str:
    r = os.path.relpath(target, page.parent).replace(os.sep, "/")
    return r + ("/" if target.suffix == "" and not r.endswith("/") else "")


def docs(page: Path, path: str) -> str:
    anchor = ""
    if "#" in path:
        path, anchor = path.split("#", 1)
        anchor = "#" + anchor
    return rel(page, DOCS / path) + anchor if path else rel(page, DOCS) + anchor


def status(key: str) -> str:
    return f'<span class="status" data-status="{key}">{STATUS[key]}</span>'


def link_for(page: Path, concept: str, href: str) -> tuple[str, str]:
    """Return (href, extra attributes)."""
    kind, _, value = href.partition(":")
    if kind == "docs":
        return docs(page, value), ""
    if kind == "ext":
        return value, ' rel="noopener noreferrer"'
    if kind == "toy":
        inv = TOYS[value][2]
        if concept == "b":
            return rel(page, HERE / "b/investigations" / inv / "index.html") + "#try", ""
        return rel(page, HERE / concept / "workbench/playground/index.html") + f"#{value}", ""
    raise ValueError(href)


def links(page: Path, concept: str, items) -> str:
    out = []
    for label, href in items:
        h, extra = link_for(page, concept, href)
        out.append(f'<li><a href="{e(h)}"{extra}>{e(label)} <span aria-hidden="true">↗</span></a></li>')
    return f'<ul class="mini-links">{"".join(out)}</ul>' if out else ""


def inv_href(page: Path, concept: str, slug: str) -> str:
    if concept == "c":
        return rel(page, HERE / "c/workbench/playground/index.html") + f"#{slug}"
    return rel(page, HERE / concept / "investigations" / slug / "index.html")


CONCEPT_NAMES = {"a": "A / The ledger", "b": "B / Standing questions", "c": "C / The open drawer"}


def banner(page: Path, concept: str | None) -> str:
    hub = rel(page, HERE / "index.html")
    name = CONCEPT_NAMES.get(concept, "Concept index")
    return (f'<div class="proto-banner" role="note"><div class="shell"><span class="mono">UNPUBLISHED PROTOTYPE / {e(name.upper())}</span>'
            f'<span>A design sprint concept, not a live page. <a href="{hub}">All concepts</a></span></div></div>')


# ---------------------------------------------------------------- page shell
SHELL_HEAD = """<!doctype html>
<html lang="en" data-theme="night">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#17191b">
<meta name="robots" content="noindex, nofollow">
<meta name="color-scheme" content="dark light">
<link rel="icon" href="{d}assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{d}assets/site.css">
{css}
<script>document.documentElement.classList.add("has-js")</script>
<script src="{d}assets/site.js" defer></script>
{js}
<title>{title} — Moth &amp; Gravel (prototype)</title>
<script>(()=>{{let t;try{{t=localStorage.getItem("moth-and-gravel-theme")}}catch(_){{}}const d=document.documentElement,c=t==="afterlight"||t==="night"?t:"system";d.dataset.themeChoice=c;d.dataset.theme=c!=="system"?c:matchMedia("(prefers-color-scheme: light)").matches?"afterlight":"night"}})()</script>
</head>
<body class="{body_class}">
<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header" id="top">
<div class="header-inner shell">
<a class="brand" href="{home}" title="Moth &amp; Gravel home">
<span class="brand-stamp" aria-hidden="true"><img src="{d}assets/nav-mark.svg" width="44" height="44" alt=""></span>
<span class="brand-type">MOTH <span class="brand-amp">&amp;</span> GRAVEL<span class="brand-sub">INDEPENDENT WORKS</span></span>
</a>
<nav class="main-nav" id="primary-nav" aria-label="Main navigation"><a href="{home}">The studio</a><a href="{d}notes/">Field notes</a><a href="{d}questions/">Bring a question</a></nav>
<p class="header-mail"><a class="header-mail-link" href="mailto:hello@mothandgravel.com?subject=A%20question%20for%20Moth%20%26%20Gravel"><span class="header-mail-short">Email </span><span class="header-mail-address">hello@mothandgravel.com</span></a><button class="copy-mail" type="button" data-copy-email hidden>Copy<span class="visually-hidden"> email address</span></button></p>
<div class="header-actions">
<button class="light-switch" id="light-switch" type="button"><span class="switch-orb" aria-hidden="true"></span><span class="switch-label"><span class="visually-hidden">Theme: </span><span data-theme-label>System</span></span></button>
<button class="menu-toggle" id="menu-toggle" type="button" aria-expanded="false" aria-controls="primary-nav">
<span>Menu</span><span class="menu-bars" aria-hidden="true"><span></span><span></span></span>
</button>
</div>
</div>
</header>
{banner}
<main id="main" class="shell proto-main">
{body}
</main>
<footer class="shell journey-footer"><a href="{home}">Moth &amp; Gravel / Independent works</a><p class="footer-mail"><a href="mailto:hello@mothandgravel.com?subject=Hello%2C%20Moth%20%26%20Gravel">hello@mothandgravel.com</a><button class="copy-mail" type="button" data-copy-email hidden>Copy<span class="visually-hidden"> email address</span></button></p><span class="mono">DRAWN TO LIGHT. BUILT FOR ROUGH GROUND.</span></footer>
</body>
</html>
"""


def write_page(path: Path, concept: str | None, title: str, body: str, *, toys=False, extra_css=(), body_class="proto-page"):
    path.parent.mkdir(parents=True, exist_ok=True)
    d = docs(path, "")
    shared = HERE / "shared"
    css = [rel(path, shared / "concepts.css")] + [rel(path, shared / "playground.css")] * bool(toys) + [docs(path, c) for c in extra_css]
    js = f'<script src="{rel(path, shared / "lazy.js")}" defer></script>' if toys else ""
    home = rel(path, HERE / concept / "index.html") if concept else d
    path.write_text(SHELL_HEAD.format(
        d=d, css="\n".join(f'<link rel="stylesheet" href="{c}">' for c in css), js=js, title=e(title),
        body_class=body_class, home=home, banner=banner(path, concept), body=body))


def toy_bench(page: Path, concept: str, key: str, inv: dict | None = None, heading="h2") -> str:
    title, product, slug = TOYS[key]
    i = inv or INV[slug]
    ask = inv_href(page, concept, slug)
    return f"""<section class="bench" id="{key}" aria-labelledby="{key}-title">
<div class="bench-head"><div><p class="mono">{e(product.upper())} / ASKS: {e(i['short'].upper())}</p><{heading} id="{key}-title">{e(i['toy_title'])}</{heading}></div>
<div><p>{e(i['toy_lead'])}</p><a class="editorial-link" href="{ask}">{e(i['q'])} <span aria-hidden="true">↗</span></a></div></div>
<div class="toy-mount" id="toy-{key}" data-toy="{key}"><p>The toy loads when it comes into view. It needs JavaScript; the description above stands on its own.</p></div>
<p class="bench-scope">{e(i['toy_scope'])}</p>
</section>"""


# ---------------------------------------------------------------- home variants
def home_variant(concept: str, transform) -> None:
    out = HERE / concept / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    src = (DOCS / "index.html").read_text()
    prefix = docs(out, "")
    src = re.sub(r'(href|src|srcset)="\./', lambda m: f'{m.group(1)}="{prefix}', src)
    src = re.sub(r"(srcset=\"[^\"]*)", lambda m: m.group(1).replace(", ./", ", " + prefix), src)
    src = src.replace("['.work-grid','./assets/", f"['.work-grid','{prefix}assets/").replace("['#moth-interlude','./assets/", f"['#moth-interlude','{prefix}assets/")
    src = src.replace('<meta name="robots" content="index, follow">', '<meta name="robots" content="noindex, nofollow">')
    src = re.sub(r'<link rel="canonical"[^>]*>\n?', "", src)
    src = re.sub(r"<!-- owner:[^>]*-->\n?", "", src)
    src = re.sub(r'<script type="application/ld\+json">.*?</script>', "", src, flags=re.S)
    src = src.replace("<!-- home-style:end -->", f'<!-- home-style:end -->\n<link rel="stylesheet" href="{rel(out, HERE / "shared/concepts.css")}">')
    src = src.replace('<main id="main">', banner(out, concept) + '\n<main id="main">', 1)
    new = transform(out, src)
    assert new != src, concept
    out.write_text(new)


def made_here_ledger(page: Path) -> str:
    rows = []
    for t in THINGS:
        asks = " ".join(f'<a class="line-link" href="{inv_href(page, "a", s)}">{e(INV[s]["q"])}</a><br>' for s in t["asks"])
        note = f'<p class="made-note">{e(t["note"])}</p>' if t.get("note") else ""
        rows.append(f"""<li id="made-{t['key']}"><h3>{e(t['name'])}</h3><div><p>{e(t['what'])}</p>{note}{links(page, "a", t['links'])}</div>{status(t['status'])}<p class="ledger-asks"><span>KEEPS ASKING</span>{asks}</p></li>""")
    legend = "".join(f"<li>{status(k)}</li>" for k in STATUS)
    play = rel(page, HERE / "a/workbench/playground/index.html")
    return f"""<section class="made-section shell section-space" id="made-here" aria-labelledby="made-title">
<div class="section-kicker mono"><span>MADE HERE</span><span>ONE STUDIO / TWELVE THINGS / PLAIN STATUS</span></div>
<div class="section-lead"><h2 id="made-title">Made here.<br><em>Said plainly.</em></h2>
<p>Everything on this list was made at this bench. Some of it is in daily use. One of it you can play today. Most of it is still a prototype or a study, and each line says which.</p></div>
<ul class="ledger-legend" aria-label="What each status means">{legend}</ul>
<ol class="ledger">{''.join(rows)}</ol>
<div class="ledger-more"><a class="editorial-link" href="{play}">Try three of them in the playground <span aria-hidden="true">↗</span></a><a class="editorial-link" href="{inv_href(page, 'a', 'how-old')}">Follow a question across them <span aria-hidden="true">↗</span></a></div>
</section>
"""


def concept_a(out: Path, src: str) -> str:
    return src.replace('<section id="field-notes"', made_here_ledger(out) + '\n<section id="field-notes"', 1)


def concept_b(out: Path, src: str) -> str:
    cards = []
    for i in CORE:
        mats = "".join(f"<li>{e(BY_KEY[k]['name'])}</li>" for k in i["things"])
        cards.append(f"""<li class="question-card"><p class="mono">STANDING INVESTIGATION / {i['n']}</p><h3><a href="{inv_href(out, 'b', i['slug'])}">{e(i['q'])}</a></h3>
<p>{e(i['lead'])}</p>
<div><p class="mono">{len(i['notes'])} NOTES · {len(i['specimens'])} SPECIMENS · ONE THING TO TRY</p><ul class="question-materials" aria-label="Made here, and asking this">{mats}</ul></div></li>""")
    roll = "".join(f"<li><strong>{e(t['name'])}</strong>{status(t['status'])}</li>" for t in THINGS)
    w = INV["window"]
    section = f"""<section class="made-section section-space" id="investigations" aria-labelledby="inv-title"><div class="shell">
<div class="section-kicker mono"><span>STANDING INVESTIGATIONS</span><a href="{rel(out, HERE / 'b/investigations/index.html')}">ALL THREE QUESTIONS ↗</a></div>
<div class="section-lead"><h2 id="inv-title">Three questions.<br><em>Still open.</em></h2>
<p>Everything we make ends up asking one of these. Each question gathers the notes, specimens and things that keep returning to it, and one small thing you can try.</p></div>
<ol class="questions-grid">{''.join(cards)}</ol>
<p class="question-forming"><span class="mono">FORMING / {w['n']}</span> {e(w['q'])} One note so far. It becomes a standing question when a second piece of work asks it.</p>
<div class="made-roll"><div class="section-kicker mono"><span>MADE HERE / WHERE THE QUESTIONS COME FROM</span><span>ONE STUDIO</span></div><ul>{roll}</ul></div>
</div></section>
"""
    return src.replace('<section id="work"', section + '<section id="work"', 1)


def concept_c(out: Path, src: str) -> str:
    items = "".join(f"<li><div><strong>{e(t['name'])}</strong>{status(t['status'])}</div><p>{e(t['what'])}</p></li>" for t in THINGS)
    play = rel(out, HERE / "c/workbench/playground/index.html")
    wb = docs(out, "workbench/")
    block = f"""<div class="shelf" id="made-here" aria-labelledby="shelf-title">
<div><p class="mono section-kicker">MADE HERE / ONE STUDIO</p><h3 id="shelf-title">Also on<br><em>the shelf.</em></h3><p>The specimens above come from these. Each one says how far along it is.</p><a class="editorial-link" href="{play}">Pick one up in the playground <span aria-hidden="true">↗</span></a></div>
<ul class="shelf-list">{items}</ul></div>
<div class="rooms" aria-label="Two rooms on the bench">
<article class="room-door"><p class="mono">ROOM 01 / AN EXAMPLE STUDY</p><h3>The mending notebook.</h3><p>A fictional question, two approaches and a doubt worth keeping. A preview of working together.</p><a class="editorial-link" href="{wb}">Look inside <span aria-hidden="true">↗</span></a></article>
<article class="room-door"><p class="mono">ROOM 02 / THE PLAYGROUND</p><h3>Three drawers. Three questions.</h3><p>Small working pieces of real projects, each filed under the question it keeps asking. Open a drawer and try one.</p><a class="editorial-link" href="{play}">Open the drawers <span aria-hidden="true">↗</span></a></article>
</div>
"""
    return src.replace('<div class="bench-ledger">', block + '<div class="bench-ledger">', 1)


# ---------------------------------------------------------------- sub-pages
def note_link(page, n):
    return docs(page, "notes/" + n[2])


def playground_a() -> None:
    p = HERE / "a/workbench/playground/index.html"
    benches = "".join(toy_bench(p, "a", k) for k in ("stamp", "grid", "week"))
    body = f"""<div class="proto-top mono"><span>THE WORKBENCH / PLAYGROUND</span><a href="{rel(p, HERE / 'a/index.html')}#made-here">Back to Made here ↗</a></div>
<nav aria-label="Workbench rooms"><ul class="room-tabs"><li><a href="{docs(p, 'workbench/')}"><span class="mono">01</span> The example study</a></li><li><a href="#main" aria-current="page"><span class="mono">02</span> The playground</a></li></ul></nav>
<div class="proto-head"><div><h1>Pick it up.<br><em>Put it back.</em></h1></div><div><p>Three small working pieces of things made here. Each is a reduction: one rule, honestly cut down, so you can try the idea in a minute.</p><p class="made-note">Nothing you do here is saved or sent.</p></div></div>
{benches}"""
    write_page(p, "a", "Playground", body, toys=True)


def investigation_a(i: dict) -> None:
    p = HERE / "a/investigations" / i["slug"] / "index.html"
    things = "".join(f'<li><a href="{rel(p, HERE / "a/index.html")}#made-{k}">{e(BY_KEY[k]["name"])}</a><p>{STATUS[BY_KEY[k]["status"]]}. {e(BY_KEY[k]["what"])}</p></li>' for k in i["things"])
    notes = "".join(f'<li><a href="{note_link(p, n)}">{n[0]} / {e(n[1])}</a></li>' for n in i["notes"])
    specs = "".join(f'<li><a href="{docs(p, s[2])}">Specimen {s[0]} / {e(s[1])}</a></li>' for s in i["specimens"]) or "<li><p>None yet.</p></li>"
    others = "".join(f'<li><a href="{inv_href(p, "a", o["slug"])}">{e(o["q"])}</a></li>' for o in INVESTIGATIONS if o is not i)
    try_ = (f'<a class="editorial-link" href="{rel(p, HERE / "a/workbench/playground/index.html")}#{i["toy"]}">Try it: {e(i["toy_title"])} <span aria-hidden="true">↗</span></a>' if i.get("toy") else "")
    body = f"""<div class="proto-top mono"><span>A QUESTION WE KEEP ASKING / {i['n']}</span><a href="{rel(p, HERE / 'a/index.html')}#made-here">Back to Made here ↗</a></div>
<div class="proto-head"><div><h1>{e(i['q'])}</h1></div><div><p>{e(i['lead'])}</p>{try_}</div></div>
<div class="collection"><section aria-labelledby="c1"><h2 id="c1">MADE HERE, AND ASKING IT</h2><ul>{things}</ul></section>
<section aria-labelledby="c2"><h2 id="c2">FIELD NOTES</h2><ul>{notes}</ul></section>
<section aria-labelledby="c3"><h2 id="c3">SPECIMENS</h2><ul>{specs}</ul></section></div>
<section class="bench" aria-labelledby="c4"><h2 id="c4" class="mono">THE OTHER QUESTIONS</h2><ul class="mini-links">{others}</ul></section>"""
    write_page(p, "a", i["q"], body)


def investigations_b() -> None:
    p = HERE / "b/investigations/index.html"
    rows = []
    for i in INVESTIGATIONS:
        mats = ", ".join(BY_KEY[k]["name"] for k in i["things"])
        forming = '<p class="made-note">Forming. One note so far.</p>' if i.get("forming") else f'<p class="inv-try mono">TRY / {e(i["toy_title"].upper())}</p>'
        title = f'<a href="{inv_href(p, "b", i["slug"])}">{e(i["q"])}</a>' if not i.get("forming") else e(i["q"])
        rows.append(f'<li><span class="mono">{i["n"]}</span><h2>{title}</h2><div><p>{e(i["lead"])}</p><p class="made-note">Asked by {e(mats)}. {len(i["notes"])} notes, {len(i["specimens"])} specimens.</p>{forming}</div></li>')
    body = f"""<div class="proto-top mono"><span>STANDING INVESTIGATIONS / INDEX</span><a href="{rel(p, HERE / 'b/index.html')}#investigations">Back to the studio ↗</a></div>
<div class="proto-head"><div><h1>Questions we<br><em>keep asking.</em></h1></div><div><p>A field note answers once. A standing investigation stays open: every new piece of work that asks the same question is added to it.</p></div></div>
<ol class="inv-index">{''.join(rows)}</ol>"""
    write_page(p, "b", "Standing investigations", body)


def investigation_b(i: dict) -> None:
    p = HERE / "b/investigations" / i["slug"] / "index.html"
    stops = []
    for idx, k in enumerate(i["things"], 1):
        t = BY_KEY[k]
        stops.append(f"""<section class="thread-stop" id="{k}" tabindex="-1" aria-labelledby="{k}-t">
<div class="thread-margin"><p class="mono">{idx:02d} / {e(t['name'].upper())}</p><p>{status(t['status'])}</p></div>
<div class="thread-copy"><h2 id="{k}-t">{e(t['name'])}</h2><p>{e(t['what'])}</p>{f'<p class="made-note">{e(t["note"])}</p>' if t.get('note') else ''}{links(p, 'b', [l for l in t['links'] if not l[1].startswith('toy:')])}</div></section>""")
    notes = "".join(f'<li><a href="{note_link(p, n)}">{n[0]} / {e(n[1])}</a></li>' for n in i["notes"])
    specs = "".join(f'<li><a href="{docs(p, s[2])}">Specimen {s[0]} / {e(s[1])}</a></li>' for s in i["specimens"]) or "<li><p>None yet.</p></li>"
    nav = "".join(f'<li><a href="#{k}"><span class="mono">{n:02d}</span> {e(BY_KEY[k]["name"])}</a></li>' for n, k in enumerate(i["things"], 1))
    dist_t, dist_p = i["distinction"]
    body = f"""<div class="thread-meta mono"><span>STANDING INVESTIGATION / {i['n']}</span><a href="{rel(p, HERE / 'b/investigations/index.html')}">All three questions ↗</a></div>
<div class="thread-heading"><h1>{e(i['q'])}</h1><div><p>{e(i['lead'])}</p><p class="thread-invitation">{len(i['things'])} things made here ask it. Start with the one you can try.</p><a class="under-link" href="#try">Try it first <span aria-hidden="true">↓</span></a></div></div>
<nav aria-label="Things made here that ask this"><ol class="room-tabs">{nav}</ol></nav>
<div id="try">{toy_bench(p, 'b', i['toy'], i)}</div>
<div class="thread-distinction" style="margin:40px 0"><p><span class="mono">WHAT WE KEEP SEPARATE</span><strong>{e(dist_t)}</strong></p><p>{e(dist_p)}</p></div>
{''.join(stops)}
<div class="collection"><section aria-labelledby="n1"><h2 id="n1">FIELD NOTES ON THIS QUESTION</h2><ul>{notes}</ul></section><section aria-labelledby="n2"><h2 id="n2">SPECIMENS</h2><ul>{specs}</ul></section>
<section aria-labelledby="n3"><h2 id="n3">YOUR VERSION</h2><ul><li><a href="{docs(p, 'questions/')}">Bring a moment like this</a><p>A rough account is enough. Nothing is sent until you send it.</p></li></ul></section></div>"""
    write_page(p, "b", i["q"], body, toys=True, extra_css=["assets/thread.css"], body_class="thread-page")


def playground_b() -> None:
    p = HERE / "b/workbench/playground/index.html"
    benches = "".join(toy_bench(p, "b", k) for k in ("grid", "stamp", "week"))
    body = f"""<div class="proto-top mono"><span>THE WORKBENCH / PLAYGROUND</span><a href="{rel(p, HERE / 'b/index.html')}#investigations">Back to the questions ↗</a></div>
<nav aria-label="Workbench rooms"><ul class="room-tabs"><li><a href="{docs(p, 'workbench/')}"><span class="mono">01</span> The example study</a></li><li><a href="#main" aria-current="page"><span class="mono">02</span> The playground</a></li></ul></nav>
<div class="proto-head"><div><h1>Every toy<br><em>asks something.</em></h1></div><div><p>The same three pieces that open each standing investigation, gathered on one bench. Each one names the question it belongs to.</p></div></div>
{benches}"""
    write_page(p, "b", "Playground", body, toys=True)


def playground_c() -> None:
    p = HERE / "c/workbench/playground/index.html"
    drawers = []
    for n, i in enumerate(INVESTIGATIONS):
        things = "".join(f'<li>{e(BY_KEY[k]["name"])} · <span class="made-note">{STATUS[BY_KEY[k]["status"]]}</span></li>' for k in i["things"])
        notes = "".join(f'<li><a href="{note_link(p, x)}">{x[0]} / {e(x[1])}</a></li>' for x in i["notes"])
        specs = "".join(f'<li><a href="{docs(p, s[2])}">Specimen {s[0]} / {e(s[1])}</a></li>' for s in i["specimens"]) or "<li>None yet.</li>"
        toy = toy_bench(p, "c", i["toy"], i, heading="h3") if i.get("toy") else '<p class="question-forming">Nothing to try in this drawer yet. It holds one note, and stays a forming question until a second piece of work asks it.</p>'
        drawers.append(f"""<details class="drawer" id="{i['slug']}" {'open' if n == 0 else ''}>
<summary><span class="mono">DRAWER {i['n']}</span><h2>{e(i['q'])}</h2><span class="drawer-hint" aria-hidden="true"><span class="hint-closed">OPEN ↓</span><span class="hint-open">CLOSE ↑</span></span></summary>
<div class="drawer-body"><p class="made-note" style="font-size:17px;color:var(--secondary)">{e(i['lead'])}</p>{toy}
<div class="drawer-behind"><div><h3>MADE HERE, AND ASKING IT</h3><ul>{things}</ul></div><div><h3>THE NOTES BEHIND IT</h3><ul>{notes}</ul></div><div><h3>SPECIMENS</h3><ul>{specs}</ul></div></div></div></details>""")
    body = f"""<div class="proto-top mono"><span>THE WORKBENCH / ROOM 02</span><a href="{rel(p, HERE / 'c/index.html')}#made-here">Back to the shelf ↗</a></div>
<nav aria-label="Workbench rooms"><ul class="room-tabs"><li><a href="{docs(p, 'workbench/')}"><span class="mono">01</span> The example study</a></li><li><a href="#main" aria-current="page"><span class="mono">02</span> The playground</a></li></ul></nav>
<div class="proto-head"><div><h1>Open<br><em>a drawer.</em></h1></div><div><p>Every drawer holds one question we keep asking, a small working piece that asks it, and the notes and specimens filed behind it.</p><p class="made-note">Nothing you do here is saved or sent.</p></div></div>
{''.join(drawers)}"""
    write_page(p, "c", "Playground", body, toys=True)


def hub() -> None:
    p = HERE / "index.html"
    rows = [
        ("a", "The ledger", "Things first. A plain “Made here” list on the home page: every project, what it is, its status, and which questions it asks. Investigations are light collection pages. The playground sits beside the example study.", ["index.html#made-here", "workbench/playground/index.html", "investigations/how-old/index.html"]),
        ("b", "Standing questions", "Questions first. Three investigation cards on the home page; each opens a thread-style page that begins with a toy and walks through the things that ask it. “Made here” is a compact roll beneath.", ["index.html#investigations", "investigations/index.html", "investigations/green-light/index.html", "workbench/playground/index.html"]),
        ("c", "The open drawer", "Hands first. The home page’s working-specimens section grows a short shelf and two room doors. The playground is the second Workbench room; its drawers are the investigations, each with a toy and the notes behind it.", ["index.html#made-here", "workbench/playground/index.html"]),
    ]
    items = []
    for c, name, desc, pages in rows:
        ls = "".join(f'<li><a href="{c}/{pg}">{e(pg.replace("index.html", "").rstrip("/") or "home")}</a></li>' for pg in pages)
        items.append(f'<li><span class="mono">{c.upper()}</span><h2><a href="{c}/index.html">{e(name)}</a></h2><div><p>{e(desc)}</p><ul class="mini-links">{ls}</ul></div></li>')
    body = f"""<div class="proto-top mono"><span>DESIGN SPRINT / MADE HERE, PLAYGROUND, STANDING INVESTIGATIONS</span><span>17 OCT 2026</span></div>
<div class="proto-head"><div><h1>Three<br><em>directions.</em></h1></div><div><p>Unpublished concepts for the owner to choose between. Each one is built in the site’s real styles, works in Night and Afterlight, and has working toys.</p><p class="made-note">Read design/made-here-sprint.md for the critique, comparison and questions.</p></div></div>
<ol class="inv-index">{''.join(items)}</ol>"""
    write_page(p, None, "Made here sprint", body)


def main() -> None:
    home_variant("a", concept_a)
    home_variant("b", concept_b)
    home_variant("c", concept_c)
    playground_a()
    for i in INVESTIGATIONS:
        investigation_a(i)
    investigations_b()
    for i in CORE:
        investigation_b(i)
    playground_b()
    playground_c()
    hub()


if __name__ == "__main__":
    main()
