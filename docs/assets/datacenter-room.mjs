import { rateLimit } from './field-power-core.mjs';

/** Authored architectural study, in metres. No surveyed ESIF layout or per-rack load. */
export async function createRoom(container,{onSelect=()=>{},onStatus=()=>{}}={}) {
  const {THREE:T,OrbitControls,RoomEnvironment,RGBELoader,RoundedBoxGeometry,RectAreaLightUniformsLib,EffectComposer,RenderPass,GTAOPass,OutputPass,mergeGeometries}=await import('./datacenter-engine.mjs');
  RectAreaLightUniformsLib.init();
  const scene=new T.Scene();scene.background=new T.Color('#161c1d');scene.fog=new T.FogExp2('#252b2a',.006);
  const renderer=new T.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
  const gl=renderer.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');
  const software=debug?/swiftshader|llvmpipe|software/i.test(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)):false;
  renderer.setPixelRatio(software?1:Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=T.SRGBColorSpace;renderer.info.autoReset=false;
  renderer.toneMapping=T.AgXToneMapping;renderer.toneMappingExposure=1.05;renderer.shadowMap.enabled=!software;renderer.shadowMap.type=T.PCFSoftShadowMap;
  renderer.domElement.tabIndex=0;renderer.domElement.setAttribute('role','img');renderer.domElement.setAttribute('aria-label','Interactive authored data-centre room. Drag to orbit and scroll to approach. Named camera views and meter selection are available as buttons outside this image.');
  renderer.domElement.className='dc-room-canvas';container.append(renderer.domElement);
  const camera=new T.PerspectiveCamera(51,1,.08,100);camera.position.set(.35,1.7,2.3);
  const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,1.6,-7);controls.enableDamping=true;controls.dampingFactor=.12;
  controls.minDistance=1.2;controls.maxDistance=29;controls.maxPolarAngle=Math.PI*.485;controls.minPolarAngle=.15;controls.zoomToCursor=true;
  controls.mouseButtons={LEFT:T.MOUSE.ROTATE,MIDDLE:T.MOUSE.DOLLY,RIGHT:T.MOUSE.PAN};controls.touches={ONE:T.TOUCH.ROTATE,TWO:T.TOUCH.DOLLY_PAN};
  const disposables=[],buckets=new Map(),selectable=[],labels=[],lights=[];
  const mat=(color,metalness=0,roughness=.5,extra={})=>{const m=new T.MeshStandardMaterial({color,metalness,roughness,...extra});disposables.push(m);return m;};
  const powder=mat('#242a2c',.03,.48),chassis=mat('#475057',.78,.29),black=mat('#0e1417',.02,.88),aluminium=mat('#9a9d98',.86,.25),brass=mat('#a18b60',.81,.33),ivory=mat('#c4c0af',.1,.7),rubber=mat('#121b1e',.05,.86),wallMat=mat('#777971',.12,.67),floorMat=mat('#777c77',.12,.23),pipeMat=mat('#b49e76',.78,.3),cool=mat('#757f7a',.45,.47);
  const finishCanvas=document.createElement('canvas');finishCanvas.width=finishCanvas.height=128;const finishCtx=finishCanvas.getContext('2d'),finishPixels=finishCtx.createImageData(128,128);let seed=8147;
  for(let i=0;i<finishPixels.data.length;i+=4){seed=(Math.imul(seed,1664525)+1013904223)>>>0;const c=165+(seed>>>28)*4;finishPixels.data[i]=finishPixels.data[i+1]=finishPixels.data[i+2]=c;finishPixels.data[i+3]=255;}finishCtx.putImageData(finishPixels,0,0);
  const finishTexture=new T.CanvasTexture(finishCanvas);finishTexture.wrapS=finishTexture.wrapT=T.RepeatWrapping;finishTexture.repeat.set(12,18);powder.roughnessMap=finishTexture;powder.needsUpdate=true;disposables.push(finishTexture);
  const whiteLight=mat('#e8e1ce',0,.5,{emissive:'#fff2d3',emissiveIntensity:3.4});
  const led=mat('#d6c397',.2,.35,{emissive:'#d6c397',emissiveIntensity:1.6});
  const glass=new T.MeshPhysicalMaterial({color:'#7b9392',metalness:.05,roughness:.09,transmission:.25,transparent:true,opacity:.22,ior:1.48,thickness:.012,side:T.DoubleSide});disposables.push(glass);
  const perforations=document.createElement('canvas');perforations.width=128;perforations.height=128;
  const pctx=perforations.getContext('2d');pctx.fillStyle='#fff';pctx.fillRect(0,0,128,128);pctx.fillStyle='#000';
  for(let y=0;y<128;y+=8)for(let x=0;x<128;x+=8){pctx.beginPath();pctx.arc(x+(y%16?4:0),y,2.6,0,Math.PI*2);pctx.fill();}
  const holes=new T.CanvasTexture(perforations);holes.wrapS=holes.wrapT=T.RepeatWrapping;holes.repeat.set(3,10);holes.anisotropy=4;disposables.push(holes);
  const grille=mat('#353d3e',.7,.45,{alphaMap:holes,alphaTest:.5,side:T.DoubleSide});
  const axis=new T.Vector3(0,1,0),m4=new T.Matrix4(),q=new T.Quaternion(),v=new T.Vector3();
  const add=(geometry,material,x,y,z,category='',rotation=0)=>{
    q.setFromAxisAngle(axis,rotation);m4.compose(new T.Vector3(x,y,z),q,new T.Vector3(1,1,1));geometry.applyMatrix4(m4);
    const prepared=geometry.index?geometry.toNonIndexed():geometry;if(prepared!==geometry)geometry.dispose();
    const key=material.uuid+category;if(!buckets.has(key))buckets.set(key,{material,category,geometries:[]});buckets.get(key).geometries.push(prepared);
  };
  const box=(w,h,d,x,y,z,material,category='',round=0,rotation=0)=>add(round?new RoundedBoxGeometry(w,h,d,2,Math.min(round,w/3,h/3,d/3)):new T.BoxGeometry(w,h,d),material,x,y,z,category,rotation);
  const tube=(points,r,material,category='')=>add(new T.TubeGeometry(new T.CatmullRomCurve3(points.map(p=>new T.Vector3(...p))),Math.max(8,points.length*7),r,10,false),material,0,0,0,category);
  const cylinder=(r,h,x,y,z,material,category='',turn=false)=>{const g=new T.CylinderGeometry(r,r,h,16);if(turn)g.rotateX(Math.PI/2);add(g,material,x,y,z,category);};
  const panelText=(text,sub,width,height,x,y,z,rotation=0)=>{
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=256;const ctx=canvas.getContext('2d');
    ctx.fillStyle='#252d2d';ctx.fillRect(0,0,1024,256);ctx.strokeStyle='#a8946b';ctx.lineWidth=3;ctx.strokeRect(12,12,1000,232);
    ctx.fillStyle='#e6e1d2';ctx.font='46px Georgia';ctx.fillText(text,40,110);ctx.fillStyle='#b7a47e';ctx.font='22px monospace';ctx.fillText(sub,40,177);
    const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;disposables.push(texture);
    const material=mat('#ffffff',.05,.6,{map:texture});const mesh=new T.Mesh(new T.PlaneGeometry(width,height),material);mesh.position.set(x,y,z);mesh.rotation.y=rotation;scene.add(mesh);return mesh;
  };
  // Sealed floor tiles, real gaps, low skirting and a quiet brass aisle marking.
  box(18,.24,24,0,-.2,-2,black);
  box(18,.055,24,0,-.05,-2,floorMat);
  // Fine tile joints are mapped, avoiding subpixel geometry and shadow acne.
  const floorCanvas=document.createElement('canvas');floorCanvas.width=floorCanvas.height=1024;const fc=floorCanvas.getContext('2d');fc.fillStyle='#9fa59e';fc.fillRect(0,0,1024,1024);fc.strokeStyle='#7c827b';fc.lineWidth=2;for(let t=0;t<=1024;t+=128){fc.beginPath();fc.moveTo(t,0);fc.lineTo(t,1024);fc.moveTo(0,t);fc.lineTo(1024,t);fc.stroke();}
  const floorTexture=new T.CanvasTexture(floorCanvas);floorTexture.colorSpace=T.SRGBColorSpace;floorTexture.wrapS=floorTexture.wrapT=T.RepeatWrapping;floorTexture.repeat.set(3.75,5);floorTexture.anisotropy=8;floorMat.map=floorTexture;disposables.push(floorTexture);
  for(const x of [-1.1,1.1])box(.023,.003,16,x,-.02,-2,brass);
  for(let z=-9;z<=6;z+=2.6){box(.13,.004,.04,-1.05,-.014,z,brass);box(.13,.004,.04,1.05,-.014,z,brass);}
  // An enclosed working hall; the visitor stays below the service ceiling.
  const ceilingMat=mat('#303937',.35,.65);
  box(18,.16,24,0,4.45,-2,ceilingMat);
  for(let x=-8.4;x<9;x+=1.2){box(.035,.12,24,x,4.31,-2,black);}
  for(let z=-13;z<10;z+=1.2)box(18,.12,.025,0,4.31,z,black);
  for(const x of [-6.6,6.6]){box(.18,.38,24,x,4.12,-2,powder);}
  // Brushed service panels and inspection hatches vary the wall rhythm.
  for(const x of [-8.87,8.87])for(let z=-12;z<5;z+=2.4){box(.08,2.6,.018,x,1.65,z,aluminium);box(.06,.025,2.3,x,2.92,z+1.1,black);}
  for(const x of [-8.84,8.84]){box(.12,1.1,1.8,x,1.5,3,ivory,'plug_and_light_kw');}
  // Walls stop short at the entry; this is an inspectable architectural room.
  box(18,4.4,.2,0,2.1,-13.8,wallMat);box(.2,4.4,23,-9,2.1,-2.4,wallMat);box(.2,4.4,23,9,2.1,-2.4,wallMat);
  for(const x of [-8.84,8.84])box(.12,.16,23,x,.08,-2.4,aluminium);
  for(let x=-8;x<=8;x+=2){box(.025,3.8,.035,x,2.1,-13.66,aluminium);}
  box(2.6,3.25,.1,0,1.58,-13.63,powder, 'hvac_kw',.025);
  box(.04,.45,.07,1.08,1.35,-13.54,brass,'hvac_kw',.012);
  panelText('MOTH & GRAVEL','COMPUTE HALL / A RECORDED ACCOUNT',3.8,.95,-4.8,2.6,-13.62);
  panelText('08 / THE LOAD','GEOMETRY AUTHORED · FACILITY METERS RECORDED',3.7,.92,4.5,2.6,-13.62);
  // Racks are constructed in local coordinates, then rotated towards their aisle.
  for(const [row,x] of [[0,-5.1],[1,-2.1],[2,2.1],[3,5.1]])for(let n=0;n<(software?6:10);n++){
    const z=-9+n*.78,rotation=x<0?Math.PI/2:-Math.PI/2;
    const local=(lx,ly,lz)=>{v.set(lx,ly,lz).applyAxisAngle(axis,rotation);return [v.x+x,ly,v.z+z];};
    const part=(w,h,d,lx,ly,lz,m,round=0)=>{const pos=local(lx,ly,lz);box(w,h,d,...pos,m,'it_power_kw',round,rotation);};
    part(.69,2.25,1.15,0,1.18,0,powder,.024);
    part(.59,2.05,.014,0,1.2,.585,black);
    part(.018,2.1,.035,-.311,1.2,.61,aluminium);part(.018,2.1,.035,.311,1.2,.61,aluminium);
    part(.63,.032,.04,0,2.25,.61,chassis);part(.63,.032,.04,0,.15,.61,chassis);
    part(.025,.27,.032,.28,1.2,.65,brass,.009);
    // 2U chassis, module vents, rack ears, bolts and restrained working lights.
    for(let s=0;s<(software?9:18);s++){
      const y=.27+s*.105;if((n+row)%5===0&&s>12)continue;
      part(.56,.087,.035,0,y,.586,s%5?chassis:black,.004);
      part(.017,.065,.025,-.28,y,.61,aluminium);part(.017,.065,.025,.28,y,.61,aluminium);
      for(let f=0;f<3;f++){
        const pos=local(-.16+f*.16,y,.612);const fan=new T.CylinderGeometry(.031,.031,.008,12);fan.rotateX(Math.PI/2);fan.rotateY(rotation);add(fan,black,...pos,'it_power_kw');
        part(.008,.008,.005,-.248+f*.013,y+.014,.62,s%7===0?led:black);
      }
      for(const side of [-1,1])part(.006,.006,.005,side*.275,y+.023,.628,brass);
    }
    // Real perforation cut-outs sit in front of the chassis; every fourth door is glass.
    part(.598,2.04,.002,0,1.2,.64,n%4===0?glass:grille);
    part(.57,.018,.2,0,2.32,.18,brass);
    for(const side of [-1,1]){
      const pos=local(side*.2,.075,0);cylinder(.028,.085,...pos,aluminium,'it_power_kw');
      const a=local(side*.2,2.28,-.45),b=local(side*.2,2.9,-.44),c=local(side*.2,3.12,-.38);
      tube([a,b,c],.013,side<0?rubber:pipeMat,'it_power_kw');
    }
    if(n===(software?5:9)){
      box(1.02,1.92,.018,x,1.18,z+.357,powder,'it_power_kw',.008);
      for(const dx of [-.46,.46])box(.012,1.82,.012,x+dx,1.18,z+.371,aluminium,'it_power_kw');
      for(let vent=0;vent<12;vent++)box(.72,.012,.018,x,.43+vent*.027,z+.38,black,'it_power_kw');
      box(.024,.24,.035,x+.4,1.22,z+.386,brass,'it_power_kw',.008);
      panelText(`HALL / ${String.fromCharCode(65+row)}`,'SERVICE / KEEP CLEAR',.69,.17,x,1.94,z+.39);
      for(const dx of [-.43,.43])for(const yy of [.31,2.02])box(.012,.012,.009,x+dx,yy,z+.39,brass,'it_power_kw');
    }
    if(n%3===0){const pos=local(0,2.16,.663);panelText(`${String.fromCharCode(65+row)} / ${String(n+1).padStart(2,'0')}`,'ILLUSTRATIVE RACK',.42,.105,...pos,rotation);}
  }
  // Overhead services: cable trays, suspended lighting, water supplies and real joints.
  for(const x of [-5.1,-2.1,2.1,5.1]){
    box(.55,.08,10.6,x,3.25,-5.25,black);
    for(let z=-10;z<.5;z+=.35)box(.58,.018,.035,x,3.3,z,aluminium);
    for(const dx of [-.16,.16])tube([[x+dx,3.48,1],[x+dx,3.48,-10],[x+dx,2.8,-12.5]],.045,pipeMat,'pump_kw');
    for(let z=-10;z<1;z+=2){box(.025,.75,.025,x,3.75,z,aluminium);cylinder(.062,.025,x+.16,3.48,z,brass,'pump_kw',true);}
  }
  for(const x of [-3.65,0,3.65,7.4])for(const z of [-8,-3,2]){
    box(.085,.06,3.1,x,3.67,z,aluminium);box(.06,.014,3,x,3.635,z,whiteLight,'plug_and_light_kw');
    const light=new T.RectAreaLight('#fff3db',60,1.1,3.1);light.position.set(x,3.5,z);light.rotation.x=-Math.PI/2;scene.add(light);lights.push(light);
  }
  // Mechanical gallery: insulated loops, valves, twin pumps and heat rejection plant.
  for(const x of [7.2,8.0]){
    tube([[x,.45,-9],[x,2.75,-9],[x,2.75,-3],[x,1.1,-2]],.07,pipeMat,'pump_kw');
    for(const z of [-8.5,-7,-5.5,-4]){cylinder(.105,.05,x,2.75,z,aluminium,'pump_kw',true);box(.28,.026,.09,x,2.95,z,brass,'pump_kw',.01);}
  }
  for(const z of [-4,-6]){
    box(1.55,.16,1.2,7.5,.06,z,ivory,'pump_kw',.025);cylinder(.27,.8,7.4,.54,z,cool,'pump_kw',true);
    cylinder(.34,.12,7.4,.54,z+.42,aluminium,'pump_kw',true);cylinder(.15,.32,7.4,.9,z,black,'pump_kw');
    box(.42,.28,.36,7.85,.43,z,powder,'pump_kw',.035);
    // Flange fasteners, motor cooling rings and real connections to both headers.
    for(let ring=-3;ring<=3;ring++)cylinder(.284,.018,7.4,.54,z+ring*.075,powder,'pump_kw',true);
    for(let bolt=0;bolt<8;bolt++){const angle=bolt*Math.PI/4;cylinder(.018,.035,7.4+Math.cos(angle)*.29,.54+Math.sin(angle)*.29,z+.5,brass,'pump_kw',true);}
    tube([[7.4,.54,z+.52],[7.4,.54,z+.75],[7.2,.65,z+.9],[7.2,2.75,z+.9]],.083,pipeMat,'pump_kw');
    tube([[7.4,.54,z-.45],[7.4,.54,z-.7],[8,.8,z-.8],[8,2.75,z-.8]],.083,pipeMat,'pump_kw');
    for(const dz of [.63,-.56])cylinder(.105,.04,7.4,.54,z+dz,aluminium,'pump_kw',true);
    box(.08,.1,.16,7.4,.15,z+.2,rubber,'pump_kw',.01);
    box(.08,.1,.16,7.4,.15,z-.2,rubber,'pump_kw',.01);
  }
  box(1.3,2.65,3.2,-7.4,1.36,-6.5,ivory,'hvac_kw',.055);
  for(let j=0;j<22;j++)box(.015,.04,3.05,-6.735,.3+j*.105,-6.5,aluminium,'hvac_kw');
  box(1.35,.65,2.2,-7.4,3.05,-9,cool,'hvac_kw',.05);
  box(4.3,1.65,1.8,4.4,.9,-11.8,cool,'cooling_kw',.08);
  for(const x of [3.2,5.6]){
    cylinder(.6,.07,x,1.77,-11.8,black,'cooling_kw');
    for(let j=0;j<8;j++){const angle=j*Math.PI/4;box(.07,.025,.5,x+Math.sin(angle)*.26,1.815,-11.8+Math.cos(angle)*.26,aluminium,'cooling_kw',.005,angle);}
  }
  panelText('WATER LOOP','PUMP POWER / WHOLE-FACILITY CATEGORY',1.7,.42,7.3,1.7,-8.45,-Math.PI/2);
  // Mesh batching preserves category-level picking while keeping draw calls bounded.
  for(const {material,category,geometries} of buckets.values()){
    const merged=mergeGeometries(geometries,false);geometries.forEach(g=>g.dispose());
    const instanceMaterial=category?material.clone():material;if(category)disposables.push(instanceMaterial);
    const mesh=new T.Mesh(merged,instanceMaterial);mesh.castShadow=material!==glass&&material!==whiteLight&&material!==floorMat;mesh.receiveShadow=true;mesh.userData.category=category;mesh.userData.highlightable=material!==led&&material!==whiteLight&&!material.map;scene.add(mesh);disposables.push(merged);if(category)selectable.push(mesh);
  }
  const ambient=new T.HemisphereLight('#e4e4d7','#363b35',.18);scene.add(ambient);
  const key=new T.DirectionalLight('#fff1d3',1.1);key.position.set(-1,4.1,3);key.castShadow=true;
  key.shadow.mapSize.set(2048,2048);key.shadow.camera.left=-13;key.shadow.camera.right=13;key.shadow.camera.top=15;key.shadow.camera.bottom=-15;key.shadow.camera.far=40;key.shadow.bias=-.00018;key.shadow.normalBias=.025;key.shadow.radius=4;scene.add(key);
  const fill=new T.DirectionalLight('#c8d8e1',.18);fill.position.set(5,4,-10);scene.add(fill);
  const pmrem=new T.PMREMGenerator(renderer);let environment,hdrSource;
  try{const hdr=await new RGBELoader().loadAsync(new URL('./data-center/studio-small-09.hdr',import.meta.url).href);hdr.mapping=T.EquirectangularReflectionMapping;hdrSource=hdr;environment=pmrem.fromEquirectangular(hdr);}
  catch{const roomEnv=new RoomEnvironment();environment=pmrem.fromScene(roomEnv,.04);roomEnv.dispose();}
  scene.environment=environment.texture;scene.environmentIntensity=.35;
  try{const normal=await new T.TextureLoader().loadAsync(new URL('./data-center/floor-normal.jpg',import.meta.url).href);normal.wrapS=normal.wrapT=T.RepeatWrapping;normal.repeat.set(1,1);normal.anisotropy=8;floorMat.normalMap=normal;floorMat.normalScale.set(.025,.025);floorMat.needsUpdate=true;disposables.push(normal);}catch{/* material remains fully functional */}
  const composer=new EffectComposer(renderer);composer.addPass(new RenderPass(scene,camera));
  const ao=new GTAOPass(scene,camera,800,500);ao.blendIntensity=.8;ao.updateGtaoMaterial({radius:.3,distanceExponent:1,thickness:.7,scale:1,samples:8});ao.enabled=!software;composer.addPass(ao);composer.addPass(new OutputPass());
  const presets={aisle:{position:[.35,1.7,2.3],target:[0,1.6,-7]},overview:{position:[7.7,3.75,5.8],target:[-1,1.2,-5]},it_power_kw:{position:[.1,1.7,-.5],target:[-2.1,1.1,-3]},pump_kw:{position:[6.6,1.6,.4],target:[7.35,.8,-5]},hvac_kw:{position:[-6.4,1.8,.4],target:[-7.2,1.5,-6]},cooling_kw:{position:[.8,3.4,-7.6],target:[4.2,1,-11.7]},plug_and_light_kw:{position:[.8,2.4,3.7],target:[0,3.6,-4]}};
  let dirty=8,visible=true,destroyed=false,request=0,last=0,arrival=null,selected='',moving=false,drawing=false,pathTracer=null,refining=false,refineLimit=96,lastStatusSample=-1;
  const stopRefining=()=>{if(refining){refining=false;onStatus('Interactive lighting. Use Refine light to accumulate indirect illumination at a fixed viewpoint.');}};
  const draw=now=>{
    request=0;if(destroyed||!visible||document.hidden)return;
    drawing=true;const dt=last?Math.min((now-last)/1000,.1):1/60;last=now;
    if(arrival){arrival.elapsed=rateLimit(arrival.elapsed,1,1/1.25,dt*1000);const ease=arrival.elapsed**2*(3-2*arrival.elapsed);camera.position.lerpVectors(arrival.from,arrival.to,ease);controls.target.lerpVectors(arrival.fromTarget,arrival.toTarget,ease);dirty=5;if(arrival.elapsed===1)arrival=null;}
    const changed=controls.update();if(changed)dirty=5;
    if(refining&&pathTracer){pathTracer.renderSample();if(Math.floor(pathTracer.samples)%8===0&&Math.floor(pathTracer.samples)!==lastStatusSample){lastStatusSample=Math.floor(pathTracer.samples);onStatus(`Refining indirect light / ${lastStatusSample} of ${refineLimit} samples. Move the camera to stop.`);}if(pathTracer.samples>=refineLimit){refining=false;onStatus(`Refined light / ${Math.floor(pathTracer.samples)} samples. Move to resume interactive rendering.`);}container.dataset.rendered='true';}
    else if(dirty>0||moving){renderer.info.reset();composer.render();dirty--;container.dataset.rendered='true';}
    drawing=false;if((dirty>0||arrival||moving||refining)&&!request)request=requestAnimationFrame(draw);
  };
  const invalidate=()=>{dirty=6;if(!drawing&&!request&&visible&&!document.hidden)request=requestAnimationFrame(draw);};
  const resize=()=>{stopRefining();const {width,height}=container.getBoundingClientRect();if(!width||!height)return;camera.aspect=width/height;camera.updateProjectionMatrix();const scale=software?Math.min(.5,600/width):1;renderer.setSize(width*scale,height*scale,false);composer.setSize(width*scale,height*scale);invalidate();};
  const ro=new ResizeObserver(resize);ro.observe(container);
  const observer=new IntersectionObserver(e=>{visible=e[0].isIntersecting;if(visible)invalidate();else{cancelAnimationFrame(request);request=0;}},{threshold:0});observer.observe(container);
  const onVisibility=()=>{if(document.hidden){cancelAnimationFrame(request);request=0;}else invalidate();};document.addEventListener('visibilitychange',onVisibility);
  controls.addEventListener('change',invalidate);controls.addEventListener('start',()=>{stopRefining();arrival=null;moving=true;invalidate();});controls.addEventListener('end',()=>{moving=false;invalidate();});
  const ray=new T.Raycaster(),pointer=new T.Vector2();let down;
  renderer.domElement.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY];});
  renderer.domElement.addEventListener('pointerup',e=>{if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)return;const b=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-b.left)/b.width*2-1,-(e.clientY-b.top)/b.height*2+1);ray.setFromCamera(pointer,camera);const hit=ray.intersectObjects(selectable)[0];if(hit)onSelect(hit.object.userData.category);});
  renderer.domElement.addEventListener('keydown',e=>{const k=e.key;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-','Home'].includes(k))stopRefining();if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-','Home'].includes(k))e.preventDefault();if(k==='Home')focus('aisle');else if(k==='+'||k==='-'){camera.position.sub(controls.target).multiplyScalar(k==='+'?.88:1.12).add(controls.target);invalidate();}else if(k.startsWith('Arrow')){const angle=k==='ArrowLeft'?.12:k==='ArrowRight'?-.12:0;const offset=camera.position.clone().sub(controls.target).applyAxisAngle(axis,angle);if(k==='ArrowUp')offset.y+=.2;if(k==='ArrowDown')offset.y-=.2;camera.position.copy(controls.target).add(offset);invalidate();}});
  renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();destroyed=true;cancelAnimationFrame(request);onStatus('Graphics context lost. Recorded readings and calculations remain available. Reload the page to re-enter the room.');});
  const focus=id=>{
    stopRefining();
    const preset=presets[id]??presets.aisle;
    const to=new T.Vector3(...preset.position),toTarget=new T.Vector3(...preset.target);
    if(matchMedia('(prefers-reduced-motion: reduce)').matches){camera.position.copy(to);controls.target.copy(toTarget);arrival=null;}
    else arrival={from:camera.position.clone(),to,fromTarget:controls.target.clone(),toTarget,elapsed:0};invalidate();
  };
  const setSelection=id=>{stopRefining();selected=id;for(const obj of selectable){const chosen=obj.userData.category===id;const m=obj.material;if(m.emissive&&obj.userData.highlightable){m.emissive.set(chosen?'#544326':'#000000');m.emissiveIntensity=chosen?.14:0;}}invalidate();};
  // Edge-aware reconstruction of the radiance buffer. This filters rendering
  // noise only; it never filters, estimates or alters the measured account.
  const displayScene=new T.Scene(),displayCamera=new T.OrthographicCamera(-1,1,1,-1,0,1);
  const denoise=new T.ShaderMaterial({depthTest:false,depthWrite:false,uniforms:{map:{value:null},pixel:{value:new T.Vector2(1,1)}},vertexShader:`varying vec2 uvScreen;void main(){uvScreen=uv;gl_Position=vec4(position.xy,0.,1.);}`,fragmentShader:`uniform sampler2D map;uniform vec2 pixel;varying vec2 uvScreen;
    void main(){vec3 centre=texture2D(map,uvScreen).rgb;vec3 sum=vec3(0.);float weights=0.;
      for(int y=-2;y<=2;y++){for(int x=-2;x<=2;x++){vec2 offset=vec2(float(x),float(y));vec3 colour=texture2D(map,uvScreen+offset*pixel).rgb;vec3 delta=colour-centre;float w=exp(-dot(offset,offset)/4.-dot(delta,delta)/.10);sum+=colour*w;weights+=w;}}
      gl_FragColor=vec4(sum/max(weights,.00001),1.);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`});
  const displayGeometry=new T.PlaneGeometry(2,2);displayScene.add(new T.Mesh(displayGeometry,denoise));disposables.push(denoise,displayGeometry);
  const refine=async(limit=96,{scale=.65}={})=>{
    if(software)throw Error('Refined lighting needs a hardware WebGL2 device. Interactive rendering remains available.');
    onStatus('Preparing indirect light. Keep the camera still while samples accumulate.');
    arrival=null;moving=false;controls.update();
    if(!pathTracer){const {WebGLPathTracer}=await import('./datacenter-pathtracer.mjs');pathTracer=new WebGLPathTracer(renderer);pathTracer.bounces=4;pathTracer.filterGlossyFactor=.5;pathTracer.tiles.set(3,3);pathTracer.renderScale=.65;pathTracer.dynamicLowRes=false;pathTracer.renderDelay=0;pathTracer.fadeDuration=0;pathTracer.minSamples=1;pathTracer.rasterizeSceneCallback=()=>{};pathTracer.renderToCanvasCallback=(target,r)=>{r.setRenderTarget(null);r.setScissorTest(false);denoise.uniforms.map.value=target.texture;denoise.uniforms.pixel.value.set(1/target.width,1/target.height);r.render(displayScene,displayCamera);};}
    const oldEnv=scene.environment;if(hdrSource)scene.environment=hdrSource;
    try{pathTracer.setScene(scene,camera);}finally{scene.environment=oldEnv;}
    pathTracer.renderScale=Math.max(.4,Math.min(1,scale));const buffer=renderer.getDrawingBufferSize(new T.Vector2());pathTracer.tiles.set(Math.max(3,Math.ceil(buffer.x*pathTracer.renderScale/192)),Math.max(3,Math.ceil(buffer.y*pathTracer.renderScale/192)));pathTracer.updateCamera();pathTracer.reset();refineLimit=limit;lastStatusSample=-1;refining=true;dirty=0;if(!request)request=requestAnimationFrame(draw);
  };
  resize();focus('aisle');onStatus('Room ready. Drag to orbit; scroll to approach. Camera views and meter buttons offer the same inspection without dragging.');
  return {focus,setSelection,refine,probe:()=>{if(!pathTracer)return null;const sample=new Float32Array(4);renderer.readRenderTargetPixels(pathTracer.target,Math.floor(pathTracer.target.width/2),Math.floor(pathTracer.target.height/2),1,1,sample);return Array.from(sample);},render:invalidate,getInfo:()=>({three:T.REVISION,softwareRenderer:software,quality:software?'reduced geometric detail and resolution':'full geometry',ambientOcclusion:ao.enabled,contextLost:gl.isContextLost(),refining,samples:pathTracer?.samples??0,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,selected,geometry:'authored; no rack power allocation'}),capture:()=>{if(gl.isContextLost())throw Error('Graphics context lost; no capture can be published.');if(!pathTracer||pathTracer.samples<1)composer.render();return renderer.domElement.toDataURL('image/png');},dispose(){destroyed=true;cancelAnimationFrame(request);ro.disconnect();observer.disconnect();document.removeEventListener('visibilitychange',onVisibility);controls.dispose();pathTracer?.dispose();composer.dispose();hdrSource?.dispose();environment.dispose();pmrem.dispose();disposables.forEach(x=>x.dispose?.());renderer.dispose();renderer.domElement.remove();}};
}
