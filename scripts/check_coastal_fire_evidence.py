"""Verify the dated Coastal watch thermal and agency evidence packet offline."""
from datetime import datetime, timedelta
import json
import struct
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

from check_coastal_day_followup import BASE, digest, receipt


EVIDENCE = BASE / '2026-11-21-fire-evidence'
THERMAL_LAYERS = {
    'rgb_firetemperature': ['fire-rgb-0700.png', 'fire-rgb-1100.png', 'fire-rgb-1300.png', 'fire-rgb-1500.png'],
    'ir105_hrfi': ['ir105-1300.png', 'ir105-1500.png'],
}


def load(name):
    return json.loads((EVIDENCE / name).read_bytes())


def check_hashes():
    manifest = load('sha256.json')
    assert set(manifest) == {p.name for p in EVIDENCE.iterdir() if p.name != 'sha256.json'}
    for name, expected in manifest.items():
        assert digest(EVIDENCE / name) == expected, name
        if not name.endswith('.receipt.json'):
            continue
        record = load(name)
        assert record['file'] + '.receipt.json' == name and record['status'] == 200, name
        assert datetime.fromisoformat(record['requestedAtUtc']) <= datetime.fromisoformat(record['downloadCompletedAtUtc']), name
        body = EVIDENCE / record['file']
        assert record['bytes'] == body.stat().st_size and record['sha256'] == digest(body), name


def check_thermal():
    start = datetime.fromisoformat('2026-11-20T22:00:00Z')
    known_hashes = set()
    for layer, names in THERMAL_LAYERS.items():
        root = ET.parse(EVIDENCE / f'eumetsat-{layer}-domain.xml').getroot()
        times = sorted(map(datetime.fromisoformat, root.findtext('{*}Domain').split(',')))
        assert int(root.findtext('{*}Size')) == len(times) == 131, layer
        assert times == [start + timedelta(minutes=10*i) for i in range(131)], layer
        for name in names:
            record = receipt(name, EVIDENCE)
            query = parse_qs(urlsplit(record['url']).query)
            clock = name.removesuffix('.png')[-4:]
            label = datetime.fromisoformat(f'2026-11-21T{clock[:2]}:{clock[2:]}:00Z')
            assert query['layers'] == [f'mtg_fd:{layer}']
            assert query['bbox'] == ['23,59,28.5,61'] and query['crs'] == ['CRS:84']
            assert list(map(datetime.fromisoformat, query['time'])) == [label] and label in times
            png = (EVIDENCE / name).read_bytes()
            assert png[:8] == b'\x89PNG\r\n\x1a\n' and png[12:16] == b'IHDR', name
            assert struct.unpack('>II', png[16:24]) == (1100, 400), name
            known_hashes.add(record['sha256'])
    assert len(known_hashes) == 6


def check_official():
    document = load('official-record.json')
    assert document['incidentDate'] == '2026-11-21'
    publications = {datetime.fromisoformat(record['publishedAt']).isoformat() for record in document['releases']}
    assert {'2026-11-21T14:58:00+02:00', '2026-11-21T15:03:00+02:00',
            '2026-11-21T20:42:00+02:00'} <= publications
    for name, label in [('press-photo-05.jpg', '21/11/26 16:38:09:08'), ('press-evening-photo.jpg', None)]:
        record = next(image for image in document['images']
                      if image['source']['sha256'] == receipt(name, EVIDENCE)['sha256'])
        assert record['displayedCameraLabel'] == label and record['cameraTimestampUtc'] is None
    assert document['movingImageReport']['directRecordingVerified'] is False


def check_nasa():
    summary = load('nasa-firms-region-summary.json')
    assert summary['windowStartUtc'] == '2026-11-20T22:00:00+00:00'
    assert summary['windowEndUtc'] == '2026-11-21T22:00:00+00:00' and summary['windowEndExclusive']
    assert summary['regionWgs84'] == [23, 59, 28.5, 61]
    exports = summary['rollingExports']
    assert [export['regionalRows'] for export in exports] == [6, 3, 0]
    assert all(export['regionalCountsByCentroidMask'] == {'mappedLand': export['regionalRows']} for export in exports[:2])
    assert min(export['regionalMinSourceLabelUtc'] for export in exports[:2]) == '2026-11-20T23:56:00+00:00'
    assert max(export['regionalMaxSourceLabelUtc'] for export in exports[:2]) == '2026-11-21T01:36:00+00:00'
    for catalogue, count in zip(summary['granuleCatalogues'], (7, 8), strict=True):
        assert len(catalogue['entries']) == catalogue['entryCount'] == count
        for entry in catalogue['entries']:
            assert datetime.fromisoformat(entry['endsUtc']) - datetime.fromisoformat(entry['startsUtc']) == timedelta(minutes=6)


if __name__ == '__main__':
    check_hashes()
    check_thermal()
    check_official()
    check_nasa()
    print('Fire evidence packet verified: 6 thermal frames, 2 official stills, 9 regional detections and 15 granule windows.')
