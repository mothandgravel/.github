"""Validate the public archive against provider payloads and frozen file hashes."""
import csv
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]/'docs'
DATA=ROOT/'data/coastal-sources/2026-11-11'
record=json.loads((ROOT/'design/coastal-source-notebook-provenance.json').read_text(encoding='utf-8'))
for asset in record['files']:
    content=(ROOT/asset['path']).read_bytes()
    assert len(content)==asset['bytes'] and hashlib.sha256(content).hexdigest()==asset['sha256'],asset['path']
full=json.loads((DATA/'environment-observations.json').read_text(encoding='utf-8'))
selected=json.loads((DATA/'selected.json').read_text(encoding='utf-8'))
manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf-8'))
raw={}
for name in ('harmaja-weather.xml','finnish-wave-observations.xml','finnish-sea-level-observations.xml'):
    receipt=manifest['receipts'][name]
    assert hashlib.sha256((DATA/'raw'/name).read_bytes()).hexdigest()==receipt['sha256']
    for member in ET.parse(DATA/'raw'/name).getroot().findall('{*}member'):
        obs=list(member)[0]
        location=obs.find('.//{http://xml.fmi.fi/namespace/om/atmosphericfeatures/1.1}Location')
        station=location.find('{*}identifier').text
        prop=obs.find('{*}observedProperty').attrib['{http://www.w3.org/1999/xlink}href']
        param=parse_qs(urlsplit(prop).query)['param'][0]
        for pair in obs.findall('.//{http://www.opengis.net/waterml/2.0}MeasurementTVP'):
            key=(station,param,pair.find('{*}time').text)
            assert key not in raw
            raw[key]=(pair.find('{*}value').text,name)
seen=set();missing=zero=0
for s in full['series']:
    assert s['publicationTime'] is None
    for point in s['points']:
        key=(s['stationId'],s['parameter'],point['observedAt'])
        assert key not in seen;seen.add(key)
        original,name=raw[key]
        assert original==point['rawValue'] and name==s['sourceFile']
        n=float(original)
        if math.isfinite(n):
            assert n==point['value'];zero+=n==0
        else:
            assert point['value'] is None;missing+=1
assert seen==raw.keys() and len(seen)==2400
assert missing==manifest['counts']['missingSamples']==525 and zero==20
with (DATA/'environment-observations.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)==len(raw)
csv_keys=set()
for row in rows:
    key=(row['station_id'],row['parameter'],row['observed_utc']);assert key not in csv_keys;csv_keys.add(key)
    assert row['raw_value']==raw[key][0]
    n=float(raw[key][0]);assert (row['value']=='' if not math.isfinite(n) else float(row['value'])==n)
assert csv_keys==raw.keys()
by_id={s['id']:s for s in full['series']}
assert len(selected['series'])==7
for s in selected['series']:
    assert s==by_id[s['id']] and s['unit']
    meta=ET.parse(DATA/'raw'/('parameter-'+s['parameter']+'.xml')).getroot()
    assert meta.find('.//{*}uom').attrib['uom']==s['unit']
assert manifest['danishArchive']['studyDateListed'] is False
assert manifest['danishArchive']['latestListedDate']=='2026-11-10'
assert [c['products'] for c in manifest['catalogues']]==[9,17]
assert manifest['catalogues'][0]['cloudMin'] is None and manifest['catalogues'][0]['cloudMax'] is None
optical=json.loads((DATA/'raw/sentinel-2-l2a-day-catalogue.json').read_text(encoding='utf-8'))
clouds=[f['properties']['eo:cloud_cover'] for f in optical['features']]
assert manifest['catalogues'][1]['cloudMin']==min(clouds) and manifest['catalogues'][1]['cloudMax']==max(clouds)
print('Coastal sources: all 2,400 pairs and CSV rows exact; 525 nulls, 20 zeros preserved; 7 verified-unit channels; all file hashes match.')
