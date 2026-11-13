"""Append bounded public-source checks. Never edit published data or fetch AIS tracks."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import argparse
import gzip
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'docs/data/coastal-sources/2026-11-11'
LIMIT=2_000_000
DEADLINE='2026-11-14T18:00:00Z'
NAMES=['harmaja-weather.xml','finnish-wave-observations.xml','finnish-sea-level-observations.xml',
       'sentinel-1-grd-day-catalogue.json','sentinel-2-l2a-day-catalogue.json','danish-november-archive-list.xml','seismo-calendar.html']

def digest(payload):return hashlib.sha256(payload).hexdigest()

def meaning(name,payload):
    if name.endswith('catalogue.json'):
        data=json.loads(payload)
        if any(l.get('rel')=='next' for l in data.get('links',[])):raise ValueError('Catalogue has another page; comparison is incomplete')
        return [{'id':f['id'],**{k:f['properties'].get(k) for k in ['datetime','start_datetime','published','eopf:datatake_id','eo:cloud_cover']}} for f in sorted(data['features'],key=lambda f:f['id'])]
    if name=='danish-november-archive-list.xml':
        root=ET.fromstring(payload)
        if root.find('{*}IsTruncated').text!='false':raise ValueError('Truncated archive listing')
        return [{e.tag.rsplit('}',1)[-1]:e.text for e in c} for c in root.findall('{*}Contents')]
    if name=='seismo-calendar.html':
        class Calendar(HTMLParser):
            def __init__(self):super().__init__();self.links=[]
            def handle_starttag(self,tag,attrs):
                href=dict(attrs).get('href','')
                if tag=='a' and re.search(r'phel2026\d{3}\.html$',href):self.links.append(href)
        cal=Calendar();cal.feed(payload.decode('utf-8'))
        return {'studyDateLinks':sorted(h for h in cal.links if h.endswith('phel2026315.html')),'latestLinkedDayOfYear':max((int(re.search(r'2026(\d{3})\.html$',h)[1]) for h in cal.links),default=None)}
    root=ET.fromstring(payload)
    if root.tag!='{http://www.opengis.net/wfs/2.0}FeatureCollection':raise ValueError('Not an observation response')
    rows=[]
    for member in root.findall('{*}member'):
        obs=list(member)[0]
        station=obs.find('.//{http://xml.fmi.fi/namespace/om/atmosphericfeatures/1.1}Location/{*}identifier').text
        parameter=obs.find('{*}observedProperty').attrib['{http://www.w3.org/1999/xlink}href']
        rows.extend([station,parameter,p.find('{*}time').text,p.find('{*}value').text] for p in obs.findall('.//{http://www.opengis.net/waterml/2.0}MeasurementTVP'))
    if not rows:raise ValueError('Empty observation payload needs investigation; not treated as missing measurements')
    return sorted(rows)

def semantic_hash(value):return digest(json.dumps(value,sort_keys=True,separators=(',',':')).encode())

def availability(name,semantic):
    if name=='danish-november-archive-list.xml':
        return {'studyDateListed':any(item['Key']=='aisdk-2026-11-11.zip' for item in semantic)}
    if name=='seismo-calendar.html':return {'studyDateLinked':bool(semantic['studyDateLinks'])}
    return None

def check(output,until=DEADLINE):
    deadline=datetime.fromisoformat(until.replace('Z','+00:00'))
    if deadline.tzinfo is None:raise ValueError('Deadline must include its timezone')
    now=datetime.now(timezone.utc)
    if now>=deadline:
        result={'status':'stopped','checkedAt':now.isoformat(),'deadline':deadline.isoformat(),'reason':'The bounded follow-up window has ended; no requests sent.'}
        print(json.dumps(result));return result
    manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True,exist_ok=True)
    state_path=output/'state.json'
    previous=json.loads(state_path.read_text()) if state_path.exists() else {}
    stamp=now.strftime('%Y-%m-%dT%H-%M-%S-%fZ')
    capture=output/stamp;capture.mkdir(exist_ok=False)
    def request(name):
        base=manifest['receipts'][name]
        prior=previous.get(name,{})
        headers={'User-Agent':'MothGravel-source-availability-check/1.0','Accept-Encoding':'gzip'}
        for key,header in [('etag','If-None-Match'),('lastModified','If-Modified-Since')]:
            value=prior.get(key) or base.get(key)
            if value:headers[header]=value
        record={'file':name,'url':base['url'],'requestedAt':datetime.now(timezone.utc).isoformat()}
        initial=DATA/'raw'/name
        if not initial.exists():initial=ROOT/'artifacts/research/2026-11-13-november11'/name
        before=None;published=None
        try:
            record['phase']='baseline'
            if initial.exists():published=semantic_hash(meaning(name,initial.read_bytes()))
            body=Path(prior['bodyFile']) if prior.get('bodyFile') else Path(prior.get('capture',''))/name
            if not body.is_file():body=initial
            semantic_before=meaning(name,body.read_bytes()) if body.is_file() else None
            if semantic_before is not None:before=semantic_hash(semantic_before)
            record.update(beforeSemanticSha256=before,publishedSemanticSha256=published)
            record['phase']='request'
            with urlopen(Request(base['url'],headers=headers),timeout=30) as response:
                record.update(status=response.status,finalUrl=response.url,retrievedAt=datetime.now(timezone.utc).isoformat())
                wire=response.read(LIMIT+1)
                if len(wire)>LIMIT:raise ValueError('Wire response exceeds 2 MB limit')
                payload=gzip.GzipFile(fileobj=BytesIO(wire)).read(LIMIT+1) if response.headers.get('Content-Encoding')=='gzip' else wire
                if len(payload)>LIMIT:raise ValueError('Decoded response exceeds 2 MB limit')
                (capture/name).write_bytes(payload)
                record.update(bodyFile=str(capture/name),bytes=len(payload),sha256=digest(payload),phase='interpretation')
                semantic=meaning(name,payload)
                record.update(status=response.status,finalUrl=response.url,retrievedAt=datetime.now(timezone.utc).isoformat(),
                              bytes=len(payload),sha256=digest(payload),wireSha256=digest(wire),semanticSha256=semantic_hash(semantic),
                              etag=response.headers.get('ETag'),lastModified=response.headers.get('Last-Modified'),
                              cacheControl=response.headers.get('Cache-Control'),retryAfter=response.headers.get('Retry-After'),
                              serverDate=response.headers.get('Date'),beforeSemanticSha256=before)
                record['changed']=record['semanticSha256']!=before if before else None
                record['differsFromPublished']=record['semanticSha256']!=published if published else None
                record['availability']=availability(name,semantic)
                record['bodyFile']=str(capture/name)
                (capture/name).write_bytes(payload)
                (capture/(name+'.meaning.json')).write_text(json.dumps(semantic,indent=2)+'\n',encoding='utf-8')
        except HTTPError as error:
            record.update(status=error.code,retrievedAt=datetime.now(timezone.utc).isoformat(),
                          retryAfter=error.headers.get('Retry-After'),serverDate=error.headers.get('Date'),
                          cacheControl=error.headers.get('Cache-Control'))
            if error.code==304:
                record.update(changed=False if before else None,semanticSha256=before,
                              differsFromPublished=before!=published if before and published else None,
                              bodyFile=str(body) if body.is_file() else None,
                              availability=availability(name,semantic_before) if semantic_before is not None else None,
                              etag=prior.get('etag') or base.get('etag'),lastModified=prior.get('lastModified') or base.get('lastModified'))
                if before is None:record['error']='304 without an inspectable baseline; availability remains unknown'
            else:
                error_body=error.read(8192);error_name=name+'.http-error.txt';(capture/error_name).write_bytes(error_body)
                record.update(error=str(error),changed=None,errorBodyFile=error_name,errorBodySha256=digest(error_body),errorBodyBytes=len(error_body))
        except Exception as error:
            record.setdefault('status',None)
            record.update(error=str(error),changed=None)
        (capture/(name+'.receipt.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        return record
    with ThreadPoolExecutor(max_workers=3) as pool:records=list(pool.map(request,NAMES))
    state=dict(previous)
    for record in records:
        if record.get('semanticSha256'):state[record['file']]={**record,'capture':str(capture)}
    # Capture directories are append-only; only this small comparison index advances.
    temporary=output/'state.next.json';temporary.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8');temporary.replace(state_path)
    summary={'checkedAt':now.isoformat(),'capture':str(capture),'changed':[r['file'] for r in records if r.get('changed') is True],
             'differsFromPublished':[r['file'] for r in records if r.get('differsFromPublished') is True],
             'availability':{r['file']:r.get('availability') for r in records if r['file'] in ['danish-november-archive-list.xml','seismo-calendar.html']},
             'unknownOrFailed':[r['file'] for r in records if r.get('changed') is None],
             'records':records,'limits':'No AIS ZIP, military movements, imagery raster or seismic waveform obtained. Availability and environmental data only. No guaranteed publication time inferred.'}
    (capture/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'capture':str(capture),'changed':summary['changed'],'differsFromPublished':summary['differsFromPublished'],
                      'availability':summary['availability'],'unknownOrFailed':summary['unknownOrFailed'],'statuses':{r['file']:r.get('status') for r in records}},indent=2))
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/research/2026-11-13-november11/updates')
    parser.add_argument('--until',default=DEADLINE,help='Explicit timezone-qualified stop time; default is the requested follow-up deadline')
    args=parser.parse_args()
    check(args.output.resolve(),args.until)
