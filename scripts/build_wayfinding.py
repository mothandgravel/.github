#!/usr/bin/env python3
"""Author one studio map into every public page; no runtime routing required."""
from pathlib import Path
from html import escape
import json
import posixpath
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1] / 'docs'


def load(name):
    return json.loads((ROOT / 'assets' / name).read_text(encoding='utf-8'))


def destination(href):
    url = urlsplit(href)
    assert href.startswith('/') and not url.netloc and not url.query, href
    path = ROOT / url.path.lstrip('/')
    if path.is_dir():
        path /= 'index.html'
    assert path.is_file(), f'Missing navigation destination: {href}'
    if url.fragment:
        assert re.search(r'\bid=[\"\']' + re.escape(url.fragment) + r'[\"\']', path.read_text(encoding='utf-8')), href


def local(href, page):
    # A 404 can be served at any unknown depth. Its paths must be root-relative.
    if page.name == '404.html':
        return href
    url = urlsplit(href)
    parent = page.relative_to(ROOT).parent.as_posix()
    target = url.path.lstrip('/') or '.'
    result = posixpath.relpath(target, parent)
    if url.path.endswith('/') and not result.endswith('/'):
        result += '/'
    if result == './':
        result = './'
    if not result.startswith('.'):
        result = './' + result
    if page == ROOT / 'index.html' and url.path == '/' and url.fragment:
        return '#' + url.fragment
    return result + ('#' + url.fragment if url.fragment else '')


def current(href, page):
    route = '/' + page.relative_to(ROOT).as_posix()
    route = route.removesuffix('index.html')
    return href.endswith('/') and (route == href or (href in ['/specimens/', '/notes/'] and route.startswith(href)))


def link(item, page, extra=''):
    route = '/' + page.relative_to(ROOT).as_posix().removesuffix('index.html')
    state = f' aria-current="{"page" if route == item["href"] else "location"}"' if current(item['href'], page) else ''
    return f'<a href="{local(item["href"], page)}"{state}{extra}>{escape(item["label"])}</a>'


def header(page, nav):
    routes = []
    for i, item in enumerate(nav['routes'], 1):
        label = f'<span class="nav-sheet-index mono" aria-hidden="true">{i:02}</span><span class="nav-sheet-label">{escape(item["label"])}</span><span class="nav-sheet-hint">{escape(item["hint"])}</span>'
        routes.append(link(item, page).replace(escape(item['label']) + '</a>', label + '</a>'))
    shortcuts = ''.join(f'<a class="nav-shortcut" href="{local(x["href"], page)}"><strong>{escape(x["label"])} ↗</strong><span>{escape(x["hint"])}</span></a>' for x in nav['shortcuts'])
    studio = ''.join(link(x, page) for x in nav['studio'])
    return f'''<header class="site-header shared-header" id="top"><div class="header-inner shell">
<a class="brand" href="{local('/', page)}" title="Moth &amp; Gravel home"><span class="brand-stamp" aria-hidden="true"><img src="{local('/assets/nav-mark.svg', page)}" width="44" height="44" alt=""></span><span class="brand-type">MOTH <span class="brand-amp">&amp;</span> GRAVEL<span class="brand-sub">INDEPENDENT WORKS</span></span></a>
<nav class="collection-nav" aria-label="Collections">{''.join(link(x, page) for x in nav['routes'][:2])}{link(nav['routes'][3], page, ' class="collection-contact"')}</nav>
<p class="header-mail"><a class="header-mail-link" href="mailto:hello@mothandgravel.com?subject=A%20question%20for%20Moth%20%26%20Gravel"><span class="header-mail-short">Email </span><span class="header-mail-address">hello@mothandgravel.com</span></a><button class="copy-mail" type="button" data-copy-email hidden>Copy<span class="visually-hidden"> email address</span></button></p>
<button class="light-switch" id="light-switch" type="button"><span class="switch-orb" aria-hidden="true"></span><span class="switch-label"><span class="visually-hidden">Theme: </span><span data-theme-label>System</span></span></button>
<details class="studio-index"><summary class="menu-toggle" id="menu-toggle" aria-controls="primary-nav"><span>Menu</span><span class="menu-bars" aria-hidden="true"><span></span><span></span></span></summary>
<nav class="main-nav studio-sheet" id="primary-nav" aria-label="Studio index"><div class="nav-sheet-heading"><span class="mono">M+G / THE STUDIO INDEX</span><p>A few ways in.</p></div>{''.join(routes)}<section class="nav-shortcuts" aria-labelledby="shortcut-heading"><p class="mono" id="shortcut-heading">Straight to.</p><div>{shortcuts}</div></section><div class="nav-studio">{studio}</div></nav></details>
</div></header>'''


