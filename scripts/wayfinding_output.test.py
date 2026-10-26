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
            self.assertNotIn('href="/threads/"', text)

    def test_generated_slots_have_no_drift(self):
        build(check=True)

    def test_collection_keeps_exhibits_and_rooms_distinct(self):
        items = json.loads((ROOT / 'assets/specimens.json').read_text())
        self.assertEqual(sum(bool(x.get('exhibit')) for x in items), 2)
        self.assertEqual(sum(len(x.get('children', [])) for x in items), 5)
        self.assertEqual(len(items), 9)


if __name__ == '__main__':
    unittest.main()
