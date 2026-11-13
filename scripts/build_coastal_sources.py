"""Promote a verified, saved research retrieval. Never fetch or retimestamp data."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

def build(source):
    bundle = json.loads((source/'environment-observations.json').read_text(encoding='utf-8'))
    research = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    assert bundle['dateLocal'] == '2026-11-11'
    out = ROOT/'docs/data/coastal-sources/2026-11-11'
    raw = out/'raw'
    raw.mkdir(parents=True, exist_ok=True)
    wanted = [('Helsinki Harmaja','ws_10min'),('Helsinki Harmaja','wg_10min'),('Helsinki Harmaja','vis'),
              ('Suomenlahti aaltopoiju','WaveHs'),('Loviisa Orrengrund aaltopoiju','WaveHs'),
              ('Helsinki Kaivopuisto','WLEVN2K_PT1S_INSTANT'),('Helsinki Kaivopuisto','WATLEV')]
    selected = [next(s for s in bundle['series'] if (s['station'],s['parameter'])==key) for key in wanted]
    assert all(s['unit'] for s in selected)
    files = sorted({s['sourceFile'] for s in selected} | {'parameter-'+s['parameter']+'.xml' for s in selected}
                   | {'sentinel-1-grd-day-catalogue.json','sentinel-2-l2a-day-catalogue.json','danish-november-archive-list.xml','mystar-requested-day.json'})
    receipts = {}
    for name in files:
        receipt = json.loads((source/(name+'.receipt.json')).read_text(encoding='utf-8'))
        assert receipt['status'] == 200
        payload = (source/name).read_bytes()
        assert hashlib.sha256(payload).hexdigest()==receipt['sha256'] and len(payload)==receipt['bytes']
        shutil.copyfile(source/name,raw/name)
        shutil.copyfile(source/(name+'.receipt.json'),raw/(name+'.receipt.json'))
        receipts[name]=receipt
    seismic=json.loads((source/'seismo-calendar.html.receipt.json').read_text(encoding='utf-8'))
    shutil.copyfile(source/'mystar-requested-day.json.first-attempt.receipt.json',raw/'mystar-requested-day.json.first-attempt.receipt.json')
    receipts['seismo-calendar.html']=seismic
    # Preserve the receipt, not a third-party HTML page with external scripts/styles.
    shutil.copyfile(source/'seismo-calendar.html.receipt.json',raw/'seismo-calendar.html.receipt.json')
    for name in ('environment-observations.json','environment-observations.csv'):
        shutil.copyfile(source/name,out/name)
    def dump(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    dump('selected.json',{k:v for k,v in bundle.items() if k!='series'} | {'series':selected})
    catalogues=json.loads(json.dumps(research['catalogues']))
    for catalogue in catalogues:
        features=json.loads((source/catalogue['file']).read_text(encoding='utf-8'))['features']
        clouds=[f['properties'].get('eo:cloud_cover') for f in features]
        clouds=[v for v in clouds if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)]
        catalogue['cloudMin']=min(clouds) if clouds else None
        catalogue['cloudMax']=max(clouds) if clouds else None
    manifest={
        'schema':'mg.coastal-sources.v1','dateLocal':bundle['dateLocal'],'timezone':bundle['timezone'],
        'windowStartUtc':bundle['windowStartUtc'],'windowEndUtcExclusive':bundle['windowEndUtcExclusive'],
        'counts':research['counts'],'receipts':receipts,'catalogues':catalogues,
        'retrievalClock':'The original capture script recorded its timestamp at request start. Download completion was not recorded. This is not a station receiver clock.',
        'danishArchive':research['danishArchive'],'seismology':research['seismology'],
        'aisProbe':{'requestedDayFixes':0,'controlDate':'2026-11-13','controlFixes':1,
                    'datedResponse':'raw/mystar-requested-day.json','datedReceipt':'raw/mystar-requested-day.json.receipt.json',
                    'failedAttemptReceipt':'raw/mystar-requested-day.json.first-attempt.receipt.json',
                    'meaning':'A commercial MyStar control did not recover a historical track through Digitraffic’s latest-fix endpoint. No vessel-absence inference.'},
        'helcomArchive':research['helcomArchive'],'sourceDocs':research['sourceDocs'],
        'limits':bundle['limits'],
        'reuse':'FMI observations: CC BY 4.0. Copernicus catalogue metadata and Danish directory retained as source records. No third-party imagery, AIS ZIP or seismic waveform republished.',
    }
    dump('manifest.json',manifest)
    inventory=[]
    for path in sorted(out.rglob('*')):
        if path.is_file():
            inventory.append({'path':path.relative_to(ROOT/'docs').as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    provenance={
        'title':'The day, as recorded.','date':'2026-11-11','format':'mg.coastal-source-notebook.v1',
        'source':'Finnish Meteorological Institute / Copernicus Data Space / public archive metadata',
        'dataDirectory':'data/coastal-sources/2026-11-11/','transformation':'Saved provider payloads; FMI WaterML pairs normalized to JSON and CSV. Seven channels selected for display. No interpolation or zero filling. Source timestamps retained.',
        'originalReceiptTimes':[receipts[n]['retrievedAt'] for n in sorted(receipts)],
        'retrievalClock':manifest['retrievalClock'],
        'missingMetadata':'Absent optical cloud-cover attributes remain null; no cloud statistics are inferred for radar products.',
        'claims':'Environmental station context and archive availability. Not an incident reconstruction, military track, radar association or operationally validated tool.',
        'coastline':{'file':'assets/coastal-replay-land.json','source':'Natural Earth 1:10m land','license':'Public domain','meaning':'Context map, not a nautical chart. Station coordinates come from FMI.'},
        'files':inventory,
    }
    (ROOT/'docs/design/coastal-source-notebook-provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'Promoted {len(selected)} channels; {len(inventory)} files; no network requests.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    build(p.parse_args().source.resolve())
