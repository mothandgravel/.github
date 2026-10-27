"""Generated navigation must resolve at every page depth, including a 404 URL."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import json
import unittest
from build_wayfinding import ROOT, build


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
        expected = {x['href'] for group in registry.values() for x in group}
        for page in ROOT.rglob('*.html'):
            text = page.read_text()
            header = text.split('<!-- shared-header:start -->')[1].split('<!-- shared-header:end -->')[0]
            base = 'https://mothandgravel.com/' + page.relative_to(ROOT).as_posix()
            if page.name == '404.html':
                base = 'https://mothandgravel.com/an/unknown/depth/'
            resolved = {urlsplit(urljoin(base, href)).path.removesuffix('index.html') + ('#' + urlsplit(href).fragment if urlsplit(href).fragment else '') for href in Links(header).links}
            self.assertTrue(expected <= resolved, f'{page}: {expected - resolved}')
            self.assertNotIn('/threads/', resolved)

    def test_generated_slots_have_no_drift(self):
        build(check=True)

    def test_collection_keeps_exhibits_and_rooms_distinct(self):
        items = json.loads((ROOT / 'assets/specimens.json').read_text())
        self.assertEqual(sum(bool(x.get('exhibit')) for x in items), 2)
        self.assertEqual(sum(len(x.get('children', [])) for x in items), 5)
        self.assertEqual(len(items), 9)

    def test_thread_context_returns_each_piece_to_its_actual_stop(self):
        thread = json.loads((ROOT / 'assets/thread.json').read_text(encoding='utf-8'))
        pieces = [('specimens/connected-to-what/index.html', 'thread-context', 'reading', 'reply'),
                  ('index.html', 'thread-context-reply', 'reply', 'promise'),
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
            if name != 'index.html':
                identity = 'connection-meta' if name.startswith('specimens/') else 'note-meta'
                self.assertLess(text.index('class="' + identity), text.index('<!-- ' + slot + ':start -->'))
        self.assertEqual([s['label'] for s in thread['stops']],
                         ['The ageing reading', 'The missing reply', 'The reassuring signal'])


if __name__ == '__main__':
    unittest.main()
