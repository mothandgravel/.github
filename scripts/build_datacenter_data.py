#!/usr/bin/env python3
"""Build the bounded ESIF replay from checksum-pinned publisher Parquet files.

python scripts/build_datacenter_data.py PATH_TO_DOWNLOADS [--check]
Requires pyarrow==21.0.0. No network, timezone conversion or missing-value filling.
"""
import argparse
import hashlib
import json
import math
import sys
from decimal import Decimal, localcontext
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'power.parquet': '19cd12405dde9144b1a360e8c8418666c399a3d0d15a7f846880d71ab22f9dd4',
    'weather.parquet': '97b424993fa77a15117fb2c4659a2c327fc83280f943fab47d9036260289a6a0',
    'README.md': 'f69d32f1af598c48a899d54d48b26def2ca78a0c11d848516169570ecae4c029',
    'LICENSE.html': '24768d4c58eb513d63422cdd54479e2ec88d272651d66262f6f2debed75ca74b',
}
FIELDS = ['it_power_kw', 'cooling_kw', 'pump_kw', 'hvac_kw', 'plug_and_light_kw', 'pue', 'energy_reuse', 'ere']


def audit_table(table, pa, pc):
    times = table['ts']
    dt = pc.subtract(pc.cast(times.slice(1), pa.int64()), pc.cast(times.slice(0, len(times)-1), pa.int64()))
    fields = {}
    for field in table.schema:
        col = table[field.name]
        item = {'nulls': col.null_count}
        if pa.types.is_floating(field.type):
            item.update(range=pc.min_max(col).as_py(), negative=pc.sum(pc.cast(pc.less(col, 0), pa.int64())).as_py())
        fields[field.name] = item
    return {'rows': table.num_rows, 'timestamp_range': {k: str(v) for k, v in pc.min_max(times).as_py().items()},
            'timestamp_type': str(times.type), 'fields': fields,
            'interval_seconds_quantiles': pc.quantile(pc.divide(dt, 1e6), q=[0, .25, .5, .75, 1]).to_pylist(),
            'backwards_steps': pc.sum(pc.cast(pc.less(dt, 0), pa.int64())).as_py(),
            'duplicate_adjacent_timestamps': pc.sum(pc.cast(pc.equal(dt, 0), pa.int64())).as_py()}


