#!/usr/bin/env python3
"""Dependency-free integrity check for the Moth & Gravel GitHub Pages site."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import re
import json
import hashlib
import os
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / "docs"
ERRORS: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.references: list[str] = []
        self.anchors: list[str] = []
        self.image_count = 0
        self.stylesheets: list[str] = []
        self.note_ends = 0
        self.reading_ends = 0
        self.article_stack: list[bool] = []
        self.reading_end_in_prose = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get('class') or '').split()
        if tag == 'link' and 'stylesheet' in (attributes.get('rel') or '').split():
            self.stylesheets.append(attributes.get('href') or '')
        if tag == 'article':
            self.article_stack.append('note-prose' in classes)
        if 'note-end' in classes:
            self.note_ends += 1
        if 'reading-exit' in classes:
            self.reading_ends += 1
            self.reading_end_in_prose |= any(self.article_stack)
        identifier = attributes.get("id")
        if identifier:
            check(identifier not in self.ids, f"Duplicate HTML id: {identifier}")
            self.ids.add(identifier)

        if tag == "img":
            self.image_count += 1
            check("alt" in attributes, "Every image needs an alt attribute (which may be empty for decorative images).")

        if tag == "a" and attributes.get("href", "").startswith("#"):
            self.anchors.append(attributes["href"][1:])

        for key in ("href", "src"):
            value = attributes.get(key, "") or ""
            if value.startswith("./"):
                self.references.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'article' and self.article_stack:
            self.article_stack.pop()

    def reading_issues(self) -> list[str]:
        issues = []
        if self.stylesheets.count('../assets/reading-room.css') != 1:
            issues.append('needs exactly one reading-room stylesheet')
        if self.note_ends != 1 or self.reading_ends != 1:
            issues.append('needs one generated ending, with no separate legacy ending')
        if self.reading_end_in_prose:
            issues.append('reading ending must stay outside narrated article prose')
        return issues



def contrast_ratio(first: str, second: str) -> float:
    """WCAG contrast ratio of two six-digit CSS hex colors."""

    def luminance(value: str) -> float:
        components = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [
            component / 12.92 if component <= 0.04045
            else ((component + 0.055) / 1.055) ** 2.4
            for component in components
        ]
        return sum(component * weight for component, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def css_token(style: str, selector: str, token: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", style, flags=re.S)
    if match is None:
        raise ValueError(f"Could not find selector {selector}")
    prop = re.search(r"--" + re.escape(token) + r":\s*(#[0-9a-fA-F]{6})", match.group(1))
    if prop is None:
        raise ValueError(f"Could not find color token --{token} in {selector}")
    return prop.group(1)

def main() -> int:
    html_file = ROOT / "index.html"
    check(html_file.is_file(), "Missing docs/index.html")
    if not html_file.is_file():
        print("\n".join(ERRORS), file=sys.stderr)
        return 1

    html = html_file.read_text(encoding="utf-8")
    parser = SiteParser()
    parser.feed(html)
    for anchor in parser.anchors:
        check(anchor in parser.ids, f"Broken local anchor: #{anchor}")
    for relative_path in parser.references:
        target = (ROOT / urlsplit(relative_path).path).resolve()
        check(target.is_relative_to(ROOT.resolve()), f"Path escapes docs/: {relative_path}")
        check(target.is_file() or (target.is_dir() and (target / "index.html").is_file()),
              f"Missing local asset or index page: {relative_path}")

    check('<html lang="en"' in html, "Missing HTML language")
    check('name="description"' in html, "Missing search description")
    check('rel="canonical"' in html, "Missing canonical URL")
    check("https://mothandgravel.com/" in html, "Canonical domain not found")
    check("https://github.com/mothandgravel" in html, "Missing genuine GitHub contact link")
    check('issues/new?template=signal.yml' in html, "Missing public signal route")
    check('id="studio"' in html, "Missing studio introduction")
    check(len(parser.ids) >= 8, "Expected semantic page landmarks")

    css = (ROOT / "assets" / "site.css").read_text(encoding="utf-8")
    check(css.count("{") == css.count("}"), "Unbalanced CSS braces")
    check('data-theme="afterlight"' in css, "Light theme styles missing")
    check("prefers-reduced-motion" in css, "Reduced-motion support missing")
    check("@media (max-width:660px)" in css, "Mobile layout support missing")
    check(".has-nav-sheet .main-nav" in css, "Progressive enhancement for mobile navigation missing")
    check('data-theme-label' in html, "Theme control needs a visible label stating the current setting")
    check('src="./assets/nav-mark.svg"' in html, "Official brand symbol missing from masthead")
    try:
        light_accent = css_token(css, ':root[data-theme="afterlight"]', "gold-bright")
        light_background = css_token(css, ':root[data-theme="afterlight"]', "bg")
        light_surface = css_token(css, ':root[data-theme="afterlight"]', "surface")
        light_button_ink = css_token(css, ':root[data-theme="afterlight"]', "accent-ink")
        light_muted = css_token(css, ':root[data-theme="afterlight"]', "muted")
        light_surface_2 = css_token(css, ':root[data-theme="afterlight"]', "surface-2")
        check(contrast_ratio(light_accent, light_background) >= 4.5,
              "Afterlight accent text contrast is below 4.5:1 on background")
        check(contrast_ratio(light_accent, light_surface) >= 4.5,
              "Afterlight accent text contrast is below 4.5:1 on panels")
        check(contrast_ratio(light_button_ink, light_accent) >= 4.5,
              "Afterlight CTA text contrast is below 4.5:1")
        check(contrast_ratio(light_muted, light_surface_2) >= 4.5,
              "Afterlight muted text contrast is below 4.5:1 on stone panels")
    except ValueError as error:
        check(False, str(error))

    js = (ROOT / "assets" / "site.js").read_text(encoding="utf-8")
    check('aria-expanded' in js and 'prefers-color-scheme' in js, "Menu state or system theme handling not wired")
    check("localStorage" in js, "Theme preference handling missing")

    check((ROOT / "CNAME").read_text(encoding="utf-8").strip() == "mothandgravel.com", "Wrong custom-domain CNAME")
    check((ROOT / "404.html").is_file(), "Missing custom 404")
    check((ROOT / "robots.txt").is_file(), "Missing robots.txt")
    sitemap = ET.parse(ROOT / "sitemap.xml").getroot()
    check(any(node.text == "https://mothandgravel.com/" for node in sitemap.iter() if node.tag.endswith("loc")), "Missing homepage in sitemap")

    # Sprint 02: public work must be real and all outbound actions usable.
    note_file = ROOT / "notes" / "001-curiosity-with-calluses.html"
    check(note_file.is_file(), "Field Note 001 is missing")
    check(html.count('class="work-card-link"') == 3, "All three specimens need a related study")
    check(html.count('class="work-card"') == 3, "Workbench should display three working specimens")

    for specimen in ('ajo', 'skystack', 'kitronik'):
        check(f'id="specimen-{specimen}"' in html, f'Missing {specimen} specimen')
    check(html.count('class="specimen-record"') == 3, 'Each specimen needs a native working record')
    provenance = json.loads((ROOT.parent / 'design/working-specimens-provenance.json').read_text())
    check([item['id'] for item in provenance['artifacts']] == ['coastal-watch', 'liveconnect', 'ajo', 'skystack', 'kitronik'],
          'Specimen provenance must match the visible selection')
    for item in provenance['artifacts']:
        if 'asset' in item:
            # Recorded asset paths stay relative to the published docs/design folder they were written in.
            asset = Path(os.path.normpath(ROOT / 'design' / item['asset']))
            check(asset.is_file() and hashlib.sha256(asset.read_bytes()).hexdigest() == item['assetSha256'],
                  f"Specimen asset differs from recorded output: {item['id']}")
    check((ROOT / 'assets/specimens/sky-stamp-footprints.svg').is_file(), 'Missing native footprint replay')
    connection_provenance = json.loads((ROOT.parent / 'design/connection-study-provenance.json').read_text())
    for illustration in connection_provenance['illustrations']:
        if 'sha256' in illustration:
            asset = ROOT.parent / illustration['path']
            check(asset.is_file() and hashlib.sha256(asset.read_bytes()).hexdigest() == illustration['sha256'],
                  'Connection illustration differs from recorded artwork')
    connection_page = ROOT / 'specimens/connected-to-what/index.html'
    check(connection_page.is_file(), 'Missing inspectable LiveConnect specimen')
    check('id="specimen-liveconnect"' in html and 'href="./specimens/connected-to-what/"' in html,
          'Inspectable specimen must be discoverable from the bench')
    if connection_page.is_file():
        connection_html = connection_page.read_text()
        connection_parser = SiteParser()
        connection_parser.feed(connection_html)
        for anchor in connection_parser.anchors:
            check(anchor in connection_parser.ids, f'Connection specimen broken anchor #{anchor}')
        for relative in re.findall(r'(?:href|src)="(\.\.?/[^\"]+)"', connection_html):
            target = (connection_page.parent / urlsplit(relative).path).resolve()
            check(target.is_relative_to(ROOT.resolve()) and (target.is_file() or
                  (target.is_dir() and (target / 'index.html').is_file())),
                  f'Connection specimen broken destination {relative}')
        check('https://mothandgravel.com/specimens/connected-to-what/' in (ROOT / 'sitemap.xml').read_text(),
              'Inspectable specimen missing from sitemap')
        check('href="../../#specimen-ajo"' in connection_html, 'Specimen needs its next question')
        check('<noscript>' in connection_html and '<table>' in connection_html,
              'Specimen must retain all three readings without JavaScript')
    coastal_page = ROOT / 'specimens/coastal-watch/index.html'
    check(coastal_page.is_file(), 'Missing Coastal watch specimen')
    check('id="specimen-coastal-watch"' in html and 'href="./specimens/coastal-watch/"' in html,
          'Coastal watch must be discoverable from the bench')
    coastal_record = json.loads((ROOT / 'design/coastal-watch-provenance.json').read_text())
    for item in coastal_record['assets']:
        asset = ROOT / item['file']
        check(asset.is_file() and hashlib.sha256(asset.read_bytes()).hexdigest() == item['sha256'],
              f"Coastal watch media differs from recorded capture: {item['file']}")
    if coastal_page.is_file():
        coastal_html = coastal_page.read_text(encoding='utf-8')
        coastal_parser = SiteParser()
        coastal_parser.feed(coastal_html)
        for anchor in coastal_parser.anchors:
            check(anchor in coastal_parser.ids, f'Coastal watch broken anchor #{anchor}')
        for relative in re.findall(r'(?:href|src|poster)="(\.\.?/[^\"]+)"', coastal_html):
            target = (coastal_page.parent / urlsplit(relative).path).resolve()
            check(target.is_relative_to(ROOT.resolve()) and (target.is_file() or
                  (target.is_dir() and (target / 'index.html').is_file())),
                  f'Coastal watch broken destination {relative}')
        video = re.search(r'<video\b([^>]*)>', coastal_html)
        check(video is not None and 'controls' in video[1] and 'preload="none"' in video[1]
              and 'autoplay' not in video[1], 'Coastal watch film must be user-initiated')
        check('id="film-description"' in coastal_html and '<ol>' in coastal_html,
              'Silent film needs a readable sequence')
        check('https://mothandgravel.com/specimens/coastal-watch/' in (ROOT / 'sitemap.xml').read_text(),
              'Coastal watch missing from sitemap')
    maritime_page = ROOT / 'specimens/maritime-study/index.html'
    check(maritime_page.is_file(), 'Missing maritime study specimen')
    check('id="specimen-maritime-study"' in html and 'href="./specimens/maritime-study/"' in html,
          'Maritime study must be discoverable from the bench')
    maritime_record = json.loads((ROOT / 'design/maritime-study-provenance.json').read_text())
    for item in maritime_record['originals'] + maritime_record['derivatives']:
        asset = ROOT / item['file']
        check(asset.is_file() and hashlib.sha256(asset.read_bytes()).hexdigest() == item['sha256'],
              f"Maritime study media differs from its record: {item['file']}")
    check('https://github.com/navivra' not in json.dumps(maritime_record), 'Private source repository must not be linked')
    if maritime_page.is_file():
        maritime_html = maritime_page.read_text(encoding='utf-8')
        maritime_parser = SiteParser()
        maritime_parser.feed(maritime_html)
        for anchor in maritime_parser.anchors:
            check(anchor in maritime_parser.ids, f'Maritime study broken anchor #{anchor}')
        sources = re.findall(r'(?:href|src|data-poster)="(\.\.?/[^\"]+)"', maritime_html)
        sources += [part.split()[0] for srcset in re.findall(r'srcset="([^"]+)"', maritime_html) for part in srcset.split(',')]
        for relative in sources:
            target = (maritime_page.parent / urlsplit(relative).path).resolve()
            check(target.is_relative_to(ROOT.resolve()) and (target.is_file() or
                  (target.is_dir() and (target / 'index.html').is_file())),
                  f'Maritime study broken destination {relative}')
        published = {item['file'] for item in maritime_record['originals'] + maritime_record['derivatives']}
        for relative in sources:
            path = (maritime_page.parent / urlsplit(relative).path).resolve()
            if path.is_relative_to((ROOT / 'assets/specimens/maritime-study').resolve()):
                check(str(path.relative_to(ROOT.resolve())) in published, f'Unrecorded maritime media {relative}')
        videos = re.findall(r'<video\b([^>]*)>', maritime_html)
        check(len(videos) == 3, 'Maritime study needs its three films')
        for attributes in videos:
            check(all(token in attributes for token in ('controls', 'preload="none"', 'muted', 'playsinline', 'data-poster=', 'aria-describedby'))
                  and 'autoplay' not in attributes, 'Maritime films must be silent, user-initiated and described')
        for ident in ('motion', 'inspection', 'night'):
            check(f'id="{ident}-description"' in maritime_html, f'Maritime film {ident} needs a readable sequence')
        for boundary in ('Positions are fixed.', 'nearby FMI observations', 'Night is a lighting study, not a forecast.',
                         'reference-informed and simplified', 'tracks and alerts are synthetic', 'not navigation',
                         'CC BY 4.0', 'ODbL', 'public domain'):
            check(boundary in maritime_html, f'Maritime study boundary missing: {boundary}')
        check(not re.search(r'certif(ied|ication) (bridge|compliance)|compliance verified|ISM|SOLAS|ISPS', maritime_html),
              'Maritime study must not imply compliance or certification')
        check('https://mothandgravel.com/specimens/maritime-study/' in (ROOT / 'sitemap.xml').read_text(),
              'Maritime study missing from sitemap')
    mapping_page = ROOT / 'specimens/whose-map/index.html'
    check(mapping_page.is_file(), 'Missing camera and mapping capture study')
    captures = json.loads((ROOT.parent / 'design/buggy-captures-provenance.json').read_text())
    for item in captures['assets'] + captures.get('deliveryPreviews', []):
        asset = ROOT.parent / item['file']
        check(asset.is_file() and hashlib.sha256(asset.read_bytes()).hexdigest() == item['sha256'],
              'Mapping capture differs from recorded evidence')
    if mapping_page.is_file():
        mapping_html = mapping_page.read_text()
        mapping_parser = SiteParser()
        mapping_parser.feed(mapping_html)
        for anchor in mapping_parser.anchors:
            check(anchor in mapping_parser.ids, f'Mapping capture broken anchor #{anchor}')
        for relative in re.findall(r'(?:href|src)="(\.\.?/[^\"]+)"', mapping_html):
            target = (mapping_page.parent / urlsplit(relative).path).resolve()
            check(target.is_relative_to(ROOT.resolve()) and (target.is_file() or
                  (target.is_dir() and (target / 'index.html').is_file())),
                  f'Mapping capture broken destination {relative}')
        check('https://mothandgravel.com/specimens/whose-map/' in (ROOT / 'sitemap.xml').read_text(),
              'Mapping capture study missing from sitemap')
        check('href="../../notes/006-map-leaves-room.html#bench-captures"' in mapping_html,
              'Mapping specimen must return to its visual addendum')
    check("['.work-grid','./assets/specimens.mjs']" in html, 'Optional specimen handling module missing')
    check("['#moth-interlude','./assets/moth-interlude.mjs']" in html, 'Optional moth scene loader missing')
    check('id="moth-interlude"' in html and 'id="moth-question"' in html, 'Moth interlude resting composition missing')
    for path in ('moth-interlude.mjs', 'moth-choreography.mjs', 'moth-interlude.css', 'moth-rig.svg'):
        check((ROOT / 'assets' / path).is_file(), f'Moth scene resource missing: {path}')
    for path in ('moth-webgl.mjs', 'moth-mesh.mjs', 'moth-model.json'):
        check((ROOT / 'assets' / path).is_file(), f'Volumetric moth resource missing: {path}')
    check('animation:float-moth' not in css, 'Hero still has an endless moth loop')

    check('https://github.com/mothandgravel/.github/tree/main/docs' in html, "Workbench source link is missing")
    check('https://github.com/mothandgravel/.github/tree/main/profile/assets' in html, "Workbench brand assets link is missing")
    check('class="bench-ledger"' in html, "Early-days status is missing")
    check('notes/001-curiosity-with-calluses.html' in (ROOT / "sitemap.xml").read_text(encoding="utf-8"),
          "Published Field Note missing from sitemap")

    # Sprint 03: make Field Notes browsable and reject phantom destinations.
    note_index = ROOT / "notes" / "index.html"
    theme_note = ROOT / "notes" / "002-afterlight-nightfall.html"
    check(note_index.is_file(), "Field Notes index is missing")
    check(theme_note.is_file(), "Field Note 002 theme study is missing")
    check('href="./notes/"' in html, "Homepage Field Notes navigation must lead to the index")
    catalog = json.loads((ROOT / 'assets' / 'notes.json').read_text())
    feed = ET.parse(ROOT / 'notes/feed.xml').getroot()
    feed_items = feed.findall('channel/item')
    expected_feed_urls = {'https://mothandgravel.com/notes/' + n['slug'] for n in catalog}
    check(len(feed_items) == len(catalog), 'RSS feed must contain each published note once')
    check({item.findtext('guid') for item in feed_items} == expected_feed_urls,
          'RSS identities must match the published catalog')
    check(all(item.findtext('guid') == item.findtext('link') for item in feed_items),
          'RSS links must use the stable article identities')
    featured = next((n for n in catalog if n.get('featured')), sorted(catalog, key=lambda n: int(n['id']), reverse=True)[0])
    feature_html = re.search(r'<article class="note-feature">(.*?)</article>', html, re.S)
    check(feature_html is not None and feature_html.group(1).count(f'href="./notes/{featured["slug"]}"') == 2,
          "Selected Field Note needs its featured title and reading action")
    check('id="field-notes"' in html and 'class="note-feature"' in html,
          "Homepage needs an independent editorial Field Notes section")
    check('class="editorial-stack"' in html, "Recent-note discovery stack is missing")
    for expected in ["notes/"] + ["notes/" + note["slug"] for note in catalog]:
        check(f"https://mothandgravel.com/{expected}" in (ROOT / "sitemap.xml").read_text(encoding="utf-8"),
              f"Sitemap is missing {expected}")

    extra_pages = {}
    for name, file in [("field notes index", note_index), ("theme study", theme_note)] + [
        ("note " + note["id"], ROOT / "notes" / note["slug"]) for note in catalog
    ]:
        if not file.is_file():
            continue
        body = file.read_text(encoding="utf-8")
        extra_pages[name] = body
        page_parser = SiteParser()
        page_parser.feed(body)
        if file == note_index:
            check(page_parser.stylesheets.count('../assets/reading-room.css') == 1,
                  'Field Notes index needs exactly one reading-room stylesheet')
        check('<html lang="en"' in body, f"{name} needs an HTML language")
        check('<main id="main"' in body, f"{name} needs a main landmark")
        check(body.count("<h1") == 1, f"{name} should have exactly one h1")
        check('rel="canonical"' in body, f"{name} is missing a canonical URL")
        check('id="light-switch"' in body, f"{name} has no appearance control")
        for relative in re.findall(r'(?:href|src)="(\.\./assets/[^"]+)"', body):
            target = (file.parent / relative).resolve()
            check(target.is_relative_to(ROOT.resolve()) and target.is_file(),
                  f"{name} has a broken local asset: {relative}")
    for note in catalog:
        path = ROOT / 'notes' / note['slug']
        note_source = path.read_text(encoding='utf-8')
        check(f'https://mothandgravel.com/notes/{note["slug"]}' in note_source,
              f'{note["id"]} canonical route missing')
        page_parser = SiteParser()
        page_parser.feed(note_source)
        for issue in page_parser.reading_issues():
            check(False, f'{note["id"]} {issue}')
        for anchor in page_parser.anchors:
            check(anchor in page_parser.ids, f'{note["id"]} broken local anchor #{anchor}')
        for relative in re.findall(r'(?:href|src)="(\.\.?/[^\"]+)"', note_source):
            target = (path.parent / urlsplit(relative).path).resolve()
            check(target.is_relative_to(ROOT.resolve()) and (target.is_file() or
                  (target.is_dir() and (target / 'index.html').is_file())),
                  f'{note["id"]} broken local destination {relative}')
    if note_index.is_file():
        check('href="./001-curiosity-with-calluses.html"' in extra_pages["field notes index"],
              "Field Notes index missing Note 001 link")
        check('href="./002-afterlight-nightfall.html"' in extra_pages["field notes index"],
              "Field Notes index missing Note 002 link")
    if theme_note.is_file():
        theme_html = extra_pages["theme study"]
        check(theme_html.count('class="study-sample ') == 2, "Theme study needs two color specimens")
        check(theme_html.count('class="study-metric"') == 6, "Theme study needs six color pair measurements")
        check('href="./"' in theme_html, "Theme study must link back to the Field Notes index")

    # Curated routes must work as ordinary documents, including return fragments.
    thread_page = ROOT / 'threads/something-happened/index.html'
    thread_html = thread_page.read_text()
    thread_parser = SiteParser()
    thread_parser.feed(thread_html)
    for anchor in thread_parser.anchors:
        check(anchor in thread_parser.ids, f'Thread broken anchor #{anchor}')
    for relative in re.findall(r'(?:href|src)="([^"]+)"', thread_html):
        url = urlsplit(relative)
        if url.scheme or url.netloc or not url.path:
            continue
        target = (thread_page.parent / url.path).resolve()
        if target.is_dir():
            target /= 'index.html'
        check(target.is_relative_to(ROOT.resolve()) and target.is_file(),
              f'Thread missing local destination: {relative}')
        if url.fragment and target.is_file():
            destination = SiteParser()
            destination.feed(target.read_text())
            check(url.fragment in destination.ids, f'Thread missing destination fragment: {relative}')
    check('https://mothandgravel.com/threads/something-happened/' in (ROOT / 'sitemap.xml').read_text(),
          'Curated thread missing from sitemap')

    # Discovery must survive a text-only request and agree with the public record.
    for file in [ROOT / 'index.html', note_index, connection_page, mapping_page, maritime_page, thread_page] + [ROOT / 'notes' / n['slug'] for n in catalog]:
        source = file.read_text()
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', source, re.S)
        check(len(blocks) == 1, f'{file.name}: expected one generated identity graph')
        if len(blocks) != 1:
            continue
        try:
            data = json.loads(blocks[0])
            graph = data['@graph']
            check(data['@context'] == 'https://schema.org', f'{file.name}: unknown schema context')
            types = lambda n: n['@type'] if isinstance(n['@type'], list) else [n['@type']]
            studio = next(n for n in graph if 'Organization' in types(n))
            check(studio.get('email') == 'hello@mothandgravel.com' and studio['contactPoint']['email'] == studio['email'],
                  f'{file.name}: studio enquiry address missing')
            check(studio['name'] == 'Moth & Gravel' and studio['founder']['name'] == 'slideep',
                  f'{file.name}: public studio identity disagrees with visible copy')
            check(studio['location']['name'] == 'Finland', f'{file.name}: public location differs')
            # ProfessionalService is allowed; a street address or a plain LocalBusiness needs verification first.
            check(all('LocalBusiness' not in types(n) for n in graph) and 'address' not in studio,
                  f'{file.name}: unverified local business claim')
            page = next(n for n in graph if n['@type'] in ('WebPage', 'CollectionPage'))
            canonical = re.search(r'<link rel="canonical" href="([^"]+)"', source).group(1)
            check(page['url'] == canonical, f'{file.name}: schema and canonical URL differ')
            if file.name[0].isdigit():
                note = next(n for n in catalog if n['slug'] == file.name)
                article = next(n for n in graph if n['@type'] == 'BlogPosting')
                check(article['headline'] == note['title'] and article['description'] == note['summary'],
                      f'{file.name}: article identity disagrees with the public catalog')
                check(article['mainEntityOfPage']['@id'] == page['@id'], f'{file.name}: article page reference broken')
                check(article['author']['@id'] == studio['@id'], f'{file.name}: unverified author')
                meta = re.search(r'<div class="note-meta mono">(.*?)</div>', source).group(1)
                check(not re.search(r'\d{2} [A-Z]{3} \d{4}', meta), f'{file.name}: publication stamp returned')
            elif file == note_index:
                listing = next(n for n in graph if n['@type'] == 'ItemList')
                check({n['url'] for n in listing['itemListElement']} == expected_feed_urls,
                      'Machine-readable collection differs from the published archive')
        except (ValueError, KeyError, StopIteration, AttributeError) as error:
            check(False, f'{file.name}: invalid discovery graph ({error})')
    check('studio-answers' in html and 'based in finland' in html.lower(),
          'Machine identity must be backed by visible useful answers and location')
    for route in ('questions', 'workbench', 'workbench/return'):
        path = ROOT / route / 'index.html'
        check(path.is_file(), f'Missing {route} journey')
        if not path.is_file():
            continue
        source = path.read_text()
        journey = SiteParser()
        journey.feed(source)
        check(source.count('<h1') == 1 and '<main id="main"' in source,
              f'{route}: missing unique heading or main landmark')
        check(f'https://mothandgravel.com/{route}/' in source,
              f'{route}: missing canonical identity')
        for anchor in journey.anchors:
            check(anchor in journey.ids, f'{route}: broken local anchor #{anchor}')
        for relative in re.findall(r'(?:href|src)="(\.\.?/[^\"]+)"', source):
            target = (path.parent / urlsplit(relative).path).resolve()
            check(target.is_relative_to(ROOT.resolve()) and (target.is_file() or
                  (target.is_dir() and (target / 'index.html').is_file())),
                  f'{route}: broken local destination {relative}')
    preview = (ROOT / 'workbench/index.html').read_text()
    check('noindex, follow' in preview, 'Example workbench must be labelled outside search indexing')
    sitemap_text = (ROOT / 'sitemap.xml').read_text()
    # The fictional example rooms stay out; the playground (room 02) holds real, published work.
    check(not re.search(r'<loc>https://mothandgravel\.com/workbench/(return/)?</loc>', sitemap_text),
          'Example workbench must stay out of the published-content sitemap')
    check(re.search(r'<a href="playground/">[^<]*playground', preview, re.I) is not None,
          'Example workbench must lead to its second room, the playground')

    # Standing investigations and the playground: three questions on the home page, one open
    # question page, a light index, and room 02 with three lazy toys. Nothing links a page that
    # does not exist yet, the live game is not linked, and no organisation names appear.
    check(len(re.findall(r'<p class="service-ask mono">0[123] / (?:PAGE COMING|OPEN NOW)</p>', html)) == 3 and 'href="./investigations/green-light/"' in html,
          'Home must show three standing questions, with the green-light page linked')
    check('href="./workbench/">Workbench</a>' in html, 'Menu Workbench must lead to the two-room workbench')
    # Made here: the homepage renders it after load from assets/made-here.mjs; the static list on
    # /investigations/ is the no-script route. Both must say the same thing.
    module_items = re.findall(r"\['([^']+)', '(pr|pl|sd|in|)', '([^']+)'\]", (ROOT / 'assets/made-here.mjs').read_text())
    index_items = re.findall(r'<li><strong>([^<]+)</strong><span class="status" data-status="(\w+)">([^<]+)</span></li>',
                             (ROOT / 'investigations/index.html').read_text())
    kinds = {'pr': 'production', 'pl': 'playable', 'sd': 'study', 'in': 'internal', '': 'prototype'}
    check(len(module_items) == 12 and [(n, kinds[k], t) for n, k, t in module_items] == index_items,
          'Made here must list the same twelve things and statuses on the homepage and the questions index')
    check('id="made-here" data-made-here' in html and 'href="./investigations/#made-here"' in html
          and "addEventListener('load',()=>{import('./assets/made-here.mjs')" in html, 'Made here must load after the page, with a no-script link')
    check('run.app' not in html, 'The live Cyber Grid is not linked yet')
    for page_path, needles in {
        'investigations/index.html': ['href="./green-light/"', 'PAGE COMING'],
        'investigations/green-light/index.html': ['data-toy="grid"', 'assets/playground.mjs', 'assets/thread.css'],
        'workbench/playground/index.html': ['data-toy="stamp"', 'data-toy="grid"', 'data-toy="week"', 'aria-current="page"', 'href="../"'],
    }.items():
        page_file = ROOT / page_path
        check(page_file.is_file(), f'Missing {page_path}')
        if not page_file.is_file():
            continue
        page_html = page_file.read_text(encoding='utf-8')
        url = 'https://mothandgravel.com/' + page_path.removesuffix('index.html')
        check(f'<loc>{url}</loc>' in sitemap_text, f'{page_path} missing from sitemap')
        check(f'<link rel="canonical" href="{url}">' in page_html and 'og:title' in page_html
              and 'twitter:card' in page_html and '<!-- discovery:start -->' in page_html,
              f'{page_path} needs canonical, social preview and structured data')
        for needle in needles:
            check(needle in page_html, f'{page_path} is missing {needle}')
        check(not re.search(r'navivra|kistradegoods|digablesolutions|vesuno|run\.app', page_html, re.I),
              f'{page_path} names an organisation, a private project or the unlinked game')
        parsed = SiteParser()
        parsed.feed(page_html)
        for anchor in parsed.anchors:
            check(anchor in parsed.ids, f'{page_path} broken anchor #{anchor}')
        for relative in re.findall(r'(?:href|src)="(\.\.?/[^"]*|[a-z][^":#]*/?)"', page_html):
            if relative.startswith(('http', 'mailto')):
                continue
            target = (page_file.parent / urlsplit(relative).path).resolve()
            check(target.is_file() or (target.is_dir() and (target / 'index.html').is_file()),
                  f'{page_path} broken destination {relative}')
    check(not re.search(r'navivra|kistradegoods|digablesolutions|vesuno', html, re.I),
          'Home names an organisation or a private project')
    for toy in ('stamp', 'grid', 'week'):
        check((ROOT / f'assets/playground/{toy}.mjs').is_file(), f'Missing playground toy {toy}')
    check('playground' not in re.sub(r'href="[^"]*"', '', html.split('<!-- home-style:end -->')[0]),
          'Toys and their styles must not load on the home page')
    check('href="#contact">Start a conversation' in html, 'Missing early enquiry invitation')
    check(html.count('mailto:hello@mothandgravel.com') >= 4, 'Missing private email route in header, band, contact and footer')
    robots = (ROOT / 'robots.txt').read_text()
    check('Allow: /' in robots and 'Disallow: /' not in robots,
          'Published text must be crawlable')

    # Each published ratio must agree with the actual palette used by the theme.
    for label, foreground, background, expected in (
        ("Afterlight primary", "#222423", "#FFFCF6", 15.25),
        ("Afterlight quiet", "#565B56", "#E9E4D9", 5.47),
        ("Afterlight brass", "#090A0B", "#9A7946", 4.90),
        ("Nightfall primary", "#F1EEE6", "#202324", 13.65),
        ("Nightfall quiet", "#B5B3AA", "#292D2E", 6.62),
        ("Nightfall brass", "#17191B", "#D4B37C", 8.85),
    ):
        ratio = contrast_ratio(foreground, background)
        check(ratio >= 4.5 and abs(ratio - expected) < 0.06,
              f"Incorrect or insufficient WCAG contrast for {label}: {ratio:.2f}")

    cover = ROOT / "assets" / "social-cover.png"
    check(cover.is_file(), "Social-preview PNG is missing")
    if cover.is_file():
        image_header = cover.read_bytes()[:24]
        check(image_header[:8] == b"\x89PNG\r\n\x1a\n", "Social preview is not a valid PNG header")
        if image_header[:8] == b"\x89PNG\r\n\x1a\n":
            check(struct.unpack(">II", image_header[16:24]) == (1200, 630),
                  "Social preview dimensions must be 1200 by 630")

    if note_file.is_file():
        note_html = note_file.read_text(encoding="utf-8")
        note_parser = SiteParser()
        note_parser.feed(note_html)
        check('<html lang="en"' in note_html, "Field Note must declare a language")
        check('<main id="main"' in note_html, "Field Note must have a main landmark")
        check('href="../#work"' in note_html, "Field Note must return to the workbench")
        check('rel="canonical"' in note_html, "Field Note is missing its canonical URL")
        check('id="light-switch"' in note_html, "Field Note is missing its functional theme control")
        for relative in re.findall(r'(?:href|src)="(\.\./assets/[^"]+)"', note_html):
            target = (note_file.parent / relative).resolve()
            check(target.is_relative_to(ROOT.resolve()), f"Field Note escapes docs/: {relative}")
            check(target.is_file(), f"Field Note local asset missing: {relative}")
    else:
        note_html = ""

    for page_name, page_html in (("home", html), ("field note", note_html)):
        if not page_html:
            continue
        check('property="og:image" content="https://mothandgravel.com/assets/social-cover.png"' in page_html,
              f"{page_name} social-preview URL missing")
        check('name="twitter:card" content="summary_large_image"' in page_html,
              f"{page_name} large-card metadata missing")
        check('property="og:image:alt"' in page_html, f"{page_name} social image accessibility text missing")

    check(".work-card-link:focus-visible" in css, "Workbench has no visible keyboard affordance")
    check(".note-heading h1" in css, "Field Note styles are missing")

    for svg in (ROOT / "assets").glob("*.svg"):
        check(ET.parse(svg).getroot().tag.endswith("svg"), f"Invalid SVG file: {svg.name}")

    if ERRORS:
        print("\n".join(f"FAIL: {issue}" for issue in ERRORS), file=sys.stderr)
        return 1

    print(f"PASS: site integrity ({len(parser.ids)} IDs, {len(parser.references)} local references, {parser.image_count} images)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
