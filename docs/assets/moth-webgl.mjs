import { buildMothMeshes } from './moth-mesh.mjs';

const vertex = `
attribute vec3 a_position; attribute vec3 a_normal; attribute vec3 a_color;
uniform mat4 u_model;
varying vec3 v_normal; varying vec3 v_color; varying vec3 v_surface;
void main(){
  vec4 p=u_model*vec4(a_position,1.0);
  gl_Position=vec4(p.x/397.5,p.y/227.9,-p.z/700.0,1.0);
  v_normal=mat3(u_model)*a_normal; v_color=a_color; v_surface=a_position;
}`;
const fragment = `
precision mediump float;
uniform vec3 u_light; uniform float u_paper; varying vec3 v_normal; varying vec3 v_color; varying vec3 v_surface;
void main(){
  vec3 n=normalize(v_normal); if(!gl_FrontFacing)n=-n;
  float diffuse=max(dot(n,u_light),0.0);
  float grain=fract(sin(dot(floor(v_surface.xy*1.4),vec2(12.9898,78.233)))*43758.5453);
  float rim=pow(1.0-abs(n.z),2.0)*.12;
  vec3 light=vec3(.34+.07*u_paper)+vec3(.74,.70,.62)*diffuse;
  gl_FragColor=vec4(v_color*(light+rim)*(.97+grain*.04),1.0);
}`;
const identity = () => new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);
const multiply=(a,b)=>{const out=new Float32Array(16);for(let j=0;j<4;j++)for(let i=0;i<4;i++)for(let k=0;k<4;k++)out[i+j*4]+=a[i+k*4]*b[k+j*4];return out;};
const translate=(x,y,z)=>{const m=identity();m[12]=x;m[13]=y;m[14]=z;return m;};
const rotateY=a=>new Float32Array([Math.cos(a),0,-Math.sin(a),0,0,1,0,0,Math.sin(a),0,Math.cos(a),0,0,0,0,1]);
const rotateX=a=>new Float32Array([1,0,0,0,0,Math.cos(a),Math.sin(a),0,0,-Math.sin(a),Math.cos(a),0,0,0,0,1]);
const rotateZ=a=>new Float32Array([Math.cos(a),Math.sin(a),0,0,-Math.sin(a),Math.cos(a),0,0,0,0,1,0,0,0,0,1]);
const hinge=(pivot,rotation)=>multiply(translate(...pivot),multiply(rotation,translate(...pivot.map(v=>-v))));
const names={'wing-soft-fore':'softFore','wing-soft-hind':'softHind','wing-stone-fore':'stoneFore','wing-stone-hind':'stoneHind'};

/** A bounded GPU surface. The interlude owns the only clock; pause keeps its pixels. */
export async function createMothRenderer(container, onLost) {
  const canvas=document.createElement('canvas');
  canvas.className='moth-volume';canvas.setAttribute('aria-hidden','true');canvas.hidden=true;
  const gl=canvas.getContext('webgl',{alpha:true,antialias:true,premultipliedAlpha:false,preserveDrawingBuffer:true,depth:true,stencil:false});
  if(!gl)throw new Error('WebGL unavailable');
  const shaders=[],buffers=[];
  let program,disposed=false;
  const cleanup=()=>{
    if(disposed)return;disposed=true;
    canvas.removeEventListener('webglcontextlost',lost);
    if(!gl.isContextLost()){buffers.forEach(b=>gl.deleteBuffer(b));shaders.forEach(s=>gl.deleteShader(s));if(program)gl.deleteProgram(program);}
    canvas.remove();
  };
  const lost=event=>{event.preventDefault();cleanup();onLost();};
  canvas.addEventListener('webglcontextlost',lost);
  try {
    const response=await fetch(new URL('./moth-model.json',import.meta.url));
    if(!response.ok)throw new Error('Moth model unavailable');
    const meshes=buildMothMeshes(await response.json());
    if(disposed||gl.isContextLost())throw new Error('Moth context lost during setup');
    const compile=(type,source)=>{
      const shader=gl.createShader(type);if(!shader)throw new Error('Moth shader allocation failed');
      shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);
      if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw new Error('Moth shader compilation failed');
      return shader;
    };
    program=gl.createProgram();if(!program)throw new Error('Moth program allocation failed');
    gl.attachShader(program,compile(gl.VERTEX_SHADER,vertex));gl.attachShader(program,compile(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error('Moth program linking failed');
    gl.useProgram(program);
    const attributes=['a_position','a_normal','a_color'].map(name=>gl.getAttribLocation(program,name));
    const model=gl.getUniformLocation(program,'u_model'),light=gl.getUniformLocation(program,'u_light'),paper=gl.getUniformLocation(program,'u_paper');
    const parts=meshes.map(mesh=>{
      const buffer=gl.createBuffer();if(!buffer)throw new Error('Moth buffer allocation failed');buffers.push(buffer);
      gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,mesh.data,gl.STATIC_DRAW);
      return {name:mesh.name,pivot:mesh.pivot,buffer,count:mesh.data.length/9};
    });
    gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.clearColor(0,0,0,0);
    container.append(canvas);
    let lastPose;
    const render=(pose,time,width)=>{
      if(disposed||gl.isContextLost())return false;
      const w=Math.max(1,Math.round(width*Math.min(devicePixelRatio||1,2))),h=Math.round(w*430/750);
      if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}
      const moving=['lift','travel','inspect','depart'].includes(pose.phase);
      const bank=moving?Math.sin(time*.0018)*.27:.12;
      const pitch=moving?Math.sin(time*.0023)*.045:0;
      const key=[w,h,bank,pitch,pose.heading,pose.bodyPitch,pose.antennaAngle,...Object.values(names).map(name=>pose[name].compression)];
      if(lastPose&&key.every((value,i)=>value===lastPose[i]))return true;
      lastPose=key;
      const global=multiply(rotateX(pitch),rotateY(bank));
      const bodyRotation=hinge([5,50,18],rotateZ(-pose.bodyPitch*Math.PI/180));
      const heading=pose.heading*Math.PI/180,c=Math.cos(heading),s=Math.sin(heading);
      const lx=-.46*c-.62*s,ly=-.46*s+.62*c,lz=.76,n=Math.hypot(lx,ly,lz);
      gl.useProgram(program);gl.uniform3f(light,lx/n,ly/n,lz/n);
      gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
      for(const part of parts) {
        let matrix=global;
        if(names[part.name]) {
          const compression=pose[names[part.name]].compression;
          const angle=Math.acos(Math.max(-1,Math.min(1,compression)))*(part.name.includes('soft')?1:-1);
          matrix=multiply(global,hinge(part.pivot,rotateY(angle)));
        } else if(part.name==='moth-body') {
          matrix=multiply(global,bodyRotation);
        } else if(part.name==='moth-antennae') {
          matrix=multiply(global,multiply(bodyRotation,hinge(part.pivot,rotateZ(-pose.antennaAngle*Math.PI/180))));
        }
        gl.uniform1f(paper,part.name.includes('soft')?1:0);
        gl.uniformMatrix4fv(model,false,matrix);gl.bindBuffer(gl.ARRAY_BUFFER,part.buffer);
        attributes.forEach((location,i)=>{gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,3,gl.FLOAT,false,36,i*12);});
        gl.drawArrays(gl.TRIANGLES,0,part.count);
      }
      canvas.hidden=false;
      return true;
    };
    return {canvas,render,dispose:cleanup,contactOffset:192/795,triangles:parts.reduce((sum,p)=>sum+p.count/3,0)};
  } catch(error) { cleanup();throw error; }
}
