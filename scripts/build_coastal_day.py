"""Build the 21 November notebook from frozen public-source responses, offline."""
import argparse
import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DAY = ROOT / 'docs/data/coastal-days/2026-11-21'
PROVENANCE = ROOT / 'docs/design/coastal-day-20261121-provenance.json'
START = '2026-11-20T22:00:00Z'
CUTOFF = '2026-11-21T17:00:00Z'
FILES = ['loviisa-orrengrund-weather.xml', 'orrengrund-waves.xml', 'gulf-waves.xml',
         'orrengrund-native.xml', 'orrengrund-hourly.xml',
         'hamina-sea-level.xml', 'metar.csv', 'estonian-gauges.json', 'danish-day-list.xml',
         'sparta-location-gzip.json', 'sparta-latest-gzip.json', 'sparta-after-0800.json',
         'sparta-vessel.json', 'sentinel-1-grd-day-catalogue.json', 'sentinel-2-l2a-day-catalogue.json']
UNITS = {'ws_10min': 'm/s', 'wg_10min': 'm/s', 'wd_10min': '°', 'vis': 'm', 't2m': '°C',
         'WaveHs': 'm', 'ModalWDi': '°', 'WTP': 's', 'WHDD': '°', 'TWATER': '°C',
         'WLEVN2K_PT1S_INSTANT': 'mm', 'WATLEV': 'mm'}
EXPECTED = {'loviisa-orrengrund-weather.xml': ('101039', 'Loviisa Orrengrund', 10, 5),
            'orrengrund-waves.xml': ('108495', 'Loviisa Orrengrund aaltopoiju', 30, 5),
            'gulf-waves.xml': ('134221', 'Suomenlahti aaltopoiju', 30, 5),
            'hamina-sea-level.xml': ('134254', 'Hamina Pitäjänsaari', 30, 2)}


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def load(name):
    return json.loads((DAY / 'raw' / name).read_text(encoding='utf-8'))


