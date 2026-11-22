"""Verify the saved source clocks and regional satellite evidence."""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
from pathlib import Path
from struct import unpack
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/data/coastal-days'
PACKET = DATA / '2026-11-21-sparta-view'
FOLLOWUP = DATA / '2026-11-22-sparta-update'
PAGE = ROOT / 'docs/specimens/coastal-watch/source-notebook/21-november/sparta-ii/index.html'
REGION = '23,59,28.5,61'
LABELS = {
    '2026-11-21T17:00:00.000Z', '2026-11-21T19:00:00.000Z', '2026-11-21T21:50:00.000Z',
    '2026-11-22T04:00:00.000Z', '2026-11-22T08:00:00.000Z',
}
LAYERS = {'mtg_fd:rgb_geocolour', 'mtg_fd:ir105_hrfi', 'mtg_fd:rgb_firetemperature'}
AFTERNOON_LABEL = '2026-11-22T12:30:00.000Z'


def read_json(path):
    return json.loads(path.read_bytes())


def verify_packet(packet, labels):
    inventory = read_json(packet / 'sha256.json')
    assert set(inventory) == {file.name for file in packet.iterdir()} - {'sha256.json'}
    for name, digest in inventory.items():
        assert sha256((packet / name).read_bytes()).hexdigest() == digest, name

    frames = set()
    for path in packet.glob('*.receipt.json'):
        receipt = read_json(path)
        name = receipt['file']
        body = (packet / name).read_bytes()
        assert receipt['status'] == 200 and receipt['bytes'] == len(body), name
        assert inventory[name] == receipt['sha256'], name
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

    assert frames == {(label, layer) for label in labels for layer in LAYERS}


def verify_original_counts():
    ledger = (PACKET / 'ledger.html').read_text(encoding='utf-8')
    for path in PACKET.glob('*.receipt.json'):
        name = read_json(path)['file']
        assert f'href="{name}"' in ledger and f'href="{path.name}"' in ledger, name
    for product, count in [('VJ102IMG_NRT', 5), ('VJ202IMG_NRT', 4)]:
        assert len(read_json(PACKET / f'22-cmr-{product}.json')['feed']['entry']) == count
    for product, count in [('1-grd', 5), ('2-l2a', 0)]:
        assert len(read_json(PACKET / f'22-sentinel-{product}-day-catalogue.json')['features']) == count


def verify_afternoon_satellite():
    snapshot = read_json(FOLLOWUP / 'satellite.json')
    assert snapshot['retrievalMinuteUtc'] == '2026-11-22T12:55:00Z'
    expected = (('2-l2a', 0, 20), ('1-grd', 5, 5), ('VJ102IMG', 5, 6),
                ('VJ202IMG', 4, 6), ('VJ114IMG', 5, 6), ('VJ214IMG', 4, 6))
    for row, (product, earlier, later) in zip(snapshot['catalogues'], expected, strict=True):
        assert product in row['file']
        bodies = [read_json(FOLLOWUP / row[field]) for field in ('earlierFile', 'file')]
        counts = [len(body['features'] if 'features' in body else body['feed']['entry']) for body in bodies]
        assert counts == [earlier, later] == [row['earlierCount'], row['afternoonCount']], product
        assert (FOLLOWUP / row['receipt']).is_file() and (FOLLOWUP / row['earlierReceipt']).is_file(), product
        if product == '2-l2a':
            assert {feature['properties']['datetime'] for feature in bodies[1]['features']} == {
                '2026-11-22T09:52:29.024000Z'
            }
    for source in snapshot['eumetsatCatalogues']:
        document = ElementTree.parse(FOLLOWUP / source['file'])
        domain = document.find('{*}Domain').text.split(',')
        assert len(set(domain)) == 88 and max(domain) == AFTERNOON_LABEL
    assert len(snapshot['eumetsatCatalogues']) == len(snapshot['eumetsatRenders']) == 3
    assert {row['productLabelUtc'] for row in snapshot['eumetsatRenders']} == {AFTERNOON_LABEL}


def verify_official_followup():
    record = read_json(FOLLOWUP / 'official.json')
    page = PAGE.read_text(encoding='utf-8')
    checked = datetime.fromisoformat(record['checkedAtUtc']).replace(second=0, microsecond=0)
    assert checked.isoformat().replace('+00:00', 'Z') in page
    tow = record['tow']
    assert tow['state'] == 'start-unconfirmed' and tow['startedAtUtc'] is None
    for field in ('plan', 'morningUpdate', 'preparation'):
        assert tow[field]['publishedAtUtc'] in page and tow[field]['url'] in page
    reports = record['laterReports']
    for report in reports.values():
        assert report['publishedAtUtc'] in page and report['url'] in page
        assert datetime.fromisoformat(report['sourceReceipt']['downloadCompletedAtUtc']) > datetime.fromisoformat(report['publishedAtUtc'])
    assert tow['latestEvidence'] == 'laterReports.briefingTow'
    assert reports['heatCameraInterview']['recordingAtUtc'] is None
    assert reports['heatCameraInterview']['containsThermalFrames'] is False
    assert reports['briefingOpening']['broadcastUrl'] in page

    media = record['media']
    receipt = read_json(FOLLOWUP / media['receipt'])
    assert media['captureAtUtc'] is None and media['publishedAtUtc'] is None
    assert not any(media[field] for field in ('exifPresent', 'gpsDirectoryPresent', 'xmpPresent', 'iptcLocationPresent'))
    assert parsedate_to_datetime(receipt['lastModified']) == datetime.fromisoformat(media['httpLastModifiedUtc'])
    assert media['httpLastModifiedUtc'] in page and media['receipt'] in page
    recheck = media['afterBriefingStarted']['filesTabReceipt']['downloadCompletedAtUtc']
    assert datetime.fromisoformat(recheck) > datetime.fromisoformat(reports['briefingTow']['publishedAtUtc'])
    assert recheck.replace('+00:00', 'Z') in page


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
    assert f'datetime="{AFTERNOON_LABEL.replace(".000", "")}"' in page
    assert '12 h 01 min <span>26.356 s</span>' in page
    assert video['watchUrl'] in page
    assert '<video' not in page and '<audio' not in page and '<iframe' not in page


if __name__ == '__main__':
    verify_packet(PACKET, LABELS)
    verify_packet(FOLLOWUP, {AFTERNOON_LABEL})
    verify_original_counts()
    verify_afternoon_satellite()
    verify_official_followup()
    verify_clocks()
    print('Sparta II: saved AIS and clip clocks, 18 satellite frames, both catalogue snapshots and source receipts verified')
