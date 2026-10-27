"""Authoring contracts for generated endings, including future catalog states."""
from copy import deepcopy
from html import escape
from html.parser import HTMLParser
import json
import sys
import unittest

from build_notes import load_notes, reading_exit, specimen_for, row, archive_feature, archive_connections, ROOT
from check_site import SiteParser


def fixtures():
    result = []
    for case in ('fallback', 'independent', 'thread-only', 'overlapping-revision', 'featured-revision'):
        notes = deepcopy(load_notes())
        by_id = {note['id']: note for note in notes}
        note = by_id['001']
        note.pop('nextReading', None)
        note['related'] = ['002']
        note['thread'] = ''
        next_id = '002'
        if case == 'independent':
            note['related'] = []
            next_id = None
        elif case == 'thread-only':
            note['related'] = []
            note['thread'] = by_id['002']['thread'] = 'fixture-thread'
            next_id = None
        elif case == 'overlapping-revision':
            note['related'].append('003')
            for identifier in ('001', '002', '003'):
                by_id[identifier]['thread'] = 'fixture-thread'
            by_id['003']['supersedes'] = ['001']
        elif case == 'featured-revision':
            by_id['002']['supersedes'] = ['001']
        result.append({'case': case, 'html': reading_exit(note, notes),
                       'note': note, 'notes': notes,
                       'nextSlug': by_id[next_id]['slug'] if next_id else None,
                       'bridge': by_id[next_id]['summary'] if next_id else None})
    return result


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.hrefs = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.hrefs.append(dict(attrs).get('href'))


class ReadingOutputTests(unittest.TestCase):
    def setUp(self):
        self.cases = {case['case']: case for case in fixtures()}

    def test_archive_connections_resolve_existing_specimens_and_keep_evidence_captions(self):
        notes = load_notes()
        specimens = json.loads((ROOT / 'docs/assets/specimens.json').read_text(encoding='utf-8'))
        featured = next(n for n in notes if n['featured'])
        self.assertIn('SPECIMEN 008', archive_feature(featured, specimens))
        self.assertIn('../specimens/data-center/#fi-account', Links(archive_feature(featured, specimens)).hrefs)
        html = archive_connections(notes, featured, specimens)
        self.assertIn('SPECIMEN 006', html)
        self.assertIn('SPECIMEN 005', html)
        self.assertIn('synthetic tracks', html)
        self.assertIn('no live voyage', html)
        self.assertNotIn('object-fit', html)
        for note in notes:
            output = row(note, './', specimens=specimens)
            item = specimen_for(note, specimens)
            if item:
                self.assertIn(note['specimen']['href'], Links(output).hrefs)
                self.assertIn('SPECIMEN ' + item['id'], output)
            else:
                self.assertNotIn('archive-specimen', output)
        self.assertNotIn('archive-specimen', row(next(n for n in notes if n['id'] == '015'), './', specimens=specimens))
        investigation = row(next(n for n in notes if n['id'] == '015'), './', specimens=specimens)
        self.assertIn('INVESTIGATION', investigation)
        self.assertIn('../investigations/take-it-back/', Links(investigation).hrefs)
        self.assertNotIn('Return to ', row(next(n for n in notes if n['id'] == '012'), './', specimens=specimens))

    def test_optional_choice_uses_first_relation_and_summary(self):
        case = self.cases['fallback']
        self.assertEqual(Links(case['html']).hrefs.count('./' + case['nextSlug']), 1)
        self.assertIn(escape(case['bridge']), case['html'])

    def test_independent_note_keeps_usable_exits_without_a_false_recommendation(self):
        html = self.cases['independent']['html']
        self.assertNotIn('class="reading-next"', html)
        self.assertIn('reading-exit-solo', html)
        self.assertIn('../questions/', Links(html).hrefs)
        self.assertIn('./', Links(html).hrefs)

    def test_revision_keeps_specific_label_when_also_related_and_in_thread(self):
        html = self.cases['overlapping-revision']['html']
        self.assertIn('Revisited in', html)
        links = Links(html).hrefs
        self.assertEqual(len(links), len(set(links)))

    def test_featured_revision_is_identified_as_a_revisit(self):
        self.assertIn('REVISITED IN / 002', self.cases['featured-revision']['html'])

    def test_thread_without_a_primary_continuation_does_not_skip_a_heading_level(self):
        html = self.cases['thread-only']['html']
        self.assertIn('<h2 class="mono">Continue the thread</h2>', html)
        self.assertNotIn('<h3', html)

    def test_page_contract_accepts_one_styled_ending_outside_prose(self):
        page = SiteParser()
        page.feed('<link rel="stylesheet" href="../assets/reading-room.css">'
                  '<article class="note-prose"><p>A study.</p></article>'
                  + self.cases['fallback']['html'])
        self.assertEqual(page.reading_issues(), [])

    def test_page_contract_rejects_missing_style_and_legacy_duplicate(self):
        page = SiteParser()
        page.feed(self.cases['fallback']['html'] + '<div class="note-end"></div>')
        self.assertEqual(len(page.reading_issues()), 2)

    def test_page_contract_keeps_navigation_out_of_narration(self):
        page = SiteParser()
        page.feed('<link rel="stylesheet" href="../assets/reading-room.css">'
                  '<article class="note-prose"><article>A nested material.</article>'
                  + self.cases['fallback']['html'] + '</article>')
        self.assertEqual(len(page.reading_issues()), 1)


if __name__ == '__main__':
    if sys.argv[1:] == ['--fixtures']:
        print(json.dumps(fixtures()))
    else:
        unittest.main()
