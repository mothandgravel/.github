"""Generated navigation must resolve at every page depth, including a 404 URL."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import json
import re
import unittest
from build_wayfinding import ROOT, build, site_pages, studio_pages


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs)['href'])


class Wayfinding(unittest.TestCase):
    def test_all_pages_use_the_same_real_destinations(self):
        registry = json.loads((ROOT / 'assets/wayfinding.json').read_text())
        expected = {x['href'] for group in ('routes', 'shortcuts', 'studio') for x in registry[group]}
        expected.add(registry['services']['href'])
        for page in studio_pages():
            text = page.read_text()
            header = text.split('<!-- shared-header:start -->')[1].split('<!-- shared-header:end -->')[0]
            base = 'https://mothandgravel.com/' + page.relative_to(ROOT).as_posix()
            if page.name == '404.html':
                base = 'https://mothandgravel.com/an/unknown/depth/'
            resolved = {urlsplit(urljoin(base, href)).path.removesuffix('index.html') + ('#' + urlsplit(href).fragment if urlsplit(href).fragment else '') for href in Links(header).links}
            self.assertTrue(expected <= resolved, f'{page}: {expected - resolved}')
            self.assertNotIn('/threads/', resolved)

    def test_primary_order_and_business_footer_on_every_page(self):
        domain = 'https://mothandgravel.com'
        destinations = ['/services/', '/specimens/', '/notes/', '/#contact']
        labels = ['Services', 'Specimens', 'Field notes', 'Contact']
        details = [
            'Based in Finland. We work with teams here and abroad, with calls and documentation in English and Finnish.',
            'B2B invoicing through Kissamos Trade Goods (Y-tunnus 2929371-6). NDA ready.',
        ]
        for page in site_pages():
            route = page.relative_to(ROOT).as_posix()
            with self.subTest(page=route):
                text = page.read_text(encoding='utf-8')
                primary = re.findall(r'<nav\b[^>]*aria-label="Primary"[^>]*>.*?</nav>', text, re.S)
                self.assertEqual(len(primary), 1)
                self.assertEqual(re.findall(r'>([^<>]+)</a>', primary[0]), labels)
                base = domain + ('/unknown/deep/path/' if route == '404.html' else '/' + route.removesuffix('index.html'))
                self.assertEqual([urljoin(base, href) for href in Links(primary[0]).links],
                                 [domain + href for href in destinations])
                footer = re.search(r'<footer\b.*?</footer>', text, re.S).group()
                business = footer.split('<!-- shared-business:start -->')[1].split('<!-- shared-business:end -->')[0]
                self.assertEqual([re.sub(r'<[^>]+>', '', line) for line in re.findall(r'<p>(.*?)</p>', business)],
                                 details)
                self.assertEqual(text.count('B2B invoicing through '), 1)

    def test_generated_slots_have_no_drift(self):
        build(check=True)

    def test_collection_resolves_specimen_records_and_child_rooms(self):
        items = json.loads((ROOT / 'assets/specimens.json').read_text())
        self.assertEqual([item['href'] for item in items if item['id'] in ('001', '002')],
                         ['/specimens/skystack/', '/specimens/ajo/'])
        self.assertEqual(sum(len(x.get('children', [])) for x in items), 6)
        coastal = next(x for x in items if x['id'] == '005')
        self.assertIn('/specimens/coastal-watch/source-notebook/', [x['href'] for x in coastal['children']])
        self.assertEqual(len(items), 10)

    def test_thread_context_returns_each_piece_to_its_actual_stop(self):
        thread = json.loads((ROOT / 'assets/thread.json').read_text(encoding='utf-8'))
        pieces = [('specimens/connected-to-what/index.html', 'thread-context', 'reading', 'reply'),
                  ('specimens/ajo/index.html', 'thread-context', 'reply', 'promise'),
                  ('notes/005-green-light.html', 'thread-context', 'promise', 'your-question')]
        for name, slot, current, continuation in pieces:
            text = (ROOT / name).read_text(encoding='utf-8')
            content = text.split('<!-- ' + slot + ':start -->')[1].split('<!-- ' + slot + ':end -->')[0]
            self.assertIn(thread['name'].replace('&', '&amp;'), content)
            self.assertIn('RETURN TO STOP', content)
            base = 'https://mothandgravel.com/' + name
            resolved = [urljoin(base, href) for href in Links(content).links]
            self.assertEqual(resolved, ['https://mothandgravel.com' + thread['href'] + '#' + current,
                                        'https://mothandgravel.com' + thread['href'] + '#' + continuation])
            identity = {'specimens/connected-to-what/index.html': 'connection-meta',
                        'specimens/ajo/index.html': 'work-card-top',
                        'notes/005-green-light.html': 'note-meta'}[name]
            self.assertLess(text.index('class="' + identity), text.index('<!-- ' + slot + ':start -->'))
        self.assertEqual([s['label'] for s in thread['stops']],
                         ['The ageing reading', 'The missing reply', 'The reassuring signal'])


if __name__ == '__main__':
    unittest.main()
