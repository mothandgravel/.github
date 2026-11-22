"""Draw the single saved AIS report on Coastal watch's existing coastline."""

import argparse
import hashlib
import json
from math import cos, radians
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/assets'
COAST = ASSETS / 'coastal-replay-land.json'
REPORT = ROOT / 'docs/data/coastal-days/2026-11-21/raw/sparta-location-gzip.json'
OUTPUT = ASSETS / 'sparta-ii-map.svg'

WIDTH, HEIGHT = 900, 620
WEST, EAST, NORTH = 24, 27.75, 60.69
LONGITUDE_SCALE = WIDTH / (EAST - WEST)
LATITUDE_SCALE = LONGITUDE_SCALE / cos(radians(60))
SOUTH = NORTH - HEIGHT / LATITUDE_SCALE


def read_report():
    raw = REPORT.read_bytes()
    receipt = json.loads(REPORT.with_suffix('.json.receipt.json').read_text(encoding='utf-8'))
    if len(raw) != receipt['bytes'] or hashlib.sha256(raw).hexdigest() != receipt['sha256']:
        raise ValueError('The saved AIS response does not match its retrieval receipt.')

    response = json.loads(raw)
    features = response['features']
    if response['type'] != 'FeatureCollection' or len(features) != 1:
        raise ValueError('Expected exactly one saved AIS report.')

    report = features[0]
    geometry = report['geometry']
    if (geometry['type'] != 'Point' or report['properties']['mmsi'] != 273394890
            or report['properties']['timestampExternal'] != 1795244502644):
        raise ValueError('Expected the original 21 November Sparta II point.')

    longitude, latitude = geometry['coordinates']
    if not (WEST < longitude < EAST and SOUTH < latitude < NORTH):
        raise ValueError('The saved AIS report lies outside the map.')
    return longitude, latitude


def project(longitude, latitude):
    return (longitude - WEST) * LONGITUDE_SCALE, (NORTH - latitude) * LATITUDE_SCALE


def coast_paths():
    coast = json.loads(COAST.read_text(encoding='utf-8'))
    for polygon in coast['polygons']:
        rings = []
        for ring in polygon:
            points = ' '.join(f'{x:.2f},{y:.2f}' for x, y in (project(*p) for p in ring))
            rings.append(f'M{points}Z')
        yield f'      <path d="{" ".join(rings)}"/>'


def grid():
    lines, ticks = [], []
    for longitude in (25, 26, 27):
        x, _ = project(longitude, NORTH)
        lines.append(f'M{x:.2f},0V{HEIGHT}')
        ticks.append(f'    <text x="{x:.2f}" y="48" text-anchor="middle">{longitude}° E</text>')
    for latitude in (59.5, 60, 60.5):
        _, y = project(WEST, latitude)
        lines.append(f'M0,{y:.2f}H{WIDTH}')
    return ' '.join(lines), '\n'.join(ticks)


def render():
    coast = '\n'.join(coast_paths())
    grid_lines, ticks = grid()
    x, y = project(*read_report())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="map-title map-desc">
  <title id="map-title">One saved Sparta II AIS report in the Gulf of Finland</title>
  <desc id="map-desc">One gold point shows the position in the saved Digitraffic AIS report with a morning source timestamp on 21 November 2026. Regional coastline is from Natural Earth. North is up.</desc>
  <defs>
    <clipPath id="chart-area"><rect width="900" height="620"/></clipPath>
    <linearGradient id="water" x2="0" y2="1">
      <stop stop-color="#183138"/>
      <stop offset="1" stop-color="#12282d"/>
    </linearGradient>
    <linearGradient id="land" x2="0" y2="1">
      <stop stop-color="#293e37"/>
      <stop offset="1" stop-color="#233733"/>
    </linearGradient>
    <pattern id="print-grain" width="8" height="8" patternUnits="userSpaceOnUse">
      <rect x="1" y="2" width="1" height="1" fill="#d8d4bd"/>
    </pattern>
    <g id="coast" fill-rule="evenodd" stroke-linejoin="round">
{coast}
    </g>
  </defs>
  <g clip-path="url(#chart-area)">
    <rect width="900" height="620" fill="url(#water)"/>
    <use href="#coast" fill="none" stroke="#132526" stroke-width="9"/>
    <use href="#coast" fill="url(#land)" stroke="#55706a" stroke-width="1.7"/>
    <rect width="900" height="620" fill="url(#print-grain)" opacity=".12"/>
    <path d="{grid_lines}" fill="none" stroke="#6a8987" stroke-opacity=".32" stroke-width="1.5" stroke-dasharray="3 7"/>
    <path d="M26,71V26H71 M829,26H874V71 M874,549V594H829 M71,594H26V549" fill="none" stroke="#74918c" stroke-opacity=".6" stroke-width="2"/>
  </g>
  <g font-family="Arial, sans-serif" fill="#b6c3b6" font-size="25" font-weight="600" letter-spacing="2">
{ticks}
  </g>
  <g font-family="Arial, sans-serif" fill="#d8d4bd" paint-order="stroke" stroke="#182b2c" stroke-width="5" stroke-linejoin="round">
    <g font-size="43" letter-spacing="6" font-weight="600">
      <text x="333" y="136">FINLAND</text>
      <text x="540" y="563">ESTONIA</text>
    </g>
    <g font-size="34" letter-spacing="1" font-weight="500">
      <text x="225" y="220" text-anchor="middle">Helsinki</text>
      <text x="179" y="545" text-anchor="middle">Tallinn</text>
    </g>
    <text x="107" y="389" font-family="Georgia, serif" font-size="48" font-style="italic" fill="#9db9b6">Gulf of Finland</text>
  </g>
  <g fill="#eac38b" stroke="#172a2b" stroke-width="4">
    <circle id="sparta-ais-report" cx="{x:.2f}" cy="{y:.2f}" r="11"/>
    <text x="{x + 25:.2f}" y="{y + 11:.2f}" paint-order="stroke" stroke-linejoin="round" font-family="Arial, sans-serif" font-weight="700" font-size="35" letter-spacing="2">SPARTA II</text>
  </g>
</svg>
'''.encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check that the published map is current.')
    args = parser.parse_args()
    result = render()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes().replace(b'\r\n', b'\n') != result:
            parser.exit(1, 'Sparta II map is out of date. Run scripts/build_sparta_view_map.py.\n')
    else:
        OUTPUT.write_bytes(result)


if __name__ == '__main__':
    main()
