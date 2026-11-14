import {cloudAt,radarAt,buoyAt,radarGridAt,radarCellLocation,waveDirectionFrom,mapBearingVector,secondAtUtc} from './coastal-weather-model.mjs';

const $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg';
const node=(tag,attrs={},value)=>{const n=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(value!==undefined)n.textContent=value;return n;};
const text=(id,value)=>{$(id).textContent=value;};
const clock=time=>new Intl.DateTimeFormat('en-GB',{timeZone:'UTC',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(time))+' UTC';
const x=lon=>(lon-23)/5.5*1100,y=lat=>(61-lat)/2*400;
const label=n=>n===null?'Missing':String(Math.round(n*100)/100);
const rateLabel=n=>new Intl.NumberFormat('en-GB',{maximumSignificantDigits:4}).format(n);

export function createWeatherMap({target,data,cloudImage,loadImage,root,onCell,onStation,onFailure,onPresentationChange}){
  let rainVersion=0,currentSecond=43206,station='134221',selected=null,inspect=false,compare=false,origin='native row / column',rainState='Opening image';
  const layers={clouds:true,rain:true,buoys:true};let opacity=.85;
  const rain=node('image',{id:'cw-map-rain',x:0,y:0,width:1100,height:400,visibility:'hidden',preserveAspectRatio:'none',class:'cw-map-rain'});
  // Insert directly above the clouds; coastline, station glyphs and labels remain above rain.
  target.append(rain);
  const buoys=node('g',{id:'cw-map-wave-glyphs'}),selection=node('g',{id:'cw-map-selection','aria-hidden':'true'});
  function applyLayers(){
    cloudImage.style.opacity=layers.clouds?'1':'0';rain.style.opacity=layers.rain?String(opacity):'0';buoys.style.display=layers.buoys?'':'none';
    $('cw-cloud-message').style.display=layers.clouds?'':'none';$('cw-sky').dataset.cloudLayer=String(layers.clouds);
    for(const kind of Object.keys(layers))$('cw-layer-'+kind).setAttribute('aria-pressed',String(layers[kind]));
    $('cw-rain-opacity').disabled=!layers.rain;text('cw-opacity-value',Math.round(opacity*100)+'%');
    $('cw-map-inspect').disabled=!layers.rain;
    text('cw-map-cloud-state',(layers.clouds?'':'Layer hidden · ')+'Pixel acquisition unknown');
    text('cw-map-radar-state',(layers.rain?'':'Layer hidden · ')+rainState);
    text('cw-map-buoy-state',(layers.buoys?'':'Layer hidden · ')+'Hourly samples · spaces unmeasured');
    const f=radarAt(data,currentSecond);text('cw-map-rain-stamp',!layers.rain?'RAIN / LAYER HIDDEN':f?`RAIN / ${clock(f.intervalEndUtc)} END LABEL`:'RAIN / NO ELIGIBLE PRODUCT');
  }
  function setRainState(value){rainState=value;applyLayers();}
  function renderSelection(){
    selection.replaceChildren();if(!selected||!inspect)return;
    const p=selected.location,px=x(p.longitude),py=y(p.latitude),ax=x(p.agencyLongitude),ay=y(p.agencyLatitude);
    if(compare){selection.append(node('line',{x1:px,y1:py,x2:ax,y2:ay,class:'cw-map-alternative-link'}),node('circle',{cx:ax,cy:ay,r:8,class:'cw-map-alternative'}));}
    selection.append(node('path',{d:`M${px-10} ${py}H${px+10}M${px} ${py-10}V${py+10}`,class:'cw-map-selected'}));
    const inside=p.longitude>=23&&p.longitude<=28.5&&p.latitude>=59&&p.latitude<=61;
    const approxDistance=Math.abs(p.latitude-p.agencyLatitude)*111.4;
    text('cw-map-cell-position',`Approximate centre / ${p.latitude.toFixed(3)}° N, ${p.longitude.toFixed(3)}° E. Agency example / ${p.agencyLatitude.toFixed(3)}° N, same longitude; about ${approxDistance.toFixed(1)} km apart along the meridian.${inside?'':' This native cell is outside the full map crop.'} Not an accuracy bound.`);
    const inPhone=p.longitude>=24.15&&p.longitude<=26.9;
    if(innerWidth<=760&&!inPhone)$('cw-map-cell-position').append(' Outside the current phone crop; the native controls still inspect it.');
    const buoy=buoyAt(data,station,currentSecond);
    text('cw-map-cell-context',`${origin}. Column ${selected.x}, row ${selected.y} / radar end label ${clock(selected.intervalEndUtc)}; selected buoy sample ${clock(buoy.points.WaveHs.observedAt)}. These are separate clocks. A tap chooses a native cell, roughly 0.8 km across near 60° N; it does not establish point accuracy. Alternative placement can put a different cell at the same place.`);
  }
  function setInspect(value){
    inspect=value;$('cw-map-inspection').hidden=!value;$('cw-map-inspect').setAttribute('aria-pressed',String(value));
    text('cw-map-inspect',value?'Stop map inspection ×':'Inspect a place ↗');target.classList.toggle('cw-map-inspecting',value);renderSelection();
  }
  function sampleAtStation(){
    const f=radarAt(data,currentSecond),b=data.buoys.find(b=>b.id===station);
    origin=`Started at ${b.station} buoy coordinates / approximate radar placement, not rainfall measured by the buoy`;
    const cell=f&&radarGridAt(f,b.longitude,b.latitude);if(cell)onCell(cell.column,cell.row);else text('cw-map-cell-value','No eligible saved radar frame. Physical value unknown.');
  }
  for(const kind of Object.keys(layers))$('cw-layer-'+kind).onclick=()=>{layers[kind]=!layers[kind];if(kind==='rain'&&!layers.rain)setInspect(false);applyLayers();onPresentationChange();};
  $('cw-rain-opacity').oninput=()=>{opacity=Number($('cw-rain-opacity').value)/100;applyLayers();onPresentationChange();};
  $('cw-map-inspect').onclick=()=>{setInspect(!inspect);if(inspect&&!selected)sampleAtStation();onPresentationChange();};
  $('cw-placement-compare').onclick=()=>{compare=!compare;$('cw-placement-compare').setAttribute('aria-pressed',String(compare));text('cw-placement-compare',compare?'Hide alternative placement ×':'Show alternative placement ↗');renderSelection();onPresentationChange();};
  target.onclick=e=>{
    const glyph=e.target.closest('[data-cw-buoy-glyph]');if(glyph&&layers.buoys){onStation(glyph.dataset.cwBuoyGlyph);return;}
    if(!inspect||!layers.rain)return;
    const ctm=target.getScreenCTM();if(!ctm)return;
    const pt=new DOMPoint(e.clientX,e.clientY).matrixTransform(ctm.inverse()),lon=23+pt.x/1100*5.5,lat=61-pt.y/400*2,f=radarAt(data,currentSecond),cell=f&&radarGridAt(f,lon,lat);
    origin='Picked on the map / approximate source-cell selection';
    if(cell)onCell(cell.column,cell.row);else{selected=null;renderSelection();text('cw-map-cell-value','No eligible radar cell at this time and place. Physical value unknown.');text('cw-map-cell-position','');text('cw-map-cell-context','');}
  };
  $('cw-map-native-controls').onclick=()=>{$('cw-cell-details').open=true;origin='Chosen with native row / column controls';$('cw-cell-x').focus();};
  for(const button of document.querySelectorAll('[data-cw-map-buoy]'))button.onclick=()=>onStation(button.dataset.cwMapBuoy);
  const f=data.radar[0],g=f.georeferencing,c=g.footprintChecks;
  text('cw-placement-check',`First composite / ${c.cornerMercator.boundaryCellCount.toLocaleString('en-GB')} non-crop boundary cells. Median absolute difference from nominal radar range: ${(c.cornerMercator.medianAbsoluteRangeResidualMetres/1000).toFixed(2)} km with corner-anchored Mercator; ${(c.agencyPlateCarree.medianAbsoluteRangeResidualMetres/1000).toFixed(2)} km with the agency display example. These small range residuals coexist with about 8 km of latitude disagreement inside this map. Both methods share longitudes; this check cannot validate east–west placement. Range extremes outside the file are excluded. All twelve checks and the literal-scale diagnostic are retained.`);
  const facts=$('cw-placement-facts');facts.replaceChildren();
  for(const [key,value]of [['Registration','LL / UR outer corners + supplied ellipsoidal Mercator'],['Native increment / inferred',g.derivedProjectedPixelMetres.map(n=>n.toFixed(2)).join(' × ')+' projected m (about 0.8 ground km near 60° N)'],['Source increment / unused',[f.where.xscale,f.where.yscale].map(n=>n.toFixed(2)).join(' × ')+' declared m'],['Declared / projected ratios',g.declaredToCornerScaleRatios.map(n=>n.toFixed(4)).join(' / ')+'; broadly compatible with ground/projected Mercator scaling'],['Axis-ratio difference',g.axisScaleRatioDisagreementPercent.toFixed(2)+'% / one uniform Mercator scale does not reconcile both'],['Lower-right latitude / unused',g.unusedLowerRightLatitude.toFixed(6)+'° N'],['Provider confirmation','Unknown / not obtained'],['Surveyed accuracy','Unknown']]){
    const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=key;dd.textContent=value;facts.append(dt,dd);
  }
  applyLayers();
  return {
    finish(){target.append(buoys,selection);},
    relayout(){renderSelection();},
    inspectionActive(){return inspect;},
    layerVisible(kind){return layers[kind]===true;},
    setSelectionOrigin(value){origin=value;},
    prepareStation(id){
      if(!inspect)return;
      const b=data.buoys.find(b=>b.id===id),f=radarAt(data,currentSecond)??data.radar[0],cell=radarGridAt(f,b.longitude,b.latitude);
      origin=`Started at ${b.station} buoy coordinates / approximate radar placement, not rainfall measured by the buoy`;
      if(cell){$('cw-cell-x').value=String(cell.column);$('cw-cell-y').value=String(cell.row);}
    },
    snapshot(){return {layers:{...layers},rainOpacity:opacity,mapInspection:inspect,showAlternativePlacement:compare,selectionOrigin:origin,registrationMethod:g.method,registrationAccuracyMetres:null};},
    update(second,stationId){
      currentSecond=second;station=stationId;
      const cloud=cloudAt(data,second),radar=radarAt(data,second),b=buoyAt(data,station,second);
      text('cw-map-cloud-clock',cloud?clock(cloud.productTimeUtc):'No eligible product');
      text('cw-map-radar-clock',radar?clock(radar.intervalEndUtc):'No eligible product');
      text('cw-map-buoy-clock',clock(b.points.WaveHs.observedAt));
      buoys.replaceChildren();
      for(const [i,id]of ['103976','134221','108495'].entries()){
        const {station:s,points:p}=buoyAt(data,id,second),cx=x(s.longitude),cy=y(s.latitude),d=waveDirectionFrom(p.ModalWDi.value),missing=p.WaveHs.value===null,group=node('g',{'data-cw-buoy-glyph':id,'data-missing-direction':String(!d),'data-missing-height':String(missing),class:'cw-map-buoy-target'});
        group.append(node('circle',{cx,cy,r:10,class:'cw-wave-dot'}));
        if(missing)group.append(node('path',{d:`M${cx-5} ${cy-5}L${cx+5} ${cy+5}M${cx+5} ${cy-5}L${cx-5} ${cy+5}`,class:'cw-wave-missing'}));
        if(id===station)group.append(node('circle',{cx,cy,r:16,class:'cw-wave-selected'}));
        if(d){const v=mapBearingVector(d.fromDegrees,s.latitude),ox=cx+v.dx*37,oy=cy+v.dy*37,tx=cx+v.dx*14,ty=cy+v.dy*14;
          group.append(node('line',{x1:ox,y1:oy,x2:tx,y2:ty,class:'cw-wave-arrow'}),node('path',{d:`M${tx+v.dx*8-v.dy*5} ${ty+v.dy*8+v.dx*5}L${tx} ${ty}L${tx+v.dx*8+v.dy*5} ${ty+v.dy*8-v.dx*5}`,class:'cw-wave-arrow'}));
        }
        group.append(node('text',{x:cx+19,y:cy+5,class:'cw-wave-index'},String(i+1).padStart(2,'0')));
        group.append(node('title',{},`${s.station}, ${clock(p.WaveHs.observedAt)} sample. Height ${label(p.WaveHs.value)} m; modal period ${label(p.WTP.value)} s; direction ${d?'from '+d.fromDegrees+' degrees':'missing'}. Arrow is a schematic direction, not a motion vector.`));buoys.append(group);
        const button=document.querySelector(`[data-cw-map-buoy="${id}"]`);button.setAttribute('aria-pressed',String(id===station));
        button.querySelector('strong').textContent=`${p.WaveHs.value===null?'Missing height':label(p.WaveHs.value)+' m'} / ${p.WTP.value===null?'missing period':label(p.WTP.value)+' s'}`;
        button.querySelector('small').textContent=`${d?'From '+d.fromDegrees+'°':'Direction missing'} · ${clock(p.WaveHs.observedAt)} sample`;
      }
      applyLayers();
    },
    async renderRain(frame){
      const version=++rainVersion;rain.setAttribute('visibility','hidden');rain.removeAttribute('data-frame-id');
      selected=null;renderSelection();text('cw-map-cell-position','');text('cw-map-cell-value','Choose a place on the map or use the native row and column controls below.');
      text('cw-map-cell-context','');
      if(!frame){
        const inside=currentSecond>=secondAtUtc(data.radar[0].intervalEndUtc)&&currentSecond<=secondAtUtc(data.radar.at(-1).intervalEndUtc);
        text('cw-map-status',inside?'Rain layer absent / age-limit gap between eligible product labels. No earlier rain carried forward.':'Rain layer absent / outside the saved 10:00–10:55 UTC strip. This does not mean dry weather.');
        setRainState(inside?'Age-limit gap · no retained image':'Outside saved coverage · not dry weather');text('cw-map-cell-value','No eligible saved radar frame. Physical value unknown.');return;
      }
      text('cw-map-status','Opening the saved rain layer. Previous rain image hidden.');setRainState('Opening image · end label, not sweep time');
      try{
        const image=await loadImage(new URL(frame.mapImage,root),frame.mapImageSha256);if(version!==rainVersion)return;
        if(image.width!==1100||image.height!==400)throw Error('Unexpected map image');
        rain.setAttribute('href',image.url);rain.setAttribute('visibility','visible');rain.dataset.frameId=frame.id;
        text('cw-map-status','Rain placed from source corners and Mercator projection. Approximate registration; scale convention unconfirmed. Hatching = no data. Dots = below detection. Crossed buoy = missing height. Arrows show where waves come from, not drift. Opacity blends display colours; inspect cells for numbers.');
        setRainState('Placement inferred · sweep unknown');
      }catch(error){
        if(version!==rainVersion)return;
        text('cw-map-status',`${error.message.includes('SHA-256')?'Rain layer failed its integrity check.':'Rain layer could not open.'} The source record exists; use “Try this saved radar image again” below. Clouds and buoy records keep their own status.`);setRainState('Image unavailable · not a data gap');onFailure();
      }
    },
    selectCell(frame,cell,description){
      selected={...cell,location:radarCellLocation(frame,cell.x,cell.y)};
      text('cw-map-cell-value',cell.kind==='quantitative'?`${rateLabel(cell.value)} mm/h / radar-derived estimate`:cell.kind==='missing'?'No radar data / physical value unknown':'Below detection / no measured zero');renderSelection();return selected.location;
    },
    cellFailure(){selected=null;renderSelection();text('cw-map-cell-value','Native cells could not be read or verified. No physical value assigned.');text('cw-map-cell-position','');},
    clearSelection(){selected=null;renderSelection();text('cw-map-cell-position','');text('cw-map-cell-context','');text('cw-map-cell-value','Choose a valid native row / column or a place on the map.');},
  };
}
