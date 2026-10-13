#!/usr/bin/env python3
"""Generate editorial slots from the public catalog. --check rejects stale output."""
from pathlib import Path
from html import escape
import argparse
import json
import re
from datetime import date
from email.utils import format_datetime
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from build_discovery import build as build_discovery
from build_home_styles import build as build_home_styles

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/assets/notes.json"


def load_notes():
    notes = json.loads(CATALOG.read_text())
    ids = {n["id"] for n in notes}
    assert len(ids) == len(notes), "Duplicate note identifier"
    for n in notes:
        for key in ("related", "supersedes"):
            n.setdefault(key, [])
        n.setdefault("topics", [])
        n.setdefault("thread", "")
        n.setdefault("project", "")
        n.setdefault("featured", False)
        assert re.fullmatch(r"\d{3,}", n["id"])
        assert re.fullmatch(r"\d{3,}-[a-z0-9-]+\.html", n["slug"])
        assert (ROOT / "docs/notes" / n["slug"]).is_file(), n["slug"]
        if n.get('cover'):
            for key in ('small', 'large'):
                assert re.fullmatch(r'[a-z0-9-]+\.webp', n['cover'][key])
                assert (ROOT / 'docs/assets/notes' / n['cover'][key]).is_file()
        date.fromisoformat(n["date"])
        assert n["title"] and n["summary"]
        assert n["visual"] in ("foundations", "themes", "forms")
        assert all(i in ids and i != n["id"] for i in n["related"] + n["supersedes"])
    return sorted(notes, key=lambda n: int(n["id"]), reverse=True)


def visual(n, asset_prefix):
    if n.get('cover'):
        cover = n['cover']
        return f'<div class="editorial-art editorial-cover" aria-hidden="true"><picture><source srcset="{asset_prefix}{cover["small"]} 800w, {asset_prefix}{cover["large"]} 1600w" sizes="(max-width: 760px) 100vw, 65vw"><img src="{asset_prefix}{cover["large"]}" alt="" width="{cover["width"]}" height="{cover["height"]}" loading="lazy" decoding="async"></picture></div>'

    if n["visual"] == "themes":
        return '<div class="editorial-art theme-art" aria-hidden="true"><span class="art-paper"><small>AFTERLIGHT</small><b>Aa</b><i></i></span><span class="art-stone"><small>NIGHTFALL</small><b>Aa</b><i></i></span></div>'
    if n["visual"] == "forms":
        return '<div class="editorial-art form-art" aria-hidden="true">\n          <div class="form-art-specimen"><small>RIVER</small><svg viewBox="0 0 240 170" focusable="false"><path class="diagram-river" d="M20 135 C30 45 70 135 92 70 S160 130 180 58 S216 45 220 18"/><path class="diagram-current" d="M20 135 C30 45 70 135 92 70 S160 130 180 58 S216 45 220 18"/><circle class="diagram-marker" cx="91" cy="72" r="9"/></svg></div>\n          <div class="form-art-specimen"><small>CIRCLE</small><svg viewBox="0 0 240 170" focusable="false"><ellipse class="diagram-table" cx="120" cy="85" rx="61" ry="46"/><g class="diagram-seats"><circle cx="120" cy="24" r="13"/><circle cx="187" cy="54" r="13"/><circle cx="187" cy="116" r="13"/><circle cx="53" cy="116" r="13"/><circle cx="53" cy="54" r="13"/></g><circle class="diagram-selected" cx="120" cy="146" r="15"/></svg></div>\n          <div class="form-art-specimen"><small>FOCUS</small><svg viewBox="0 0 240 170" focusable="false"><rect class="diagram-paper" x="65" y="16" width="110" height="138" rx="3"/><g class="diagram-copy"><path d="M82 43 h45 M82 63 h76 M82 78 h62 M82 93 h69"/></g><path class="diagram-current" d="M82 127 h41 M137 121 l8 6 -8 6"/></svg></div>\n          <small>FORM / PURPOSE</small>\n        </div>'
    return '<div class="editorial-art foundation-art" aria-hidden="true"><span>?</span><small>AN IDEA NEEDS A REASON</small></div>'


def feature(n, prefix, heading):
    return f'''<article class="note-feature">
      {visual(n, '../assets/notes/' if prefix == './' else './assets/notes/')}
      <div class="note-feature-copy">
        <p class="editorial-meta mono">FEATURED / {n['id']} · {escape(n['type'].upper())}</p>
        <h{heading}><a href="{prefix}{n['slug']}">{escape(n['title'])}</a></h{heading}>
        <p>{escape(n['summary'])}</p>
        <a class="editorial-link" href="{prefix}{n['slug']}">Read field note {n['id']} <span aria-hidden="true">↗</span></a>
      </div>
    </article>'''