def decimal_reference(rows, start, end):
    """Independent boundary-insertion quadrature using 50-digit decimal arithmetic."""
    times = [datetime.fromisoformat(row[1]) for row in rows]
    components = FIELDS[:5]
    energies = {k: Decimal(0) for k in components}
    with localcontext() as ctx:
        ctx.prec = 50
        def micros(delta):
            return Decimal((delta.days*86400+delta.seconds)*1000000+delta.microseconds)
        # Build new boundary points; then integrate the resulting clipped polyline.
        points = []
        for t in [start, *[t for t in times if start < t < end], end]:
            j = next(i for i, x in enumerate(times) if x >= t)
            if times[j] == t:
                values = [Decimal(str(v)) for v in rows[j][2:7]]
            else:
                fraction = micros(t-times[j-1])/micros(times[j]-times[j-1])
                values = [Decimal(str(rows[j-1][k])) + fraction*(Decimal(str(rows[j][k]))-Decimal(str(rows[j-1][k]))) for k in range(2,7)]
            points.append((t, values))
        for (t0,p0),(t1,p1) in zip(points,points[1:]):
            delta_hours=micros(t1-t0)/Decimal(3600000000)
            for k,a,b in zip(components,p0,p1):energies[k]+=(a+b)/2*delta_hours
        total=sum(energies.values())
        return {'start':start.isoformat(),'end':end.isoformat(),'componentKWh':{k:str(v) for k,v in energies.items()},'totalKWh':str(total),'ITKWh':str(energies['it_power_kw']),'periodPUE':str(total/energies['it_power_kw'])}


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def build(source, check):
    source = source.resolve()
    # Research-only installed dependencies may accompany the downloaded archive.
    if (source / 'python-packages').is_dir():
        sys.path.insert(0, str(source / 'python-packages'))
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    if pa.__version__ != '21.0.0':
        raise ValueError('Use the reviewed pyarrow==21.0.0 reader')
    for name, expected in EXPECTED.items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Source hash mismatch: {name}')
    parser = Text()
    parser.feed((source / 'LICENSE.html').read_text(encoding='utf-8'))
    text = ' '.join(' '.join(parser.parts).split())
    begin = text.index('The National Renewable Energy Laboratory (NREL) is operated')
    end = text.index('USE OR PERFORMANCE OF THE DATA.', begin) + len('USE OR PERFORMANCE OF THE DATA.')
    notice = text[begin:end]
    power = pq.read_table(source / 'power.parquet')
    archive_audit = {'power.parquet': audit_table(power, pa, pc)}
    start, end = datetime(2025, 7, 14), datetime(2025, 7, 21)
    # One bracketing record on either side supports exact window boundaries.
    start_index = pc.index(pc.greater_equal(power['ts'], pa.scalar(start)), True).as_py()
    end_index = pc.index(pc.greater_equal(power['ts'], pa.scalar(end)), True).as_py()
    if start_index < 1 or end_index <= start_index:
        raise ValueError('Replay interval cannot be bracketed')
    selected = power.slice(start_index - 1, end_index - start_index + 2).select(['ts', *FIELDS])
    if selected['ts'].null_count or power['ts'].type.tz is not None:
        raise ValueError('Review timestamp semantics before rebuilding')
    rows = []
    for i, row in enumerate(selected.to_pylist(), start_index - 1):
        values = [row[k] for k in FIELDS]
        if any(v is not None and not math.isfinite(v) for v in values):
            raise ValueError('Nonfinite selected power value')
        rows.append([i, row['ts'].isoformat(timespec='microseconds'), *values])
    weather = pq.read_table(source / 'weather.parquet')
    archive_audit['weather.parquet'] = audit_table(weather, pa, pc)
    indices = pc.indices_nonzero(pc.and_(pc.greater_equal(weather['ts'], pa.scalar(datetime(2025, 7, 13, 23, 58))), pc.less_equal(weather['ts'], pa.scalar(end))))
    weather_rows = [[r['ts'].isoformat(timespec='microseconds'), r['outdoor_air_temp'], r['outdoor_air_humidity']] for r in weather.take(indices).to_pylist()]
    payload = {
        'schema': 'mg-esif-1', 'licenseNotice': notice,
        'source': {'title': 'NLR HPC Facility Power Usage Effectiveness (PUE) Data', 'authors': ['Struan Clark', 'Justin Strelka'],
                   'catalog': 'https://data.nlr.gov/submissions/300', 'doi': '10.7799/3015212', 'credit': 'DOE/NREL/ALLIANCE; dataset published by National Laboratory of the Rockies',
                   'retrieved': '2026-10-22', 'inputSha256': EXPECTED, 'reader': 'pyarrow==21.0.0', 'inputURLs': {'power.parquet':'https://data.nlr.gov/system/files/300/1757103411-esif.influx.buildingData.PUE.combined.parquet','weather.parquet':'https://data.nlr.gov/system/files/300/1757105566-esif.influx.buildingData.outside.combined_2.parquet','README.md':'https://data.nlr.gov/system/files/300/1769711385-README.md','LICENSE.html':'https://data.nlr.gov/node/300/license'}},
        'time': {'start': start.isoformat(), 'endExclusive': end.isoformat(), 'zone': None,
                 'semantics': 'Naive source-clock readings. Calendar arithmetic never asserts an absolute UTC instant. One bracketing observation is retained on each side.'},
        'columns': ['sourceRow', 'sourceClock', *FIELDS], 'rows': rows,
        'weatherColumns': ['sourceClock', 'outdoor_air_temp', 'outdoor_air_humidity'], 'weatherRows': weather_rows,
        'weatherUnit': {'outdoor_air_temp': 'degF, per publisher README', 'outdoor_air_humidity': '%RH'},
        'methods': {'samplingAssumption': 'Reported power is treated as point samples. Publisher does not specify sensor averaging or aggregation windows.',
                    'powerToEnergy': 'Piecewise-linear power interpolation and trapezoidal integration; only valid intervals <=90 seconds. No extrapolation; excluded time remains uncovered.',
                    'periodPUE': 'Integrated five-component facility energy / integrated IT energy over identical valid intervals. Never the arithmetic mean of sample PUE.',
                    'weather': 'Most recent same-facility source-clock observation at or before power time, maximum age 90 seconds. Clock alignment is unverified.',
                    'heatReuse': 'energy_reuse and ere are preserved only as raw fields. Their units/definitions are insufficiently documented for derived heat-recovery claims.',
                    'scene': 'Authored room and equipment geometry. Facility totals are not disaggregated into invented rack measurements.'},
        'archiveAudit': archive_audit,
    }
    # Inspection is source data metadata, not a second set of derived replay values.
    payload['archiveAudit'].pop('sample_window', None)
    out = ROOT / 'docs/assets/data-center'
    out.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n'
    files = {out / 'esif-week.json': body, out / 'publisher-notice.txt': notice + '\n', out / 'source-readme.txt': (source / 'README.md').read_text(encoding='utf-8')}
    references = [decimal_reference(rows, datetime(2025,7,14,23), datetime(2025,7,15)), decimal_reference(rows,datetime(2025,7,18,9),datetime(2025,7,18,10))]
    files[out / 'numerical-reference.json'] = json.dumps({'licenseNotice':notice,'method':'Independent Python Decimal, precision 50; boundary insertion then trapezoids. Derived from the pinned source float values as decimal strings. Numerical reference, not meter calibration.','accounts':references},indent=2)+'\n'
    record = {'dataset': 'ESIF measured replay', 'file': 'assets/data-center/esif-week.json', 'sha256': hashlib.sha256(body.encode()).hexdigest(),
              'rows': len(rows), 'weatherRows': len(weather_rows), 'windowSamples': end_index - start_index,
              'source': payload['source'], 'method': payload['methods'], 'licenseFile': 'assets/data-center/publisher-notice.txt'}
    files[ROOT / 'docs/design/datacenter-provenance.json'] = json.dumps(record, indent=2, ensure_ascii=False) + '\n'
    for path, content in files.items():
        if check:
            if path.read_text(encoding='utf-8').replace('\r\n', '\n') != content.replace('\r\n', '\n'):
                raise ValueError(f'Stale generated asset: {path}')
        else:
            path.write_text(content, encoding='utf-8', newline='\n')
    print(f'{len(rows)} bracketing power records; {len(weather_rows)} weather records; {len(body.encode())} bytes')


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('source', type=Path)
    cli.add_argument('--check', action='store_true')
    args = cli.parse_args()
    build(args.source, args.check)