def slot(text, name, value, fallback):
    block = f'<!-- {name}:start -->\n{value}\n<!-- {name}:end -->'
    pattern = rf'<!-- {name}:start -->.*?<!-- {name}:end -->'
    if re.search(pattern, text, re.S):
        text, count = re.subn(pattern, lambda _: block, text, flags=re.S)
        assert count == 1, name
        return text
    return fallback(text, block)


def catalogue(items):
    cards = []
    page = ROOT / 'specimens/index.html'
    for x in items:
        loading = 'eager' if x['id'] == '009' else 'lazy'
        image = f'<img src="{local("/" + x["image"], page)}" width="{x["width"]}" height="{x["height"]}" alt="{escape(x["alt"], quote=True)}" loading="{loading}">' if x.get('image') else '<div class="specimen-trace" aria-label="Two states from the saved lost-query simulator record"><span>01 / REPLY LOST</span><b>Answer missing.</b><span>02 / RESULT QUERIED</span><b>Result found.</b><span>1 application at the receiver / both states</span></div>'
        children = ''.join(f'<a href="{local(c["href"], page)}">{escape(c["label"])} ↗</a>' for c in x.get('children', []))
        cards.append(f'''<article class="specimen-entry{' specimen-featured' if x['id']=='009' else ''}" id="specimen-{x['id']}"><div class="specimen-art">{image}<p>{escape(x['boundary'])}</p></div><div class="specimen-copy"><p class="mono">{x['id']} / {escape(x['name'])}{' / EARLIER EXHIBIT' if x.get('exhibit') else ''}</p><h2><a href="{local(x['href'], page)}">{escape(x['title'])}</a></h2><p>{escape(x['summary'])}</p><a class="specimen-open" href="{local(x['href'], page)}">{'Visit the homepage exhibit' if x.get('exhibit') else 'Open the specimen'} <span aria-hidden="true">↗</span></a>{f'<nav class="specimen-rooms" aria-label="Inside {escape(x["name"])}">{children}</nav>' if children else ''}</div></article>''')
    return '\n'.join(cards)


def thread_context(thread, stop, index, page):
    total = len(thread['stops'])
    current_stop = local(thread['href'] + '#' + stop['id'], page)
    continuation = local(thread['href'] + '#' + stop['next'], page)
    next_number = f'{index + 2:02} / ' if index + 1 < total else ''
    return f'''<nav class="thread-context" aria-label="{escape(thread['name'], quote=True)} / stop {index + 1} of {total}"><p class="thread-context-title"><span class="mono">IN THREAD 01</span>{escape(thread['name'])}</p><a class="thread-context-back" href="{current_stop}"><span class="mono">RETURN TO STOP {index + 1:02} OF {total:02}</span><strong>{escape(stop['label'])}&#160;<span aria-hidden="true">↗</span></strong></a><a class="thread-context-next" href="{continuation}"><span class="mono">CONTINUE THE THREAD</span><strong>{next_number}{escape(stop['nextLabel'])}&#160;<span aria-hidden="true">→</span></strong></a></nav>'''