def build():
    receipts = {}
    for name in FILES:
        receipt = load(name + '.receipt.json')
        payload = (DAY / 'raw' / name).read_bytes()
        assert receipt['status'] == 200 and len(payload) == receipt['bytes'], name
        assert hashlib.sha256(payload).hexdigest() == receipt['sha256'], name
        assert datetime.fromisoformat(receipt['requestedAtUtc']) <= datetime.fromisoformat(receipt['downloadCompletedAtUtc'])
        receipts[name] = receipt
    series = []
    for filename, (station_id, station_name, step, n_channels) in EXPECTED.items():
        root = ET.parse(DAY / 'raw' / filename).getroot()
        assert root.tag == '{http://www.opengis.net/wfs/2.0}FeatureCollection'
        assert int(root.attrib['numberReturned']) == n_channels
        query = parse_qs(urlsplit(receipts[filename]['url']).query)
        assert query['fmisid'] == [station_id] and query['timestep'] == [str(step)]
        assert query['starttime'] == [START] and query['endtime'] == [CUTOFF]
        by_id = {n.attrib['{http://www.opengis.net/gml/3.2}id']: n for n in root.iter()
                 if '{http://www.opengis.net/gml/3.2}id' in n.attrib}
        for member in root.findall('{*}member'):
            obs = list(member)[0]
            loc = obs.find('.//{http://xml.fmi.fi/namespace/om/atmosphericfeatures/1.1}Location')
            assert loc.find('{*}identifier').text == station_id
            name = next(n.text for n in loc.findall('{*}name') if n.attrib.get('codeSpace', '').endswith('/name'))
            assert name == station_name, 'Reject a mislabeled or relocated station'
            pos = obs.find('.//{http://www.opengis.net/samplingSpatial/2.0}shape//{*}pos')
            lat, lon = map(float, pos.text.split())
            assert 59 < lat < 61 and 25 < lon < 28
            definition = obs.find('{*}observedProperty').attrib['{http://www.w3.org/1999/xlink}href']
            param, = parse_qs(urlsplit(definition).query)['param']
            points = []
            for tvp in obs.findall('.//{http://www.opengis.net/waterml/2.0}MeasurementTVP'):
                stamp, raw = tvp.find('{*}time').text, tvp.find('{*}value').text
                value = None if raw == 'NaN' else float(raw)
                assert value is None or math.isfinite(value)
                assert datetime.fromisoformat(stamp) == datetime.fromisoformat(START) + timedelta(minutes=step * len(points))
                points.append({'time': stamp, 'raw': raw, 'value': value})
            assert len(points) == 1140 // step + 1 and points[-1]['time'] == CUTOFF
            result_times = {n.text for n in obs.findall('.//{*}resultTime//{*}timePosition')}
            for node in obs.findall('.//{*}resultTime'):
                href = node.attrib.get('{http://www.w3.org/1999/xlink}href')
                if href:
                    assert href.startswith('#') and href[1:] in by_id
                    result_times.update(n.text for n in by_id[href[1:]].findall('.//{*}timePosition'))
            result_times = sorted(result_times)
            series.append({'id': f'{station_id}:{param}', 'stationId': station_id, 'station': name,
                           'latitude': lat, 'longitude': lon, 'parameter': param, 'unit': UNITS[param],
                           'intervalMinutes': step, 'file': filename, 'definition': definition,
                           'responseTimeUtc': root.attrib['timeStamp'], 'resultTimeLabelsUtc': result_times,
                           'points': points})
    ais = load('sparta-location-gzip.json')
    controls = {}
    for filename, step in [('orrengrund-native.xml', None), ('orrengrund-hourly.xml', ['60'])]:
        query = parse_qs(urlsplit(receipts[filename]['url']).query)
        assert query['fmisid'] == ['108495'] and query['starttime'] == [START] and query['endtime'] == [CUTOFF]
        assert query.get('timestep') == step
        controls[filename] = {}
        root = ET.parse(DAY / 'raw' / filename).getroot()
        for member in root.findall('{*}member'):
            obs = list(member)[0]
            definition = obs.find('{*}observedProperty').attrib['{http://www.w3.org/1999/xlink}href']
            param, = parse_qs(urlsplit(definition).query)['param']
            controls[filename][param] = {p.find('{*}time').text: p.find('{*}value').text
                                       for p in obs.findall('.//{http://www.opengis.net/waterml/2.0}MeasurementTVP')}
    for s in [s for s in series if s['stationId'] == '108495']:
        assert {p['time']: p['raw'] for p in s['points'] if p['value'] is not None} == controls['orrengrund-native.xml'][s['parameter']]
        assert {p['time']: p['raw'] for p in s['points'][::2]} == controls['orrengrund-hourly.xml'][s['parameter']]
    wave = next(s for s in series if s['id'] == '108495:WaveHs')['points']
    cadence = {'stationId': '108495', 'halfHourSlots': len(wave),
               'halfHourNumeric': sum(p['value'] is not None for p in wave),
               'halfHourMissing': sum(p['value'] is None for p in wave),
               'onHourSlots': len(wave[::2]), 'onHourNumeric': sum(p['value'] is not None for p in wave[::2]),
               'additionalHalfPastNumeric': sum(p['value'] is not None for p in wave[1::2]),
               'nativeAvailableAgrees': True, 'file': 'orrengrund-native.xml', 'hourlyFile': 'orrengrund-hourly.xml'}
    assert ais == load('sparta-latest-gzip.json') and len(ais['features']) == 1
    assert load('sparta-after-0800.json')['features'] == []
    vessel = load('sparta-vessel.json')
    assert vessel['name'].strip() == 'SPARTA II' and vessel['mmsi'] == 273394890 and vessel['imo'] == 9160994
    fix, = ais['features']
    assert fix['mmsi'] == vessel['mmsi'] and fix['geometry']['type'] == 'Point'
    assert fix['properties']['timestampExternal'] == 1795244502644
    assert fix['geometry']['coordinates'] == [26.229092, 59.984677]
    assert load('estonian-gauges.json') == []
    listing = ET.parse(DAY / 'raw/danish-day-list.xml').getroot()
    assert listing.find('{*}IsTruncated').text == 'false' and listing.find('{*}KeyCount').text == '0'
    reports = list(csv.DictReader(io.StringIO((DAY / 'raw/metar.csv').read_text(encoding='utf-8'))))
    for report in reports:
        stamp = report['valid'].replace(' ', 'T') + ':00Z'
        assert START <= stamp <= CUTOFF and report['station'] in ['EFHK', 'EETN'] and report['metar']
        report['time'] = stamp
    catalogues = []
    for name in FILES[-2:]:
        data = load(name)
        assert not any(link.get('rel') == 'next' for link in data.get('links', [])), 'Incomplete catalogue page'
        entries = [{'id': f['id'], 'time': f['properties']['datetime'],
                    'cloudCoverPercent': f['properties'].get('eo:cloud_cover')} for f in data['features']]
        assert all(START <= e['time'] < '2026-11-21T22:00:00Z' for e in entries)
        catalogues.append({'file': name, 'entries': entries, 'count': len(entries)})
    failures = []
    for path in sorted((DAY / 'raw').glob('cloud-*.png.receipt.json')):
        receipt = json.loads(path.read_text(encoding='utf-8'))
        assert 'getaddrinfo failed' in receipt.get('error', '') and not receipt.get('sha256') and 'status' not in receipt
        failures.append(receipt)
    assert len(failures) == 7
    news = {key: load(key + '.html.receipt.json') for key in ['border-guard', 'iltalehti']}
    return {'schema': 'mg.coastal-day.v1', 'dateLocal': '2026-11-21', 'timezone': 'Europe/Helsinki',
            'startUtc': START, 'endUtcExclusive': '2026-11-21T22:00:00Z', 'queryEndUtcInclusive': CUTOFF,
            'capturedAtUtc': max(r['downloadCompletedAtUtc'] for r in [*receipts.values(), *news.values()]),
            'series': series, 'receipts': receipts, 'reports': reports, 'catalogues': catalogues,
            'cadence': cadence,
            'ais': {'metadata': vessel, 'response': ais, 'file': 'sparta-location-gzip.json',
                    'sameLatestResponseFile': 'sparta-latest-gzip.json', 'emptyLaterQueryFile': 'sparta-after-0800.json',
                    'sourceTimeUtc': '2026-11-21T07:01:42.644Z', 'vesselTransmissionTimeUtc': None,
                    'meaning': 'One latest-returned position. timestampExternal is a source clock; the vessel transmission clock and historical completeness are unverified.'},
            'availability': {'danishDayListed': False, 'estonianGaugeRows': 0, 'cloudRequestsFailed': failures},
            'news': news}


