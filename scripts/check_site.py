#!/usr/bin/env python3
"""Dependency-free integrity check for the Moth & Gravel GitHub Pages site."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
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
        target = (ROOT / relative_path).resolve()
        check(target.is_relative_to(ROOT.resolve()), f"Path escapes docs/: {relative_path}")
        check(target.is_file() or (target.is_dir() and (target / "index.html").is_file()),
              f"Missing local asset or index page: {relative_path}")

    check('<html lang="en"' in html, "Missing HTML language")
    check('name="description"' in html, "Missing search description")
    check('rel="canonical"' in html, "Missing canonical URL")
    check("https://mothandgravel.com/" in html, "Canonical domain not found")
    check("https://github.com/mothandgravel" in html, "Missing genuine GitHub contact link")
    check(len(parser.ids) >= 8, "Expected semantic page landmarks")

    css = (ROOT / "assets" / "site.css").read_text(encoding="utf-8")
    check(css.count("{") == css.count("}"), "Unbalanced CSS braces")
    check('data-theme="afterlight"' in css, "Light theme styles missing")
    check("prefers-reduced-motion" in css, "Reduced-motion support missing")
    check("@media (max-width:660px)" in css, "Mobile layout support missing")
    check(".has-js .main-nav" in css, "Progressive enhancement for mobile navigation missing")
    check('aria-label="Afterlight theme"' in html, "Theme toggle needs a stable accessible label")
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
    check('aria-expanded' in js and 'aria-pressed' in js, "Accessible interactive controls not wired")
    check("localStorage" in js, "Theme preference handling missing")

    check((ROOT / "CNAME").read_text(encoding="utf-8").strip() == "mothandgravel.com", "Wrong custom-domain CNAME")
    check((ROOT / "404.html").is_file(), "Missing custom 404")
    check((ROOT / "robots.txt").is_file(), "Missing robots.txt")
    sitemap = ET.parse(ROOT / "sitemap.xml").getroot()
    check(any(node.text == "https://mothandgravel.com/" for node in sitemap.iter() if node.tag.endswith("loc")), "Missing homepage in sitemap")

    # Sprint 02: public work must be real and all outbound actions usable.
    note_file = ROOT / "notes" / "001-curiosity-with-calluses.html"
    check(note_file.is_file(), "Field Note 001 is missing")
    check(html.count('class="work-card-link"') == 3, "Expected three real workbench links")
    check('href="./notes/001-curiosity-with-calluses.html"' in html, "Workbench note link is missing")
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
    check('href="./notes/002-afterlight-nightfall.html"' in html,
          "Homepage workbench must expose the theme study")
    for expected in ("notes/", "notes/001-curiosity-with-calluses.html",
                     "notes/002-afterlight-nightfall.html"):
        check(f"https://mothandgravel.com/{expected}" in (ROOT / "sitemap.xml").read_text(encoding="utf-8"),
              f"Sitemap is missing {expected}")

    extra_pages = {}
    for name, file in (("field notes index", note_index), ("theme study", theme_note)):
        if not file.is_file():
            continue
        body = file.read_text(encoding="utf-8")
        extra_pages[name] = body
        page_parser = SiteParser()
        page_parser.feed(body)
        check('<html lang="en"' in body, f"{name} needs an HTML language")
        check('<main id="main"' in body, f"{name} needs a main landmark")
        check(body.count("<h1") == 1, f"{name} should have exactly one h1")
        check('rel="canonical"' in body, f"{name} is missing a canonical URL")
        check('id="light-switch"' in body, f"{name} has no appearance control")
        for relative in re.findall(r'(?:href|src)="(\.\./assets/[^"]+)"', body):
            target = (file.parent / relative).resolve()
            check(target.is_relative_to(ROOT.resolve()) and target.is_file(),
                  f"{name} has a broken local asset: {relative}")
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