def build(check=False):
    nav, items, notes = load('wayfinding.json'), load('specimens.json'), load('notes.json')
    thread = load('thread.json')
    stops = []
    for index, stop in enumerate(thread['stops']):
        destination(thread['href'] + '#' + stop['id'])
        destination(thread['href'] + '#' + stop['next'])
        if stop['kind'] == 'specimen':
            target = next(item['href'] for item in items if item['id'] == stop['ref'])
        else:
            assert stop['kind'] == 'note', stop
            target = '/notes/' + next(note['slug'] for note in notes if note['id'] == stop['ref'])
        destination(target)
        url = urlsplit(target)
        path = ROOT / url.path.lstrip('/')
        if path.is_dir():
            path /= 'index.html'
        stops.append((path, url.fragment, index, stop))
    assert [x['id'] for x in items] == [f'{i:03}' for i in range(9, 0, -1)]
    assert len(nav['routes']) == 4 and len(nav['shortcuts']) == 3
    for item in nav['routes'] + nav['shortcuts'] + nav['studio'] + items + [c for x in items for c in x.get('children', [])]:
        destination(item['href'])
    for item in items:
        if item.get('image'):
            assert (ROOT / item['image']).is_file(), item['image']
    pages = sorted(ROOT.rglob('*.html'))
    for page in pages:
        old = page.read_text(encoding='utf-8')
        text = slot(old, 'shared-header', header(page, nav), lambda s, b: re.sub(r'<header\b[^>]*class="site-header[^\"]*".*?</header>', lambda _: b, s, count=1, flags=re.S))
        assert '<!-- shared-header:start -->' in text, f'Missing masthead: {page}'
        footer = '<nav class="shared-footer-nav shell" aria-label="Explore the studio">' + ''.join(link(x, page) for x in nav['routes']) + link({'label':'Example workbench','href':'/workbench/'}, page) + '</nav>'
        text = slot(text, 'shared-footer', footer, lambda s, b: s.replace('</footer>', b + '\n</footer>'))
        assert '<!-- shared-footer:start -->' in text, f'Missing footer: {page}'
        for destination_page, fragment, index, stop in stops:
            if page != destination_page:
                continue
            context = thread_context(thread, stop, index, page)
            if fragment:
                def add_to_exhibit(source, block):
                    pattern = r'(<article\b[^>]*\bid="' + re.escape(fragment) + r'"[^>]*>\s*<div class="work-card-top[^>]*>.*?</div>)'
                    result, count = re.subn(pattern, lambda match: match[0] + '\n' + block, source, count=1, flags=re.S)
                    assert count == 1, f'Missing thread exhibit: {fragment}'
                    return result
                text = slot(text, 'thread-context-' + stop['id'], context, add_to_exhibit)
            else:
                text = slot(text, 'thread-context', context, lambda source, block: source.replace('<!-- thread-context-anchor -->', block))
                assert '<!-- thread-context:start -->' in text, f'Place thread-context-anchor after the piece identity: {page}'
        if page == ROOT / 'specimens/index.html':
            text = slot(text, 'specimen-catalogue', catalogue(items), lambda s, b: s.replace('<!-- catalogue -->', b))
        elif 'specimens' in page.relative_to(ROOT).parts:
            item = next(x for x in items if str(page.relative_to(ROOT)).replace('\\', '/').startswith(x['href'].lstrip('/')))
            crumbs = '<nav class="collection-context shell" aria-label="Specimen collection"><a href="' + local('/specimens/', page) + '">All specimens ↗</a>'
            if page != ROOT / item['href'].lstrip('/') / 'index.html':
                crumbs += f'<a href="{local(item["href"], page)}">{item["id"]} / {escape(item["name"])} ↗</a>'
            crumbs += '</nav>'
            text = slot(text, 'specimen-parent', crumbs, lambda s, b: re.sub(r'(<main\b[^>]*>)', lambda m: m[0] + '\n' + b, s, count=1))
            related = [n for n in notes if n.get('specimen') and urlsplit(n['specimen']['href'].removeprefix('../')).path.rstrip('/') == item['href'].strip('/')]
            reading = '<aside class="specimen-reading"><p class="mono">FROM THE SAME WORK / FIELD NOTES</p>' + ''.join(f'<a href="{local("/notes/" + n["slug"], page)}">{n["id"]} / {escape(n["title"])} ↗</a>' for n in related) + '</aside>' if related else ''
            text = slot(text, 'specimen-reading', reading, lambda s, b: s.replace('</main>', b + '\n</main>'))
        if check:
            assert old == text, f'Stale shared navigation: {page}; run scripts/build_notes.py'
        elif text != old:
            page.write_text(text, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    import sys
    build('--check' in sys.argv)
