"""Explicit registration of this saved Estonian grid; never silently repair source metadata."""
import numpy as np
from pyproj import CRS, Transformer, Geod

METHOD='mg.corner-mercator.v1'
AGENCY='https://keskkonnaportaal.ee/et/avaandmed/radariandmestik/radariandmete-kirjeldus'
ODIM='https://www.eumetnet.eu/wp-content/uploads/2026/01/ODIM_H5_v2.4.2_final.pdf'
RADARS=[{'id':'eehar','name':'Harku','longitude':24+36/60+10/3600,'latitude':59+23/60+53/3600,'documentedRangeMetres':250000},
        {'id':'eesyr','name':'Sürgavere','longitude':25+31/60+7/3600,'latitude':58+28/60+56/3600,'documentedRangeMetres':250000}]

def transforms(w):
    # These assertions deliberately scope the method to the inspected packet.
    assert w['projdef']=='+proj=merc +a=6378137 +lat_0=0 +lon_0=0 +rf=298.257224'
    assert w['xsize']==w['ysize']==720 and w['UL_lon']==w['LL_lon'] and w['UR_lon']==w['LR_lon'] and w['UL_lat']==w['UR_lat']
    crs=CRS.from_proj4(w['projdef'])
    fwd=Transformer.from_crs('EPSG:4326',crs,always_xy=True)
    inv=Transformer.from_crs(crs,'EPSG:4326',always_xy=True)
    left,bottom=fwd.transform(w['LL_lon'],w['LL_lat']);right,top=fwd.transform(w['UR_lon'],w['UR_lat'])
    return fwd,inv,[left,bottom,right,top]

def native_at(w,lon,lat):
    fwd,_,(left,bottom,right,top)=transforms(w);x,y=fwd.transform(lon,lat)
    return np.floor((x-left)/(right-left)*720).astype(int),np.floor((top-y)/(top-bottom)*720).astype(int)

def coordinate(w,column,row,agency=False):
    u=(np.asarray(column)+.5)/720;v=(np.asarray(row)+.5)/720
    if agency:return w['LL_lon']+u*(w['UR_lon']-w['LL_lon']),w['UR_lat']-v*(w['UR_lat']-w['LL_lat'])
    _,inv,(left,bottom,right,top)=transforms(w)
    return inv.transform(left+u*(right-left),top-v*(top-bottom))

