// Source contours become closed surfaces, bevelled stones and a lathed body.
const bone = [.91,.87,.77], vein = [.23,.24,.22];
const sub = (a,b) => a.map((v,i)=>v-b[i]);
const cross = (a,b) => [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const unit = a => { const n=Math.hypot(...a)||1; return a.map(v=>v/n); };
const sourcePoint = (p,z) => [p[0]-495,520-p[1],z];
const area = (a,b,c) => (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);

function triangulate(points) {
  const indices=points.map((_,i)=>i), output=[];
  if(points.reduce((sum,p,i)=>sum+p[0]*points[(i+1)%points.length][1]-points[(i+1)%points.length][0]*p[1],0)<0)indices.reverse();
  let guard=points.length*points.length;
  while(indices.length>3 && guard-->0) {
    let found=false;
    for(let i=0;i<indices.length;i++) {
      const a=indices[(i+indices.length-1)%indices.length],b=indices[i],c=indices[(i+1)%indices.length];
      if(area(points[a],points[b],points[c])<=.00001)continue;
      if(indices.some(k=>k!==a&&k!==b&&k!==c&&area(points[a],points[b],points[k])>=-.00001&&area(points[b],points[c],points[k])>=-.00001&&area(points[c],points[a],points[k])>=-.00001))continue;
      output.push([a,b,c]);indices.splice(i,1);found=true;break;
    }
    if(!found)throw new Error('Moth contour could not be triangulated');
  }
  if(indices.length===3)output.push(indices);
  return output;
}

function builder() {
  const data=[];
  const triangle=(a,b,c,color,normals)=>{
    const raw=cross(sub(b,a),sub(c,a));if(Math.hypot(...raw)<.000001)return;
    const face=unit(raw);
    [a,b,c].forEach((p,i)=>data.push(...p,...(normals?.[i]||face),...color));
  };
  const quad=(a,b,c,d,color)=>{triangle(a,b,c,color);triangle(a,c,d,color);};
  const tube=(points,radius,color)=>{
    for(let i=0;i<points.length-1;i++) {
      const a=points[i],b=points[i+1],axis=unit(sub(b,a));
      const side=unit(cross(axis,Math.abs(axis[2])>.9?[0,1,0]:[0,0,1])),up=cross(axis,side);
      const at=(p,angle)=>p.map((v,k)=>v+radius*(side[k]*Math.cos(angle)+up[k]*Math.sin(angle)));
      for(let j=0;j<6;j++) {
        const t=j*Math.PI/3,n=(j+1)*Math.PI/3;
        quad(at(a,t),at(b,t),at(b,n),at(a,n),color);
        if(i===0)triangle(a,at(a,n),at(a,t),color);
        if(i===points.length-2)triangle(b,at(b,t),at(b,n),color);
      }
    }
  };
  return {triangle,quad,tube,finish:()=>new Float32Array(data)};
}

function paper(wing) {
  const mesh=builder(),points=wing.outline;
  const curl=p=>4+22*Math.pow(Math.abs(p[0]-wing.pivot[0])/360,1.7)+5*Math.sin((p[1]-wing.pivot[1])*.015);
  const normal=(p,side)=>unit([-side*(curl([p[0]+.1,p[1]])-curl([p[0]-.1,p[1]]))/.2,
    side*(curl([p[0],p[1]+.1])-curl([p[0],p[1]-.1]))/.2,side]);
  const surface=(tri,side)=>{
    const p=tri.map(i=>sourcePoint(i,curl(i)+side*1.8));
    // Source y is downward; reverse the front to face the camera.
    const order=side>0?[0,2,1]:[0,1,2];
    mesh.triangle(...order.map(i=>p[i]),bone,order.map(i=>normal(tri[i],side)));
  };
  for(const tri of triangulate(points)) {
    const [a,b,c]=tri.map(i=>points[i]);
    const ab=a.map((v,i)=>(v+b[i])/2),bc=b.map((v,i)=>(v+c[i])/2),ca=c.map((v,i)=>(v+a[i])/2);
    for(const part of [[a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca]]){surface(part,1);surface(part,-1);}
  }
  for(let i=0;i<points.length;i++) {
    const a=points[i],b=points[(i+1)%points.length];
    mesh.quad(sourcePoint(a,curl(a)-1.8),sourcePoint(b,curl(b)-1.8),sourcePoint(b,curl(b)+1.8),sourcePoint(a,curl(a)+1.8),[.67,.63,.54]);
  }
  for(const line of wing.veins)mesh.tube(line.map(p=>sourcePoint(p,curl(p)+2.7)),2.2,vein);
  return mesh.finish();
}

function gravel(wing) {
  const mesh=builder();
  wing.stones.forEach((points,index)=>{
    const center=points.reduce((v,p)=>[v[0]+p[0]/points.length,v[1]+p[1]/points.length],[0,0]);
    const height=10+(index*7%11),tone=.69+(index*3%9)*.025;
    const color=[tone,tone*.98,tone*.92];
    const lower=points.map(p=>sourcePoint(p,-8));
    const edge=points.map(p=>sourcePoint(p,2));
    const inner=points.map(p=>sourcePoint(p.map((v,i)=>center[i]+(v-center[i])*.76),height));
    const peak=sourcePoint([center[0]+(index%3-1)*3,center[1]+(index%2?2:-2)],height+6);
    for(let i=0;i<points.length;i++) {
      const j=(i+1)%points.length;
      mesh.quad(lower[i],lower[j],edge[j],edge[i],color);
      mesh.quad(edge[i],edge[j],inner[j],inner[i],color);
      mesh.triangle(inner[i],inner[j],peak,color);
      mesh.triangle(lower[j],lower[i],sourcePoint(center,-8),color);
    }
  });
  return mesh.finish();
}

function body(source) {
  const mesh=builder();
  const lathe=(rings,color,depth=.72)=>{
    const point=(ring,angle)=>sourcePoint([500+ring[1]*Math.cos(angle),ring[0]],18+ring[1]*Math.sin(angle)*depth);
    for(let i=0;i<rings.length-1;i++)for(let j=0;j<16;j++) {
      const a=j*Math.PI/8,b=(j+1)*Math.PI/8;
      mesh.quad(point(rings[i],a),point(rings[i+1],a),point(rings[i+1],b),point(rings[i],b),color);
    }
  };
  lathe([[386,0],[390,12],[400,20],[414,22],[430,17],[442,0]],bone,.9);
  lathe([[430,0],[440,24],[465,30],[492,29],[520,22],[550,22],[580,20],[610,18],[640,15],[669,11],[695,6],[717,0]],bone);
  for(const [y,r] of [[550,22],[580,20],[610,18],[640,15],[669,11]])lathe([[y-1.8,r+.5],[y+1.8,r+.5]],vein);
  return mesh.finish();
}

function antennae(source) {
  const mesh=builder();
  for(const branch of source.antennae)mesh.tube(branch.map(p=>sourcePoint(p,25+(389-p[1])*.08)),3.4,bone);
  return mesh.finish();
}

export function buildMothMeshes(source) {
  validateModel(source);
  const meshes=[...source.wings.map(wing=>({name:wing.name,pivot:sourcePoint(wing.pivot,0),data:wing.outline?paper(wing):gravel(wing)})),
    {name:'moth-body',pivot:[5,50,18],data:body(source)},
    {name:'moth-antennae',pivot:[5,131,25],data:antennae(source)}];
  if(meshes.some(mesh=>!mesh.data.length||mesh.data.some(value=>!Number.isFinite(value)))
    ||meshes.reduce((n,mesh)=>n+mesh.data.length/27,0)>5000)throw new TypeError('Invalid studio moth model');
  return meshes;
}

function validateModel(source) {
  const fail=()=>{throw new TypeError('Invalid studio moth model');};
  const point=p=>Array.isArray(p)&&p.length===2&&p.every(n=>typeof n==='number'&&Number.isFinite(n))&&p[0]>=120&&p[0]<=870&&p[1]>=305&&p[1]<=735;
  const line=(p,min=2,max=256)=>Array.isArray(p)&&p.length>=min&&p.length<=max&&p.every(point);
  const polygon=p=>line(p,3)&&Math.abs(p.reduce((a,v,i)=>a+v[0]*p[(i+1)%p.length][1]-p[(i+1)%p.length][0]*v[1],0))>1;
  if(!source||source.version!==1||source.source!=='moth-rig.svg'||!Array.isArray(source.viewBox)
    ||source.viewBox.join(',')!=='120,305,750,430'||!/^[a-f0-9]{64}$/.test(source.sourceSha256||'')
    ||!Array.isArray(source.wings)||source.wings.length!==4||!Array.isArray(source.antennae)||source.antennae.length!==2)fail();
  const expected=new Set(['wing-soft-hind','wing-stone-hind','wing-soft-fore','wing-stone-fore']);
  for(const wing of source.wings){
    if(!wing||!expected.delete(wing.name)||!point(wing.pivot))fail();
    if(wing.name.includes('soft')){
      if(!polygon(wing.outline)||!Array.isArray(wing.veins)||wing.veins.length>10||!wing.veins.every(p=>line(p)))fail();
    }else if(!Array.isArray(wing.stones)||!wing.stones.length||wing.stones.length>32||!wing.stones.every(p=>line(p,3,16)&&polygon(p)))fail();
  }
  if(!source.antennae.every(p=>line(p)))fail();
}
