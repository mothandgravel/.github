"""Count regional archive rows from a local ZIP. Output aggregate evidence only."""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_region(path):
    collection = json.loads(path.read_text(encoding='utf-8'))
    feature, = collection['features']
    if feature['properties']['mrgid'] != 2407 or feature['geometry']['type'] != 'MultiPolygon':
        raise ValueError('Expected the Marine Regions Gulf of Finland multipolygon')
    if collection['crs']['properties']['name'] != 'urn:ogc:def:crs:EPSG::4326':
        raise ValueError('Expected EPSG:4326 with GeoJSON longitude/latitude positions')
    polygons = feature['geometry']['coordinates']
    points = [point for polygon in polygons for ring in polygon for point in ring]
    xs, ys = zip(*points)
    west, south, east, north = min(xs), min(ys), max(xs), max(ys)
    if not (22 < west < 24 and 59 < south < 60 and 29 < east < 39 and 60 < north < 64):
        raise ValueError('Unexpected extent or coordinate order')
    return west, south, east, north


def scan(archive, region):
    bounds = load_region(region)
    west, south, east, north = bounds
    counts = Counter({name: 0 for name in ['allRows', 'validCoordinateRows', 'invalidCoordinateRows',
                     'boundingRectangleRows', 'weatherMapRectangleRows']})
    labels_by_date = Counter()
    earliest = latest = None
    with zipfile.ZipFile(archive) as zipped:
        member, = [m for m in zipped.infolist() if not m.is_dir()]
        if member.filename != 'aisdk-2026-11-11.csv' or member.file_size > 8_000_000_000:
            raise ValueError('Unexpected archive member name or decoded size')
        with io.TextIOWrapper(zipped.open(member), encoding='utf-8-sig', newline='') as stream:
            rows = csv.reader(stream, strict=True)
            header = next(rows)
            clock, latitude, longitude = [header.index(key) for key in ('# Timestamp', 'Latitude', 'Longitude')]
            for row in rows:
                if len(row) != len(header):
                    raise ValueError(f'Unexpected CSV column count at line {rows.line_num}')
                counts['allRows'] += 1
                label = row[clock]
                if len(label) != 19 or label[2] != '/' or label[5] != '/' or label[10] != ' ':
                    raise ValueError(f'Unexpected timestamp format at line {rows.line_num}')
                # Sort the source's wall-clock labels without assigning a timezone.
                sortable = label[6:10] + '-' + label[3:5] + '-' + label[:2] + 'T' + label[11:]
                labels_by_date[sortable[:10]] += 1
                if earliest is None or sortable < earliest:
                    earliest = sortable
                if latest is None or sortable > latest:
                    latest = sortable
                try:
                    lat, lon = float(row[latitude]), float(row[longitude])
                except ValueError:
                    counts['invalidCoordinateRows'] += 1
                    continue
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    counts['invalidCoordinateRows'] += 1
                    continue
                counts['validCoordinateRows'] += 1
                if 23 <= lon <= 28.5 and 59 <= lat <= 61:
                    counts['weatherMapRectangleRows'] += 1
                if west <= lon <= east and south <= lat <= north:
                    counts['boundingRectangleRows'] += 1
    # ZipExtFile checks the member CRC when EOF is reached.
    if not counts['allRows'] or counts['allRows'] != counts['validCoordinateRows'] + counts['invalidCoordinateRows']:
        raise ValueError('Scan did not account for all CSV rows')
    # The rectangle encloses the polygon. A positive count would require a narrower test.
    counts['gulfRows'] = 0 if counts['boundingRectangleRows'] == 0 else None
    return {
        'archiveSha256': digest(archive),
        'archiveBytes': archive.stat().st_size,
        'csvMember': member.filename,
        'csvBytes': member.file_size,
        'csvCrc32': f'{member.CRC:08x}',
        'readToEndWithZipCrcValidation': True,
        'regionMrgid': 2407,
        'regionGeojsonSha256': digest(region),
        'boundsWestSouthEastNorth': list(bounds),
        'weatherMapBoundsWestSouthEastNorth': [23, 59, 28.5, 61],
        'counts': dict(counts),
        'csvTimeLabels': {'field': '# Timestamp', 'format': 'DD/MM/YYYY HH:MM:SS',
                          'earliest': earliest, 'latest': latest, 'timezone': None,
                          'rowCountsByLabelDate': dict(sorted(labels_by_date.items()))},
        'scanCompletedAtUtc': datetime.now(timezone.utc).isoformat(),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('region', type=Path)
    args = parser.parse_args()
    print(json.dumps(scan(args.archive, args.region), indent=2, allow_nan=False))
