"""Rebuild the saved weather passage offline: original clouds, native radar cells, original buoy values."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import zlib
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/data/coastal-weather/2026-11-11'
try:
    import h5py,numpy as np
except ImportError:
    sys.path.insert(0,str(ROOT/'artifacts/research/coastal-weather-tools'))
    import h5py,numpy as np

from coastal_radar_placement import summary as placement_summary,crop as placement_crop

START=datetime(2026,11,10,22,tzinfo=timezone.utc)
PARAMETERS=['WaveHs','ModalWDi','WTP','WHDD','TWATER']
STATIONS=['134221','103976','108495']
PALETTE=[(.05,(130,165,169)),(.2,(173,197,183)),(.5,(211,208,161)),(1,(225,179,112)),(2,(213,131,79)),(5,(157,77,64))]
ABOVE_COLOUR=(104,53,67)
def dump(v):return (json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')
def sha(data):return hashlib.sha256(data).hexdigest()
def stamp(value):return datetime.fromisoformat(value.replace('Z','+00:00')).isoformat().replace('+00:00','Z')
def odim_time(date,time):return datetime.strptime(date+time,'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
def plain(v):
    if isinstance(v,bytes):return v.decode('utf8').strip()
    if isinstance(v,np.generic):return v.item()
    return v
def attrs(obj):return {k:plain(v) for k,v in obj.attrs.items()}
def gzip_bytes(data):
    obj=zlib.compressobj(9,zlib.DEFLATED,-15)
    return b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff'+obj.compress(data)+obj.flush()+struct.pack('<II',zlib.crc32(data),len(data))
def png(w,h,pixels):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    scan=b''.join(b'\0'+pixels[y*w*4:(y+1)*w*4] for y in range(h))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(scan,9))+chunk(b'IEND',b'')

def generate():
    plan=json.loads((OUT/'capture.json').read_text(encoding='utf8'))
    assert plan['schema']=='mg.coastal-weather-capture.v1'
    raw=OUT/'raw';receipts={}
    for path in sorted(raw.glob('*.receipt.json'),key=lambda p:p.name):
        r=json.loads(path.read_text(encoding='utf8'));name=path.name.removesuffix('.receipt.json');assert name==r['file']
        if r.get('sha256'):
            data=(raw/name).read_bytes();assert sha(data)==r['sha256'] and len(data)==r['bytes'],name
            assert datetime.fromisoformat(r['requestedAt'])<=datetime.fromisoformat(r['completedAt'])
        receipts[name]=r
    domain=ET.parse(raw/plan['cloudDomainFile']).getroot()
    times=next(x.text for x in domain if x.tag.endswith('Domain')).split(',')
    assert len(times)==len(set(times))==144
    assert [stamp(t) for t in sorted(times)]==[datetime.fromtimestamp(START.timestamp()+i*600,timezone.utc).isoformat().replace('+00:00','Z') for i in range(144)]
    clouds=[];derived={}
    for item in plan['clouds']:
        time=stamp(item['productTimeUtc']);assert item['productTimeUtc'] in times
        name=item['sourceFile'];r=receipts[name];available=bool(r.get('sha256') and not r.get('error') and not r.get('warnings'))
        if available:
            data=(raw/name).read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',data[16:24])==(1100,400)
        clouds.append({'id':time,'productTimeUtc':time,'sourceFile':name,'available':available,
            'perPixelAcquisitionUtc':None,'firstPublicationUtc':None,'domainFile':plan['cloudDomainFile']})
    assert len(clouds)==144 and len({f['id'] for f in clouds})==144
    radar=[]
    for item in plan['radar']:
        name=item['sourceFile'];r=receipts[name];assert r.get('status')==200 and r.get('sha256') and not r.get('error'),name
        assert r['bytes']==item['catalogueBytes']
        with h5py.File(raw/name,'r') as f:
            global_what=attrs(f['what']);where=attrs(f['where']);how=attrs(f['how']);what=attrs(f['dataset1/what'])
            if 'what' in f['dataset1/data1']:what={**what,**attrs(f['dataset1/data1/what'])}
            matrix=f['dataset1/data1/data'][:]
            assert matrix.shape==(720,720) and matrix.dtype.kind=='f' and matrix.dtype.itemsize==4
            assert np.isfinite(matrix).all() and what['quantity']=='RATE' and what['product']=='PCAPPI'
            assert what['gain']==1 and what['offset']==0 and what['nodata']==65535 and what['undetect']==0
            missing=matrix==what['nodata'];below=(matrix==what['undetect'])&~missing;measured=~(missing|below)
            assert (matrix[measured]>=0).all()
            values=matrix*what['gain']+what['offset']
            colours=np.zeros((*matrix.shape,4),dtype=np.uint8);colours[below]=[61,81,87,255]
            for i,cut in enumerate(PALETTE):
                lo=0 if i==0 else PALETTE[i-1][0]
                pick=measured&(values>lo)&(values<=cut[0]);colours[pick]=[*cut[1],255]
            colours[measured&(values>PALETTE[-1][0])]=[*ABOVE_COLOUR,255]
            # All native cells remain in native row/column order. No geographic warp.
            prefix=name.removesuffix('.h5');derived[prefix+'.png']=png(720,720,colours.tobytes())
            float_bytes=matrix.astype('<f4',copy=False).tobytes(order='C')
            derived[prefix+'.f32.gz']=gzip_bytes(float_bytes)
            derived[prefix+'.map.png']=png(1100,400,placement_crop(where,matrix,colours,[23,59,28.5,61]))
            begin=odim_time(what['startdate'],what['starttime']);end=odim_time(what['enddate'],what['endtime'])
            assert datetime.fromisoformat(begin.replace('Z','+00:00'))<=datetime.fromisoformat(end.replace('Z','+00:00'))
            assert abs(datetime.fromisoformat(begin.replace('Z','+00:00')).timestamp()-how['startepochs'])<1
            assert abs(datetime.fromisoformat(end.replace('Z','+00:00')).timestamp()-how['endepochs'])<1
            radar.append({**item,'id':name,'intervalStartUtc':begin,'intervalEndUtc':end,'productTimeUtc':odim_time(global_what['date'],global_what['time']),
                'width':720,'height':720,'quantity':'RATE','unit':'mm/h','gain':what['gain'],'offset':what['offset'],
                'noDataCode':what['nodata'],'undetectCode':what['undetect'],'image':prefix+'.png','pixels':prefix+'.f32.gz',
                'imageSha256':sha(derived[prefix+'.png']),
                'pixelsEncoding':'gzip little-endian IEEE754 float32, row-major, native 720 x 720',
                'pixelsUncompressedBytes':len(float_bytes),'pixelsUncompressedSha256':sha(float_bytes),
                'cellCounts':{'missing':int(missing.sum()),'belowDetection':int(below.sum()),'quantitative':int(measured.sum())},
                'quantitativeRange':[float(values[measured].min()),float(values[measured].max())],
                'sourceNodes':how['nodes'].split(','),'globalWhat':global_what,'datasetWhat':what,'where':where,
                'mapImage':prefix+'.map.png','mapImageWidth':1100,'mapImageHeight':400,
                'mapImageSha256':sha(derived[prefix+'.map.png']),
                'georeferencing':placement_summary(where,matrix),
                'timeMeaning':'ODIM dataset product interval as supplied; underlying radar sweep and per-pixel acquisition unknown.',
                'underlyingSweepAcquisitionUtc':None,'perPixelAcquisitionUtc':None,
                'originalReceiverTimeUtc':None,'firstPublicationUtc':None})
    radar.sort(key=lambda r:r['intervalEndUtc']);assert len(radar)==12
    evidence=json.loads((OUT/'placement-evidence.json').read_text(encoding='utf8'))
    assert evidence['schema']=='mg.coastal-radar-placement-evidence.v1'
    assert [r['source'] for r in evidence['records']]==['agency','proj','odim']
    for r in evidence['records']:
        assert r['status']==200 and r['bytes']>0 and len(r['sha256'])==64 and r['firstPublicationUtc'] is None
        assert datetime.fromisoformat(r['requestedAtUtc'])<=datetime.fromisoformat(r['downloadCompletedAtUtc'])
    original=ROOT/'docs/data/coastal-sources/2026-11-11/environment-observations.json'
    environment=json.loads(original.read_text(encoding='utf8'))
    buoys=[]
    for sid in STATIONS:
        series=[s for s in environment['series'] if s['stationId']==sid and s['parameter'] in PARAMETERS]
        assert {s['parameter'] for s in series}==set(PARAMETERS)
        for s in series:
            assert len(s['points'])==24
            for i,p in enumerate(s['points']):
                assert datetime.fromisoformat(p['observedAt'].replace('Z','+00:00')).timestamp()==START.timestamp()+i*3600
                assert p['value'] is None and p['rawValue']=='NaN' or float(p['rawValue'])==p['value']
        buoys.append({'id':sid,'station':series[0]['station'],'latitude':series[0]['latitude'],'longitude':series[0]['longitude'],'series':series})
    notebook={'schema':'mg.coastal-weather.v1','dateLocal':'2026-11-11','timezone':'Europe/Helsinki',
        'windowStartUtc':'2026-11-10T22:00:00Z','windowEndUtcExclusive':'2026-11-11T22:00:00Z',
        'bbox':[23,59,28.5,61],'clouds':clouds,'radar':radar,'buoys':buoys,'receipts':receipts,
        'policies':{'cloudMaxAgeSecondsExclusive':600,'radarMaxAgeSecondsExclusive':300,
            'radarOutsideSavedSpan':'unavailable','buoyMaxAgeSecondsExclusive':3600,
            'noFutureSelection':True,'interpolation':False,'waveDirectionConvention':'from, clockwise degrees from north',
            'noFutureSelectionAppliesTo':'Declared cloud product labels, radar product-interval end labels and buoy sample labels. Unknown physical acquisition times are excluded.',
            'waveIllustration':'A labelled schematic of reported height and modal period; not a recorded surface or spectrum.'},
        'sources':{
            'clouds':{'origin':'EUMETSAT / Meteosat Third Generation FCI','distribution':'EUMETView / Geo Colour RGB',
                'credit':'Contains modified EUMETSAT Meteosat product 2026','licence':'CC BY 4.0 / Core Advanced Image Products',
                'licenceUrl':'https://www.eumetsat.int/legal-framework/data-policy',
                'policyEvidenceUrl':'https://www-cdn.eumetsat.int/files/2026-02/44253%20-%20Basic%20Documents.pdf#page=210',
                'policyEvidence':'Data Policy Articles 4–6: FCI Advanced Image Products are Core, CC BY 4.0, redistribution with attribution.',
                'definitionUrl':'https://view.eumetsat.int/',
                'limits':'Rendered cloud context. Product timestamps, not per-pixel acquisition times. Day/night composite treatments differ. No cloud-motion vector or rainfall inferred.'},
            'radar':{'origin':'Keskkonnaagentuur / Harku and Sürgavere weather radars','distribution':'KAIA / Estonian Environment Agency',
                'credit':'Keskkonnaagentuur radar products 2026 / CC BY 4.0','licence':'CC BY 4.0',
                'licenceUrl':'https://keskkonnaportaal.ee/et/avaandmed/meteoroloogiliste-radarite-andmestik',
                'definitionUrl':'https://keskkonnaportaal.ee/et/avaandmed/radariandmestik/radariandmete-kirjeldus',
                'placementEvidenceFile':'placement-evidence.json',
                'limits':'Radar-derived rain-rate estimates, not rain-gauge accumulations. Two contributing radars, one derived composite. Corner-anchored Mercator registration, footprint checked but not surveyed or provider-confirmed. Source scales and LR latitude still conflict. Approximate map-cell coordinates only. ODIM product-interval labels retained; underlying sweep and pixel acquisition unknown. No-data and below-detection remain distinct.'},
            'buoys':{'origin':'Finnish Meteorological Institute / wave buoys','distribution':'FMI WFS',
                'credit':'Finnish Meteorological Institute / CC BY 4.0','licence':'CC BY 4.0',
                'licenceUrl':'https://en.ilmatieteenlaitos.fi/open-data-licence',
                'definitionUrl':'https://en.ilmatieteenlaitos.fi/guidance-to-observations',
                'sourceDataFile':'data/coastal-sources/2026-11-11/environment-observations.json',
                'sourceDataSha256':sha(original.read_bytes()),
                'limits':'Hourly requested samples, not a continuous wave record. Nulls stay missing. Direction means from. Directional spread is not a confidence interval. First publication and station receipt times unknown.'}}}
    derived['notebook.json']=dump(notebook)
    return derived

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--import-sources',type=Path);p.add_argument('--check',action='store_true');args=p.parse_args()
    if args.import_sources:
        assert not args.check
        (OUT/'raw').mkdir(parents=True,exist_ok=True)
        plan=json.loads((args.import_sources/'capture.json').read_text(encoding='utf8'))
        names={plan['cloudDomainFile'],plan['radarIndexFile'],*[f['sourceFile'] for f in plan['clouds']],*[f['sourceFile'] for f in plan['radar']]}
        originals=[]
        for name in sorted(names):
            for suffix in ('','.receipt.json','.error.txt'):
                source=args.import_sources/'raw'/(name+suffix)
                if source.exists():originals.append(source)
        # Provider landing HTML is retained in the private research capture, not served as an active page.
        for source in [args.import_sources/'capture.json',*originals]:
            target=OUT/('raw/'+source.name if source.parent.name=='raw' else source.name)
            if target.exists():assert target.read_bytes()==source.read_bytes(),'Preserve existing captures'
            else:shutil.copyfile(source,target)
    outputs=generate()
    for name,data in outputs.items():
        if args.check:
            previous=(OUT/name).read_bytes()
            if previous!=data:
                at=next((i for i,(a,b) in enumerate(zip(previous,data)) if a!=b),min(len(previous),len(data)))
                print(f'Derived mismatch at byte {at}: {name}',file=sys.stderr)
                print('Saved: '+repr(previous[max(0,at-60):at+160]),file=sys.stderr)
                print('Rebuilt: '+repr(data[max(0,at-60):at+160]),file=sys.stderr)
            assert previous==data,'Derived file drift: '+name
        else:(OUT/name).write_bytes(data)
    inventory=[{'path':p.relative_to(ROOT/'docs').as_posix(),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(OUT.rglob('*'),key=lambda p:p.relative_to(OUT).as_posix()) if p.is_file()]
    provenance={'schema':'mg.coastal-weather-provenance.v1','dateLocal':'2026-11-11',
        'transformation':'Cloud PNGs unchanged from WMS. Radar float32 cells copied in native order to deterministic gzip. Native palette PNGs preserved; map PNGs use corner-anchored ellipsoidal Mercator registration and nearest native-cell sampling into the CRS:84 cloud crop. No-data hatching and below-detection stippling are distinct display classes, not physical values. All source attributes retained; unconfirmed scale convention and conflicting LR latitude excluded explicitly. Buoy samples unchanged.',
        'paletteRateMMH':[{'maximumInclusiveMMH':upper,'colour':colour} for upper,colour in PALETTE]+[{'minimumExclusiveMMH':5,'maximumInclusiveMMH':None,'colour':ABOVE_COLOUR}],
        'scope':'Environmental context. No vessel association, incident attribution or damage assessment.',
        'clockMeaning':'Declared product labels and supplied radar product intervals kept separate from retrieval receipts. Underlying radar sweep, per-pixel acquisition, first publication and original station reception remain unknown.',
        'dependencies':'tools/specimens/coastal-weather-requirements.txt','files':inventory}
    target=ROOT/'docs/design/coastal-weather-provenance.json'
    if args.check:assert target.read_bytes()==dump(provenance),'Provenance drift'
    else:target.write_bytes(dump(provenance))
    print(f'Weather passage: 144 cloud slots, 12 native radar frames, 3 buoys; {len(inventory)} files verified offline.')
if __name__=='__main__':main()
