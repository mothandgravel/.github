"""Verify the saved source clocks and regional satellite evidence."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from struct import unpack
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/data/coastal-days'
PACKET = DATA / '2026-11-21-sparta-view'
PAGE = ROOT / 'docs/specimens/coastal-watch/source-notebook/21-november/sparta-ii/index.html'
REGION = '23,59,28.5,61'
LABELS = {
    '2026-11-21T17:00:00.000Z', '2026-11-21T19:00:00.000Z', '2026-11-21T21:50:00.000Z',
    '2026-11-22T04:00:00.000Z', '2026-11-22T08:00:00.000Z',
}
LAYERS = {'mtg_fd:rgb_geocolour', 'mtg_fd:ir105_hrfi', 'mtg_fd:rgb_firetemperature'}


def read_json(path):
    return json.loads(path.read_bytes())


def verify_packet():
    inventory = read_json(PACKET / 'sha256.json')
    assert set(inventory) == {file.name for file in PACKET.iterdir()} - {'sha256.json'}
    for name, digest in inventory.items():
        assert sha256((PACKET / name).read_bytes()).hexdigest() == digest, name

    ledger = (PACKET / 'ledger.html').read_text(encoding='utf-8')
    frames = set()
    for path in PACKET.glob('*.receipt.json'):
        receipt = read_json(path)
        name = receipt['file']
        body = (PACKET / name).read_bytes()
        assert receipt['status'] == 200 and receipt['bytes'] == len(body), name
        assert inventory[name] == receipt['sha256'], name
        assert f'href="{name}"' in ledger and f'href="{path.name}"' in ledger, name
        assert datetime.fromisoformat(receipt['requestedAtUtc']).utcoffset() == timedelta(0), name
        if name.endswith('.png'):
            request = parse_qs(urlparse(receipt['url']).query)
            assert body[:8] == b'\x89PNG\r\n\x1a\n' and unpack('>II', body[16:24]) == (1100, 400), name
            assert request['bbox'] == [REGION] and request['crs'] == ['CRS:84'], name
            elapsed_since_label = datetime.fromisoformat(receipt['requestedAtUtc']) - datetime.fromisoformat(request['time'][0])
            assert elapsed_since_label > timedelta(0), name
            sample = request['time'][0], request['layers'][0]
            assert sample not in frames, name
            frames.add(sample)

    assert frames == {(label, layer) for label in LABELS for layer in LAYERS}
    for product, count in [('VJ102IMG_NRT', 5), ('VJ202IMG_NRT', 4)]:
        assert len(read_json(PACKET / f'22-cmr-{product}.json')['feed']['entry']) == count
    for product, count in [('1-grd', 5), ('2-l2a', 0)]:
        assert len(read_json(PACKET / f'22-sentinel-{product}-day-catalogue.json')['features']) == count


def verify_clocks():
    source = read_json(DATA / '2026-11-21/raw/sparta-location-gzip.json')
    assert len(source['features']) == 1
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    ais = epoch + timedelta(milliseconds=source['features'][0]['properties']['timestampExternal'])
    video = read_json(DATA / '2026-11-21-video-clock/video-source.json')['officialPost']
    published = datetime.fromisoformat(video['publishedAtUtc'])
    assert published - ais == timedelta(hours=12, minutes=1, seconds=26, milliseconds=356)
    assert read_json(DATA / '2026-11-21-follow-up/sparta-1000-to-1300-eet.json')['features'] == []

    page = PAGE.read_text(encoding='utf-8')
    for date in (ais.isoformat(timespec='milliseconds'), published.isoformat(timespec='seconds')):
        assert f'datetime="{date.replace("+00:00", "Z")}"' in page
    for label in LABELS:
        assert f'datetime="{label.replace(".000", "")}"' in page
    assert '12 h 01 min <span>26.356 s</span>' in page
    assert video['watchUrl'] in page
    assert '<video' not in page and '<audio' not in page and '<iframe' not in page


if __name__ == '__main__':
    verify_packet()
    verify_clocks()
    print('Sparta II: saved AIS and clip clocks, 15 satellite frames, catalogue counts and source receipts verified')
