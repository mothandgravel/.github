#!/usr/bin/env python3
"""Dependency-free integrity check for the Moth & Gravel GitHub Pages site."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
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
        check(target.is_file(), f"Missing local asset: {relative_path}")

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

    for svg in (ROOT / "assets").glob("*.svg"):
        check(ET.parse(svg).getroot().tag.endswith("svg"), f"Invalid SVG file: {svg.name}")

    if ERRORS:
        print("\n".join(f"FAIL: {issue}" for issue in ERRORS), file=sys.stderr)
        return 1

    print(f"PASS: site integrity ({len(parser.ids)} IDs, {len(parser.references)} local references, {parser.image_count} images)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
