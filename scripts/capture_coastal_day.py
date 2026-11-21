"""Capture a bounded, dated public-source notebook. Never overwrite saved bytes.

Network access is explicit. This captures environmental context and one named
commercial vessel's endpoint response; it does not reconstruct an incident.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import gzip
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LIMIT = 3_000_000


def now():
    return datetime.now(timezone.utc).isoformat()


def capture(folder, name, url):
    path = folder / name
    receipt_path = folder / (name + '.receipt.json')
    if receipt_path.exists():
        record = json.loads(receipt_path.read_text(encoding='utf-8'))
        if record.get('sha256'):
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
        return record
    assert not path.exists(), 'Preserve original captures'
    record = {'file': name, 'url': url, 'requestedAtUtc': now(),
              'firstPublicationUtc': None, 'originalReceiverTimeUtc': None}
    try:
        request = Request(url, headers={'User-Agent': 'MothGravel-source-notebook/1.0',
                                       'Accept-Encoding': 'gzip', 'Accept': '*/*',
                                       'Digitraffic-User': 'MothGravel/source-notebook'})
        with urlopen(request, timeout=40) as response:
            wire = response.read(LIMIT + 1)
            assert len(wire) <= LIMIT, 'Wire response exceeded bounded capture'
            payload = gzip.GzipFile(fileobj=BytesIO(wire)).read(LIMIT + 1) if response.headers.get('Content-Encoding') == 'gzip' else wire
            assert len(payload) <= LIMIT, 'Decoded response exceeded bounded capture'
            path.write_bytes(payload)
            record.update(status=response.status, finalUrl=response.url,
                          downloadCompletedAtUtc=now(), bytes=len(payload),
                          sha256=hashlib.sha256(payload).hexdigest(),
                          wireBytes=len(wire), wireSha256=hashlib.sha256(wire).hexdigest(),
                          contentEncoding=response.headers.get('Content-Encoding'),
                          serverDate=response.headers.get('Date'),
                          lastModified=response.headers.get('Last-Modified'),
                          etag=response.headers.get('ETag'),
                          contentType=response.headers.get('Content-Type'),
                          contentRange=response.headers.get('Content-Range'))
    except HTTPError as error:
        payload = error.read(8192)
        error_path = folder / (name + '.error.txt')
        error_path.write_bytes(payload)
        record.update(status=error.code, error=str(error), failedAtUtc=now(),
                      errorBodyFile=error_path.name,
                      errorBodySha256=hashlib.sha256(payload).hexdigest())
    except Exception as error:
        record.update(error=str(error), errorType=type(error).__name__, failedAtUtc=now())
    receipt_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    return record


def jobs():
    start, end = '2026-11-20T22:00:00Z', '2026-11-21T17:00:00Z'
    def fmi(query, **kwargs):
        return 'https://opendata.fmi.fi/wfs?' + urlencode(dict(
            service='WFS', version='2.0.0', request='GetFeature', storedquery_id=query,
            starttime=start, endtime=end, **kwargs))
    result = [
        ('orrengrund-waves.xml', fmi('fmi::observations::wave::timevaluepair', fmisid='108495',
            timestep=30, parameters='WaveHs,ModalWDi,WTP,WHDD,TWATER')),
        ('gulf-waves.xml', fmi('fmi::observations::wave::timevaluepair', fmisid='134221',
            timestep=30, parameters='WaveHs,ModalWDi,WTP,WHDD,TWATER')),
        ('loviisa-orrengrund-weather.xml', fmi('fmi::observations::weather::timevaluepair', fmisid='101039',
            timestep=10, parameters='ws_10min,wg_10min,wd_10min,vis,t2m')),
        ('hamina-sea-level.xml', fmi('fmi::observations::mareograph::timevaluepair', fmisid='134254',
            timestep=30, parameters='WLEVN2K_PT1S_INSTANT,WATLEV')),
        ('sparta-location-gzip.json', 'https://meri.digitraffic.fi/api/ais/v1/locations?mmsi=273394890&from=1795212000000&to=1795280400000'),
        ('sparta-vessel.json', 'https://meri.digitraffic.fi/api/ais/v1/vessels/273394890'),
        ('sparta-latest-gzip.json', 'https://meri.digitraffic.fi/api/ais/v1/locations?mmsi=273394890'),
        ('sparta-after-0800.json', 'https://meri.digitraffic.fi/api/ais/v1/locations?mmsi=273394890&from=1795248000000'),
        ('danish-day-list.xml', 'https://s3.eu-central-1.amazonaws.com/aisdata.ais.dk/?list-type=2&prefix=aisdk-2026-11-21&max-keys=10'),
        ('metar.csv', 'https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?' + urlencode([
            ('station', 'EFHK'), ('station', 'EETN'), ('data', 'metar'), ('sts', start), ('ets', end),
            ('tz', 'Etc/UTC'), ('format', 'onlycomma'), ('latlon', 'yes'), ('elev', 'yes'), ('missing', 'M'), ('direct', 'no')])),
        ('estonian-gauges.json', 'https://keskkonnaandmed.envir.ee/f_hydroseire?' + urlencode({
            'jaam_kood': 'in.(86094,41801,26045)', 'aegrida_nimi': 'in.("WL avg","WT avg")',
            'timeline_ts_utc': 'gte.2026-11-20T22:00:00', 'order': 'jaam_nimi,aegrida_nimi,timeline_ts_utc',
            'limit': 300}) + '&timeline_ts_utc=lte.2026-11-21T17%3A00%3A00'),
    ]
    wave_url = dict(result)['orrengrund-waves.xml']
    result += [('orrengrund-native.xml', wave_url.replace('timestep=30&', '')),
               ('orrengrund-hourly.xml', wave_url.replace('timestep=30', 'timestep=60'))]
    original = json.loads((Path(__file__).resolve().parents[1] / 'docs/data/coastal-sources/2026-11-11/manifest.json').read_text(encoding='utf-8'))
    for name in ['sentinel-1-grd-day-catalogue.json', 'sentinel-2-l2a-day-catalogue.json']:
        result.append((name, original['receipts'][name]['url'].replace('2026-11-10', '2026-11-20').replace('2026-11-11', '2026-11-21')))
    result += [('border-guard.html', 'https://www.epressi.com/tiedotteet/turvallisuus/vaurioitunut-venalainen-rahtialus-suomenlahdella.html'),
               ('iltalehti.html', 'https://www.iltalehti.fi/ulkomaat/a/f6514cc0-038d-4dc3-8f0e-a12c6e763e75')]
    # A small saved strip, not an implied full-day cloud recording.
    for clock in ['0700', '0710', '0720', '0730', '0740', '0750', '0800']:
        stamp = f'2026-11-21T{clock[:2]}:{clock[2:]}:00.000Z'
        result.append(('cloud-' + clock + '.png', 'https://view.eumetsat.int/geoserver/wms?' + urlencode({
            'service': 'WMS', 'version': '1.3.0', 'request': 'GetMap', 'layers': 'mtg_fd:rgb_geocolour',
            'styles': '', 'format': 'image/png', 'crs': 'CRS:84', 'bbox': '23,59,28.5,61',
            'width': 1100, 'height': 400, 'time': stamp, 'transparent': 'true'})))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for record in pool.map(lambda job: capture(args.output, *job), jobs()):
            print(json.dumps({key: record.get(key) for key in ['file', 'status', 'bytes', 'error']}), flush=True)
