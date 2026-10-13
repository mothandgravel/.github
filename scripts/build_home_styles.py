#!/usr/bin/env python3
"""One render-ready homepage response, derived from the authored stylesheet."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def build(check=False):
    source = (ROOT / 'docs/assets/site.css').read_text()
    # These authored sections style the landing. Article-only sections stay external.
    core = source.split('/* SPRINT 02 / FIELD NOTES')[0]
    editorial = source.split('/* Field Notes: one editorial feature,')[1].split('/* Photographic editorial cover')[0]
    editorial = '/* Field Notes: one editorial feature,' + editorial
    covers = source.split('.editorial-cover {')[1].split('.metaphor-heading {')[0]
    covers = '.editorial-cover {' + covers
    invitations = source.split('/* Invitations to follow the work,')[1].split('/* Field Note 005:')[0]
    invitations = '/* Invitations to follow the work,' + invitations
    answers = source.split('/* Useful answers and an early invitation,')[1]
    answers = '/* Useful answers and an early invitation,' + answers
    css = '\n'.join([core, editorial, covers, invitations, answers])
    # Preserve CSS tokens and quoted content; only comments/line indentation leave.
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    css = '\n'.join(line.strip() for line in css.splitlines() if line.strip())
    assert '</style' not in css.lower()
    block = '<!-- home-style:start -->\n<style>\n' + css + '\n</style>\n<!-- home-style:end -->'
    path = ROOT / 'docs/index.html'
    old = path.read_text()
    if '<!-- home-style:start -->' in old:
        new, count = re.subn(r'<!-- home-style:start -->.*?<!-- home-style:end -->',
                             lambda _: block, old, flags=re.S)
    else:
        new, count = re.subn(r'<link rel="stylesheet" href="\./assets/site.css">',
                             lambda _: block, old)
    assert count == 1, 'Missing or duplicate homepage style slot'
    if check:
        assert old == new, 'Stale homepage styles: run scripts/build_notes.py'
    else:
        path.write_text(new)
