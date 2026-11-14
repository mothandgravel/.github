"""Capture one bounded civilian weather passage. Explicit network command; never used by the site."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

LIMIT=2_000_000
def dump(value):return (json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf8')
def now():return datetime.now(timezone.utc).isoformat()

def capture(root,name,url):
    path=root/name;rp=root/(name+'.receipt.json')
    if rp.exists():
        r=json.loads(rp.read_text(encoding='utf8'))
        if 'sha256' in r:assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256']
        return r
    assert not path.exists(),'Never overwrite an original capture'
    assert shutil.disk_usage(root).free >= 20*1024**3+LIMIT,'Keep at least 20 GiB free'
    r={'file':name,'url':url,'requestedAt':now()}
    try:
        with urlopen(Request(url,headers={'User-Agent':'MothGravel-weather-passage-research/1.0','Accept-Encoding':'gzip'}),timeout=30) as response:
            r.update(status=response.status,finalUrl=response.url,serverDate=response.headers.get('Date'),lastModified=response.headers.get('Last-Modified'),etag=response.headers.get('ETag'),contentType=response.headers.get('Content-Type'),contentRange=response.headers.get('Content-Range'),warnings=response.headers.get_all('Warning',[]))
            wire=response.read(LIMIT+1)
            if len(wire)>LIMIT:raise ValueError('Wire response exceeds 2 MB cap')
            data=gzip.GzipFile(fileobj=BytesIO(wire)).read(LIMIT+1) if response.headers.get('Content-Encoding')=='gzip' else wire
            if len(data)>LIMIT:raise ValueError('Decoded response exceeds 2 MB cap')
            if name.endswith('.png') and data[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Not a PNG; HTTP success is not image success')
            if name.endswith('.h5') and data[:8]!=b'\x89HDF\r\n\x1a\n':raise ValueError('Not HDF5')
            path.write_bytes(data)
            r.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),wireSha256=hashlib.sha256(wire).hexdigest(),completedAt=now())
    except HTTPError as error:
        body=error.read(8192);ep=root/(name+'.error.txt');ep.write_bytes(body)
        r.update(status=error.code,error=str(error),errorBodyFile=ep.name,errorBodySha256=hashlib.sha256(body).hexdigest(),failedAt=now())
    except Exception as error:r.update(error=str(error),failedAt=now())
    rp.write_bytes(dump(r));time.sleep(.1)
    return r

class State(HTMLParser):
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if 'data-mfl-initial-state' in d:self.state=json.loads(d['data-mfl-initial-state'])
        if 'data-mfl-fetch-uri' in d:self.url=urljoin('https://avaandmed.keskkonnaportaal.ee',d['data-mfl-fetch-uri'])

class ContentLink(HTMLParser):
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='a' and 'Content.aspx' in d.get('href',''):self.url=urljoin('https://avaandmed.keskkonnaportaal.ee',d['href'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    raw=args.output/'raw';raw.mkdir(parents=True,exist_ok=True)
    domain='eumetsat-geocolour-times.xml'
    domain_url='https://view.eumetsat.int/geoserver/gwc/service/wmts?service=WMTS&version=1.0.0&request=GetDomainValues&layer=mtg_fd:rgb_geocolour&domain=time&time=2026-11-10T22:00:00Z/2026-11-11T21:59:59Z&limit=200'
    assert capture(raw,domain,domain_url).get('sha256')
    values=next(x.text for x in ET.parse(raw/domain).getroot() if x.tag.endswith('Domain')).split(',')
    assert len(values)==len(set(values))==144
    jobs=[];clouds=[]
    for stamp in sorted(values):
        t=datetime.fromisoformat(stamp.replace('Z','+00:00'));name='eumetsat-'+t.strftime('%Y%m%d-%H%M')+'.png'
        url='https://view.eumetsat.int/geoserver/wms?'+urlencode({'service':'WMS','version':'1.3.0','request':'GetMap','layers':'mtg_fd:rgb_geocolour','styles':'','format':'image/png','crs':'CRS:84','bbox':'23,59,28.5,61','width':1100,'height':400,'time':stamp,'transparent':'true'})
        jobs.append((name,url));clouds.append({'productTimeUtc':stamp,'sourceFile':name})
    with ThreadPoolExecutor(max_workers=3) as pool:
        for i,r in enumerate(pool.map(lambda j:capture(raw,*j),jobs),1):
            if i%12==0 or r.get('error'):print(json.dumps({'clouds':i,'status':r.get('status'),'error':r.get('error')}),flush=True)
    page='estonia-precipitation-archive.html'
    assert capture(raw,page,'https://avaandmed.keskkonnaportaal.ee/dhs/Active/documentList.aspx?ViewId=501c5fca-0010-4abf-829d-6e90b7dbf08a').get('sha256')
    parser=State();parser.feed((raw/page).read_text(encoding='utf8'));parser.state['Filters']={'RMTitle':'*2026111110*'};parser.state['PageSize']=20
    index='estonia-precipitation-1000-hour-list.json'
    assert capture(raw,index,parser.url+'&'+urlencode({'state':json.dumps(parser.state,separators=(',',':')),'page':0})).get('sha256')
    listing=json.loads((raw/index).read_text(encoding='utf8'));assert listing['error'] is None
    assert listing['totalItemCount']==len(listing['items'])==12
    radar=[];jobs=[]
    for item in listing['items']:
        fields={f['name']:f['html'] for f in item['fields']};name=re.search(r'comp\.20261111\d{6}\.CAP\.\d+\.h5',fields['RMTitle'])[0]
        link=ContentLink();link.feed(fields['RMTitle']);jobs.append((name,link.url))
        radar.append({'sourceFile':name,'catalogueId':item['id'],'catalogueUiTime':fields['Timestamp'],'catalogueBytes':int(fields['RMFileSize'])})
    with ThreadPoolExecutor(max_workers=3) as pool:
        for r in pool.map(lambda j:capture(raw,*j),jobs):print(json.dumps({'radar':r['file'],'status':r.get('status'),'error':r.get('error')}),flush=True)
    plan={'schema':'mg.coastal-weather-capture.v1','dateLocal':'2026-11-11','timezone':'Europe/Helsinki','cloudDomainFile':domain,'clouds':clouds,'radarIndexFile':index,'radar':radar}
    path=args.output/'capture.json'
    if path.exists():assert path.read_bytes()==dump(plan),'Capture plan changed; preserve original'
    else:path.write_bytes(dump(plan))
    print('Saved 144 cloud requests and 12 radar requests; failed receipts remain explicit.')

if __name__=='__main__':main()