def summary(w,matrix):
    fwd,inv,(left,bottom,right,top)=transforms(w)
    # Boundary is data adjacent to no-data in four-neighbour topology. Exclude
    # two edge rows/columns where the rectangular file crop truncates coverage.
    mask=matrix!=65535;pad=np.pad(mask,1,constant_values=False);inside=np.ones(mask.shape,dtype=bool)
    for dy,dx in [(-1,0),(1,0),(0,-1),(0,1)]:inside &= pad[1+dy:721+dy,1+dx:721+dx]
    yy,xx=np.where(mask&~inside);keep=(xx>1)&(xx<718)&(yy>1)&(yy<718);xx=xx[keep];yy=yy[keep]
    u=(xx+.5)/720;v=(yy+.5)/720;geod=Geod(ellps='WGS84')
    candidates={
        'cornerMercator':coordinate(w,xx,yy),
        'agencyPlateCarree':coordinate(w,xx,yy,True),
        'literalMetreScales':inv.transform(left+u*w['xscale']*720,top-v*w['yscale']*720)
    }
    checks={}
    for name,(lon,lat) in candidates.items():
        distances=np.stack([geod.inv(np.full_like(lon,r['longitude']),np.full_like(lat,r['latitude']),lon,lat)[2] for r in RADARS]).min(axis=0)
        residual=np.abs(distances-250000)
        checks[name]={'boundaryCellCount':len(xx),'medianAbsoluteRangeResidualMetres':round(float(np.median(residual)),3),
                      'p90AbsoluteRangeResidualMetres':round(float(np.quantile(residual,.9)),3),
                      'maximumAbsoluteRangeResidualMetres':round(float(residual.max()),3)}
    # Pyproj-derived controls are consumed by the independent JavaScript tests.
    controls=[]
    for col,row in [(0,0),(719,0),(0,719),(719,719),(350,300),(445,208)]:
        lon,lat=coordinate(w,col,row);_,alternative=coordinate(w,col,row,True)
        controls.append({'column':col,'row':row,'longitude':lon,'latitude':lat,'agencyLatitude':float(alternative),
                         'alternativeSeparationMetres':round(geod.inv(lon,lat,lon,float(alternative))[2],3)})
    ratios=np.array([w['xscale']*720/(right-left),w['yscale']*720/(top-bottom)])
    return {'method':METHOD,'presentation':'corner-anchored Mercator registration','verified':False,
        'placementStatus':'metadata-derived / footprint checked / not surveyed',
        'metadataReconciled':False,'providerConfirmed':False,'surveyValidated':False,
        'boundsLongitudeLatitude':[w['LL_lon'],w['LL_lat'],w['UR_lon'],w['UR_lat']],
        'projectedBoundsMetres':[left,bottom,right,top],
        'derivedProjectedPixelMetres':[(right-left)/720,(top-bottom)/720],
        'declaredGridSpanMetres':[w['xsize']*w['xscale'],w['ysize']*w['yscale']],
        'declaredToCornerScaleRatios':ratios.tolist(),
        'sphericalEquivalentTrueScaleLatitudesDegrees':np.degrees(np.arccos(ratios)).tolist(),
        'axisScaleRatioDisagreementPercent':float((ratios.max()/ratios.min()-1)*100),
        'scaleDiagnosticLimit':'Most of the factor-of-two difference is compatible with Mercator ground/projected scale near 60 N. This does not confirm a ground-scale convention; differing axis ratios and the LR latitude remain unexplained. Literal-metre interpretation is a diagnostic, not evidence of a 58 km geolocation error.',
        'projectedCornerSpanMetres':[right-left,top-bottom],
        'unusedLowerRightLatitude':w['LR_lat'],
        'selection':'Use supplied Mercator CRS, LL/UR outer pixel corners and native north-to-south row order. Infer projected increments from bounds. Do not use contradictory metre scales or LR latitude.',
        'alternative':'Agency example uses the same LL/UR rectangle directly in PlateCarree. Inspect its alternative latitude for the same native cell. This is sensitivity to an interpretation, not an error bound.',
        'evidenceUrls':[AGENCY,ODIM,'https://proj.org/en/stable/operations/projections/merc.html'],
        'radars':RADARS,'footprintChecks':checks,
        'footprintCheckLimit':'Geometric consistency only. Same source mask, not independent geolocation evidence. Candidates share longitudes, so this does not discriminate east/west placement. Northern/southern range extremes are cropped and excluded; small range residuals can coexist with several kilometres of latitude disagreement. Residuals approach the roughly 0.8 km ground-cell quantisation. Nominal range, holes and beam geometry affect residuals. No calibration fitted; no accuracy inferred.',
        'controlPoints':controls,
        'limit':'Registration is reproducible, not a geolocation accuracy certificate. Source scales and LR corner still conflict. Approximate cell coordinates only; no navigation or site-level rainfall claim.'}

def crop(w,matrix,colours,bbox,width=1100,height=400):
    west,south,east,north=bbox
    lon=west+(np.arange(width)+.5)/width*(east-west)
    lat=north-(np.arange(height)+.5)/height*(north-south)
    lons,lats=np.meshgrid(lon,lat);x,y=native_at(w,lons,lats)
    valid=(x>=0)&(x<720)&(y>=0)&(y<720)
    out=np.zeros((height,width,4),dtype=np.uint8)
    # Output pixels nearest-sample the original class. No interpolation of RATE.
    out[valid]=colours[y[valid],x[valid]]
    raw=np.full((height,width),65535,dtype=np.float32);raw[valid]=matrix[y[valid],x[valid]]
    row,col=np.indices((height,width));hatch=(row+col)%10<2
    dots=(row%8<2)&(col%8<2)
    out[raw==0]=[108,153,160,12]
    out[(raw==0)&dots]=[108,153,160,210]
    out[(raw==65535)&hatch]=[188,180,160,110]
    out[(raw==65535)&~hatch]=[0,0,0,0]
    return out.tobytes()