def run(capture=None, check=False):
    if capture:
        assert not DAY.exists(), 'Never overwrite a published snapshot; use a separate follow-up'
        raw = DAY / 'raw'
        raw.mkdir(parents=True)
        for name in FILES:
            for suffix in ['', '.receipt.json']:
                shutil.copyfile(capture / (name + suffix), raw / (name + suffix))
        for path in capture.glob('cloud-*.png.receipt.json'):
            shutil.copyfile(path, raw / path.name)
        for name in ['border-guard.html.receipt.json', 'iltalehti.html.receipt.json']:
            shutil.copyfile(capture / name, raw / name)
    output = encoded(build())
    if check:
        assert (DAY / 'notebook.json').read_bytes() == output, 'Rebuild saved notebook'
        inventory = json.loads(PROVENANCE.read_text(encoding='utf-8'))['files']
        assert set(inventory) == {p.relative_to(ROOT / 'docs').as_posix() for p in DAY.rglob('*') if p.is_file()}
        for name, digest in inventory.items():
            assert hashlib.sha256((ROOT / 'docs' / name).read_bytes()).hexdigest() == digest, name
    else:
        (DAY / 'notebook.json').write_bytes(output)
        inventory = {p.relative_to(ROOT / 'docs').as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(DAY.rglob('*')) if p.is_file()}
        PROVENANCE.write_bytes(encoded({'schema': 'mg.coastal-day-provenance.v1', 'dateLocal': '2026-11-21', 'files': inventory}))
    print('Verified dated notebook: original bytes, station identities, native clocks, AIS response and gaps.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    assert not (args.capture and args.check)
    run(args.capture, args.check)
