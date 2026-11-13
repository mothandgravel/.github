"""A new HTTP response is not necessarily new evidence."""
import json
from contextlib import redirect_stdout
from io import BytesIO,StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import xml.etree.ElementTree as ET
import monitor_coastal_sources as monitor
from monitor_coastal_sources import meaning,semantic_hash

DATA=Path(__file__).resolve().parents[1]/'docs/data/coastal-sources/2026-11-11/raw'

class SourceChanges(unittest.TestCase):
    def configuration(self,root,name,baseline=None):
        data=root/'data';(data/'raw').mkdir(parents=True)
        (data/'manifest.json').write_text(json.dumps({'receipts':{name:{'url':'https://example.test/source','status':200}}}))
        if baseline is not None:(data/'raw'/name).write_bytes(baseline)
        return data

    def test_deadline_sends_no_requests(self):
        with TemporaryDirectory() as temp,patch.object(monitor,'urlopen') as request,redirect_stdout(StringIO()):
            result=monitor.check(Path(temp)/'unused','2000-01-01T00:00:00Z')
            self.assertEqual(result['status'],'stopped');request.assert_not_called()

    def test_304_without_a_baseline_is_unknown(self):
        with TemporaryDirectory() as temp,redirect_stdout(StringIO()):
            root=Path(temp);name='unknown-baseline.xml';data=self.configuration(root,name)
            with patch.object(monitor,'DATA',data),patch.object(monitor,'NAMES',[name]),patch.object(monitor,'urlopen',side_effect=HTTPError('https://example.test/source',304,'Not modified',{},None)):
                result=monitor.check(root/'updates','2999-01-01T00:00:00Z')
            self.assertEqual(result['unknownOrFailed'],[name]);self.assertIsNone(result['records'][0]['changed'])

    def test_change_remains_visible_against_the_published_packet(self):
        original=(DATA/'harmaja-weather.xml').read_bytes();changed=ET.fromstring(original)
        changed.find('.//{http://www.opengis.net/waterml/2.0}value').text='0.0'
        payload=ET.tostring(changed)
        class Response(BytesIO):
            status=200;url='https://example.test/source';headers={}
        with TemporaryDirectory() as temp,redirect_stdout(StringIO()):
            root=Path(temp);name='harmaja-weather.xml';data=self.configuration(root,name,original)
            with patch.object(monitor,'DATA',data),patch.object(monitor,'NAMES',[name]),patch.object(monitor,'urlopen',side_effect=lambda *a,**k:Response(payload)):
                first=monitor.check(root/'updates','2999-01-01T00:00:00Z')
                second=monitor.check(root/'updates','2999-01-01T00:00:00Z')
            self.assertEqual(first['changed'],[name]);self.assertEqual(second['changed'],[])
            self.assertEqual(first['differsFromPublished'],[name]);self.assertEqual(second['differsFromPublished'],[name])

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
