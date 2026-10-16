#!/usr/bin/env python3
"""One render-ready homepage response, derived from the authored stylesheet."""
from pathlib import Path
from html.parser import HTMLParser
import re

ROOT = Path(__file__).resolve().parents[1]


class LandingElements(HTMLParser):
    def __init__(self):
        super().__init__()
        # Menu/root classes appear only after enhancement, but their styles must ship.
        self.classes = {'has-js', 'is-open', 'has-site-controls', 'has-nav-sheet', 'nav-sheet-heading',
                        'nav-sheet-index', 'nav-sheet-label', 'nav-sheet-hint',
                        'nav-sheet-foot', 'nav-sheet-invitation', 'nav-sheet-mail'}
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.classes.update(values.get('class', '').split())
        if values.get('id'):
            self.ids.add(values['id'])


def used_rules(css, elements):
    """Select rules for the generated landing, retaining media and state behavior.

    The authored CSS uses ordinary qualified rules, media queries and keyframes.
    Strings are tokens, so braces/commas inside quoted values remain untouched.
    """
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[^{}"\']+|[{}]', css)

    def select(start, end):
        selected = []
        cursor = start
        while cursor < end:
            opening = cursor
            while opening < end and tokens[opening] != '{':
                opening += 1
            if opening == end:
                assert not ''.join(tokens[cursor:end]).strip(), 'Unsupported CSS statement'
                break
            depth, closing = 1, opening + 1
            while depth and closing < end:
                depth += (tokens[closing] == '{') - (tokens[closing] == '}')
                closing += 1
            assert depth == 0, 'Unbalanced authored CSS'
            header = ''.join(tokens[cursor:opening]).strip()
            body = ''.join(tokens[opening + 1:closing - 1])
            if header.startswith(('@media', '@supports')):
                body = select(opening + 1, closing - 1)
                if body:
                    selected.append(header + '{' + body + '}')
            elif header.startswith('@'):
                assert header.startswith('@keyframes'), 'Unsupported CSS at-rule'
                selected.append(header + '{' + body + '}')
            else:
                branches = []
                for selector in header.split(','):
                    classes = set(re.findall(r'\.([A-Za-z_-][\w-]*)', selector))
                    ids = set(re.findall(r'#([A-Za-z_-][\w-]*)', selector))
                    if classes <= elements.classes and ids <= elements.ids:
                        branches.append(selector.strip())
                if branches:
                    selected.append(','.join(branches) + '{' + body + '}')
            cursor = closing
        return '\n'.join(selected)

    return select(0, len(tokens))


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
    # Home-only rooms live in their own file so the shared stylesheet stays small for other pages.
    home = (ROOT / 'docs/assets/home.css').read_text()
    css = '\n'.join([core, editorial, covers, invitations, answers, home])
    # Preserve CSS tokens and quoted content; only comments/line indentation leave.
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    elements = LandingElements()
    path = ROOT / 'docs/index.html'
    elements.feed(path.read_text())
    css = used_rules(css, elements)
    css = '\n'.join(line.strip() for line in css.splitlines() if line.strip())
    # Trim syntax whitespace while preserving strings, selector descendants and calc spacing.
    tokens = re.split(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')', css)
    for i in range(0, len(tokens), 2):
        tokens[i] = re.sub(r'\s*([{},;])\s*', r'\1', tokens[i])
        tokens[i] = re.sub(r':\s+', ':', tokens[i])
        tokens[i] = tokens[i].replace(';}', '}')
    css = ''.join(tokens)
    assert '</style' not in css.lower()
    block = '<!-- home-style:start -->\n<style>\n' + css + '\n</style>\n<!-- home-style:end -->'
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