def row(n, prefix, heading=3):
    return f'''<article class="archive-entry notes-index-entry" data-note-id="{n['id']}">
      <div class="editorial-meta mono">{n['id']} / {escape(n['type'].upper())}</div>
      <div><h{heading}><a href="{prefix}{n['slug']}">{escape(n['title'])} <span aria-hidden="true">↗</span></a></h{heading}><p>{escape(n['summary'])}</p><p class="archive-topics mono">{' · '.join(map(escape, n['topics']))}</p></div>
    </article>'''


def stack(notes, prefix):
    count = len(notes)
    if not count:
        return ''
    return f'''<details class="editorial-stack">
      <summary><span class="mono">RECENT WRITING / {count:02d}</span><strong>Lift the stack.</strong><span class="stack-hint">Open {count} {'note' if count == 1 else 'notes'} <span aria-hidden="true">↗</span></span></summary>
      <div class="stack-entries">{''.join(row(n, prefix) for n in notes)}</div>
    </details>'''


def replace_slot(path, name, content, check):
    old = path.read_text()
    pattern = rf"(<!-- {name}:start -->).*?(<!-- {name}:end -->)"
    new, count = re.subn(pattern, lambda m: m[1] + '\n' + content + '\n' + m[2], old, flags=re.S)
    assert count == 1, f"Missing/duplicate slot {name} in {path}"
    if check:
        assert new == old, f"Stale editorial output: run python3 scripts/build_notes.py ({path})"
    else:
        path.write_text(new)


def build(check=False):
    notes = load_notes()
    # The published catalog is also the feed: unpublished research never enters it.
    ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    for tag, value in (
        ('title', 'Moth & Gravel — Field Notes'),
        ('link', 'https://mothandgravel.com/notes/'),
        ('description', 'Curious questions, working answers. Notes from an independent software workbench.'),
        ('language', 'en'),
    ):
        ET.SubElement(channel, tag).text = value
    ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link',
                  href='https://mothandgravel.com/notes/feed.xml', rel='self', type='application/rss+xml')
    for note in notes:
        item = ET.SubElement(channel, 'item')
        url = 'https://mothandgravel.com/notes/' + note['slug']
        for tag, value in (('title', note['title']), ('link', url), ('description', note['summary'])):
            ET.SubElement(item, tag).text = value
        ET.SubElement(item, 'guid', isPermaLink='true').text = url
        ET.SubElement(item, 'pubDate').text = format_datetime(
            datetime.combine(date.fromisoformat(note['date']), datetime.min.time(), tzinfo=timezone.utc),
            usegmt=True)
        for topic in note['topics']:
            ET.SubElement(item, 'category').text = topic
    ET.indent(rss)
    feed = ET.tostring(rss, encoding='unicode', xml_declaration=True) + '\n'
    feed_path = ROOT / 'docs/notes/feed.xml'
    if check:
        assert feed_path.read_text() == feed, 'Stale RSS feed: run python3 scripts/build_notes.py'
    else:
        feed_path.write_text(feed)
    featured = next((n for n in notes if n['featured']), notes[0])
    recent = [n for n in notes if n['id'] != featured['id']][:3]
    for path, name, prefix, heading in (
        (ROOT / 'docs/index.html', 'home-notes', './notes/', 3),
        (ROOT / 'docs/notes/index.html', 'collection-notes', './', 2),
    ):
        replace_slot(path, name, '<div class="editorial-selection">' + feature(featured, prefix, heading) + stack(recent, prefix) + '</div>', check)
    index = ROOT / 'docs/notes/index.html'
    replace_slot(index, 'archive', ''.join(row(n, './') for n in notes), check)
    replace_slot(index, 'note-count', f'<span>{len(notes)} published {"note" if len(notes) == 1 else "notes"}</span>', check)
    for n in notes:
        links = ''.join(f'<a class="editorial-link" href="./{other["slug"]}">{escape(other["title"])} <span aria-hidden="true">↗</span></a>' for other in notes if other['id'] in n['related'])
        thread = [other for other in notes if n['thread'] and other['thread'] == n['thread'] and other['id'] != n['id']]
        if thread:
            links += '<p class="mono">CONTINUE THE THREAD</p>' + ''.join(f'<a class="editorial-link" href="./{other["slug"]}">{escape(other["title"])} <span aria-hidden="true">↗</span></a>' for other in thread)
        revisions = [other for other in notes if n['id'] in other['supersedes']]
        if revisions:
            links += '<p class="mono">REVISITED IN</p>' + ''.join(f'<a class="editorial-link" href="./{other["slug"]}">{escape(other["title"])}</a>' for other in revisions)
        replace_slot(ROOT / 'docs/notes' / n['slug'], 'related-notes', '<aside class="note-related" aria-label="Related Field Notes"><p class="mono">RELATED READING</p>' + links + '</aside>' if links else '', check)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    check = parser.parse_args().check
    build(check)
    build_discovery(check)
    build_home_styles(check)
