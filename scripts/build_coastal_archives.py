"""Build the four dated Coastal watch archives from preserved provider bytes, offline."""
import argparse
import csv
import hashlib
import json
import re
import shutil
import struct
import zlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/data/coastal-archives/2026-11-11'
START = datetime(2026, 11, 10, 22, tzinfo=timezone.utc)
END = START + timedelta(days=1)
FILES = ['estonia-3stations-2026-11-11.json', 'metar-EFHK-EETN-2026-11-11.csv',
         'fmi-weather-radar-2026-11-11.xml']
FILES += [f'fmi-radar-{t}-gulf.tif' for t in ('1000', '1005', '1010', '1015')]
FILES += [f'nasa-modis-{p}-{suffix}' for p in ('terra', 'aqua')
          for suffix in ('2026-11-11.png', 'domains-rawslash.xml')]
PALETTE = [(-20, (74, 106, 128)), (-5, (122, 172, 183)), (10, (205, 220, 191)),
           (25, (221, 183, 112)), (40, (180, 102, 69))]


def stamp(t):
    return t.isoformat().replace('+00:00', 'Z')


def dump(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def png(width, height, pixels):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    scan = b''.join(b'\0' + pixels[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scan, 9)) + chunk(b'IEND', b''))


def radar_pixels(data):
    """Read only the specific uncompressed, single-band GeoTIFF contract we preserved."""
    assert data[:2] in (b'II', b'MM')
    order = '<' if data[:2] == b'II' else '>'
    assert struct.unpack_from(order + 'H', data, 2)[0] == 42
    at = struct.unpack_from(order + 'I', data, 4)[0]
    count = struct.unpack_from(order + 'H', data, at)[0]
    tags = {}
    sizes = {1: 1, 2: 1, 3: 2, 4: 4, 12: 8}
    for i in range(count):
        p = at + 2 + i * 12
        tag, kind, n, value = struct.unpack_from(order + 'HHII', data, p)
        if kind not in sizes:
            continue
        length = sizes[kind] * n
        raw = data[p + 8:p + 8 + length] if length <= 4 else data[value:value + length]
        if kind in (3, 4, 12):
            tags[tag] = list(struct.unpack(order + {3: 'H', 4: 'I', 12: 'd'}[kind] * n, raw))
        else:
            tags[tag] = raw.rstrip(b'\0')
    assert tags[256] == [1100] and tags[257] == [400]
    assert tags[258] == [8] and tags[259] == [1] and tags[277] == [1]
    assert tags[42113] == b'0.0'
    assert tags[34264] == [.005, 0, 0, 23, 0, -.005, 0, 61, 0, 0, 0, 0, 0, 0, 0, 1]
    assert tags[34735][-1] == 4326
    pixels = b''.join(data[p:p + n] for p, n in zip(tags[273], tags[279]))
    assert len(pixels) == 440000 and max(pixels) < 255
    return pixels


def colour(code):
    if code == 0:
        return (0, 0, 0, 0)
    dbz = .5 * code - 32
    if dbz <= PALETTE[0][0]:
        return (*PALETTE[0][1], 255)
    for (low, a), (high, b) in zip(PALETTE, PALETTE[1:]):
        if dbz <= high:
            f = (dbz - low) / (high - low)
            return (*[round(x + (y - x) * f) for x, y in zip(a, b)], 255)
    return (*PALETTE[-1][1], 255)


