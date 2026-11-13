"""A new HTTP response is not necessarily new evidence."""
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from monitor_coastal_sources import meaning,semantic_hash

DATA=Path(__file__).resolve().parents[1]/'docs/data/coastal-sources/2026-11-11/raw'

class SourceChanges(unittest.TestCase):
    def test_response_clock_changes_do_not_change_measurements(self):
        original=(DATA/'harmaja-weather.xml').read_bytes();changed=ET.fromstring(original)
        changed.attrib['timeStamp']='2026-11-14T00:00:00Z'
        self.assertEqual(semantic_hash(meaning('harmaja-weather.xml',original)),semantic_hash(meaning('harmaja-weather.xml',ET.tostring(changed))))

    def test_a_recovered_missing_value_is_detectable(self):
        original=(DATA/'finnish-wave-observations.xml').read_bytes();changed=ET.fromstring(original)
        target=next(v for v in changed.findall('.//{http://www.opengis.net/waterml/2.0}value') if v.text=='NaN')
        target.text='0.0'  # Test-only mutation, never saved or promoted.
        self.assertNotEqual(semantic_hash(meaning('finnish-wave-observations.xml',original)),semantic_hash(meaning('finnish-wave-observations.xml',ET.tostring(changed))))

    def test_incomplete_catalogue_is_unknown_not_empty(self):
        with self.assertRaises(ValueError):meaning('sentinel-1-grd-day-catalogue.json',json.dumps({'features':[],'links':[{'rel':'next'}]}).encode())

    def test_new_daily_calendar_link_is_detectable(self):
        result=meaning('seismo-calendar.html',b'<a href="./phel2026314.html">10 Nov</a><a href="./phel2026315.html">11 Nov</a>')
        self.assertEqual(result['studyDateLinks'],['./phel2026315.html'])

    def test_truncated_archive_is_unknown_not_empty(self):
        with self.assertRaises(ValueError):meaning('danish-november-archive-list.xml',b'<ListBucketResult><IsTruncated>true</IsTruncated></ListBucketResult>')

if __name__=='__main__':unittest.main()
