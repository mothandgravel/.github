"""Verify the evening follow-up packet against its receipts and original snapshot."""
import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import struct
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET


BASE = Path(__file__).resolve().parents[1] / 'docs/data/coastal-days'
ORIGINAL = BASE / '2026-11-21' / 'raw'
FOLLOW_UP = BASE / '2026-11-21-follow-up'


def load(name, folder=FOLLOW_UP):
    return json.loads((folder / name).read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(name, folder=FOLLOW_UP):
    record = load(name + '.receipt.json', folder)
    assert record['file'] == name, name
    return record


def verify_responses():
    manifest = load('sha256.json')
    assert set(manifest) == {p.name for p in FOLLOW_UP.iterdir() if p.name != 'sha256.json'}
    for name, expected in manifest.items():
        assert digest(FOLLOW_UP / name) == expected, name
        if not name.endswith('.receipt.json'):
            continue
        record = load(name)
        assert record['status'] == 200, name
        assert datetime.fromisoformat(record['requestedAtUtc']) <= datetime.fromisoformat(record['downloadCompletedAtUtc']), name
        body = FOLLOW_UP / record['file']
        if body.is_file():
            assert record['bytes'] == body.stat().st_size and record['sha256'] == digest(body), name
        else:
            # The coastal table HTML is retained in the research capture.
            assert body.suffix == '.html', name


def verify_satellites():
    root = ET.parse(FOLLOW_UP / 'eumetsat-domain.xml').getroot()
    labels = root.findtext('{*}Domain').split(',')
    times = sorted(map(datetime.fromisoformat, labels))
    start = datetime.fromisoformat('2026-11-20T22:00:00Z')
    assert len(labels) == int(root.findtext('{*}Size')) == 127
    assert times == [start + timedelta(minutes=10*i) for i in range(127)]
    frames = []
    for i in range(7):
        stamp = datetime.fromisoformat('2026-11-21T07:00:00Z') + timedelta(minutes=10*i)
        name = stamp.strftime('cloud-%H%M.png')
        old, new = receipt(name, ORIGINAL), receipt(name)
        assert 'getaddrinfo failed' in old['error'] and new['url'] == old['url'], name
        query = parse_qs(urlsplit(new['url']).query)
        assert query['layers'] == ['mtg_fd:rgb_geocolour']
        assert query['bbox'] == ['23,59,28.5,61'] and query['crs'] == ['CRS:84']
        assert list(map(datetime.fromisoformat, query['time'])) == [stamp] and stamp in times
        frames.append(name)
    for craft in ('terra', 'aqua'):
        name = f'nasa-modis-{craft}-2026-11-21.png'
        query = parse_qs(urlsplit(receipt(name)['url']).query)
        assert query['LAYERS'] == [f'MODIS_{craft.title()}_CorrectedReflectance_TrueColor']
        assert query['TIME'] == ['2026-11-21'] and query['BBOX'] == ['23,59,28.5,61']
        frames.append(name)
    assert len({digest(FOLLOW_UP / name) for name in frames}) == 9
    for name in frames:
        png = (FOLLOW_UP / name).read_bytes()
        assert png[:8] == b'\x89PNG\r\n\x1a\n' and png[12:16] == b'IHDR', name
        assert struct.unpack('>II', png[16:24]) == (1100, 400), name
    for name, count in [('sentinel-1-grd-day-catalogue.json', 7), ('sentinel-2-l2a-day-catalogue.json', 17)]:
        assert receipt(name)['url'] == receipt(name, ORIGINAL)['url'], name
        result = load(name)
        assert len(result['features']) == count and result == load(name, ORIGINAL), name
        assert all(link['rel'] != 'next' for link in result['links']), name


def verify_gauges():
    assert receipt('original-window.json')['url'] == receipt('estonian-gauges.json', ORIGINAL)['url']
    for name in ('original-window.json', 'elapsed-window.json', 'civil-day.json'):
        assert (FOLLOW_UP / name).read_bytes() == (ORIGINAL / 'estonian-gauges.json').read_bytes() == b'[]'
    assert len(load('known-day-control.json')) == 144
    snapshots = load('operational-gauges.json')['snapshots']
    assert [s['labelledAtUtc'] for s in snapshots] == [
        f'2026-11-21T{time}:00:00Z' for time in ('07', '10', '15', '19')
    ]
    with (FOLLOW_UP / 'operational-gauges.csv').open(encoding='utf-8', newline='') as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 12
    for i, snapshot in enumerate(snapshots):
        record = load(snapshot['receiptFile'])
        epoch = datetime.fromisoformat(snapshot['labelledAtUtc'])
        local = datetime.fromisoformat(snapshot['labelledAtEet'])
        assert epoch == local and local.utcoffset() == timedelta(hours=2)
        assert snapshot['sourceHtmlSha256'] == record['sha256'] and snapshot['sourceUrl'] == record['url']
        assert snapshot['retrievedAtUtc'] == record['downloadCompletedAtUtc']
        assert [s['agencyStationCode'] for s in snapshot['observations']] == ['86094', '26045', '41801']
        for csv_row, observation in zip(rows[3*i:3*i+3], snapshot['observations'], strict=True):
            assert csv_row['labelledAtUtc'] == snapshot['labelledAtUtc']
            assert all(csv_row[key] == value for key, value in observation.items())


def verify_ais():
    assert (FOLLOW_UP / 'sparta-morning.json').read_bytes() == (ORIGINAL / 'sparta-location-gzip.json').read_bytes()
    assert load('sparta-1000-to-1300-eet.json')['features'] == []
    assert (FOLLOW_UP / 'danish-day-list.xml').read_bytes() == (ORIGINAL / 'danish-day-list.xml').read_bytes()
    root = ET.parse(FOLLOW_UP / 'danish-month-list.xml').getroot()
    keys = [node.text for node in root.findall('.//{*}Key')]
    assert root.findtext('{*}IsTruncated') == 'false'
    assert sorted(keys) == [f'aisdk-2026-11-{day:02}.zip' for day in range(1, 19)]


if __name__ == '__main__':
    verify_responses()
    verify_satellites()
    verify_gauges()
    verify_ais()
    print('21 November follow-up verified: 9 source images, 12 operational rows, bounded AIS and archive controls.')
