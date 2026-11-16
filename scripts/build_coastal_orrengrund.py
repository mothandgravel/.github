"""Build the saved Orrengrund comparison from original FMI response bytes."""

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

from monitor_coastal_sources import meaning


DAY = Path(__file__).resolve().parents[1] / 'docs/data/coastal-sources/2026-11-11'
FOLLOWUP = DAY / 'follow-ups/orrengrund'
ORIGINAL = 'finnish-wave-observations.xml'
START = '2026-11-10T22:00:00Z'
END = '2026-11-11T22:00:00Z'
STATION = '108495'
CHANNELS = ['WaveHs', 'ModalWDi', 'WTP', 'WHDD', 'TWATER']


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load(folder, filename, receipt):
    payload = (folder / filename).read_bytes()
    assert receipt['status'] == 200
    assert hashlib.sha256(payload).hexdigest() == receipt['sha256']
    assert len(payload) == receipt['bytes']
    root = ET.fromstring(payload)
    if folder == FOLLOWUP:
        query = parse_qs(urlsplit(receipt['url']).query)
        assert query['fmisid'] == [STATION] and query['starttime'] == [START]
        assert query['endtime'] == ['2026-11-11T21:59:59Z']
        steps = {'half-hourly.xml': ['30'], 'hourly-control.xml': ['60'], 'default-cadence.xml': None}
        assert query.get('timestep') == steps[filename]
        assert query['parameters'] == [','.join(CHANNELS)]
        assert query['storedquery_id'] == ['fmi::observations::wave::timevaluepair']
        assert datetime.fromisoformat(receipt['requestedAtUtc']) <= datetime.fromisoformat(receipt['downloadCompletedAtUtc'])
        assert receipt['firstPublicationUtc'] is None and receipt['originalReceiverTimeUtc'] is None
        assert root.attrib['numberMatched'] == root.attrib['numberReturned'] == '5'
    result = {}
    for station, definition, stamp, raw in meaning(filename, payload):
        channel, = parse_qs(urlsplit(definition).query)['param']
        if station != STATION or channel not in CHANNELS:
            assert folder != FOLLOWUP
            continue
        assert (stamp, channel) not in result
        assert raw == 'NaN' or math.isfinite(float(raw))
        result[stamp, channel] = raw
    result_labels = sorted({node.text for node in root.findall('.//{*}resultTime//{*}timePosition')})
    return result, {'responseTimestampUtc': root.attrib['timeStamp'], 'fmiResultTimeLabelsUtc': result_labels}


def build():
    original_receipt = read_json(DAY / 'raw' / (ORIGINAL + '.receipt.json'))
    original, original_clocks = load(DAY / 'raw', ORIGINAL, original_receipt)
    sources = {'original': {'file': '../../raw/' + ORIGINAL, **original_clocks,
                            'requestedAtUtc': original_receipt['retrievedAt'], 'downloadCompletedAtUtc': None,
                            'sha256': original_receipt['sha256']}}
    records = {}
    for key, file in [('halfHourly', 'half-hourly.xml'), ('hourlyControl', 'hourly-control.xml'),
                      ('defaultCadence', 'default-cadence.xml')]:
        receipt = read_json(FOLLOWUP / (file + '.receipt.json'))
        records[key], clocks = load(FOLLOWUP, file, receipt)
        sources[key] = {'file': file, **clocks, **receipt}

    start = datetime.fromisoformat(START)
    stamps = [(start + timedelta(minutes=30 * slot)).isoformat().replace('+00:00', 'Z') for slot in range(48)]
    half = records['halfHourly']
    assert set(half) == {(stamp, channel) for stamp in stamps for channel in CHANNELS}
    on_hours = {(stamp, channel): half[stamp, channel] for stamp in stamps[::2] for channel in CHANNELS}
    assert on_hours == records['hourlyControl'] == original
    assert {key: value for key, value in half.items() if value != 'NaN'} == records['defaultCadence']

    hours = []
    for hour in range(24):
        hourly_stamp, half_stamp = stamps[2 * hour:2 * hour + 2]
        hours.append({
            'hourly': {'observedAtUtc': hourly_stamp, 'raw': {channel: original[hourly_stamp, channel] for channel in CHANNELS}},
            'halfHour': {'observedAtUtc': half_stamp, 'raw': {channel: half[half_stamp, channel] for channel in CHANNELS}},
        })

    summary = {}
    for channel in CHANNELS:
        original_values = sum(hour['hourly']['raw'][channel] != 'NaN' for hour in hours)
        extra_values = sum(hour['halfHour']['raw'][channel] != 'NaN' for hour in hours)
        summary[channel] = {
            'originalNumeric': original_values, 'originalMissing': 24 - original_values,
            'halfHourlyNumeric': original_values + extra_values, 'halfHourlyMissing': 48 - original_values - extra_values,
            'additionalAtHalfPast': extra_values,
            'hoursWithMissingOnHourAndNumericHalfPast': sum(
                hour['hourly']['raw'][channel] == 'NaN' and hour['halfHour']['raw'][channel] != 'NaN' for hour in hours),
        }
    return {'schema': 'mg.coastal-orrengrund.v1', 'station': 'Loviisa Orrengrund aaltopoiju', 'stationId': STATION,
            'dateLocal': '2026-11-11', 'timezone': 'Europe/Helsinki', 'startUtc': START, 'endUtcExclusive': END,
            'channels': CHANNELS, 'counts': summary, 'hours': hours, 'sources': sources,
            'originalReceiverTimeUtc': None, 'firstPublicationUtc': None,
            'method': 'Exact UTC labels and unchanged source strings. The :00 row is the saved hourly response and agrees with both later stepped requests. The :30 row is the later half-hour response. Every numeric value also agrees with the query without a time step. NaN is missing.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    comparison = (json.dumps(build(), ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    target = FOLLOWUP / 'comparison.json'
    if parser.parse_args().check:
        assert target.read_bytes() == comparison, 'Saved Orrengrund comparison differs from source responses'
    else:
        target.write_bytes(comparison)
    print('Orrengrund: all five channels match at :00. At :30, 11 numeric readings and 13 missing values per channel.')