def generate():
    raw = OUT / 'raw'
    receipts = {}
    for name in FILES:
        data = (raw / name).read_bytes()
        r = json.loads((raw / (name + '.receipt.json')).read_text(encoding='utf-8'))
        assert r['status'] == 200 and r.get('error') is None, name
        assert len(data) == r['bytes'] and hashlib.sha256(data).hexdigest() == r['sha256'], name
        assert datetime.fromisoformat(r['requestedAt']) <= datetime.fromisoformat(r['completedAt'])
        receipts[name] = r
    source = 'estonia-3stations-2026-11-11.json'
    rows = json.loads((raw / source).read_text(encoding='utf-8'), parse_float=Decimal)
    assert len(rows) == 144 and receipts[source]['contentRange'] == '0-143/144'
    groups = defaultdict(list)
    for r in rows:
        t = datetime.fromisoformat(r['timeline_ts_utc']).replace(tzinfo=timezone.utc)
        assert START <= t < END
        assert datetime.fromisoformat(r['timeline_ts_local']) == t.replace(tzinfo=None) + timedelta(hours=2)
        groups[(r['jaam_kood'], r['aegrida_nimi'])].append(r)
    gauges = []
    for (code, parameter), items in sorted(groups.items()):
        expected = [(START + timedelta(hours=h)).replace(tzinfo=None).isoformat() for h in range(24)]
        assert [r['timeline_ts_utc'] for r in items] == expected
        gauges.append({'id': f'{code}:{parameter}', 'stationCode': str(code), 'station': items[0]['jaam_nimi'],
                       'latitude': float(items[0]['jaam_laiuskraad']), 'longitude': float(items[0]['jaam_pikkuskraad']),
                       'parameter': parameter, 'unit': 'cm' if parameter == 'WL avg' else '°C',
                       'statistic': 'hourly mean', 'intervalEdge': None,
                       'gaugeZeroMetresEH2000': -5 if parameter == 'WL avg' else None,
                       'sourceFile': source, 'points': [{'labelledAt': r['timeline_ts_utc'] + 'Z',
                         'localLabel': r['timeline_ts_local'] + '+02:00',
                         'value': float(r['vaartus']) if r['vaartus'] is not None else None,
                         'rawValue': str(r['vaartus']) if r['vaartus'] is not None else None} for r in items]})
    source = 'metar-EFHK-EETN-2026-11-11.csv'
    reports = []
    with (raw / source).open(encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            t = datetime.strptime(r['valid'], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            clock = re.search(r'\b(\d{2})(\d{2})(\d{2})Z\b', r['metar'])
            assert START <= t < END and clock and tuple(map(int, clock.groups())) == (t.day, t.hour, t.minute)
            assert r['metar'].split()[0] == r['station']
            reports.append({'id': f'{r["station"]}:{stamp(t)}:{len(reports)}', 'station': r['station'],
                            'observedAt': stamp(t), 'archiveValidAt': stamp(t), 'raw': r['metar'],
                            'latitude': float(r['lat']), 'longitude': float(r['lon']), 'sourceFile': source})
    assert len(reports) == 96 and {r['station'] for r in reports} == {'EFHK', 'EETN'}
    ns = {'gml': 'http://www.opengis.net/gml/3.2', 'om': 'http://www.opengis.net/om/2.0'}
    scans = ET.parse(raw / 'fmi-weather-radar-2026-11-11.xml')
    times = [e.text for e in scans.findall('.//om:phenomenonTime/gml:TimeInstant/gml:timePosition', ns)]
    assert times == [f'2026-11-11T10:{m}:00Z' for m in ('00', '05', '10', '15')]
    values = [e.text.strip() for e in scans.findall('.//om:parameter/om:NamedValue/om:value/gml:Measure', ns)]
    assert values == ['0.5', '-32'] * 4
    frames, derived = [], {}
    for time in times:
        name = f'fmi-radar-{time[11:16].replace(":", "")}-gulf'
        pixels = radar_pixels((raw / (name + '.tif')).read_bytes())
        colours = bytes(v for p in pixels for v in colour(p))
        derived[name + '.png'] = png(1100, 400, colours)
        derived[name + '.bin'] = pixels
        frames.append({'id': time, 'observedAt': time, 'sourceFile': name + '.tif',
                       'metadataFile': 'fmi-weather-radar-2026-11-11.xml', 'image': name + '.png',
                       'pixels': name + '.bin', 'width': 1100, 'height': 400, 'noDataCode': 0,
                       'gain': .5, 'offset': -32, 'bbox': [23, 59, 28.5, 61], 'crs': 'EPSG:4326',
                       'pixelSizeDegrees': .005})
    images = []
    for platform in ('Terra', 'Aqua'):
        name = f'nasa-modis-{platform.lower()}-2026-11-11.png'
        domain = f'nasa-modis-{platform.lower()}-domains-rawslash.xml'
        assert ET.parse(raw / domain).findtext('.//Domain') == '2026-11-11/2026-11-12/P1D'
        data = (raw / name).read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', data[16:24]) == (1100, 400)
        images.append({'id': platform.lower(), 'platform': platform, 'instrument': 'MODIS',
                       'layer': f'MODIS_{platform}_CorrectedReflectance_TrueColor', 'productDateUtc': '2026-11-11',
                       'acquiredAt': None, 'publishedAt': None, 'sourceFile': name, 'domainFile': domain,
                       'bbox': [23, 59, 28.5, 61], 'crs': 'EPSG:4326', 'width': 1100, 'height': 400})
    notebook = {'schema': 'mg.coastal-archives.v1', 'dateLocal': '2026-11-11', 'timezone': 'Europe/Helsinki',
                'windowStartUtc': stamp(START), 'windowEndUtcExclusive': stamp(END),
                'gauges': gauges, 'reports': reports, 'frames': frames, 'images': images, 'receipts': receipts,
                'sources': {
                  'gauges': {'origin': 'Keskkonnaagentuur / Estonian Environment Agency', 'distribution': 'Keskkonnaportaal',
                    'licence': 'CC BY 4.0', 'definitionUrl': 'https://keskkonnaportaal.ee/et/avaandmed/hudroloogilise-seire-andmestik/hudroloogilise-seire-andmestiku-kirjeldus',
                    'licenceUrl': 'https://keskkonnaportaal.ee/et/avaandmed/hudroloogilise-seire-andmestik',
                    'limits': 'Operational hourly means; averaging interval edge unverified. Gauge zero is -5 m EH2000. No N2000 conversion. Later quality control may revise values.'},
                  'reports': {'origin': 'Airport weather observations / EFHK and EETN', 'distribution': 'Iowa Environmental Mesonet, Iowa State University',
                    'licence': 'IEM public-domain materials policy; attribution retained', 'licenceUrl': 'https://mesonet.agron.iastate.edu/disclaimer.php',
                    'definitionUrl': 'https://mesonet.agron.iastate.edu/request/download.phtml?network=FI__ASOS',
                    'limits': 'As-is redistribution with little quality control. Airport conditions, not over-water measurements. Original feed receipt, first publication and upstream message route unknown.'},
                  'radar': {'origin': 'Finnish Meteorological Institute / weather radar network', 'distribution': 'FMI WFS and WMS',
                    'licence': 'CC BY 4.0', 'licenceUrl': 'https://en.ilmatieteenlaitos.fi/radar-data-on-aws-s3',
                    'definitionUrl': 'https://en.ilmatieteenlaitos.fi/open-data-manual-radar-data',
                    'limits': 'Four saved weather-reflectivity frames only. Provider-resampled 0.005 degree crop. Pixel 0 is declared no-data, not dry weather. Not vessel radar or surface rainfall.'},
                  'imagery': {'origin': 'NASA / Terra MODIS and Aqua MODIS', 'distribution': 'NASA GIBS / EOSDIS',
                    'licence': 'NASA imagery / media usage guidelines; no endorsement implied', 'licenceUrl': 'https://www.nasa.gov/nasa-brand-center/images-and-media/',
                    'definitionUrl': 'https://nasa-gibs.github.io/gibs-api-docs/access-basics/',
                    'limits': 'Daily UTC corrected-reflectance products. Regional per-pixel acquisition times unresolved. A date is not an overpass time. Product availability checked separately from WMS nearest-date behaviour.'}}}
    derived['notebook.json'] = dump(notebook)
    return derived


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--import-sources', type=Path)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    if args.import_sources:
        assert not args.check
        (OUT / 'raw').mkdir(parents=True, exist_ok=True)
        for name in FILES:
            for suffix in ('', '.receipt.json'):
                target = OUT / 'raw' / (name + suffix)
                content = (args.import_sources / (name + suffix)).read_bytes()
                if target.exists():
                    assert target.read_bytes() == content, 'Do not overwrite a different archived capture'
                else:
                    shutil.copyfile(args.import_sources / (name + suffix), target)
    derived = generate()
    for name, content in derived.items():
        if args.check:
            assert (OUT / name).read_bytes() == content, name
        else:
            (OUT / name).write_bytes(content)
    inventory = [{'path': path.relative_to(ROOT / 'docs').as_posix(), 'bytes': path.stat().st_size,
                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(OUT.rglob('*')) if path.is_file()]
    provenance = {'schema': 'mg.coastal-archives-provenance.v1', 'date': '2026-11-11',
                  'source': 'Keskkonnaagentuur / Iowa Environmental Mesonet / Finnish Meteorological Institute / NASA GIBS',
                  'transformation': 'Provider originals retained. Hourly means and METAR clocks normalized without interpolation. TIFF single-band pixels copied to .bin and rendered with the documented palette; no smoothing. NASA PNGs unchanged.',
                  'paletteDBZ': PALETTE, 'noDataCode': 0, 'rasterColourClamping': 'Below -20 and above 40 dBZ share endpoint colours; original pixel codes retained.',
                  'clockMeaning': 'New captures retain UTC request start and download completion, not station receipt or first publication. NASA acquisition times remain null.',
                  'scope': 'Environmental context. Four archive products share upstream providers with other views. Not an incident reconstruction or vessel track.',
                  'files': inventory}
    target = ROOT / 'docs/design/coastal-archives-provenance.json'
    if args.check:
        assert target.read_bytes() == dump(provenance), 'Provenance drift'
    else:
        target.write_bytes(dump(provenance))
    print(f'Coastal archives: 144 gauge means, 96 original reports, 4 masked radar frames, 2 unchanged daily images; {len(inventory)} files verified offline.')


if __name__ == '__main__':
    main()
