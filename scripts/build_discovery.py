#!/usr/bin/env python3
"""Keep studio, collection and article identities in the initial HTML."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = 'https://mothandgravel.com/'


def build(check=False):
    notes = sorted(json.loads((ROOT / 'docs/assets/notes.json').read_text()),
                   key=lambda n: int(n['id']), reverse=True)
    organization = {
        '@type': 'Organization', '@id': DOMAIN + '#studio',
        'name': 'Moth & Gravel', 'url': DOMAIN,
        'description': 'An independent software and design studio in Finland. Useful tools and thoughtful interfaces, from cloud and mobile software to physical devices.',
        'logo': DOMAIN + 'assets/nav-mark.svg',
        'location': {'@type': 'Place', 'name': 'Finland'},
        'founder': {'@type': 'Person', 'name': 'slideep'},
        'sameAs': ['https://github.com/mothandgravel'],
    }
    website = {'@type': 'WebSite', '@id': DOMAIN + '#website', 'url': DOMAIN,
               'name': 'Moth & Gravel', 'inLanguage': 'en',
               'publisher': {'@id': organization['@id']}}
    pages = [(ROOT / 'docs/index.html', DOMAIN, 'Moth & Gravel — Software & Design Studio, Finland', None),
             (ROOT / 'docs/notes/index.html', DOMAIN + 'notes/', 'Field Notes — Moth & Gravel', None)]
    pages += [(ROOT / 'docs/notes' / n['slug'], DOMAIN + 'notes/' + n['slug'], n['title'], n) for n in notes]
    for path, url, title, note in pages:
        page = {'@type': 'CollectionPage' if url.endswith('notes/') else 'WebPage',
                '@id': url + '#page', 'url': url, 'name': title, 'inLanguage': 'en',
                'isPartOf': {'@id': website['@id']}}
        graph = [organization, website, page]
        if note:
            graph += [{
                '@type': 'BlogPosting', '@id': url + '#article', 'url': url,
                'headline': note['title'], 'description': note['summary'],
                'inLanguage': 'en', 'mainEntityOfPage': {'@id': page['@id']},
                'author': {'@id': organization['@id']}, 'publisher': {'@id': organization['@id']},
                'image': DOMAIN + ('assets/notes/' + note['id'] + '-cover-social.jpg' if note.get('cover') else 'assets/social-cover.png'),
                'keywords': note['topics'],
            }]
            page['mainEntity'] = {'@id': url + '#article'}
            crumbs = [('Moth & Gravel', DOMAIN), ('Field Notes', DOMAIN + 'notes/'), (note['title'], url)]
        else:
            crumbs = [('Moth & Gravel', DOMAIN)]
            if url.endswith('notes/'):
                crumbs.append(('Field Notes', url))
                graph += [{'@type': 'ItemList', '@id': url + '#entries',
                           'itemListElement': [{'@type': 'ListItem', 'position': i + 1,
                                                'name': n['title'], 'url': DOMAIN + 'notes/' + n['slug']}
                                               for i, n in enumerate(notes)]}]
                page['mainEntity'] = {'@id': url + '#entries'}
        if len(crumbs) > 1:
            graph += [{'@type': 'BreadcrumbList', 'itemListElement':
                       [{'@type': 'ListItem', 'position': i + 1, 'name': label, 'item': link}
                        for i, (label, link) in enumerate(crumbs)]}]
        payload = json.dumps({'@context': 'https://schema.org', '@graph': graph},
                             ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
        generated = '<!-- discovery:start -->\n<script type="application/ld+json">' + payload + '</script>\n<!-- discovery:end -->'
        old = path.read_text()
        if '<!-- discovery:start -->' in old:
            new, count = re.subn(r'<!-- discovery:start -->.*?<!-- discovery:end -->',
                                 lambda _: generated, old, flags=re.S)
            assert count == 1, path
        else:
            new = old.replace('</head>', generated + '\n</head>')
        if check:
            assert new == old, f'Stale discovery metadata: run scripts/build_notes.py ({path})'
        else:
            path.write_text(new)
