/* Optional path tracer, MIT. See datacenter-pathtracer.LICENSE.txt. */
var ds=Object.defineProperty;var ps=(e)=>e;function gs(e,t){this[e]=ps.bind(null,t)}var vs=(e,t)=>{for(var r in t)ds(e,r,{get:t[r],enumerable:!0,configurable:!0,set:gs.bind(t,r)})};import{PerspectiveCamera as Sl,Scene as _l,Vector2 as as,Clock as Al,NormalBlending as Il,NoBlending as ss,AdditiveBlending as Rl}from"./datacenter-engine.mjs";import{BufferGeometry as Ua}from"./datacenter-engine.mjs";import{Box3 as _s}from"./datacenter-engine.mjs";var pr=0,gr=1,Ze=2;var bt=2,Tt=1.25,vr=1,W=32,U=8,wt=65535,Di=-65536,De=Math.pow(2,-24),Ce=Symbol("SKIP_GENERATION"),St={strategy:0,maxDepth:40,targetLeafSize:10,useSharedArrayBuffer:!1,setBoundingBox:!0,onProgress:null,indirect:!1,verbose:!0,range:null,[Ce]:!1};function z(e,t,r){return r.min.x=t[e],r.min.y=t[e+1],r.min.z=t[e+2],r.max.x=t[e+3],r.max.y=t[e+4],r.max.z=t[e+5],r}function Je(e){let t=-1,r=-1/0;for(let o=0;o<3;o++){let n=e[o+3]-e[o];if(n>r)r=n,t=o}return t}function xr(e,t){t.set(e)}function yr(e,t,r){let o,n;for(let i=0;i<3;i++){let s=i+3;o=e[i],n=t[i],r[i]=o<n?o:n,o=e[s],n=t[s],r[s]=o>n?o:n}}function et(e,t,r){for(let o=0;o<3;o++){let n=t[e+2*o],i=t[e+2*o+1],s=n-i,l=n+i;if(s<r[o])r[o]=s;if(l>r[o+3])r[o+3]=l}}function Ee(e){let t=e[3]-e[0],r=e[4]-e[1],o=e[5]-e[2];return 2*(t*r+r*o+o*t)}function C(e,t){return t[e+15]===wt}function B(e,t){return t[e+6]}function O(e,t){return t[e+14]}function N(e){return e+U}function L(e,t){let r=t[e+6];return e+r*U}function ne(e,t){return t[e+7]}function k(e){return e}function _t(e,t,r,o,n){let i=1/0,s=1/0,l=1/0,c=-1/0,m=-1/0,u=-1/0,a=1/0,f=1/0,h=1/0,g=-1/0,d=-1/0,b=-1/0,T=e.offset||0;for(let p=(t-T)*6,x=(t+r-T)*6;p<x;p+=6){let v=e[p+0],y=e[p+1],w=v-y,S=v+y;if(w<i)i=w;if(S>c)c=S;if(v<a)a=v;if(v>g)g=v;let I=e[p+2],R=e[p+3],A=I-R,P=I+R;if(A<s)s=A;if(P>m)m=P;if(I<f)f=I;if(I>d)d=I;let _=e[p+4],F=e[p+5],M=_-F,D=_+F;if(M<l)l=M;if(D>u)u=D;if(_<h)h=_;if(_>b)b=_}o[0]=i,o[1]=s,o[2]=l,o[3]=c,o[4]=m,o[5]=u,n[0]=a,n[1]=f,n[2]=h,n[3]=g,n[4]=d,n[5]=b}var ie=32,xs=(e,t)=>e.candidate-t.candidate,se=Array(ie).fill().map(()=>({count:0,bounds:new Float32Array(6),rightCacheBounds:new Float32Array(6),leftCacheBounds:new Float32Array(6),candidate:0})),At=new Float32Array(6);function Ci(e,t,r,o,n,i){let s=-1,l=0;if(i===pr){if(s=Je(t),s!==-1)l=(t[s]+t[s+3])/2}else if(i===gr){if(s=Je(e),s!==-1)l=ys(r,o,n,s)}else if(i===Ze){let c=Ee(e),m=Tt*n,u=r.offset||0,a=(o-u)*6,f=(o+n-u)*6;for(let h=0;h<3;h++){let g=t[h],T=(t[h+3]-g)/ie;if(n<ie/4){let p=[...se];p.length=n;let x=0;for(let y=a;y<f;y+=6,x++){let w=p[x];w.candidate=r[y+2*h],w.count=0;let{bounds:S,leftCacheBounds:I,rightCacheBounds:R}=w;for(let A=0;A<3;A++)R[A]=1/0,R[A+3]=-1/0,I[A]=1/0,I[A+3]=-1/0,S[A]=1/0,S[A+3]=-1/0;et(y,r,S)}p.sort(xs);let v=n;for(let y=0;y<v;y++){let w=p[y];while(y+1<v&&p[y+1].candidate===w.candidate)p.splice(y+1,1),v--}for(let y=a;y<f;y+=6){let w=r[y+2*h];for(let S=0;S<v;S++){let I=p[S];if(w>=I.candidate)et(y,r,I.rightCacheBounds);else et(y,r,I.leftCacheBounds),I.count++}}for(let y=0;y<v;y++){let w=p[y],S=w.count,I=n-w.count,R=w.leftCacheBounds,A=w.rightCacheBounds,P=0;if(S!==0)P=Ee(R)/c;let _=0;if(I!==0)_=Ee(A)/c;let F=vr+Tt*(P*S+_*I);if(F<m)s=h,m=F,l=w.candidate}}else{for(let v=0;v<ie;v++){let y=se[v];y.count=0,y.candidate=g+T+v*T;let w=y.bounds;for(let S=0;S<3;S++)w[S]=1/0,w[S+3]=-1/0}for(let v=a;v<f;v+=6){let S=~~((r[v+2*h]-g)/T);if(S>=ie)S=ie-1;let I=se[S];I.count++,et(v,r,I.bounds)}let p=se[ie-1];xr(p.bounds,p.rightCacheBounds);for(let v=ie-2;v>=0;v--){let y=se[v],w=se[v+1];yr(y.bounds,w.rightCacheBounds,y.rightCacheBounds)}let x=0;for(let v=0;v<ie-1;v++){let y=se[v],w=y.count,S=y.bounds,R=se[v+1].rightCacheBounds;if(w!==0)if(x===0)xr(S,At);else yr(S,At,At);x+=w;let A=0,P=0;if(x!==0)A=Ee(At)/c;let _=n-x;if(_!==0)P=Ee(R)/c;let F=vr+Tt*(A*x+P*_);if(F<m)s=h,m=F,l=y.candidate}}}}else console.warn(`BVH: Invalid build strategy value ${i} used.`);return{axis:s,pos:l}}function ys(e,t,r,o){let n=0,i=e.offset;for(let s=t,l=t+r;s<l;s++)n+=e[(s-i)*6+o*2];return n/r}class tt{constructor(){this.boundingData=new Float32Array(6)}}function Ei(e,t,r,o,n,i){let s=o,l=o+n-1,c=i.pos,m=i.axis*2,u=r.offset||0;while(!0){while(s<=l&&r[(s-u)*6+m]<c)s++;while(s<=l&&r[(l-u)*6+m]>=c)l--;if(s<l){for(let a=0;a<t;a++){let f=e[s*t+a];e[s*t+a]=e[l*t+a],e[l*t+a]=f}for(let a=0;a<6;a++){let f=s-u,h=l-u,g=r[f*6+a];r[f*6+a]=r[h*6+a],r[h*6+a]=g}s++,l--}else return s}}var Bi,It,br,Ni,bs=Math.pow(2,32);function Rt(e){if("count"in e)return 1;else return 1+Rt(e.left)+Rt(e.right)}function Li(e,t,r){return Bi=new Float32Array(r),It=new Uint32Array(r),br=new Uint16Array(r),Ni=new Uint8Array(r),Tr(e,t)}function Tr(e,t){let r=e/4,o=e/2,n="count"in t,i=t.boundingData;for(let s=0;s<6;s++)Bi[r+s]=i[s];if(n)if(t.buffer)return Ni.set(new Uint8Array(t.buffer),e),e+t.buffer.byteLength;else return It[r+6]=t.offset,br[o+14]=t.count,br[o+15]=wt,e+W;else{let{left:s,right:l,splitAxis:c}=t,m=e+W,u=Tr(m,s),a=e/W,h=u/W-a;if(h>bs)throw Error("MeshBVH: Cannot store relative child node offset greater than 32 bits.");return It[r+6]=h,It[r+7]=c,Tr(u,l)}}function Ts(e,t,r,o,n,i){let{maxDepth:s,verbose:l,targetLeafSize:c,_strictLeafSize:m=1/0,strategy:u,onProgress:a}=n,f=e.primitiveBuffer,h=e.primitiveBufferStride,g=new Float32Array(6),d=!1,b=new tt;return _t(t,r,o,b.boundingData,g),p(b,r,o,g),b;function T(x){if(a)a((x-i.offset)/i.count)}function p(x,v,y,w=null,S=0){if(!d&&S>=s){if(d=!0,l)console.warn(`BVH: Max depth of ${s} reached when generating BVH. Consider increasing maxDepth.`)}let I=y>m;if(y<=c&&!I||S>=s)return T(v+y),x.offset=v,x.count=y,x;let R=Ci(x.boundingData,w,t,v,y,u),A=R.axis===-1?-1:Ei(f,h,t,v,y,R);if(R.axis===-1||A===v||A===v+y){if(!I)return T(v+y),x.offset=v,x.count=y,x;R.axis=Math.max(0,Je(x.boundingData)),A=v+Math.max(1,Math.floor(y/2))}x.splitAxis=R.axis;let P=new tt,_=v,F=A-v;x.left=P,_t(t,_,F,P.boundingData,g),p(P,_,F,g,S+1);let M=new tt,D=A,V=y-F;return x.right=M,_t(t,D,V,M.boundingData,g),p(M,D,V,g,S+1),x}}function Oi(e,t){let r=t.useSharedArrayBuffer?SharedArrayBuffer:ArrayBuffer,o=e.getRootRanges(t.range),n=o[0],i=o[o.length-1],s={offset:n.offset,count:i.offset+i.count-n.offset},l=new Float32Array(6*s.count);l.offset=s.offset,e.computePrimitiveBounds(s.offset,s.count,l),e._roots=o.map((c)=>{let m=Ts(e,l,c.offset,c.count,t,s),u=Rt(m),a=new r(W*u);return Li(0,m,a),a})}import{Box3 as ws}from"./datacenter-engine.mjs";class de{constructor(e){this._getNewPrimitive=e,this._primitives=[]}getPrimitive(){let e=this._primitives;if(e.length===0)return this._getNewPrimitive();else return e.pop()}releasePrimitive(e){this._primitives.push(e)}}class zi{constructor(){this.float32Array=null,this.uint16Array=null,this.uint32Array=null;let e=[],t=null;this.setBuffer=(r)=>{if(t)e.push(t);t=r,this.float32Array=new Float32Array(r),this.uint16Array=new Uint16Array(r),this.uint32Array=new Uint32Array(r)},this.clearBuffer=()=>{if(t=null,this.float32Array=null,this.uint16Array=null,this.uint32Array=null,e.length!==0)this.setBuffer(e.pop())}}}var E=new zi;var ae,Ne,Be=[],Pt=new de(()=>new ws);function ki(e,t,r,o,n,i){ae=Pt.getPrimitive(),Ne=Pt.getPrimitive(),Be.push(ae,Ne),E.setBuffer(e._roots[t]);let s=wr(0,e.geometry,r,o,n,i);E.clearBuffer(),Pt.releasePrimitive(ae),Pt.releasePrimitive(Ne),Be.pop(),Be.pop();let l=Be.length;if(l>0)Ne=Be[l-1],ae=Be[l-2];return s}function wr(e,t,r,o,n=null,i=0,s=0){let{float32Array:l,uint16Array:c,uint32Array:m}=E,u=e*2;if(C(u,c)){let f=B(e,m),h=O(u,c);return z(k(e),l,ae),o(f,h,!1,s,i+e/U,ae)}else{let A=function(_){let{uint16Array:F,uint32Array:M}=E,D=_*2;while(!C(D,F))_=N(_),D=_*2;return B(_,M)},P=function(_){let{uint16Array:F,uint32Array:M}=E,D=_*2;while(!C(D,F))_=L(_,M),D=_*2;return B(_,M)+O(D,F)},f=N(e),h=L(e,m),g=f,d=h,b,T,p,x;if(n){if(p=ae,x=Ne,z(k(g),l,p),z(k(d),l,x),b=n(p),T=n(x),T<b){g=h,d=f;let _=b;b=T,T=_,p=x}}if(!p)p=ae,z(k(g),l,p);let v=C(g*2,c),y=r(p,v,b,s+1,i+g/U),w;if(y===bt){let _=A(g),M=P(g)-_;w=o(_,M,!0,s+1,i+g/U,p)}else w=y&&wr(g,t,r,o,n,i,s+1);if(w)return!0;x=Ne,z(k(d),l,x);let S=C(d*2,c),I=r(x,S,T,s+1,i+d/U),R;if(I===bt){let _=A(d),M=P(d)-_;R=o(_,M,!0,s+1,i+d/U,x)}else R=I&&wr(d,t,r,o,n,i,s+1);if(R)return!0;return!1}}import{Box3 as it,Matrix4 as Ss}from"./datacenter-engine.mjs";var rt=new E.constructor,Ft=new E.constructor,ce=new de(()=>new it),Le=new it,Oe=new it,Sr=new it,_r=new it,Ar=!1;function Hi(e,t,r,o){if(Ar)throw Error("MeshBVH: Recursive calls to bvhcast not supported.");Ar=!0;let n=e._roots,i=t._roots,s,l=0,c=0,m=new Ss().copy(r).invert();for(let u=0,a=n.length;u<a;u++){rt.setBuffer(n[u]),c=0;let f=ce.getPrimitive();z(k(0),rt.float32Array,f),f.applyMatrix4(m);for(let h=0,g=i.length;h<g;h++)if(Ft.setBuffer(i[h]),s=J(0,0,r,m,o,l,c,0,0,f),Ft.clearBuffer(),c+=i[h].byteLength/W,s)break;if(ce.releasePrimitive(f),rt.clearBuffer(),l+=n[u].byteLength/W,s)break}return Ar=!1,s}function J(e,t,r,o,n,i=0,s=0,l=0,c=0,m=null,u=!1){let a,f;if(u)a=Ft,f=rt;else a=rt,f=Ft;let{float32Array:h,uint32Array:g,uint16Array:d}=a,b=f.float32Array,T=f.uint32Array,p=f.uint16Array,x=e*2,v=t*2,y=C(x,d),w=C(v,p),S=!1;if(w&&y)if(u)S=n(B(t,T),O(t*2,p),B(e,g),O(e*2,d),c,s+t/U,l,i+e/U);else S=n(B(e,g),O(e*2,d),B(t,T),O(t*2,p),l,i+e/U,c,s+t/U);else if(w){let I=ce.getPrimitive();z(k(t),b,I),I.applyMatrix4(r);let R=N(e),A=L(e,g);z(k(R),h,Le),z(k(A),h,Oe);let P=I.intersectsBox(Le),_=I.intersectsBox(Oe);S=P&&J(t,R,o,r,n,s,i,c,l+1,I,!u)||_&&J(t,A,o,r,n,s,i,c,l+1,I,!u),ce.releasePrimitive(I)}else{let I=N(t),R=L(t,T);z(k(I),b,Sr),z(k(R),b,_r);let A=m.intersectsBox(Sr),P=m.intersectsBox(_r);if(A&&P)S=J(e,I,r,o,n,i,s,l,c+1,m,u)||J(e,R,r,o,n,i,s,l,c+1,m,u);else if(A)if(y)S=J(e,I,r,o,n,i,s,l,c+1,m,u);else{let _=ce.getPrimitive();_.copy(Sr).applyMatrix4(r);let F=N(e),M=L(e,g);z(k(F),h,Le),z(k(M),h,Oe);let D=_.intersectsBox(Le),V=_.intersectsBox(Oe);S=D&&J(I,F,o,r,n,s,i,c,l+1,_,!u)||V&&J(I,M,o,r,n,s,i,c,l+1,_,!u),ce.releasePrimitive(_)}else if(P)if(y)S=J(e,R,r,o,n,i,s,l,c+1,m,u);else{let _=ce.getPrimitive();_.copy(_r).applyMatrix4(r);let F=N(e),M=L(e,g);z(k(F),h,Le),z(k(M),h,Oe);let D=_.intersectsBox(Le),V=_.intersectsBox(Oe);S=D&&J(R,F,o,r,n,s,i,c,l+1,_,!u)||V&&J(R,M,o,r,n,s,i,c,l+1,_,!u),ce.releasePrimitive(_)}}return S}var Mt=new class{constructor(){let e=null,t=null,r=null,o=!1;this.root=null,this.buffer=null,this.uint32Array=null,this.uint16Array=null,this.setBVH=(i,s)=>{if(o)throw Error("BVHTraversalHelper: cannot call setBVH during an active traversal.");this.root=s,this.buffer=e=i._roots[s],this.uint16Array=r=new Uint16Array(e),this.uint32Array=t=new Uint32Array(e)},this.reset=()=>{this.root=null,this.buffer=e=null,this.uint16Array=r=null,this.uint32Array=t=null},this.getRangeStart=(i)=>{let s=i*2;while(!C(s,r))i=N(i),s=i*2;return B(i,t)},this.getRangeEnd=(i)=>{let s=i*2;while(!C(s,r))i=L(i,t),s=i*2;return B(i,t)+O(s,r)};let n=(i,s,l)=>{let c=s*2,m=C(c,r);if(!i(l,m,s)&&!m){let a=N(s),f=L(s,t);n(i,a,l+1),n(i,f,l+1)}};this.traverseBuffer=(i)=>{if(o)throw Error("BVHTraversalHelper: cannot start a traversal during an active traversal.");o=!0;try{n(i,0,0)}finally{o=!1}},this.traverse=(i)=>{this.traverseBuffer((s,l,c)=>{if(l){let m=c*2,u=t[c+6],a=r[m+14];return i(s,l,new Float32Array(e,c*4,6),u,a)}else{let m=ne(c,t);return i(s,l,new Float32Array(e,c*4,6),m)}})}}};var Ui=new _s,ze=new Float32Array(6);class Ir{constructor(){this._roots=null,this.primitiveBuffer=null,this.primitiveBufferStride=null}init(e){if(e={...St,...e},"maxLeafSize"in e)console.warn('BVH: "maxLeafSize" option has been deprecated. Use "targetLeafSize", instead.'),e={...e,targetLeafSize:e.maxLeafSize};Oi(this,e)}getRootRanges(){throw Error("BVH: getRootRanges() not implemented")}writePrimitiveBounds(){throw Error("BVH: writePrimitiveBounds() not implemented")}writePrimitiveRangeBounds(e,t,r,o){let n=1/0,i=1/0,s=1/0,l=-1/0,c=-1/0,m=-1/0;for(let u=e,a=e+t;u<a;u++){this.writePrimitiveBounds(u,ze,0);let[f,h,g,d,b,T]=ze;if(f<n)n=f;if(d>l)l=d;if(h<i)i=h;if(b>c)c=b;if(g<s)s=g;if(T>m)m=T}return r[o+0]=n,r[o+1]=i,r[o+2]=s,r[o+3]=l,r[o+4]=c,r[o+5]=m,r}computePrimitiveBounds(e,t,r){let o=r.offset||0;for(let n=e,i=e+t;n<i;n++){this.writePrimitiveBounds(n,ze,0);let[s,l,c,m,u,a]=ze,f=(s+m)/2,h=(l+u)/2,g=(c+a)/2,d=(m-s)/2,b=(u-l)/2,T=(a-c)/2,p=(n-o)*6;r[p+0]=f,r[p+1]=d+(Math.abs(f)+d)*De,r[p+2]=h,r[p+3]=b+(Math.abs(h)+b)*De,r[p+4]=g,r[p+5]=T+(Math.abs(g)+T)*De}return r}shiftPrimitiveOffsets(e){let t=this._indirectBuffer;if(t)for(let r=0,o=t.length;r<o;r++)t[r]+=e;else{let r=this._roots;for(let o=0;o<r.length;o++){let n=r[o],i=new Uint32Array(n),s=new Uint16Array(n),l=n.byteLength/W;for(let c=0;c<l;c++){let m=U*c,u=2*m;if(C(u,s))i[m+6]+=e}}}}traverse(e,t=0){Mt.setBVH(this,t),Mt.traverse(e),Mt.reset()}refit(){let e=this._roots;for(let t=0,r=e.length;t<r;t++){let o=e[t],n=new Uint32Array(o),i=new Uint16Array(o),s=new Float32Array(o),l=o.byteLength/W;for(let c=l-1;c>=0;c--){let m=c*U,u=m*2;if(C(u,i)){let f=B(m,n),h=O(u,i);this.writePrimitiveRangeBounds(f,h,ze,0),s.set(ze,m)}else{let f=N(m),h=L(m,n);for(let g=0;g<3;g++){let d=s[f+g],b=s[f+g+3],T=s[h+g],p=s[h+g+3];s[m+g]=d<T?d:T,s[m+g+3]=b>p?b:p}}}}}getBoundingBox(e){return e.makeEmpty(),this._roots.forEach((r)=>{z(0,new Float32Array(r),Ui),e.union(Ui)}),e}shapecast(e){let{boundsTraverseOrder:t,intersectsBounds:r,intersectsRange:o,intersectsPrimitive:n,scratchPrimitive:i,iterate:s}=e;if(o&&n){let u=o;o=(a,f,h,g,d)=>{if(!u(a,f,h,g,d))return s(a,f,this,n,h,g,i);return!0}}else if(!o)if(n)o=(u,a,f,h)=>s(u,a,this,n,f,h,i);else o=(u,a,f)=>f;let l=!1,c=0,m=this._roots;for(let u=0,a=m.length;u<a;u++){let f=m[u];if(l=ki(this,u,r,o,t,c),l)break;c+=f.byteLength/W}return l}bvhcast(e,t,r){let{intersectsRanges:o}=r;return Hi(this,e,t,o)}}import{Box3 as Ps}from"./datacenter-engine.mjs";function Vi(){return typeof SharedArrayBuffer<"u"}import{BufferAttribute as As}from"./datacenter-engine.mjs";function ot(e){return e.index?e.index.count:e.attributes.position.count}function le(e){return ot(e)/3}function Rr(e,t=ArrayBuffer){if(e>65535)return new Uint32Array(new t(4*e));else return new Uint16Array(new t(2*e))}function Wi(e,t){if(!e.index){let r=e.attributes.position.count,o=t.useSharedArrayBuffer?SharedArrayBuffer:ArrayBuffer,n=Rr(r,o);e.setIndex(new As(n,1));for(let i=0;i<r;i++)n[i]=i}}function Is(e,t,r){let o=ot(e)/r,n=t?t:e.drawRange,i=n.start/r,s=(n.start+n.count)/r,l=Math.max(0,i),c=Math.min(o,s)-l;return{offset:Math.floor(l),count:Math.floor(c)}}function Rs(e,t){return e.groups.map((r)=>({offset:r.start/t,count:r.count/t}))}function Pr(e,t,r){let o=Is(e,t,r),n=Rs(e,r);if(!n.length)return[o];let i=[],s=o.offset,l=o.offset+o.count,c=ot(e)/r,m=[];for(let f of n){let{offset:h,count:g}=f,d=h,b=isFinite(g)?g:c-h,T=h+b;if(d<l&&T>s)m.push({pos:Math.max(s,d),isStart:!0}),m.push({pos:Math.min(l,T),isStart:!1})}m.sort((f,h)=>{if(f.pos!==h.pos)return f.pos-h.pos;else return f.type==="end"?-1:1});let u=0,a=null;for(let f of m){let h=f.pos;if(u!==0&&h!==a)i.push({offset:a,count:h-a});u+=f.isStart?1:-1,a=h}return i}function Fs(e,t){let r=e[e.length-1],o=r.offset+r.count>65536,n=e.reduce((m,u)=>m+u.count,0),i=o?4:2,s=t?new SharedArrayBuffer(n*i):new ArrayBuffer(n*i),l=o?new Uint32Array(s):new Uint16Array(s),c=0;for(let m=0;m<e.length;m++){let{offset:u,count:a}=e[m];for(let f=0;f<a;f++)l[c+f]=u+f;c+=a}return l}class Fr extends Ir{get indirect(){return!!this._indirectBuffer}get primitiveStride(){return null}get primitiveBufferStride(){return this.indirect?1:this.primitiveStride}set primitiveBufferStride(e){}get primitiveBuffer(){return this.indirect?this._indirectBuffer:this.geometry.index.array}set primitiveBuffer(e){}constructor(e,t={}){if(!e.isBufferGeometry)throw Error("BVH: Only BufferGeometries are supported.");else if(e.index&&e.index.isInterleavedBufferAttribute)throw Error("BVH: InterleavedBufferAttribute is not supported for the index attribute.");if(t.useSharedArrayBuffer&&!Vi())throw Error("BVH: SharedArrayBuffer is not available.");super();if(this.geometry=e,this.resolvePrimitiveIndex=t.indirect?(r)=>this._indirectBuffer[r]:(r)=>r,this.primitiveBuffer=null,this.primitiveBufferStride=null,this._indirectBuffer=null,t={...St,...t},!t[Ce])this.init(t)}init(e){let{geometry:t,primitiveStride:r}=this;if(e.indirect){let o=Pr(t,e.range,r),n=Fs(o,e.useSharedArrayBuffer);this._indirectBuffer=n}else Wi(t,e);if(super.init(e),!t.boundingBox&&e.setBoundingBox)t.boundingBox=this.getBoundingBox(new Ps)}getRootRanges(e){if(this.indirect)return[{offset:0,count:this._indirectBuffer.length}];else return Pr(this.geometry,e,this.primitiveStride)}raycastObject3D(){throw Error("BVH: raycastObject3D() not implemented")}}import{BufferAttribute as oa,FrontSide as So,Ray as na,Vector3 as Ro,Matrix4 as sa}from"./datacenter-engine.mjs";import{Vector3 as ue,Matrix4 as $i,Line3 as Xi}from"./datacenter-engine.mjs";import{Vector3 as Ms}from"./datacenter-engine.mjs";class j{constructor(){this.min=1/0,this.max=-1/0}setFromPointsField(e,t){let r=1/0,o=-1/0;for(let n=0,i=e.length;n<i;n++){let l=e[n][t];r=l<r?l:r,o=l>o?l:o}this.min=r,this.max=o}setFromPoints(e,t){let r=1/0,o=-1/0;for(let n=0,i=t.length;n<i;n++){let s=t[n],l=e.dot(s);r=l<r?l:r,o=l>o?l:o}this.min=r,this.max=o}isSeparated(e){return this.min>e.max||e.min>this.max}}j.prototype.setFromBox=function(){let e=new Ms;return function(r,o){let{min:n,max:i}=o,s=1/0,l=-1/0;for(let c=0;c<=1;c++)for(let m=0;m<=1;m++)for(let u=0;u<=1;u++){e.x=n.x*c+i.x*(1-c),e.y=n.y*m+i.y*(1-m),e.z=n.z*u+i.z*(1-u);let a=r.dot(e);s=Math.min(a,s),l=Math.max(a,l)}this.min=s,this.max=l}}();var Lu=function(){let e=new j;return function(r,o){let{points:n,satAxes:i,satBounds:s}=r,l=o.points,c=o.satAxes,m=o.satBounds;for(let u=0;u<3;u++){let a=s[u],f=i[u];if(e.setFromPoints(f,l),a.isSeparated(e))return!1}for(let u=0;u<3;u++){let a=m[u],f=c[u];if(e.setFromPoints(f,n),a.isSeparated(e))return!1}}}();import{Triangle as Ns,Vector3 as ee,Vector2 as qi,Line3 as ke,Plane as Ls}from"./datacenter-engine.mjs";import{Vector3 as pe,Vector2 as Ds,Plane as Cs,Line3 as Es}from"./datacenter-engine.mjs";var Bs=function(){let e=new pe,t=new pe,r=new pe;return function(n,i,s){let l=n.start,c=e,m=i.start,u=t;r.subVectors(l,m),e.subVectors(n.end,n.start),t.subVectors(i.end,i.start);let a=r.dot(u),f=u.dot(c),h=u.dot(u),g=r.dot(c),b=c.dot(c)*h-f*f,T,p;if(b!==0)T=(a*f-g*h)/b;else T=0;p=(a+T*f)/h,s.x=T,s.y=p}}(),nt=function(){let e=new Ds,t=new pe,r=new pe;return function(n,i,s,l){Bs(n,i,e);let{x:c,y:m}=e;if(c>=0&&c<=1&&m>=0&&m<=1){n.at(c,s),i.at(m,l);return}else if(c>=0&&c<=1){if(m<0)i.at(0,l);else i.at(1,l);n.closestPointToPoint(l,!0,s);return}else if(m>=0&&m<=1){if(c<0)n.at(0,s);else n.at(1,s);i.closestPointToPoint(s,!0,l);return}else{let u;if(c<0)u=n.start;else u=n.end;let a;if(m<0)a=i.start;else a=i.end;let f=t,h=r;if(n.closestPointToPoint(a,!0,t),i.closestPointToPoint(u,!0,r),f.distanceToSquared(a)<=h.distanceToSquared(u)){s.copy(f),l.copy(a);return}else{s.copy(u),l.copy(h);return}}}}(),Gi=function(){let e=new pe,t=new pe,r=new Cs,o=new Es;return function(i,s){let{radius:l,center:c}=i,{a:m,b:u,c:a}=s;if(o.start=m,o.end=u,o.closestPointToPoint(c,!0,e).distanceTo(c)<=l)return!0;if(o.start=m,o.end=a,o.closestPointToPoint(c,!0,e).distanceTo(c)<=l)return!0;if(o.start=u,o.end=a,o.closestPointToPoint(c,!0,e).distanceTo(c)<=l)return!0;let d=s.getPlane(r);if(Math.abs(d.distanceToPoint(c))<=l){let T=d.projectPoint(c,t);if(s.containsPoint(T))return!0}return!1}}();var Os=["x","y","z"],oe=0.000000000000001,Yi=oe*oe;function K(e){return Math.abs(e)<oe}class q extends Ns{constructor(...e){super(...e);this.isExtendedTriangle=!0,this.satAxes=[,,,,].fill().map(()=>new ee),this.satBounds=[,,,,].fill().map(()=>new j),this.points=[this.a,this.b,this.c],this.plane=new Ls,this.isDegenerateIntoSegment=!1,this.isDegenerateIntoPoint=!1,this.degenerateSegment=new ke,this.needsUpdate=!0}intersectsSphere(e){return Gi(e,this)}update(){let e=this.a,t=this.b,r=this.c,o=this.points,n=this.satAxes,i=this.satBounds,s=n[0],l=i[0];this.getNormal(s),l.setFromPoints(s,o);let c=n[1],m=i[1];c.subVectors(e,t),m.setFromPoints(c,o);let u=n[2],a=i[2];u.subVectors(t,r),a.setFromPoints(u,o);let f=n[3],h=i[3];f.subVectors(r,e),h.setFromPoints(f,o);let g=c.length(),d=u.length(),b=f.length();if(this.isDegenerateIntoPoint=!1,this.isDegenerateIntoSegment=!1,g<oe)if(d<oe||b<oe)this.isDegenerateIntoPoint=!0;else this.isDegenerateIntoSegment=!0,this.degenerateSegment.start.copy(e),this.degenerateSegment.end.copy(r);else if(d<oe)if(b<oe)this.isDegenerateIntoPoint=!0;else this.isDegenerateIntoSegment=!0,this.degenerateSegment.start.copy(t),this.degenerateSegment.end.copy(e);else if(b<oe)this.isDegenerateIntoSegment=!0,this.degenerateSegment.start.copy(r),this.degenerateSegment.end.copy(t);this.plane.setFromNormalAndCoplanarPoint(s,e),this.needsUpdate=!1}}q.prototype.closestPointToSegment=function(){let e=new ee,t=new ee,r=new ke;return function(n,i=null,s=null){let{start:l,end:c}=n,m=this.points,u,a=1/0;for(let f=0;f<3;f++){let h=(f+1)%3;if(r.start.copy(m[f]),r.end.copy(m[h]),nt(r,n,e,t),u=e.distanceToSquared(t),u<a){if(a=u,i)i.copy(e);if(s)s.copy(t)}}if(this.closestPointToPoint(l,e),u=l.distanceToSquared(e),u<a){if(a=u,i)i.copy(e);if(s)s.copy(l)}if(this.closestPointToPoint(c,e),u=c.distanceToSquared(e),u<a){if(a=u,i)i.copy(e);if(s)s.copy(c)}return Math.sqrt(a)}}();q.prototype.intersectsTriangle=function(){let e=new q,t=new j,r=new j,o=new ee,n=new ee,i=new ee,s=new ee,l=new ke,c=new ke,m=new ee,u=new qi,a=new qi;function f(x,v,y,w){let S=o;if(!x.isDegenerateIntoPoint&&!x.isDegenerateIntoSegment)S.copy(x.plane.normal);else S.copy(v.plane.normal);let{satBounds:I,satAxes:R}=x;for(let _=1;_<4;_++){let F=I[_],M=R[_];if(t.setFromPoints(M,v.points),F.isSeparated(t))return!1;if(s.copy(S).cross(M),t.setFromPoints(s,x.points),r.setFromPoints(s,v.points),t.isSeparated(r))return!1}let{satBounds:A,satAxes:P}=v;for(let _=1;_<4;_++){let F=A[_],M=P[_];if(t.setFromPoints(M,x.points),F.isSeparated(t))return!1;if(s.crossVectors(S,M),t.setFromPoints(s,x.points),r.setFromPoints(s,v.points),t.isSeparated(r))return!1}if(y){if(!w)console.warn("ExtendedTriangle.intersectsTriangle: Triangles are coplanar which does not support an output edge. Setting edge to 0, 0, 0.");y.start.set(0,0,0),y.end.set(0,0,0)}return!0}function h(x,v,y,w,S,I,R,A,P,_,F){let M=R/(R-A);_.x=w+(S-w)*M,F.start.subVectors(v,x).multiplyScalar(M).add(x),M=R/(R-P),_.y=w+(I-w)*M,F.end.subVectors(y,x).multiplyScalar(M).add(x)}function g(x,v,y,w,S,I,R,A,P,_,F){if(S>0)h(x.c,x.a,x.b,w,v,y,P,R,A,_,F);else if(I>0)h(x.b,x.a,x.c,y,v,w,A,R,P,_,F);else if(A*P>0||R!=0)h(x.a,x.b,x.c,v,y,w,R,A,P,_,F);else if(A!=0)h(x.b,x.a,x.c,y,v,w,A,R,P,_,F);else if(P!=0)h(x.c,x.a,x.b,w,v,y,P,R,A,_,F);else return!0;return!1}function d(x,v,y,w){let S=v.degenerateSegment,I=x.plane.distanceToPoint(S.start),R=x.plane.distanceToPoint(S.end);if(K(I))if(K(R))return f(x,v,y,w);else{if(y)y.start.copy(S.start),y.end.copy(S.start);return x.containsPoint(S.start)}else if(K(R)){if(y)y.start.copy(S.end),y.end.copy(S.end);return x.containsPoint(S.end)}else if(x.plane.intersectLine(S,o)!=null){if(y)y.start.copy(o),y.end.copy(o);return x.containsPoint(o)}else return!1}function b(x,v,y){let w=v.a;if(K(x.plane.distanceToPoint(w))&&x.containsPoint(w)){if(y)y.start.copy(w),y.end.copy(w);return!0}else return!1}function T(x,v,y){let w=x.degenerateSegment,S=v.a;if(w.closestPointToPoint(S,!0,o),S.distanceToSquared(o)<Yi){if(y)y.start.copy(S),y.end.copy(S);return!0}else return!1}function p(x,v,y,w){if(x.isDegenerateIntoSegment)if(v.isDegenerateIntoSegment){let S=x.degenerateSegment,I=v.degenerateSegment,R=n,A=i;S.delta(R),I.delta(A);let P=o.subVectors(I.start,S.start),_=R.x*A.y-R.y*A.x;if(K(_))return!1;let F=(P.x*A.y-P.y*A.x)/_,M=-(R.x*P.y-R.y*P.x)/_;if(F<0||F>1||M<0||M>1)return!1;let D=S.start.z+R.z*F,V=I.start.z+A.z*M;if(K(D-V)){if(y)y.start.copy(S.start).addScaledVector(R,F),y.end.copy(S.start).addScaledVector(R,F);return!0}else return!1}else if(v.isDegenerateIntoPoint)return T(x,v,y);else return d(v,x,y,w);else if(x.isDegenerateIntoPoint)if(v.isDegenerateIntoPoint)if(v.a.distanceToSquared(x.a)<Yi){if(y)y.start.copy(x.a),y.end.copy(x.a);return!0}else return!1;else if(v.isDegenerateIntoSegment)return T(v,x,y);else return b(v,x,y);else if(v.isDegenerateIntoPoint)return b(x,v,y);else if(v.isDegenerateIntoSegment)return d(x,v,y,w)}return function(v,y=null,w=!1){if(this.needsUpdate)this.update();if(!v.isExtendedTriangle)e.copy(v),e.update(),v=e;else if(v.needsUpdate)v.update();let S=p(this,v,y,w);if(S!==void 0)return S;let I=this.plane,R=v.plane,A=R.distanceToPoint(this.a),P=R.distanceToPoint(this.b),_=R.distanceToPoint(this.c);if(K(A))A=0;if(K(P))P=0;if(K(_))_=0;let F=A*P,M=A*_;if(F>0&&M>0)return!1;let D=I.distanceToPoint(v.a),V=I.distanceToPoint(v.b),Re=I.distanceToPoint(v.c);if(K(D))D=0;if(K(V))V=0;if(K(Re))Re=0;let Pe=D*V,Qe=D*Re;if(Pe>0&&Qe>0)return!1;n.copy(I.normal),i.copy(R.normal);let Fe=n.cross(i),he=0,hr=Math.abs(Fe.x),Mi=Math.abs(Fe.y);if(Mi>hr)hr=Mi,he=1;if(Math.abs(Fe.z)>hr)he=2;let Me=Os[he],cs=this.a[Me],ls=this.b[Me],us=this.c[Me],fs=v.a[Me],ms=v.b[Me],hs=v.c[Me];if(g(this,cs,ls,us,F,M,A,P,_,u,l))return f(this,v,y,w);if(g(v,fs,ms,hs,Pe,Qe,D,V,Re,a,c))return f(this,v,y,w);if(u.y<u.x){let dr=u.y;u.y=u.x,u.x=dr,m.copy(l.start),l.start.copy(l.end),l.end.copy(m)}if(a.y<a.x){let dr=a.y;a.y=a.x,a.x=dr,m.copy(c.start),c.start.copy(c.end),c.end.copy(m)}if(u.y<a.x||a.y<u.x)return!1;if(y){if(a.x>u.x)y.start.copy(c.start);else y.start.copy(l.start);if(a.y<u.y)y.end.copy(c.end);else y.end.copy(l.end)}return!0}}();q.prototype.distanceToPoint=function(){let e=new ee;return function(r){return this.closestPointToPoint(r,e),r.distanceTo(e)}}();q.prototype.distanceToTriangle=function(){let e=new ee,t=new ee,r=["a","b","c"],o=new ke,n=new ke;return function(s,l=null,c=null){let m=l||c?o:null;if(this.intersectsTriangle(s,m,!0)){if(l||c){if(l)m.getCenter(l);if(c)m.getCenter(c)}return 0}let u=1/0;for(let a=0;a<3;a++){let f,h=r[a],g=s[h];if(this.closestPointToPoint(g,e),f=g.distanceToSquared(e),f<u){if(u=f,l)l.copy(e);if(c)c.copy(g)}let d=this[h];if(s.closestPointToPoint(d,e),f=d.distanceToSquared(e),f<u){if(u=f,l)l.copy(d);if(c)c.copy(e)}}for(let a=0;a<3;a++){let f=r[a],h=r[(a+1)%3];o.set(this[f],this[h]);for(let g=0;g<3;g++){let d=r[g],b=r[(g+1)%3];n.set(s[d],s[b]),nt(o,n,e,t);let T=e.distanceToSquared(t);if(T<u){if(u=T,l)l.copy(e);if(c)c.copy(t)}}}return Math.sqrt(u)}}();class G{constructor(e,t,r){if(this.isOrientedBox=!0,this.min=new ue,this.max=new ue,this.matrix=new $i,this.invMatrix=new $i,this.points=[,,,,,,,,].fill().map(()=>new ue),this.satAxes=[,,,].fill().map(()=>new ue),this.satBounds=[,,,].fill().map(()=>new j),this.alignedSatBounds=[,,,].fill().map(()=>new j),this.needsUpdate=!1,e)this.min.copy(e);if(t)this.max.copy(t);if(r)this.matrix.copy(r)}set(e,t,r){this.min.copy(e),this.max.copy(t),this.matrix.copy(r),this.needsUpdate=!0}copy(e){this.min.copy(e.min),this.max.copy(e.max),this.matrix.copy(e.matrix),this.needsUpdate=!0}}G.prototype.update=function(){return function(){let t=this.matrix,r=this.min,o=this.max,n=this.points;for(let m=0;m<=1;m++)for(let u=0;u<=1;u++)for(let a=0;a<=1;a++){let f=1*m|2*u|4*a,h=n[f];h.x=m?o.x:r.x,h.y=u?o.y:r.y,h.z=a?o.z:r.z,h.applyMatrix4(t)}let i=this.satBounds,s=this.satAxes,l=n[0];for(let m=0;m<3;m++){let u=s[m],a=i[m],f=1<<m,h=n[f];u.subVectors(l,h),a.setFromPoints(u,n)}let c=this.alignedSatBounds;c[0].setFromPointsField(n,"x"),c[1].setFromPointsField(n,"y"),c[2].setFromPointsField(n,"z"),this.invMatrix.copy(this.matrix).invert(),this.needsUpdate=!1}}();G.prototype.intersectsBox=function(){let e=new j;return function(r){if(this.needsUpdate)this.update();let{min:o,max:n}=r,i=this.satBounds,s=this.satAxes,l=this.alignedSatBounds;if(e.min=o.x,e.max=n.x,l[0].isSeparated(e))return!1;if(e.min=o.y,e.max=n.y,l[1].isSeparated(e))return!1;if(e.min=o.z,e.max=n.z,l[2].isSeparated(e))return!1;for(let c=0;c<3;c++){let m=s[c],u=i[c];if(e.setFromBox(m,r),u.isSeparated(e))return!1}return!0}}();G.prototype.intersectsTriangle=function(){let e=new q,t=[,,,],r=new j,o=new j,n=new ue;return function(s){if(this.needsUpdate)this.update();if(!s.isExtendedTriangle)e.copy(s),e.update(),s=e;else if(s.needsUpdate)s.update();let l=this.satBounds,c=this.satAxes;t[0]=s.a,t[1]=s.b,t[2]=s.c;for(let f=0;f<3;f++){let h=l[f],g=c[f];if(r.setFromPoints(g,t),h.isSeparated(r))return!1}let{satBounds:m,satAxes:u}=s,a=this.points;for(let f=0;f<3;f++){let h=m[f],g=u[f];if(r.setFromPoints(g,a),h.isSeparated(r))return!1}for(let f=0;f<3;f++){let h=c[f];for(let g=0;g<4;g++){let d=u[g];if(n.crossVectors(h,d),r.setFromPoints(n,t),o.setFromPoints(n,a),r.isSeparated(o))return!1}}return!0}}();G.prototype.closestPointToPoint=function(){return function(t,r){if(this.needsUpdate)this.update();return r.copy(t).applyMatrix4(this.invMatrix).clamp(this.min,this.max).applyMatrix4(this.matrix),r}}();G.prototype.distanceToPoint=function(){let e=new ue;return function(r){return this.closestPointToPoint(r,e),r.distanceTo(e)}}();G.prototype.distanceToBox=function(){let e=["x","y","z"],t=Array(12).fill().map(()=>new Xi),r=Array(12).fill().map(()=>new Xi),o=new ue,n=new ue;return function(s,l=0,c=null,m=null){if(this.needsUpdate)this.update();if(this.intersectsBox(s)){if(c||m){if(s.getCenter(n),this.closestPointToPoint(n,o),s.closestPointToPoint(o,n),c)c.copy(o);if(m)m.copy(n)}return 0}let u=l*l,a=s.min,f=s.max,h=this.points,g=1/0;for(let b=0;b<8;b++){let T=h[b];n.copy(T).clamp(a,f);let p=T.distanceToSquared(n);if(p<g){if(g=p,c)c.copy(T);if(m)m.copy(n);if(p<u)return Math.sqrt(p)}}let d=0;for(let b=0;b<3;b++)for(let T=0;T<=1;T++)for(let p=0;p<=1;p++){let x=(b+1)%3,v=(b+2)%3,y=T<<x|p<<v,w=1<<b|T<<x|p<<v,S=h[y],I=h[w];t[d].set(S,I);let A=e[b],P=e[x],_=e[v],F=r[d],M=F.start,D=F.end;M[A]=a[A],M[P]=T?a[P]:f[P],M[_]=p?a[_]:f[P],D[A]=f[A],D[P]=T?a[P]:f[P],D[_]=p?a[_]:f[P],d++}for(let b=0;b<=1;b++)for(let T=0;T<=1;T++)for(let p=0;p<=1;p++){n.x=b?f.x:a.x,n.y=T?f.y:a.y,n.z=p?f.z:a.z,this.closestPointToPoint(n,o);let x=n.distanceToSquared(o);if(x<g){if(g=x,c)c.copy(o);if(m)m.copy(n);if(x<u)return Math.sqrt(x)}}for(let b=0;b<12;b++){let T=t[b];for(let p=0;p<12;p++){let x=r[p];nt(T,x,o,n);let v=o.distanceToSquared(n);if(v<g){if(g=v,c)c.copy(o);if(m)m.copy(n);if(v<u)return Math.sqrt(v)}}}return Math.sqrt(g)}}();class ji extends de{constructor(){super(()=>new q)}}var Y=new ji;import{Vector3 as Ki}from"./datacenter-engine.mjs";var st=new Ki,Mr=new Ki;function Qi(e,t,r={},o=0,n=1/0){let i=o*o,s=n*n,l=1/0,c=null;if(e.shapecast({boundsTraverseOrder:(u)=>(st.copy(t).clamp(u.min,u.max),st.distanceToSquared(t)),intersectsBounds:(u,a,f)=>f<l&&f<s,intersectsTriangle:(u,a)=>{u.closestPointToPoint(t,st);let f=t.distanceToSquared(st);if(f<l)Mr.copy(st),l=f,c=a;if(f<i)return!0;else return!1}}),l===1/0)return null;let m=Math.sqrt(l);if(!r.point)r.point=Mr.clone();else r.point.copy(Mr);return r.distance=m,r.faceIndex=c,r}import{Vector3 as re,Vector2 as lt,Triangle as at,DoubleSide as zs,BackSide as ks,REVISION as io}from"./datacenter-engine.mjs";var Dt=parseInt(io)>=169,Hs=parseInt(io)<=161,ge=new re,ve=new re,xe=new re,Ct=new lt,Et=new lt,Bt=new lt,Zi=new re,Ji=new re,eo=new re,ct=new re;function Us(e,t,r,o,n,i,s,l){let c;if(i===ks)c=e.intersectTriangle(o,r,t,!0,n);else c=e.intersectTriangle(t,r,o,i!==zs,n);if(c===null)return null;let m=e.origin.distanceTo(n);if(m<s||m>l)return null;return{distance:m,point:n.clone()}}function to(e,t,r,o,n,i,s,l,c,m,u){ge.fromBufferAttribute(t,i),ve.fromBufferAttribute(t,s),xe.fromBufferAttribute(t,l);let a=Us(e,ge,ve,xe,ct,c,m,u);if(a){if(o){Ct.fromBufferAttribute(o,i),Et.fromBufferAttribute(o,s),Bt.fromBufferAttribute(o,l),a.uv=new lt;let h=at.getInterpolation(ct,ge,ve,xe,Ct,Et,Bt,a.uv);if(!Dt)a.uv=h}if(n){Ct.fromBufferAttribute(n,i),Et.fromBufferAttribute(n,s),Bt.fromBufferAttribute(n,l),a.uv1=new lt;let h=at.getInterpolation(ct,ge,ve,xe,Ct,Et,Bt,a.uv1);if(!Dt)a.uv1=h;if(Hs)a.uv2=a.uv1}if(r){Zi.fromBufferAttribute(r,i),Ji.fromBufferAttribute(r,s),eo.fromBufferAttribute(r,l),a.normal=new re;let h=at.getInterpolation(ct,ge,ve,xe,Zi,Ji,eo,a.normal);if(a.normal.dot(e.direction)>0)a.normal.multiplyScalar(-1);if(!Dt)a.normal=h}let f={a:i,b:s,c:l,normal:new re,materialIndex:0};if(at.getNormal(ge,ve,xe,f.normal),a.face=f,a.faceIndex=i,Dt){let h=new re;at.getBarycoord(ct,ge,ve,xe,h),a.barycoord=h}}return a}function ro(e){return e&&e.isMaterial?e.side:e}function He(e,t,r,o,n,i,s){let l=o*3,c=l+0,m=l+1,u=l+2,{index:a,groups:f}=e;if(e.index)c=a.getX(c),m=a.getX(m),u=a.getX(u);let{position:h,normal:g,uv:d,uv1:b}=e.attributes;if(Array.isArray(t)){let T=o*3;for(let p=0,x=f.length;p<x;p++){let{start:v,count:y,materialIndex:w}=f[p];if(T>=v&&T<v+y){let S=ro(t[w]),I=to(r,h,g,d,b,c,m,u,S,i,s);if(I)if(I.faceIndex=o,I.face.materialIndex=w,n)n.push(I);else return I}}}else{let T=ro(t),p=to(r,h,g,d,b,c,m,u,T,i,s);if(p)if(p.faceIndex=o,p.face.materialIndex=0,n)n.push(p);else return p}return null}import{Vector2 as of,Vector3 as nf,Triangle as sf}from"./datacenter-engine.mjs";function H(e,t,r,o){let{a:n,b:i,c:s}=e,l=t,c=t+1,m=t+2;if(r)l=r.getX(l),c=r.getX(c),m=r.getX(m);n.x=o.getX(l),n.y=o.getY(l),n.z=o.getZ(l),i.x=o.getX(c),i.y=o.getY(c),i.z=o.getZ(c),s.x=o.getX(m),s.y=o.getY(m),s.z=o.getZ(m)}function oo(e,t,r,o,n,i,s,l){let{geometry:c,_indirectBuffer:m}=e;for(let u=o,a=o+n;u<a;u++)He(c,t,r,u,i,s,l)}function no(e,t,r,o,n,i,s){let{geometry:l,_indirectBuffer:c}=e,m=1/0,u=null;for(let a=o,f=o+n;a<f;a++){let h;if(h=He(l,t,r,a,null,i,s),h&&h.distance<m)u=h,m=h.distance}return u}function so(e,t,r,o,n,i,s){let{geometry:l}=r,{index:c}=l,m=l.attributes.position;for(let u=e,a=t+e;u<a;u++){let f;if(f=u,H(s,f*3,c,m),s.needsUpdate=!0,o(s,f,n,i))return!0}return!1}function ao(e,t=null){if(t&&Array.isArray(t))t=new Set(t);let r=e.geometry,o=r.index?r.index.array:null,n=r.attributes.position,i,s,l,c,m=0,u=e._roots;for(let f=0,h=u.length;f<h;f++)i=u[f],s=new Uint32Array(i),l=new Uint16Array(i),c=new Float32Array(i),a(0,m),m+=i.byteLength;function a(f,h,g=!1){let d=f*2;if(C(d,l)){let b=B(f,s),T=O(d,l),p=1/0,x=1/0,v=1/0,y=-1/0,w=-1/0,S=-1/0;for(let I=3*b,R=3*(b+T);I<R;I++){let A=o[I],P=n.getX(A),_=n.getY(A),F=n.getZ(A);if(P<p)p=P;if(P>y)y=P;if(_<x)x=_;if(_>w)w=_;if(F<v)v=F;if(F>S)S=F}if(c[f+0]!==p||c[f+1]!==x||c[f+2]!==v||c[f+3]!==y||c[f+4]!==w||c[f+5]!==S)return c[f+0]=p,c[f+1]=x,c[f+2]=v,c[f+3]=y,c[f+4]=w,c[f+5]=S,!0;else return!1}else{let b=N(f),T=L(f,s),p=g,x=!1,v=!1;if(t){if(!p){let A=b/U+h/W,P=T/U+h/W;x=t.has(A),v=t.has(P),p=!x&&!v}}else x=!0,v=!0;let y=p||x,w=p||v,S=!1;if(y)S=a(b,h,p);let I=!1;if(w)I=a(T,h,p);let R=S||I;if(R)for(let A=0;A<3;A++){let P=b+A,_=T+A,F=c[P],M=c[P+3],D=c[_],V=c[_+3];c[f+A]=F<D?F:D,c[f+A+3]=M>V?M:V}return R}}}function Q(e,t,r,o,n){let i,s,l,c,m,u,a=1/r.direction.x,f=1/r.direction.y,h=1/r.direction.z,g=r.origin.x,d=r.origin.y,b=r.origin.z,T=t[e],p=t[e+3],x=t[e+1],v=t[e+3+1],y=t[e+2],w=t[e+3+2];if(a>=0)i=(T-g)*a,s=(p-g)*a;else i=(p-g)*a,s=(T-g)*a;if(f>=0)l=(x-d)*f,c=(v-d)*f;else l=(v-d)*f,c=(x-d)*f;if(i>c||l>s)return!1;if(l>i||isNaN(i))i=l;if(c<s||isNaN(s))s=c;if(h>=0)m=(y-b)*h,u=(w-b)*h;else m=(w-b)*h,u=(y-b)*h;if(i>u||m>s)return!1;if(m>i||i!==i)i=m;if(u<s||s!==s)s=u;return i<=n&&s>=o}function co(e,t,r,o,n,i,s,l){let{geometry:c,_indirectBuffer:m}=e;for(let u=o,a=o+n;u<a;u++){let f=m?m[u]:u;He(c,t,r,f,i,s,l)}}function lo(e,t,r,o,n,i,s){let{geometry:l,_indirectBuffer:c}=e,m=1/0,u=null;for(let a=o,f=o+n;a<f;a++){let h;if(h=He(l,t,r,c?c[a]:a,null,i,s),h&&h.distance<m)u=h,m=h.distance}return u}function uo(e,t,r,o,n,i,s){let{geometry:l}=r,{index:c}=l,m=l.attributes.position;for(let u=e,a=t+e;u<a;u++){let f;if(f=r.resolveTriangleIndex(u),H(s,f*3,c,m),s.needsUpdate=!0,o(s,f,n,i))return!0}return!1}function fo(e,t,r,o,n,i,s){E.setBuffer(e._roots[t]),Dr(0,e,r,o,n,i,s),E.clearBuffer()}function Dr(e,t,r,o,n,i,s){let{float32Array:l,uint16Array:c,uint32Array:m}=E,u=e*2;if(C(u,c)){let f=B(e,m),h=O(u,c);oo(t,r,o,f,h,n,i,s)}else{let f=N(e);if(Q(f,l,o,i,s))Dr(f,t,r,o,n,i,s);let h=L(e,m);if(Q(h,l,o,i,s))Dr(h,t,r,o,n,i,s)}}var Vs=["x","y","z"];function mo(e,t,r,o,n,i){E.setBuffer(e._roots[t]);let s=Cr(0,e,r,o,n,i);return E.clearBuffer(),s}function Cr(e,t,r,o,n,i){let{float32Array:s,uint16Array:l,uint32Array:c}=E,m=e*2;if(C(m,l)){let a=B(e,c),f=O(m,l);return no(t,r,o,a,f,n,i)}else{let a=ne(e,c),f=Vs[a],g=o.direction[f]>=0,d,b;if(g)d=N(e),b=L(e,c);else d=L(e,c),b=N(e);let p=Q(d,s,o,n,i)?Cr(d,t,r,o,n,i):null;if(p){let y=p.point[f];if(g?y<=s[b+a]:y>=s[b+a+3])return p}let v=Q(b,s,o,n,i)?Cr(b,t,r,o,n,i):null;if(p&&v)return p.distance<=v.distance?p:v;else return p||v||null}}import{Box3 as Ws,Matrix4 as Gs}from"./datacenter-engine.mjs";var Nt=new Ws,Ue=new q,Ve=new q,ut=new Gs,ho=new G,Lt=new G;function po(e,t,r,o){E.setBuffer(e._roots[t]);let n=Er(0,e,r,o);return E.clearBuffer(),n}function Er(e,t,r,o,n=null){let{float32Array:i,uint16Array:s,uint32Array:l}=E,c=e*2;if(n===null){if(!r.boundingBox)r.computeBoundingBox();ho.set(r.boundingBox.min,r.boundingBox.max,o),n=ho}if(C(c,s)){let u=t.geometry,a=u.index,f=u.attributes.position,h=r.index,g=r.attributes.position,d=B(e,l),b=O(c,s);if(ut.copy(o).invert(),r.boundsTree)return z(k(e),i,Lt),Lt.matrix.copy(ut),Lt.needsUpdate=!0,r.boundsTree.shapecast({intersectsBounds:(p)=>Lt.intersectsBox(p),intersectsTriangle:(p)=>{p.a.applyMatrix4(o),p.b.applyMatrix4(o),p.c.applyMatrix4(o),p.needsUpdate=!0;for(let x=d*3,v=(b+d)*3;x<v;x+=3)if(H(Ve,x,a,f),Ve.needsUpdate=!0,p.intersectsTriangle(Ve))return!0;return!1}});else{let T=le(r);for(let p=d*3,x=(b+d)*3;p<x;p+=3){H(Ue,p,a,f),Ue.a.applyMatrix4(ut),Ue.b.applyMatrix4(ut),Ue.c.applyMatrix4(ut),Ue.needsUpdate=!0;for(let v=0,y=T*3;v<y;v+=3)if(H(Ve,v,h,g),Ve.needsUpdate=!0,Ue.intersectsTriangle(Ve))return!0}}}else{let u=N(e),a=L(e,l);if(z(k(u),i,Nt),n.intersectsBox(Nt)&&Er(u,t,r,o,n))return!0;if(z(k(a),i,Nt),n.intersectsBox(Nt)&&Er(a,t,r,o,n))return!0;return!1}}import{Matrix4 as qs,Vector3 as zt}from"./datacenter-engine.mjs";var Ot=new qs,Br=new G,ft=new G,Ys=new zt,$s=new zt,Xs=new zt,js=new zt;function go(e,t,r,o={},n={},i=0,s=1/0){if(!t.boundingBox)t.computeBoundingBox();Br.set(t.boundingBox.min,t.boundingBox.max,r),Br.needsUpdate=!0;let l=e.geometry,c=l.attributes.position,m=l.index,u=t.attributes.position,a=t.index,f=Y.getPrimitive(),h=Y.getPrimitive(),g=Ys,d=$s,b=null,T=null;if(n)b=Xs,T=js;let p=1/0,x=null,v=null;if(Ot.copy(r).invert(),ft.matrix.copy(Ot),e.shapecast({boundsTraverseOrder:(y)=>Br.distanceToBox(y),intersectsBounds:(y,w,S)=>{if(S<p&&S<s){if(w)ft.min.copy(y.min),ft.max.copy(y.max),ft.needsUpdate=!0;return!0}return!1},intersectsRange:(y,w)=>{if(t.boundsTree)return t.boundsTree.shapecast({boundsTraverseOrder:(I)=>ft.distanceToBox(I),intersectsBounds:(I,R,A)=>A<p&&A<s,intersectsRange:(I,R)=>{for(let A=I,P=I+R;A<P;A++){H(h,3*A,a,u),h.a.applyMatrix4(r),h.b.applyMatrix4(r),h.c.applyMatrix4(r),h.needsUpdate=!0;for(let _=y,F=y+w;_<F;_++){H(f,3*_,m,c),f.needsUpdate=!0;let M=f.distanceToTriangle(h,g,b);if(M<p){if(d.copy(g),T)T.copy(b);p=M,x=_,v=A}if(M<i)return!0}}}});else{let S=le(t);for(let I=0,R=S;I<R;I++){H(h,3*I,a,u),h.a.applyMatrix4(r),h.b.applyMatrix4(r),h.c.applyMatrix4(r),h.needsUpdate=!0;for(let A=y,P=y+w;A<P;A++){H(f,3*A,m,c),f.needsUpdate=!0;let _=f.distanceToTriangle(h,g,b);if(_<p){if(d.copy(g),T)T.copy(b);p=_,x=A,v=I}if(_<i)return!0}}}}}),Y.releasePrimitive(f),Y.releasePrimitive(h),p===1/0)return null;if(!o.point)o.point=d.clone();else o.point.copy(d);if(o.distance=p,o.faceIndex=x,n){if(!n.point)n.point=T.clone();else n.point.copy(T);n.point.applyMatrix4(Ot),d.applyMatrix4(Ot),n.distance=d.sub(n.point).length(),n.faceIndex=v}return o}function vo(e,t=null){if(t&&Array.isArray(t))t=new Set(t);let r=e.geometry,o=r.index?r.index.array:null,n=r.attributes.position,i,s,l,c,m=0,u=e._roots;for(let f=0,h=u.length;f<h;f++)i=u[f],s=new Uint32Array(i),l=new Uint16Array(i),c=new Float32Array(i),a(0,m),m+=i.byteLength;function a(f,h,g=!1){let d=f*2;if(C(d,l)){let b=B(f,s),T=O(d,l),p=1/0,x=1/0,v=1/0,y=-1/0,w=-1/0,S=-1/0;for(let I=b,R=b+T;I<R;I++){let A=3*e.resolveTriangleIndex(I);for(let P=0;P<3;P++){let _=A+P;_=o?o[_]:_;let F=n.getX(_),M=n.getY(_),D=n.getZ(_);if(F<p)p=F;if(F>y)y=F;if(M<x)x=M;if(M>w)w=M;if(D<v)v=D;if(D>S)S=D}}if(c[f+0]!==p||c[f+1]!==x||c[f+2]!==v||c[f+3]!==y||c[f+4]!==w||c[f+5]!==S)return c[f+0]=p,c[f+1]=x,c[f+2]=v,c[f+3]=y,c[f+4]=w,c[f+5]=S,!0;else return!1}else{let b=N(f),T=L(f,s),p=g,x=!1,v=!1;if(t){if(!p){let A=b/U+h/W,P=T/U+h/W;x=t.has(A),v=t.has(P),p=!x&&!v}}else x=!0,v=!0;let y=p||x,w=p||v,S=!1;if(y)S=a(b,h,p);let I=!1;if(w)I=a(T,h,p);let R=S||I;if(R)for(let A=0;A<3;A++){let P=b+A,_=T+A,F=c[P],M=c[P+3],D=c[_],V=c[_+3];c[f+A]=F<D?F:D,c[f+A+3]=M>V?M:V}return R}}}function xo(e,t,r,o,n,i,s){E.setBuffer(e._roots[t]),Nr(0,e,r,o,n,i,s),E.clearBuffer()}function Nr(e,t,r,o,n,i,s){let{float32Array:l,uint16Array:c,uint32Array:m}=E,u=e*2;if(C(u,c)){let f=B(e,m),h=O(u,c);co(t,r,o,f,h,n,i,s)}else{let f=N(e);if(Q(f,l,o,i,s))Nr(f,t,r,o,n,i,s);let h=L(e,m);if(Q(h,l,o,i,s))Nr(h,t,r,o,n,i,s)}}var Ks=["x","y","z"];function yo(e,t,r,o,n,i){E.setBuffer(e._roots[t]);let s=Lr(0,e,r,o,n,i);return E.clearBuffer(),s}function Lr(e,t,r,o,n,i){let{float32Array:s,uint16Array:l,uint32Array:c}=E,m=e*2;if(C(m,l)){let a=B(e,c),f=O(m,l);return lo(t,r,o,a,f,n,i)}else{let a=ne(e,c),f=Ks[a],g=o.direction[f]>=0,d,b;if(g)d=N(e),b=L(e,c);else d=L(e,c),b=N(e);let p=Q(d,s,o,n,i)?Lr(d,t,r,o,n,i):null;if(p){let y=p.point[f];if(g?y<=s[b+a]:y>=s[b+a+3])return p}let v=Q(b,s,o,n,i)?Lr(b,t,r,o,n,i):null;if(p&&v)return p.distance<=v.distance?p:v;else return p||v||null}}import{Box3 as Qs,Matrix4 as Zs}from"./datacenter-engine.mjs";var kt=new Qs,We=new q,Ge=new q,mt=new Zs,bo=new G,Ht=new G;function To(e,t,r,o){E.setBuffer(e._roots[t]);let n=Or(0,e,r,o);return E.clearBuffer(),n}function Or(e,t,r,o,n=null){let{float32Array:i,uint16Array:s,uint32Array:l}=E,c=e*2;if(n===null){if(!r.boundingBox)r.computeBoundingBox();bo.set(r.boundingBox.min,r.boundingBox.max,o),n=bo}if(C(c,s)){let u=t.geometry,a=u.index,f=u.attributes.position,h=r.index,g=r.attributes.position,d=B(e,l),b=O(c,s);if(mt.copy(o).invert(),r.boundsTree)return z(k(e),i,Ht),Ht.matrix.copy(mt),Ht.needsUpdate=!0,r.boundsTree.shapecast({intersectsBounds:(p)=>Ht.intersectsBox(p),intersectsTriangle:(p)=>{p.a.applyMatrix4(o),p.b.applyMatrix4(o),p.c.applyMatrix4(o),p.needsUpdate=!0;for(let x=d,v=b+d;x<v;x++)if(H(Ge,3*t.resolveTriangleIndex(x),a,f),Ge.needsUpdate=!0,p.intersectsTriangle(Ge))return!0;return!1}});else{let T=le(r);for(let p=d,x=b+d;p<x;p++){let v=t.resolveTriangleIndex(p);H(We,3*v,a,f),We.a.applyMatrix4(mt),We.b.applyMatrix4(mt),We.c.applyMatrix4(mt),We.needsUpdate=!0;for(let y=0,w=T*3;y<w;y+=3)if(H(Ge,y,h,g),Ge.needsUpdate=!0,We.intersectsTriangle(Ge))return!0}}}else{let u=N(e),a=L(e,l);if(z(k(u),i,kt),n.intersectsBox(kt)&&Or(u,t,r,o,n))return!0;if(z(k(a),i,kt),n.intersectsBox(kt)&&Or(a,t,r,o,n))return!0;return!1}}import{Matrix4 as Js,Vector3 as Vt}from"./datacenter-engine.mjs";var Ut=new Js,zr=new G,ht=new G,ea=new Vt,ta=new Vt,ra=new Vt,ia=new Vt;function wo(e,t,r,o={},n={},i=0,s=1/0){if(!t.boundingBox)t.computeBoundingBox();zr.set(t.boundingBox.min,t.boundingBox.max,r),zr.needsUpdate=!0;let l=e.geometry,c=l.attributes.position,m=l.index,u=t.attributes.position,a=t.index,f=Y.getPrimitive(),h=Y.getPrimitive(),g=ea,d=ta,b=null,T=null;if(n)b=ra,T=ia;let p=1/0,x=null,v=null;if(Ut.copy(r).invert(),ht.matrix.copy(Ut),e.shapecast({boundsTraverseOrder:(y)=>zr.distanceToBox(y),intersectsBounds:(y,w,S)=>{if(S<p&&S<s){if(w)ht.min.copy(y.min),ht.max.copy(y.max),ht.needsUpdate=!0;return!0}return!1},intersectsRange:(y,w)=>{if(t.boundsTree){let S=t.boundsTree;return S.shapecast({boundsTraverseOrder:(I)=>ht.distanceToBox(I),intersectsBounds:(I,R,A)=>A<p&&A<s,intersectsRange:(I,R)=>{for(let A=I,P=I+R;A<P;A++){let _=S.resolveTriangleIndex(A);H(h,3*_,a,u),h.a.applyMatrix4(r),h.b.applyMatrix4(r),h.c.applyMatrix4(r),h.needsUpdate=!0;for(let F=y,M=y+w;F<M;F++){let D=e.resolveTriangleIndex(F);H(f,3*D,m,c),f.needsUpdate=!0;let V=f.distanceToTriangle(h,g,b);if(V<p){if(d.copy(g),T)T.copy(b);p=V,x=F,v=A}if(V<i)return!0}}}})}else{let S=le(t);for(let I=0,R=S;I<R;I++){H(h,3*I,a,u),h.a.applyMatrix4(r),h.b.applyMatrix4(r),h.c.applyMatrix4(r),h.needsUpdate=!0;for(let A=y,P=y+w;A<P;A++){let _=e.resolveTriangleIndex(A);H(f,3*_,m,c),f.needsUpdate=!0;let F=f.distanceToTriangle(h,g,b);if(F<p){if(d.copy(g),T)T.copy(b);p=F,x=A,v=I}if(F<i)return!0}}}}}),Y.releasePrimitive(f),Y.releasePrimitive(h),p===1/0)return null;if(!o.point)o.point=d.clone();else o.point.copy(d);if(o.distance=p,o.faceIndex=x,n){if(!n.point)n.point=T.clone();else n.point.copy(T);n.point.applyMatrix4(Ut),d.applyMatrix4(Ut),n.distance=d.sub(n.point).length(),n.faceIndex=v}return o}function kr(e,t,r){if(e===null)return null;return e.point.applyMatrix4(t.matrixWorld),e.distance=e.point.distanceTo(r.ray.origin),e.object=t,e}var Wt=new G,Gt=new na,_o=new Ro,Ao=new sa,Io=new Ro,Hr=["getX","getY","getZ"];class dt extends Fr{static serialize(e,t={}){t={cloneBuffers:!0,...t};let{geometry:r,_roots:o,_indirectBuffer:n}=e,i=r.getIndex(),s={version:1,roots:null,index:null,indirectBuffer:null};if(t.cloneBuffers)s.roots=o.map((l)=>l.slice()),s.index=i?i.array.slice():null,s.indirectBuffer=n?n.slice():null;else s.roots=o,s.index=i?i.array:null,s.indirectBuffer=n;return s}static deserialize(e,t,r={}){r={setIndex:!0,indirect:Boolean(e.indirectBuffer),...r};let{index:o,roots:n,indirectBuffer:i}=e;if(!e.version)console.warn("MeshBVH.deserialize: Serialization format has been changed and will be fixed up. It is recommended to regenerate any stored serialized data."),l(n);let s=new dt(t,{...r,[Ce]:!0});if(s._roots=n,s._indirectBuffer=i||null,r.setIndex){let c=t.getIndex();if(c===null){let m=new oa(e.index,1,!1);t.setIndex(m)}else if(c.array!==o)c.array.set(o),c.needsUpdate=!0}return s;function l(c){for(let m=0;m<c.length;m++){let u=c[m],a=new Uint32Array(u),f=new Uint16Array(u);for(let h=0,g=u.byteLength/W;h<g;h++){let d=U*h,b=2*d;if(!C(b,f))a[d+6]=a[d+6]/U-h}}}}get primitiveStride(){return 3}get resolveTriangleIndex(){return this.resolvePrimitiveIndex}constructor(e,t={}){if(t.maxLeafTris)console.warn('MeshBVH: "maxLeafTris" option has been deprecated. Use "targetLeafSize", instead.'),t={...t,targetLeafSize:t.maxLeafTris};super(e,t)}shiftTriangleOffsets(e){return super.shiftPrimitiveOffsets(e)}writePrimitiveBounds(e,t,r){let o=this.geometry,n=this._indirectBuffer,i=o.attributes.position,s=o.index?o.index.array:null,c=(n?n[e]:e)*3,m=c+0,u=c+1,a=c+2;if(s)m=s[m],u=s[u],a=s[a];for(let f=0;f<3;f++){let h=i[Hr[f]](m),g=i[Hr[f]](u),d=i[Hr[f]](a),b=h;if(g<b)b=g;if(d<b)b=d;let T=h;if(g>T)T=g;if(d>T)T=d;t[r+f]=b,t[r+f+3]=T}return t}computePrimitiveBounds(e,t,r){let o=this.geometry,n=this._indirectBuffer,i=o.attributes.position,s=o.index?o.index.array:null,l=i.normalized;if(e<0||t+e-r.offset>r.length/6)throw Error("MeshBVH: compute triangle bounds range is invalid.");let c=i.array,m=i.offset||0,u=3;if(i.isInterleavedBufferAttribute)u=i.data.stride;let a=["getX","getY","getZ"],f=r.offset;for(let h=e,g=e+t;h<g;h++){let b=(n?n[h]:h)*3,T=(h-f)*6,p=b+0,x=b+1,v=b+2;if(s)p=s[p],x=s[x],v=s[v];if(!l)p=p*u+m,x=x*u+m,v=v*u+m;for(let y=0;y<3;y++){let w,S,I;if(l)w=i[a[y]](p),S=i[a[y]](x),I=i[a[y]](v);else w=c[p+y],S=c[x+y],I=c[v+y];let R=w;if(S<R)R=S;if(I<R)R=I;let A=w;if(S>A)A=S;if(I>A)A=I;let P=(A-R)/2,_=y*2;r[T+_+0]=R+P,r[T+_+1]=P+(Math.abs(R)+P)*De}}return r}raycastObject3D(e,t,r=[]){let{material:o}=e;if(o===void 0)return;Ao.copy(e.matrixWorld).invert(),Gt.copy(t.ray).applyMatrix4(Ao),Io.setFromMatrixScale(e.matrixWorld),_o.copy(Gt.direction).multiply(Io);let n=_o.length(),i=t.near/n,s=t.far/n;if(t.firstHitOnly===!0){let l=this.raycastFirst(Gt,o,i,s);if(l=kr(l,e,t),l)r.push(l)}else{let l=this.raycast(Gt,o,i,s);for(let c=0,m=l.length;c<m;c++){let u=kr(l[c],e,t);if(u)r.push(u)}}return r}refit(e=null){return(this.indirect?vo:ao)(this,e)}raycast(e,t=So,r=0,o=1/0){let n=this._roots,i=[],s=this.indirect?xo:fo;for(let l=0,c=n.length;l<c;l++)s(this,l,t,e,i,r,o);return i}raycastFirst(e,t=So,r=0,o=1/0){let n=this._roots,i=null,s=this.indirect?yo:mo;for(let l=0,c=n.length;l<c;l++){let m=s(this,l,t,e,r,o);if(m!=null&&(i==null||m.distance<i.distance))i=m}return i}intersectsGeometry(e,t){let r=!1,o=this._roots,n=this.indirect?To:po;for(let i=0,s=o.length;i<s;i++)if(r=n(this,i,e,t),r)break;return r}shapecast(e){let t=Y.getPrimitive(),r=super.shapecast({...e,intersectsPrimitive:e.intersectsTriangle,scratchPrimitive:t,iterate:this.indirect?uo:so});return Y.releasePrimitive(t),r}bvhcast(e,t,r){let{intersectsRanges:o,intersectsTriangles:n}=r,i=Y.getPrimitive(),s=this.geometry.index,l=this.geometry.attributes.position,c=this.indirect?(h)=>{let g=this.resolveTriangleIndex(h);H(i,g*3,s,l)}:(h)=>{H(i,h*3,s,l)},m=Y.getPrimitive(),u=e.geometry.index,a=e.geometry.attributes.position,f=e.indirect?(h)=>{let g=e.resolveTriangleIndex(h);H(m,g*3,u,a)}:(h)=>{H(m,h*3,u,a)};if(n){if(!(e instanceof dt))throw Error('MeshBVH: "intersectsTriangles" callback can only be used with another MeshBVH.');let h=(g,d,b,T,p,x,v,y)=>{for(let w=b,S=b+T;w<S;w++){f(w),m.a.applyMatrix4(t),m.b.applyMatrix4(t),m.c.applyMatrix4(t),m.needsUpdate=!0;for(let I=g,R=g+d;I<R;I++)if(c(I),i.needsUpdate=!0,n(i,m,I,w,p,x,v,y))return!0}return!1};if(o){let g=o;o=function(d,b,T,p,x,v,y,w){if(!g(d,b,T,p,x,v,y,w))return h(d,b,T,p,x,v,y,w);return!0}}else o=h}return super.bvhcast(e,t,{intersectsRanges:o})}intersectsBox(e,t){return Wt.set(e.min,e.max,t),Wt.needsUpdate=!0,this.shapecast({intersectsBounds:(r)=>Wt.intersectsBox(r),intersectsTriangle:(r)=>Wt.intersectsTriangle(r)})}intersectsSphere(e){return this.shapecast({intersectsBounds:(t)=>e.intersectsBox(t),intersectsTriangle:(t)=>t.intersectsSphere(e)})}closestPointToGeometry(e,t,r={},o={},n=0,i=1/0){return(this.indirect?wo:go)(this,e,t,r,o,n,i)}closestPointToPoint(e,t={},r=0,o=1/0){return Qi(this,e,t,r,o)}}import{DataTexture as Co,FloatType as ga,UnsignedIntType as va,RGBAFormat as xa,RGIntegerFormat as ya,NearestFilter as $t,BufferAttribute as ba}from"./datacenter-engine.mjs";import{DataTexture as aa,FloatType as qt,IntType as Ur,UnsignedIntType as Yt,ByteType as Po,UnsignedByteType as Fo,ShortType as ca,UnsignedShortType as la,RedFormat as ua,RGFormat as fa,RGBAFormat as Vr,RedIntegerFormat as ma,RGIntegerFormat as ha,RGBAIntegerFormat as Wr,NearestFilter as Mo}from"./datacenter-engine.mjs";function da(e){switch(e){case 1:return"R";case 2:return"RG";case 3:return"RGBA";case 4:return"RGBA"}throw Error()}function pa(e){switch(e){case 1:return ua;case 2:return fa;case 3:return Vr;case 4:return Vr}}function Do(e){switch(e){case 1:return ma;case 2:return ha;case 3:return Wr;case 4:return Wr}}class Gr extends aa{constructor(){super();this.minFilter=Mo,this.magFilter=Mo,this.generateMipmaps=!1,this.overrideItemSize=null,this._forcedType=null}updateFrom(e){let t=this.overrideItemSize,r=e.itemSize,o=e.count;if(t!==null){if(r*o%t!==0)throw Error("VertexAttributeTexture: overrideItemSize must divide evenly into buffer length.");e.itemSize=t,e.count=o*r/t}let{itemSize:n,count:i,normalized:s}=e,l=e.array.constructor,c=l.BYTES_PER_ELEMENT,m=this._forcedType,u=n;if(m===null)switch(l){case Float32Array:m=qt;break;case Uint8Array:case Uint16Array:case Uint32Array:m=Yt;break;case Int8Array:case Int16Array:case Int32Array:m=Ur;break}let a,f,h,g,d=da(n);switch(m){case qt:if(h=1,f=pa(n),s&&c===1)if(g=l,d+="8",l===Uint8Array)a=Fo;else a=Po,d+="_SNORM";else g=Float32Array,d+="32F",a=qt;break;case Ur:if(d+=c*8+"I",h=s?Math.pow(2,l.BYTES_PER_ELEMENT*8-1):1,f=Do(n),c===1)g=Int8Array,a=Po;else if(c===2)g=Int16Array,a=ca;else g=Int32Array,a=Ur;break;case Yt:if(d+=c*8+"UI",h=s?Math.pow(2,l.BYTES_PER_ELEMENT*8-1):1,f=Do(n),c===1)g=Uint8Array,a=Fo;else if(c===2)g=Uint16Array,a=la;else g=Uint32Array,a=Yt;break}if(u===3&&(f===Vr||f===Wr))u=4;let b=Math.ceil(Math.sqrt(i))||1,T=u*b*b,p=new g(T),x=e.normalized;e.normalized=!1;for(let v=0;v<i;v++){let y=u*v;if(p[y]=e.getX(v)/h,n>=2)p[y+1]=e.getY(v)/h;if(n>=3){if(p[y+2]=e.getZ(v)/h,u===4)p[y+3]=1}if(n>=4)p[y+3]=e.getW(v)/h}e.normalized=x,this.internalFormat=d,this.format=f,this.type=a,this.image.width=b,this.image.height=b,this.image.data=p,this.needsUpdate=!0,this.dispose(),e.itemSize=r,e.count=o}}class pt extends Gr{constructor(){super();this._forcedType=Yt}}class gt extends Gr{constructor(){super();this._forcedType=qt}}class qr{constructor(){this.index=new pt,this.position=new gt,this.bvhBounds=new Co,this.bvhContents=new Co,this._cachedIndexAttr=null,this.index.overrideItemSize=3}updateFrom(e){let{geometry:t}=e;if(wa(e,this.bvhBounds,this.bvhContents),this.position.updateFrom(t.attributes.position),e.indirect){let r=e._indirectBuffer;if(this._cachedIndexAttr===null||this._cachedIndexAttr.count!==r.length)if(t.index)this._cachedIndexAttr=t.index.clone();else{let o=Rr(ot(t));this._cachedIndexAttr=new ba(o,1,!1)}Ta(t,r,this._cachedIndexAttr),this.index.updateFrom(this._cachedIndexAttr)}else this.index.updateFrom(t.index)}dispose(){let{index:e,position:t,bvhBounds:r,bvhContents:o}=this;if(e)e.dispose();if(t)t.dispose();if(r)r.dispose();if(o)o.dispose()}}function Ta(e,t,r){let o=r.array,n=e.index?e.index.array:null;for(let i=0,s=t.length;i<s;i++){let l=3*i,c=3*t[i];for(let m=0;m<3;m++)o[l+m]=n?n[c+m]:c+m}}function wa(e,t,r){let o=e._roots;if(o.length!==1)throw Error("MeshBVHUniformStruct: Multi-root BVHs not supported.");let n=o[0],i=new Uint16Array(n),s=new Uint32Array(n),l=new Float32Array(n),c=n.byteLength/W,m=2*Math.ceil(Math.sqrt(c/2)),u=new Float32Array(4*m*m),a=Math.ceil(Math.sqrt(c)),f=new Uint32Array(2*a*a);for(let h=0;h<c;h++){let g=h*W/4,d=g*2,b=k(g);for(let T=0;T<3;T++)u[8*h+0+T]=l[b+0+T],u[8*h+4+T]=l[b+3+T];if(C(d,i)){let T=O(d,i),p=B(g,s),x=Di|T;f[h*2+0]=x,f[h*2+1]=p}else{let T=s[g+6],p=ne(g,s);f[h*2+0]=p,f[h*2+1]=T}}t.image.data=u,t.image.width=m,t.image.height=m,t.format=xa,t.type=ga,t.internalFormat="RGBA32F",t.minFilter=$t,t.magFilter=$t,t.generateMipmaps=!1,t.needsUpdate=!0,t.dispose(),r.image.data=f,r.image.width=a,r.image.height=a,r.format=ya,r.type=va,r.internalFormat="RG32UI",r.minFilter=$t,r.magFilter=$t,r.generateMipmaps=!1,r.needsUpdate=!0,r.dispose()}var ye={};vs(ye,{bvh_distance_functions:()=>Eo,bvh_ray_functions:()=>$r,bvh_struct_definitions:()=>Bo,common_functions:()=>Yr});var Yr=`

// A stack of uint32 indices can can store the indices for
// a perfectly balanced tree with a depth up to 31. Lower stack
// depth gets higher performance.
//
// However not all trees are balanced. Best value to set this to
// is the trees max depth.
#ifndef BVH_STACK_DEPTH
#define BVH_STACK_DEPTH 60
#endif

#ifndef INFINITY
#define INFINITY 1e20
#endif

// Utilities
uvec4 uTexelFetch1D( usampler2D tex, uint index ) {

	uint width = uint( textureSize( tex, 0 ).x );
	uvec2 uv;
	uv.x = index % width;
	uv.y = index / width;

	return texelFetch( tex, ivec2( uv ), 0 );

}

ivec4 iTexelFetch1D( isampler2D tex, uint index ) {

	uint width = uint( textureSize( tex, 0 ).x );
	uvec2 uv;
	uv.x = index % width;
	uv.y = index / width;

	return texelFetch( tex, ivec2( uv ), 0 );

}

vec4 texelFetch1D( sampler2D tex, uint index ) {

	uint width = uint( textureSize( tex, 0 ).x );
	uvec2 uv;
	uv.x = index % width;
	uv.y = index / width;

	return texelFetch( tex, ivec2( uv ), 0 );

}

vec4 textureSampleBarycoord( sampler2D tex, vec3 barycoord, uvec3 faceIndices ) {

	return
		barycoord.x * texelFetch1D( tex, faceIndices.x ) +
		barycoord.y * texelFetch1D( tex, faceIndices.y ) +
		barycoord.z * texelFetch1D( tex, faceIndices.z );

}

void ndcToCameraRay(
	vec2 coord, mat4 cameraWorld, mat4 invProjectionMatrix,
	out vec3 rayOrigin, out vec3 rayDirection
) {

	// get camera look direction and near plane for camera clipping
	vec4 lookDirection = cameraWorld * vec4( 0.0, 0.0, - 1.0, 0.0 );
	vec4 nearVector = invProjectionMatrix * vec4( 0.0, 0.0, - 1.0, 1.0 );
	float near = abs( nearVector.z / nearVector.w );

	// get the camera direction and position from camera matrices
	vec4 origin = cameraWorld * vec4( 0.0, 0.0, 0.0, 1.0 );
	vec4 direction = invProjectionMatrix * vec4( coord, 0.5, 1.0 );
	direction /= direction.w;
	direction = cameraWorld * direction - origin;

	// slide the origin along the ray until it sits at the near clip plane position
	origin.xyz += direction.xyz * near / dot( direction, lookDirection );

	rayOrigin = origin.xyz;
	rayDirection = direction.xyz;

}
`;var Eo=`

float dot2( vec3 v ) {

	return dot( v, v );

}

// implementation from https://www.shadertoy.com/view/ttfGWl, though method 2 has been removed
// and is now available at this fork: https://www.shadertoy.com/view/WlB3zW
vec3 closestPointToTriangle( vec3 p, vec3 v0, vec3 v1, vec3 v2, out vec3 barycoord ) {

    vec3 v10 = v1 - v0;
    vec3 v21 = v2 - v1;
    vec3 v02 = v0 - v2;

	vec3 p0 = p - v0;
	vec3 p1 = p - v1;
	vec3 p2 = p - v2;

    vec3 nor = cross( v10, v02 );

    // method 2, in barycentric space
    vec3  q = cross( nor, p0 );
    float d = 1.0 / dot2( nor );
    float u = d * dot( q, v02 );
    float v = d * dot( q, v10 );
    float w = 1.0 - u - v;

	if( u < 0.0 ) {

		w = clamp( dot( p2, v02 ) / dot2( v02 ), 0.0, 1.0 );
		u = 0.0;
		v = 1.0 - w;

	} else if( v < 0.0 ) {

		u = clamp( dot( p0, v10 ) / dot2( v10 ), 0.0, 1.0 );
		v = 0.0;
		w = 1.0 - u;

	} else if( w < 0.0 ) {

		v = clamp( dot( p1, v21 ) / dot2( v21 ), 0.0, 1.0 );
		w = 0.0;
		u = 1.0 - v;

	}

	// output the barycoord in v0, v1, v2 weight order
	barycoord = vec3( w, u, v );
    return u * v1 + v * v2 + w * v0;

}

float distanceToTriangles(
	// geometry info and triangle range
	sampler2D positionAttr, usampler2D indexAttr, uint offset, uint count,

	// point and cut off range
	vec3 point, float closestDistanceSquared,

	// outputs
	inout uvec4 faceIndices, inout vec3 faceNormal, inout vec3 barycoord, inout float side, inout vec3 outPoint
) {

	bool found = false;
	vec3 localBarycoord;
	for ( uint i = offset, l = offset + count; i < l; i ++ ) {

		uvec3 indices = uTexelFetch1D( indexAttr, i ).xyz;
		vec3 a = texelFetch1D( positionAttr, indices.x ).rgb;
		vec3 b = texelFetch1D( positionAttr, indices.y ).rgb;
		vec3 c = texelFetch1D( positionAttr, indices.z ).rgb;

		// get the closest point and barycoord
		vec3 closestPoint = closestPointToTriangle( point, a, b, c, localBarycoord );
		vec3 delta = point - closestPoint;
		float sqDist = dot2( delta );
		if ( sqDist < closestDistanceSquared ) {

			// set the output results
			closestDistanceSquared = sqDist;
			faceIndices = uvec4( indices.xyz, i );
			faceNormal = normalize( cross( a - b, b - c ) );
			barycoord = localBarycoord;
			outPoint = closestPoint;
			side = sign( dot( faceNormal, delta ) );

		}

	}

	return closestDistanceSquared;

}

float distanceSqToBounds( vec3 point, vec3 boundsMin, vec3 boundsMax ) {

	vec3 clampedPoint = clamp( point, boundsMin, boundsMax );
	vec3 delta = point - clampedPoint;
	return dot( delta, delta );

}

float distanceSqToBVHNodeBoundsPoint( vec3 point, sampler2D bvhBounds, uint currNodeIndex ) {

	uint cni2 = currNodeIndex * 2u;
	vec3 boundsMin = texelFetch1D( bvhBounds, cni2 ).xyz;
	vec3 boundsMax = texelFetch1D( bvhBounds, cni2 + 1u ).xyz;
	return distanceSqToBounds( point, boundsMin, boundsMax );

}

// use a macro to hide the fact that we need to expand the struct into separate fields
#define	bvhClosestPointToPoint(		bvh,		point, maxDistance, faceIndices, faceNormal, barycoord, side, outPoint	)	_bvhClosestPointToPoint(		bvh.position, bvh.index, bvh.bvhBounds, bvh.bvhContents,		point, maxDistance, faceIndices, faceNormal, barycoord, side, outPoint	)

float _bvhClosestPointToPoint(
	// bvh info
	sampler2D bvh_position, usampler2D bvh_index, sampler2D bvh_bvhBounds, usampler2D bvh_bvhContents,

	// point to check
	vec3 point, float maxDistance,

	// output variables
	inout uvec4 faceIndices, inout vec3 faceNormal, inout vec3 barycoord,
	inout float side, inout vec3 outPoint
 ) {

	// stack needs to be twice as long as the deepest tree we expect because
	// we push both the left and right child onto the stack every traversal
	int pointer = 0;
	uint stack[ BVH_STACK_DEPTH ];
	stack[ 0 ] = 0u;

	float closestDistanceSquared = maxDistance * maxDistance;
	bool found = false;
	while ( pointer > - 1 && pointer < BVH_STACK_DEPTH ) {

		uint currNodeIndex = stack[ pointer ];
		pointer --;

		// check if we intersect the current bounds
		float boundsHitDistance = distanceSqToBVHNodeBoundsPoint( point, bvh_bvhBounds, currNodeIndex );
		if ( boundsHitDistance > closestDistanceSquared ) {

			continue;

		}

		uvec2 boundsInfo = uTexelFetch1D( bvh_bvhContents, currNodeIndex ).xy;
		bool isLeaf = bool( boundsInfo.x & 0xffff0000u );
		if ( isLeaf ) {

			uint count = boundsInfo.x & 0x0000ffffu;
			uint offset = boundsInfo.y;
			closestDistanceSquared = distanceToTriangles(
				bvh_position, bvh_index, offset, count, point, closestDistanceSquared,

				// outputs
				faceIndices, faceNormal, barycoord, side, outPoint
			);

		} else {

			uint leftIndex = currNodeIndex + 1u;
			uint splitAxis = boundsInfo.x & 0x0000ffffu;
			uint rightIndex = currNodeIndex + boundsInfo.y;
			bool leftToRight = distanceSqToBVHNodeBoundsPoint( point, bvh_bvhBounds, leftIndex ) < distanceSqToBVHNodeBoundsPoint( point, bvh_bvhBounds, rightIndex );//rayDirection[ splitAxis ] >= 0.0;
			uint c1 = leftToRight ? leftIndex : rightIndex;
			uint c2 = leftToRight ? rightIndex : leftIndex;

			// set c2 in the stack so we traverse it later. We need to keep track of a pointer in
			// the stack while we traverse. The second pointer added is the one that will be
			// traversed first
			pointer ++;
			stack[ pointer ] = c2;
			pointer ++;
			stack[ pointer ] = c1;

		}

	}

	return sqrt( closestDistanceSquared );

}
`;var $r=`

#ifndef TRI_INTERSECT_EPSILON
#define TRI_INTERSECT_EPSILON 1e-5
#endif

// Raycasting
bool intersectsBounds( vec3 rayOrigin, vec3 rayDirection, vec3 boundsMin, vec3 boundsMax, out float dist ) {

	// https://www.reddit.com/r/opengl/comments/8ntzz5/fast_glsl_ray_box_intersection/
	// https://tavianator.com/2011/ray_box.html
	vec3 invDir = 1.0 / rayDirection;

	// find intersection distances for each plane
	vec3 tMinPlane = invDir * ( boundsMin - rayOrigin );
	vec3 tMaxPlane = invDir * ( boundsMax - rayOrigin );

	// get the min and max distances from each intersection
	vec3 tMinHit = min( tMaxPlane, tMinPlane );
	vec3 tMaxHit = max( tMaxPlane, tMinPlane );

	// get the furthest hit distance
	vec2 t = max( tMinHit.xx, tMinHit.yz );
	float t0 = max( t.x, t.y );

	// get the minimum hit distance
	t = min( tMaxHit.xx, tMaxHit.yz );
	float t1 = min( t.x, t.y );

	// set distance to 0.0 if the ray starts inside the box
	dist = max( t0, 0.0 );

	return t1 >= dist;

}

bool intersectsTriangle(
	vec3 rayOrigin, vec3 rayDirection, vec3 a, vec3 b, vec3 c,
	out vec3 barycoord, out vec3 norm, out float dist, out float side
) {

	// https://stackoverflow.com/questions/42740765/intersection-between-line-and-triangle-in-3d
	vec3 edge1 = b - a;
	vec3 edge2 = c - a;
	norm = cross( edge1, edge2 );

	float det = - dot( rayDirection, norm );
	float invdet = 1.0 / det;

	vec3 AO = rayOrigin - a;
	vec3 DAO = cross( AO, rayDirection );

	vec4 uvt;
	uvt.x = dot( edge2, DAO ) * invdet;
	uvt.y = - dot( edge1, DAO ) * invdet;
	uvt.z = dot( AO, norm ) * invdet;
	uvt.w = 1.0 - uvt.x - uvt.y;

	// set the hit information
	barycoord = uvt.wxy; // arranged in A, B, C order
	dist = uvt.z;
	side = sign( det );
	norm = side * normalize( norm );

	// add an epsilon to avoid misses between triangles
	uvt += vec4( TRI_INTERSECT_EPSILON );

	return all( greaterThanEqual( uvt, vec4( 0.0 ) ) );

}

bool intersectTriangles(
	// geometry info and triangle range
	sampler2D positionAttr, usampler2D indexAttr, uint offset, uint count,

	// ray
	vec3 rayOrigin, vec3 rayDirection,

	// outputs
	inout float minDistance, inout uvec4 faceIndices, inout vec3 faceNormal, inout vec3 barycoord,
	inout float side, inout float dist
) {

	bool found = false;
	vec3 localBarycoord, localNormal;
	float localDist, localSide;
	for ( uint i = offset, l = offset + count; i < l; i ++ ) {

		uvec3 indices = uTexelFetch1D( indexAttr, i ).xyz;
		vec3 a = texelFetch1D( positionAttr, indices.x ).rgb;
		vec3 b = texelFetch1D( positionAttr, indices.y ).rgb;
		vec3 c = texelFetch1D( positionAttr, indices.z ).rgb;

		if (
			intersectsTriangle( rayOrigin, rayDirection, a, b, c, localBarycoord, localNormal, localDist, localSide )
			&& localDist < minDistance
		) {

			found = true;
			minDistance = localDist;

			faceIndices = uvec4( indices.xyz, i );
			faceNormal = localNormal;

			side = localSide;
			barycoord = localBarycoord;
			dist = localDist;

		}

	}

	return found;

}

bool intersectsBVHNodeBounds( vec3 rayOrigin, vec3 rayDirection, sampler2D bvhBounds, uint currNodeIndex, out float dist ) {

	uint cni2 = currNodeIndex * 2u;
	vec3 boundsMin = texelFetch1D( bvhBounds, cni2 ).xyz;
	vec3 boundsMax = texelFetch1D( bvhBounds, cni2 + 1u ).xyz;
	return intersectsBounds( rayOrigin, rayDirection, boundsMin, boundsMax, dist );

}

// use a macro to hide the fact that we need to expand the struct into separate fields
#define	bvhIntersectFirstHit(		bvh,		rayOrigin, rayDirection, faceIndices, faceNormal, barycoord, side, dist	)	_bvhIntersectFirstHit(		bvh.position, bvh.index, bvh.bvhBounds, bvh.bvhContents,		rayOrigin, rayDirection, faceIndices, faceNormal, barycoord, side, dist	)

bool _bvhIntersectFirstHit(
	// bvh info
	sampler2D bvh_position, usampler2D bvh_index, sampler2D bvh_bvhBounds, usampler2D bvh_bvhContents,

	// ray
	vec3 rayOrigin, vec3 rayDirection,

	// output variables split into separate variables due to output precision
	inout uvec4 faceIndices, inout vec3 faceNormal, inout vec3 barycoord,
	inout float side, inout float dist
) {

	// stack needs to be twice as long as the deepest tree we expect because
	// we push both the left and right child onto the stack every traversal
	int pointer = 0;
	uint stack[ BVH_STACK_DEPTH ];
	stack[ 0 ] = 0u;

	float triangleDistance = INFINITY;
	bool found = false;
	while ( pointer > - 1 && pointer < BVH_STACK_DEPTH ) {

		uint currNodeIndex = stack[ pointer ];
		pointer --;

		// check if we intersect the current bounds
		float boundsHitDistance;
		if (
			! intersectsBVHNodeBounds( rayOrigin, rayDirection, bvh_bvhBounds, currNodeIndex, boundsHitDistance )
			|| boundsHitDistance > triangleDistance
		) {

			continue;

		}

		uvec2 boundsInfo = uTexelFetch1D( bvh_bvhContents, currNodeIndex ).xy;
		bool isLeaf = bool( boundsInfo.x & 0xffff0000u );

		if ( isLeaf ) {

			uint count = boundsInfo.x & 0x0000ffffu;
			uint offset = boundsInfo.y;

			found = intersectTriangles(
				bvh_position, bvh_index, offset, count,
				rayOrigin, rayDirection, triangleDistance,
				faceIndices, faceNormal, barycoord, side, dist
			) || found;

		} else {

			uint leftIndex = currNodeIndex + 1u;
			uint splitAxis = boundsInfo.x & 0x0000ffffu;
			uint rightIndex = currNodeIndex + boundsInfo.y;

			bool leftToRight = rayDirection[ splitAxis ] >= 0.0;
			uint c1 = leftToRight ? leftIndex : rightIndex;
			uint c2 = leftToRight ? rightIndex : leftIndex;

			// set c2 in the stack so we traverse it later. We need to keep track of a pointer in
			// the stack while we traverse. The second pointer added is the one that will be
			// traversed first
			pointer ++;
			stack[ pointer ] = c2;

			pointer ++;
			stack[ pointer ] = c1;

		}

	}

	return found;

}
`;var Bo=`
struct BVH {

	usampler2D index;
	sampler2D position;

	sampler2D bvhBounds;
	usampler2D bvhContents;

};
`;var oh=`
	${Yr}
	${$r}
`;import{BufferAttribute as Xo,BufferGeometry as $o,Mesh as La,MeshBasicMaterial as Oa}from"./datacenter-engine.mjs";import{BufferAttribute as _a,BufferGeometry as Aa}from"./datacenter-engine.mjs";import{BufferAttribute as Sa}from"./datacenter-engine.mjs";function Xt(e,t,r=0){if(e.isInterleavedBufferAttribute){let o=e.itemSize;for(let n=0,i=e.count;n<i;n++){let s=n+r;if(t.setX(s,e.getX(n)),o>=2)t.setY(s,e.getY(n));if(o>=3)t.setZ(s,e.getZ(n));if(o>=4)t.setW(s,e.getW(n))}}else{let o=t.array,n=o.constructor,i=o.BYTES_PER_ELEMENT*e.itemSize*r;new n(o.buffer,i,e.array.length).set(e.array)}}function be(e,t=null){let r=e.array.constructor,o=e.normalized,n=e.itemSize,i=t===null?e.count:t;return new Sa(new r(n*i),n,o)}function fe(e,t){if(!e&&!t)return!0;if(Boolean(e)!==Boolean(t))return!1;let r=e.count===t.count,o=e.normalized===t.normalized,n=e.array.constructor===t.array.constructor,i=e.itemSize===t.itemSize;if(!r||!o||!n||!i)return!1;return!0}function Ia(e){let t=e[0].index!==null,r=new Set(Object.keys(e[0].attributes));if(!e[0].getAttribute("position"))throw Error("StaticGeometryGenerator: position attribute is required.");for(let o=0;o<e.length;++o){let n=e[o],i=0;if(t!==(n.index!==null))throw Error("StaticGeometryGenerator: All geometries must have compatible attributes; make sure index attribute exists among all geometries, or in none of them.");for(let s in n.attributes){if(!r.has(s))throw Error('StaticGeometryGenerator: All geometries must have compatible attributes; make sure "'+s+'" attribute exists among all geometries, or in none of them.');i++}if(i!==r.size)throw Error("StaticGeometryGenerator: All geometries must have the same number of attributes.")}}function Ra(e){let t=0;for(let r=0,o=e.length;r<o;r++)t+=e[r].getIndex().count;return t}function Pa(e){let t=0;for(let r=0,o=e.length;r<o;r++)t+=e[r].getAttribute("position").count;return t}function Fa(e,t,r){if(e.index&&e.index.count!==t)e.setIndex(null);let o=e.attributes;for(let n in o)if(o[n].count!==r)e.deleteAttribute(n)}function No(e,t={},r=new Aa){let{useGroups:o=!1,forceUpdate:n=!1,skipAssigningAttributes:i=[],overwriteIndex:s=!0}=t;Ia(e);let l=e[0].index!==null,c=l?Ra(e):-1,m=Pa(e);if(Fa(r,c,m),o){let a=0;for(let f=0,h=e.length;f<h;f++){let g=e[f],d;if(l)d=g.getIndex().count;else d=g.getAttribute("position").count;r.addGroup(a,d,f),a+=d}}if(l){let a=!1;if(!r.index)r.setIndex(new _a(new Uint32Array(c),1,!1)),a=!0;if(a||s){let f=0,h=0,g=r.getIndex();for(let d=0,b=e.length;d<b;d++){let T=e[d],p=T.getIndex();if(!(!n&&!a&&i[d]))for(let v=0;v<p.count;++v)g.setX(f+v,p.getX(v)+h);f+=p.count,h+=T.getAttribute("position").count}}}let u=Object.keys(e[0].attributes);for(let a=0,f=u.length;a<f;a++){let h=!1,g=u[a];if(!r.getAttribute(g)){let T=e[0].getAttribute(g);r.setAttribute(g,be(T,m)),h=!0}let d=0,b=r.getAttribute(g);for(let T=0,p=e.length;T<p;T++){let x=e[T],v=!n&&!h&&i[T],y=x.getAttribute(g);if(!v)if(g==="color"&&b.itemSize!==y.itemSize)for(let w=d,S=y.count;w<S;w++)y.setXYZW(w,b.getX(w),b.getY(w),b.getZ(w),1);else Xt(y,b,d);d+=y.count}}}import{BufferAttribute as vt}from"./datacenter-engine.mjs";function Lo(e,t,r){let o=e.index,i=e.attributes.position.count,s=o?o.count:i,l=e.groups;if(l.length===0)l=[{count:s,start:0,materialIndex:0}];let c=e.getAttribute("materialIndex");if(!c||c.count!==i){let u;if(r.length<=255)u=new Uint8Array(i);else u=new Uint16Array(i);c=new vt(u,1,!1),e.deleteAttribute("materialIndex"),e.setAttribute("materialIndex",c)}let m=c.array;for(let u=0;u<l.length;u++){let a=l[u],f=a.start,h=a.count,g=Math.min(h,s-f),d=Array.isArray(t)?t[a.materialIndex]:t,b=r.indexOf(d);for(let T=0;T<g;T++){let p=f+T;if(o)p=o.getX(p);m[p]=b}}}function Oo(e,t){if(!e.index){let r=e.attributes.position.count,o=Array(r);for(let n=0;n<r;n++)o[n]=n;e.setIndex(o)}if(!e.attributes.normal&&(t&&t.includes("normal")))e.computeVertexNormals();if(!e.attributes.uv&&(t&&t.includes("uv"))){let r=e.attributes.position.count;e.setAttribute("uv",new vt(new Float32Array(r*2),2,!1))}if(!e.attributes.uv2&&(t&&t.includes("uv2"))){let r=e.attributes.position.count;e.setAttribute("uv2",new vt(new Float32Array(r*2),2,!1))}if(!e.attributes.tangent&&(t&&t.includes("tangent")))if(e.attributes.uv&&e.attributes.normal)e.computeTangents();else{let r=e.attributes.position.count;e.setAttribute("tangent",new vt(new Float32Array(r*4),4,!1))}if(!e.attributes.color&&(t&&t.includes("color"))){let r=e.attributes.position.count,o=new Float32Array(r*4);o.fill(1),e.setAttribute("color",new vt(o,4))}}import{BufferGeometry as Na}from"./datacenter-engine.mjs";import{Matrix4 as Ma}from"./datacenter-engine.mjs";function qe(e){let t=0;if(e.byteLength!==0){let r=new Uint8Array(e);for(let o=0;o<e.byteLength;o++){let n=r[o];t=(t<<5)-t+n,t|=0}}return t}function zo(e){let t=e.uuid,r=Object.values(e.attributes);if(e.index)r.push(e.index),t+=`index|${e.index.version}`;let o=Object.keys(r).sort();for(let n of o){let i=r[n];t+=`${n}_${i.version}|`}return t}function ko(e){let t=e.skeleton;if(t){if(!t.boneTexture)t.computeBoneTexture();return`${qe(t.boneTexture.image.data.buffer)}_${t.boneTexture.uuid}`}else return null}class Xr{constructor(e=null){if(this.matrixWorld=new Ma,this.geometryHash=null,this.skeletonHash=null,this.primitiveCount=-1,e!==null)this.updateFrom(e)}updateFrom(e){let t=e.geometry,r=(t.index?t.index.count:t.attributes.position.count)/3;this.matrixWorld.copy(e.matrixWorld),this.geometryHash=zo(t),this.primitiveCount=r,this.skeletonHash=ko(e)}didChange(e){let t=e.geometry,r=(t.index?t.index.count:t.attributes.position.count)/3;return!(this.matrixWorld.equals(e.matrixWorld)&&this.geometryHash===zo(t)&&this.skeletonHash===ko(e)&&this.primitiveCount===r)}}import{BufferGeometry as Da,Matrix3 as Ca,Matrix4 as qo,Vector3 as xt,Vector4 as Qr}from"./datacenter-engine.mjs";var Te=new xt,we=new xt,Se=new xt,Ho=new Qr,jt=new xt,jr=new xt,Uo=new Qr,Vo=new Qr,Kt=new qo,Wo=new qo;function Go(e,t,r){let{skeleton:o,geometry:n}=e,i=o.bones,s=o.boneInverses;Uo.fromBufferAttribute(n.attributes.skinIndex,t),Vo.fromBufferAttribute(n.attributes.skinWeight,t),Kt.elements.fill(0);for(let l=0;l<4;l++){let c=Vo.getComponent(l);if(c!==0){let m=Uo.getComponent(l);Wo.multiplyMatrices(i[m].matrixWorld,s[m]),Ea(Kt,Wo,c)}}return Kt.multiply(e.bindMatrix).premultiply(e.bindMatrixInverse),r.transformDirection(Kt),r}function Kr(e,t,r,o,n){jt.set(0,0,0);for(let i=0,s=e.length;i<s;i++){let l=t[i],c=e[i];if(l===0)continue;if(jr.fromBufferAttribute(c,o),r)jt.addScaledVector(jr,l);else jt.addScaledVector(jr.sub(n),l)}n.add(jt)}function Ea(e,t,r){let o=e.elements,n=t.elements;for(let i=0,s=n.length;i<s;i++)o[i]+=n[i]*r}function Ba(e){let{index:t,attributes:r}=e;if(t)for(let o=0,n=t.count;o<n;o+=3){let i=t.getX(o),s=t.getX(o+2);t.setX(o,s),t.setX(o+2,i)}else for(let o in r){let n=r[o],i=n.itemSize;for(let s=0,l=n.count;s<l;s+=3)for(let c=0;c<i;c++){let m=n.getComponent(s,c),u=n.getComponent(s+2,c);n.setComponent(s,c,u),n.setComponent(s+2,c,m)}}return e}function Yo(e,t={},r=new Da){t={applyWorldTransforms:!0,attributes:[],...t};let o=e.geometry,n=t.applyWorldTransforms,i=t.attributes.includes("normal"),s=t.attributes.includes("tangent"),l=o.attributes,c=r.attributes;for(let p in r.attributes)if(!t.attributes.includes(p)||!(p in o.attributes))r.deleteAttribute(p);if(!r.index&&o.index)r.index=o.index.clone();if(!c.position)r.setAttribute("position",be(l.position));if(i&&!c.normal&&l.normal)r.setAttribute("normal",be(l.normal));if(s&&!c.tangent&&l.tangent)r.setAttribute("tangent",be(l.tangent));if(fe(o.index,r.index),fe(l.position,c.position),i)fe(l.normal,c.normal);if(s)fe(l.tangent,c.tangent);let m=l.position,u=i?l.normal:null,a=s?l.tangent:null,f=o.morphAttributes.position,h=o.morphAttributes.normal,g=o.morphAttributes.tangent,d=o.morphTargetsRelative,b=e.morphTargetInfluences,T=new Ca;if(T.getNormalMatrix(e.matrixWorld),o.index)r.index.array.set(o.index.array);for(let p=0,x=l.position.count;p<x;p++){if(Te.fromBufferAttribute(m,p),u)we.fromBufferAttribute(u,p);if(a)Ho.fromBufferAttribute(a,p),Se.fromBufferAttribute(a,p);if(b){if(f)Kr(f,b,d,p,Te);if(h)Kr(h,b,d,p,we);if(g)Kr(g,b,d,p,Se)}if(e.isSkinnedMesh){if(e.applyBoneTransform(p,Te),u)Go(e,p,we);if(a)Go(e,p,Se)}if(n)Te.applyMatrix4(e.matrixWorld);if(c.position.setXYZ(p,Te.x,Te.y,Te.z),u){if(n)we.applyNormalMatrix(T);c.normal.setXYZ(p,we.x,we.y,we.z)}if(a){if(n)Se.transformDirection(e.matrixWorld);c.tangent.setXYZW(p,Se.x,Se.y,Se.z,Ho.w)}}for(let p in t.attributes){let x=t.attributes[p];if(x==="position"||x==="tangent"||x==="normal"||!(x in l))continue;if(!c[x])r.setAttribute(x,be(l[x]));fe(l[x],c[x]),Xt(l[x],c[x])}if(e.matrixWorld.determinant()<0)Ba(r);return r}class Zr extends Na{constructor(){super();this.version=0,this.hash=null,this._diff=new Xr}isCompatible(e,t){let r=e.geometry;for(let o=0;o<t.length;o++){let n=t[o],i=r.attributes[n],s=this.attributes[n];if(i&&!fe(i,s))return!1}return!0}updateFrom(e,t){let r=this._diff;if(r.didChange(e))return Yo(e,t,this),r.updateFrom(e),this.version++,this.hash=`${this.uuid}_${this.version}`,!0;else return!1}}var Qt=0,Jr=1,ei=2;function za(e,t){for(let r=0,o=e.length;r<o;r++)e[r].traverseVisible((i)=>{if(i.isMesh)t(i)})}function ka(e){let t=[];for(let r=0,o=e.length;r<o;r++){let n=e[r];if(Array.isArray(n.material))t.push(...n.material);else t.push(n.material)}return t}function Ha(e,t,r){if(e.length===0){t.setIndex(null);let o=t.attributes;for(let n in o)t.deleteAttribute(n);for(let n in r.attributes)t.setAttribute(r.attributes[n],new Xo(new Float32Array(0),4,!1))}else No(e,r,t);for(let o in t.attributes)t.attributes[o].needsUpdate=!0}class ti{constructor(e){this.objects=null,this.useGroups=!0,this.applyWorldTransforms=!0,this.generateMissingAttributes=!0,this.overwriteIndex=!0,this.attributes=["position","normal","color","tangent","uv","uv2"],this._intermediateGeometry=new Map,this._geometryMergeSets=new WeakMap,this._mergeOrder=[],this._dummyMesh=null,this.setObjects(e||[])}_getDummyMesh(){if(!this._dummyMesh){let e=new Oa,t=new $o;t.setAttribute("position",new Xo(new Float32Array(9),3)),this._dummyMesh=new La(t,e)}return this._dummyMesh}_getMeshes(){let e=[];if(za(this.objects,(t)=>{e.push(t)}),e.sort((t,r)=>{if(t.uuid>r.uuid)return 1;if(t.uuid<r.uuid)return-1;return 0}),e.length===0)e.push(this._getDummyMesh());return e}_updateIntermediateGeometries(){let{_intermediateGeometry:e}=this,t=this._getMeshes(),r=new Set(e.keys()),o={attributes:this.attributes,applyWorldTransforms:this.applyWorldTransforms};for(let n=0,i=t.length;n<i;n++){let s=t[n],l=s.uuid;r.delete(l);let c=e.get(l);if(!c||!c.isCompatible(s,this.attributes)){if(c)c.dispose();c=new Zr,e.set(l,c)}if(c.updateFrom(s,o)){if(this.generateMissingAttributes)Oo(c,this.attributes)}}r.forEach((n)=>{e.delete(n)})}setObjects(e){if(Array.isArray(e))this.objects=[...e];else this.objects=[e]}generate(e=new $o){let{useGroups:t,overwriteIndex:r,_intermediateGeometry:o,_geometryMergeSets:n}=this,i=this._getMeshes(),s=[],l=[],c=n.get(e)||[];this._updateIntermediateGeometries();let m=!1;if(i.length!==c.length)m=!0;for(let a=0,f=i.length;a<f;a++){let h=i[a],g=o.get(h.uuid);l.push(g);let d=c[a];if(!d||d.uuid!==g.uuid)s.push(!1),m=!0;else if(d.version!==g.version)s.push(!1);else s.push(!0)}if(Ha(l,e,{useGroups:t,forceUpdate:m,skipAssigningAttributes:s,overwriteIndex:r}),m)e.dispose();n.set(e,l.map((a)=>({version:a.version,uuid:a.uuid})));let u=Qt;if(m)u=ei;else if(s.includes(!1))u=Jr;return{changeType:u,materials:ka(i),geometry:e}}}function Va(e){let t=new Set;for(let r=0,o=e.length;r<o;r++){let n=e[r];for(let i in n){let s=n[i];if(s&&s.isTexture)t.add(s)}}return Array.from(t)}function Wa(e){let t=[],r=new Set;for(let n=0,i=e.length;n<i;n++)e[n].traverse((s)=>{if(s.visible){if(s.isRectAreaLight||s.isSpotLight||s.isPointLight||s.isDirectionalLight){if(t.push(s),s.iesMap)r.add(s.iesMap)}}});let o=Array.from(r).sort((n,i)=>{if(n.uuid<i.uuid)return 1;if(n.uuid>i.uuid)return-1;return 0});return{lights:t,iesTextures:o}}class ri{get initialized(){return Boolean(this.bvh)}constructor(e){this.bvhOptions={},this.attributes=["position","normal","tangent","color","uv","uv2"],this.generateBVH=!0,this.bvh=null,this.geometry=new Ua,this.staticGeometryGenerator=new ti(e),this._bvhWorker=null,this._pendingGenerate=null,this._buildAsync=!1,this._materialUuids=null}setObjects(e){this.staticGeometryGenerator.setObjects(e)}setBVHWorker(e){this._bvhWorker=e}async generateAsync(e=null){if(!this._bvhWorker)throw Error('PathTracingSceneGenerator: "setBVHWorker" must be called before "generateAsync" can be called.');if(this.bvh instanceof Promise){if(!this._pendingGenerate)this._pendingGenerate=new Promise(async()=>(await this.bvh,this._pendingGenerate=null,this.generateAsync(e)));return this._pendingGenerate}else{this._buildAsync=!0;let t=this.generate(e);return this._buildAsync=!1,t.bvh=this.bvh=await t.bvh,t}}generate(e=null){let{staticGeometryGenerator:t,geometry:r,attributes:o}=this,n=t.objects;t.attributes=o,n.forEach((a)=>{a.traverse((f)=>{if(f.isSkinnedMesh&&f.skeleton)f.skeleton.update()})});let i=t.generate(r),s=i.materials,l=i.changeType!==Qt||this._materialUuids===null||this._materialUuids.length!==length;if(!l){for(let a=0,f=s.length;a<f;a++)if(s[a].uuid!==this._materialUuids[a]){l=!0;break}}let c=Va(s),{lights:m,iesTextures:u}=Wa(n);if(l)Lo(r,s,s),this._materialUuids=s.map((a)=>a.uuid);if(this.generateBVH){if(this.bvh instanceof Promise)throw Error("PathTracingSceneGenerator: BVH is already building asynchronously.");if(i.changeType===ei){let a={strategy:Ze,maxLeafTris:1,indirect:!0,onProgress:e,...this.bvhOptions};if(this._buildAsync)this.bvh=this._bvhWorker.generate(r,a);else this.bvh=new dt(r,a)}else if(i.changeType===Jr)this.bvh.refit()}return{bvhChanged:i.changeType!==Qt,bvh:this.bvh,needsMaterialIndexUpdate:l,lights:m,iesTextures:u,geometry:r,materials:s,textures:c,objects:n}}}import{RGBAFormat as Si,FloatType as _i,Color as Zc,Vector2 as Jc,WebGLRenderTarget as Ai,NoBlending as el,NormalBlending as tl,Vector4 as Ii,NearestFilter as je}from"./datacenter-engine.mjs";import{BufferGeometry as Ga,Float32BufferAttribute as jo,OrthographicCamera as qa,Mesh as Ya}from"./datacenter-engine.mjs";var $a=new qa(-1,1,1,-1,0,1);class Ko extends Ga{constructor(){super();this.setAttribute("position",new jo([-1,3,0,-1,-1,0,3,-1,0],3)),this.setAttribute("uv",new jo([0,2,0,0,2,0],2))}}var Xa=new Ko;class Z{constructor(e){this._mesh=new Ya(Xa,e)}dispose(){this._mesh.geometry.dispose()}render(e){e.render(this._mesh,$a)}get material(){return this._mesh.material}set material(e){this._mesh.material=e}}import{NoBlending as Ka}from"./datacenter-engine.mjs";import{ShaderMaterial as ja}from"./datacenter-engine.mjs";class _e extends ja{set needsUpdate(e){super.needsUpdate=!0,this.dispatchEvent({type:"recompilation"})}constructor(e){super(e);for(let t in this.uniforms)Object.defineProperty(this,t,{get(){return this.uniforms[t].value},set(r){this.uniforms[t].value=r}})}setDefine(e,t=void 0){if(t===void 0||t===null){if(e in this.defines)return delete this.defines[e],this.needsUpdate=!0,!0}else if(this.defines[e]!==t)return this.defines[e]=t,this.needsUpdate=!0,!0;return!1}}class ii extends _e{constructor(e){super({blending:Ka,uniforms:{target1:{value:null},target2:{value:null},opacity:{value:1}},vertexShader:`

				varying vec2 vUv;

				void main() {

					vUv = uv;
					gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

				}`,fragmentShader:`

				uniform float opacity;

				uniform sampler2D target1;
				uniform sampler2D target2;

				varying vec2 vUv;

				void main() {

					vec4 color1 = texture2D( target1, vUv );
					vec4 color2 = texture2D( target2, vUv );

					float invOpacity = 1.0 - opacity;
					float totalAlpha = color1.a * invOpacity + color2.a * opacity;

					if ( color1.a != 0.0 || color2.a != 0.0 ) {

						gl_FragColor.rgb = color1.rgb * ( invOpacity * color1.a / totalAlpha ) + color2.rgb * ( opacity * color2.a / totalAlpha );
						gl_FragColor.a = totalAlpha;

					} else {

						gl_FragColor = vec4( 0.0 );

					}

				}`});this.setValues(e)}}import{FloatType as Qa,NearestFilter as Jo,NoBlending as Za,RGBAFormat as Ja,Vector2 as ec,WebGLRenderTarget as tc}from"./datacenter-engine.mjs";function Zt(e=1){let t="uint";if(e>1)t="uvec"+e;return`
		${t} sobolReverseBits( ${t} x ) {

			x = ( ( ( x & 0xaaaaaaaau ) >> 1 ) | ( ( x & 0x55555555u ) << 1 ) );
			x = ( ( ( x & 0xccccccccu ) >> 2 ) | ( ( x & 0x33333333u ) << 2 ) );
			x = ( ( ( x & 0xf0f0f0f0u ) >> 4 ) | ( ( x & 0x0f0f0f0fu ) << 4 ) );
			x = ( ( ( x & 0xff00ff00u ) >> 8 ) | ( ( x & 0x00ff00ffu ) << 8 ) );
			return ( ( x >> 16 ) | ( x << 16 ) );

		}

		${t} sobolHashCombine( uint seed, ${t} v ) {

			return seed ^ ( v + ${t}( ( seed << 6 ) + ( seed >> 2 ) ) );

		}

		${t} sobolLaineKarrasPermutation( ${t} x, ${t} seed ) {

			x += seed;
			x ^= x * 0x6c50b47cu;
			x ^= x * 0xb82f1e52u;
			x ^= x * 0xc7afe638u;
			x ^= x * 0x8d22f6e6u;
			return x;

		}

		${t} nestedUniformScrambleBase2( ${t} x, ${t} seed ) {

			x = sobolLaineKarrasPermutation( x, seed );
			x = sobolReverseBits( x );
			return x;

		}
	`}function Jt(e=1){let t="uint",r="float",o="",n=".r",i="1u";if(e>1)if(t="uvec"+e,r="vec"+e,o=e+"",e===2)n=".rg",i="uvec2( 1u, 2u )";else if(e===3)n=".rgb",i="uvec3( 1u, 2u, 3u )";else n="",i="uvec4( 1u, 2u, 3u, 4u )";return`

		${r} sobol${o}( int effect ) {

			uint seed = sobolGetSeed( sobolBounceIndex, uint( effect ) );
			uint index = sobolPathIndex;

			uint shuffle_seed = sobolHashCombine( seed, 0u );
			uint shuffled_index = nestedUniformScrambleBase2( sobolReverseBits( index ), shuffle_seed );
			${r} sobol_pt = sobolGetTexturePoint( shuffled_index )${n};
			${t} result = ${t}( sobol_pt * 16777216.0 );

			${t} seed2 = sobolHashCombine( seed, ${i} );
			result = nestedUniformScrambleBase2( result, seed2 );

			return SOBOL_FACTOR * ${r}( result >> 8 );

		}
	`}var er=`

	// Utils
	const float SOBOL_FACTOR = 1.0 / 16777216.0;
	const uint SOBOL_MAX_POINTS = 256u * 256u;

	${Zt(1)}
	${Zt(2)}
	${Zt(3)}
	${Zt(4)}

	uint sobolHash( uint x ) {

		// finalizer from murmurhash3
		x ^= x >> 16;
		x *= 0x85ebca6bu;
		x ^= x >> 13;
		x *= 0xc2b2ae35u;
		x ^= x >> 16;
		return x;

	}

`,Qo=`

	const uint SOBOL_DIRECTIONS_1[ 32 ] = uint[ 32 ](
		0x80000000u, 0xc0000000u, 0xa0000000u, 0xf0000000u,
		0x88000000u, 0xcc000000u, 0xaa000000u, 0xff000000u,
		0x80800000u, 0xc0c00000u, 0xa0a00000u, 0xf0f00000u,
		0x88880000u, 0xcccc0000u, 0xaaaa0000u, 0xffff0000u,
		0x80008000u, 0xc000c000u, 0xa000a000u, 0xf000f000u,
		0x88008800u, 0xcc00cc00u, 0xaa00aa00u, 0xff00ff00u,
		0x80808080u, 0xc0c0c0c0u, 0xa0a0a0a0u, 0xf0f0f0f0u,
		0x88888888u, 0xccccccccu, 0xaaaaaaaau, 0xffffffffu
	);

	const uint SOBOL_DIRECTIONS_2[ 32 ] = uint[ 32 ](
		0x80000000u, 0xc0000000u, 0x60000000u, 0x90000000u,
		0xe8000000u, 0x5c000000u, 0x8e000000u, 0xc5000000u,
		0x68800000u, 0x9cc00000u, 0xee600000u, 0x55900000u,
		0x80680000u, 0xc09c0000u, 0x60ee0000u, 0x90550000u,
		0xe8808000u, 0x5cc0c000u, 0x8e606000u, 0xc5909000u,
		0x6868e800u, 0x9c9c5c00u, 0xeeee8e00u, 0x5555c500u,
		0x8000e880u, 0xc0005cc0u, 0x60008e60u, 0x9000c590u,
		0xe8006868u, 0x5c009c9cu, 0x8e00eeeeu, 0xc5005555u
	);

	const uint SOBOL_DIRECTIONS_3[ 32 ] = uint[ 32 ](
		0x80000000u, 0xc0000000u, 0x20000000u, 0x50000000u,
		0xf8000000u, 0x74000000u, 0xa2000000u, 0x93000000u,
		0xd8800000u, 0x25400000u, 0x59e00000u, 0xe6d00000u,
		0x78080000u, 0xb40c0000u, 0x82020000u, 0xc3050000u,
		0x208f8000u, 0x51474000u, 0xfbea2000u, 0x75d93000u,
		0xa0858800u, 0x914e5400u, 0xdbe79e00u, 0x25db6d00u,
		0x58800080u, 0xe54000c0u, 0x79e00020u, 0xb6d00050u,
		0x800800f8u, 0xc00c0074u, 0x200200a2u, 0x50050093u
	);

	const uint SOBOL_DIRECTIONS_4[ 32 ] = uint[ 32 ](
		0x80000000u, 0x40000000u, 0x20000000u, 0xb0000000u,
		0xf8000000u, 0xdc000000u, 0x7a000000u, 0x9d000000u,
		0x5a800000u, 0x2fc00000u, 0xa1600000u, 0xf0b00000u,
		0xda880000u, 0x6fc40000u, 0x81620000u, 0x40bb0000u,
		0x22878000u, 0xb3c9c000u, 0xfb65a000u, 0xddb2d000u,
		0x78022800u, 0x9c0b3c00u, 0x5a0fb600u, 0x2d0ddb00u,
		0xa2878080u, 0xf3c9c040u, 0xdb65a020u, 0x6db2d0b0u,
		0x800228f8u, 0x400b3cdcu, 0x200fb67au, 0xb00ddb9du
	);

	uint getMaskedSobol( uint index, uint directions[ 32 ] ) {

		uint X = 0u;
		for ( int bit = 0; bit < 32; bit ++ ) {

			uint mask = ( index >> bit ) & 1u;
			X ^= mask * directions[ bit ];

		}
		return X;

	}

	vec4 generateSobolPoint( uint index ) {

		if ( index >= SOBOL_MAX_POINTS ) {

			return vec4( 0.0 );

		}

		// NOTE: this sobol "direction" is also available but we can't write out 5 components
		// uint x = index & 0x00ffffffu;
		uint x = sobolReverseBits( getMaskedSobol( index, SOBOL_DIRECTIONS_1 ) ) & 0x00ffffffu;
		uint y = sobolReverseBits( getMaskedSobol( index, SOBOL_DIRECTIONS_2 ) ) & 0x00ffffffu;
		uint z = sobolReverseBits( getMaskedSobol( index, SOBOL_DIRECTIONS_3 ) ) & 0x00ffffffu;
		uint w = sobolReverseBits( getMaskedSobol( index, SOBOL_DIRECTIONS_4 ) ) & 0x00ffffffu;

		return vec4( x, y, z, w ) * SOBOL_FACTOR;

	}

`,Zo=`

	// Seeds
	uniform sampler2D sobolTexture;
	uint sobolPixelIndex = 0u;
	uint sobolPathIndex = 0u;
	uint sobolBounceIndex = 0u;

	uint sobolGetSeed( uint bounce, uint effect ) {

		return sobolHash(
			sobolHashCombine(
				sobolHashCombine(
					sobolHash( bounce ),
					sobolPixelIndex
				),
				effect
			)
		);

	}

	vec4 sobolGetTexturePoint( uint index ) {

		if ( index >= SOBOL_MAX_POINTS ) {

			index = index % SOBOL_MAX_POINTS;

		}

		uvec2 dim = uvec2( textureSize( sobolTexture, 0 ).xy );
		uint y = index / dim.x;
		uint x = index - y * dim.x;
		vec2 uv = vec2( x, y ) / vec2( dim );
		return texture( sobolTexture, uv );

	}

	${Jt(1)}
	${Jt(2)}
	${Jt(3)}
	${Jt(4)}

`;class en extends _e{constructor(){super({blending:Za,uniforms:{resolution:{value:new ec}},vertexShader:`

				varying vec2 vUv;
				void main() {

					vUv = uv;
					gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

				}
			`,fragmentShader:`

				${er}
				${Qo}

				varying vec2 vUv;
				uniform vec2 resolution;
				void main() {

					uint index = uint( gl_FragCoord.y ) * uint( resolution.x ) + uint( gl_FragCoord.x );
					gl_FragColor = generateSobolPoint( index );

				}
			`})}}class oi{generate(e,t=256){let r=new tc(t,t,{type:Qa,format:Ja,minFilter:Jo,magFilter:Jo,generateMipmaps:!1}),o=e.getRenderTarget();e.setRenderTarget(r);let n=new Z(new en);return n.material.resolution.set(t,t),n.render(e),e.setRenderTarget(o),n.dispose(),r}}import{ClampToEdgeWrapping as Qn,HalfFloatType as Kc,Matrix4 as ar,Vector2 as Qc}from"./datacenter-engine.mjs";import{PerspectiveCamera as rc}from"./datacenter-engine.mjs";class ni extends rc{set bokehSize(e){this.fStop=this.getFocalLength()/e}get bokehSize(){return this.getFocalLength()/this.fStop}constructor(...e){super(...e);this.fStop=1.4,this.apertureBlades=0,this.apertureRotation=0,this.focusDistance=25,this.anamorphicRatio=1}copy(e,t){return super.copy(e,t),this.fStop=e.fStop,this.apertureBlades=e.apertureBlades,this.apertureRotation=e.apertureRotation,this.focusDistance=e.focusDistance,this.anamorphicRatio=e.anamorphicRatio,this}}class si{constructor(){this.bokehSize=0,this.apertureBlades=0,this.apertureRotation=0,this.focusDistance=10,this.anamorphicRatio=1}updateFrom(e){if(e instanceof ni)this.bokehSize=e.bokehSize,this.apertureBlades=e.apertureBlades,this.apertureRotation=e.apertureRotation,this.focusDistance=e.focusDistance,this.anamorphicRatio=e.anamorphicRatio;else this.bokehSize=0,this.apertureRotation=0,this.apertureBlades=0,this.focusDistance=10,this.anamorphicRatio=1}}import{DataTexture as ai,RedFormat as tn,LinearFilter as Ye,DataUtils as Ae,HalfFloatType as me,Source as oc,RepeatWrapping as ci,RGBAFormat as nc,FloatType as sc,ClampToEdgeWrapping as ac}from"./datacenter-engine.mjs";import{DataUtils as ic}from"./datacenter-engine.mjs";function tr(e){let t=new Uint16Array(e.length);for(let r=0,o=e.length;r<o;++r)t[r]=ic.toHalfFloat(e[r]);return t}function rn(e,t,r=0,o=e.length){let n=r,i=r+o-1;while(n<i){let s=n+i>>1;if(e[s]<t)n=s+1;else i=s}return n-r}function cc(e,t,r){return 0.2126*e+0.7152*t+0.0722*r}function lc(e,t=me){let r=e.clone();r.source=new oc({...r.image});let{width:o,height:n,data:i}=r.image,s=i;if(r.type!==t){if(t===me)s=new Uint16Array(i.length);else s=new Float32Array(i.length);let l;if(i instanceof Int8Array||i instanceof Int16Array||i instanceof Int32Array)l=2**(8*i.BYTES_PER_ELEMENT-1)-1;else l=2**(8*i.BYTES_PER_ELEMENT)-1;for(let c=0,m=i.length;c<m;c++){let u=i[c];if(r.type===me)u=Ae.fromHalfFloat(i[c]);if(r.type!==sc&&r.type!==me)u/=l;if(t===me)s[c]=Ae.toHalfFloat(u)}r.image.data=s,r.type=t}if(r.flipY){let l=s;s=s.slice();for(let c=0;c<n;c++)for(let m=0;m<o;m++){let u=n-c-1,a=4*(c*o+m),f=4*(u*o+m);s[f+0]=l[a+0],s[f+1]=l[a+1],s[f+2]=l[a+2],s[f+3]=l[a+3]}r.flipY=!1,r.image.data=s}return r}class li{constructor(){let e=new ai(tr(new Float32Array([0,0,0,0])),1,1);e.type=me,e.format=nc,e.minFilter=Ye,e.magFilter=Ye,e.wrapS=ci,e.wrapT=ci,e.generateMipmaps=!1,e.needsUpdate=!0;let t=new ai(tr(new Float32Array([0,1])),1,2);t.type=me,t.format=tn,t.minFilter=Ye,t.magFilter=Ye,t.generateMipmaps=!1,t.needsUpdate=!0;let r=new ai(tr(new Float32Array([0,0,1,1])),2,2);r.type=me,r.format=tn,r.minFilter=Ye,r.magFilter=Ye,r.generateMipmaps=!1,r.needsUpdate=!0,this.map=e,this.marginalWeights=t,this.conditionalWeights=r,this.totalSum=0}getPixelWeight(e,t,r){return cc(e,t,r)}dispose(){this.marginalWeights.dispose(),this.conditionalWeights.dispose(),this.map.dispose()}updateFrom(e){let t=lc(e);t.wrapS=ci,t.wrapT=ac;let{width:r,height:o,data:n}=t.image,i=new Float32Array(r*o),s=new Float32Array(r*o),l=new Float32Array(o),c=new Float32Array(o),m=0,u=0;for(let d=0;d<o;d++){let b=0;for(let T=0;T<r;T++){let p=d*r+T,x=Ae.fromHalfFloat(n[4*p+0]),v=Ae.fromHalfFloat(n[4*p+1]),y=Ae.fromHalfFloat(n[4*p+2]),w=this.getPixelWeight(x,v,y,d,o);b+=w,m+=w,i[p]=w,s[p]=b}if(b!==0)for(let T=d*r,p=d*r+r;T<p;T++)i[T]/=b,s[T]/=b;u+=b,l[d]=b,c[d]=u}if(u!==0)for(let d=0,b=l.length;d<b;d++)l[d]/=u,c[d]/=u;let a=new Uint16Array(o),f=new Uint16Array(r*o);for(let d=0;d<o;d++){let b=(d+1)/o,T=rn(c,b);a[d]=Ae.toHalfFloat((T+0.5)/o)}for(let d=0;d<o;d++)for(let b=0;b<r;b++){let T=d*r+b,p=(b+1)/r,x=rn(s,p,d*r,r);f[T]=Ae.toHalfFloat((x+0.5)/r)}this.dispose();let{marginalWeights:h,conditionalWeights:g}=this;h.image={width:o,height:1,data:a},h.needsUpdate=!0,g.image={width:r,height:o,data:f},g.needsUpdate=!0,this.totalSum=m,this.map=t}}import{DataTexture as uc,RGBAFormat as fc,ClampToEdgeWrapping as on,FloatType as mc,Vector3 as yt,Quaternion as hc,Matrix4 as dc,NearestFilter as nn}from"./datacenter-engine.mjs";var ui=6,pc=0,gc=1,vc=2,xc=3,yc=4,te=new yt,X=new yt,sn=new dc,$e=new hc,an=new yt,Xe=new yt,bc=new yt(0,1,0);class fi{constructor(){let e=new uc(new Float32Array(4),1,1);e.format=fc,e.type=mc,e.wrapS=on,e.wrapT=on,e.generateMipmaps=!1,e.minFilter=nn,e.magFilter=nn,this.tex=e,this.count=0}updateFrom(e,t=[]){let r=this.tex,o=Math.max(e.length*ui,1),n=Math.ceil(Math.sqrt(o));if(r.image.width!==n)r.dispose(),r.image.data=new Float32Array(n*n*4),r.image.width=n,r.image.height=n;let i=r.image.data;for(let l=0,c=e.length;l<c;l++){let m=e[l],u=l*ui*4,a=0;for(let h=0;h<ui*4;h++)i[u+h]=0;m.getWorldPosition(X),i[u+a++]=X.x,i[u+a++]=X.y,i[u+a++]=X.z;let f=pc;if(m.isRectAreaLight&&m.isCircular)f=gc;else if(m.isSpotLight)f=vc;else if(m.isDirectionalLight)f=xc;else if(m.isPointLight)f=yc;if(i[u+a++]=f,i[u+a++]=m.color.r,i[u+a++]=m.color.g,i[u+a++]=m.color.b,i[u+a++]=m.intensity,m.getWorldQuaternion($e),m.isRectAreaLight)te.set(m.width,0,0).applyQuaternion($e),i[u+a++]=te.x,i[u+a++]=te.y,i[u+a++]=te.z,a++,X.set(0,m.height,0).applyQuaternion($e),i[u+a++]=X.x,i[u+a++]=X.y,i[u+a++]=X.z,i[u+a++]=te.cross(X).length()*(m.isCircular?Math.PI/4:1);else if(m.isSpotLight){let h=m.radius||0;an.setFromMatrixPosition(m.matrixWorld),Xe.setFromMatrixPosition(m.target.matrixWorld),sn.lookAt(an,Xe,bc),$e.setFromRotationMatrix(sn),te.set(1,0,0).applyQuaternion($e),i[u+a++]=te.x,i[u+a++]=te.y,i[u+a++]=te.z,a++,X.set(0,1,0).applyQuaternion($e),i[u+a++]=X.x,i[u+a++]=X.y,i[u+a++]=X.z,i[u+a++]=Math.PI*h*h,i[u+a++]=h,i[u+a++]=m.decay,i[u+a++]=m.distance,i[u+a++]=Math.cos(m.angle),i[u+a++]=Math.cos(m.angle*(1-m.penumbra)),i[u+a++]=m.iesMap?t.indexOf(m.iesMap):-1}else if(m.isPointLight){let h=te.setFromMatrixPosition(m.matrixWorld);i[u+a++]=h.x,i[u+a++]=h.y,i[u+a++]=h.z,a++,a+=4,a+=1,i[u+a++]=m.decay,i[u+a++]=m.distance}else if(m.isDirectionalLight){let h=te.setFromMatrixPosition(m.matrixWorld),g=X.setFromMatrixPosition(m.target.matrixWorld);Xe.subVectors(h,g).normalize(),i[u+a++]=Xe.x,i[u+a++]=Xe.y,i[u+a++]=Xe.z}}this.count=e.length;let s=qe(i.buffer);if(this.hash!==s)return this.hash=s,r.needsUpdate=!0,!0;return!1}}import{DataArrayTexture as Tc,FloatType as wc,RGBAFormat as Sc}from"./datacenter-engine.mjs";function cn(e,t,r,o,n){if(t>o)throw Error();let i=e.length/t,s=e.constructor.BYTES_PER_ELEMENT*8,l=1;switch(e.constructor){case Uint8Array:case Uint16Array:case Uint32Array:l=2**s-1;break;case Int8Array:case Int16Array:case Int32Array:l=2**(s-1)-1;break}for(let c=0;c<i;c++){let m=4*c,u=t*c;for(let a=0;a<o;a++)r[n+m+a]=t>=a+1?e[u+a]/l:0}}class mi extends Tc{constructor(){super();this._textures=[],this.type=wc,this.format=Sc,this.internalFormat="RGBA32F"}updateAttribute(e,t){let r=this._textures[e];r.updateFrom(t);let o=r.image,n=this.image;if(o.width!==n.width||o.height!==n.height)throw Error("FloatAttributeTextureArray: Attribute must be the same dimensions when updating single layer.");let{width:i,height:s,data:l}=n,m=i*s*4*e,u=t.itemSize;if(u===3)u=4;cn(r.image.data,u,l,4,m),this.dispose(),this.needsUpdate=!0}setAttributes(e){let t=e[0].count,r=e.length;for(let u=0,a=r;u<a;u++)if(e[u].count!==t)throw Error("FloatAttributeTextureArray: All attributes must have the same item count.");let o=this._textures;while(o.length<r){let u=new gt;o.push(u)}while(o.length>r)o.pop();for(let u=0,a=r;u<a;u++)o[u].updateFrom(e[u]);let i=o[0].image,s=this.image;if(i.width!==s.width||i.height!==s.height||i.depth!==r)s.width=i.width,s.height=i.height,s.depth=r,s.data=new Float32Array(s.width*s.height*s.depth*4);let{data:l,width:c,height:m}=s;for(let u=0,a=r;u<a;u++){let f=o[u],g=c*m*4*u,d=e[u].itemSize;if(d===3)d=4;cn(f.image.data,d,l,4,g)}this.dispose(),this.needsUpdate=!0}}class hi extends mi{updateNormalAttribute(e){this.updateAttribute(0,e)}updateTangentAttribute(e){this.updateAttribute(1,e)}updateUvAttribute(e){this.updateAttribute(2,e)}updateColorAttribute(e){this.updateAttribute(3,e)}updateFrom(e,t,r,o){this.setAttributes([e,t,r,o])}}import{DataTexture as Ac,RGBAFormat as Ic,ClampToEdgeWrapping as mn,FloatType as Rc,FrontSide as Pc,BackSide as Fc,DoubleSide as Mc,NearestFilter as hn}from"./datacenter-engine.mjs";function di(e,t){if(e.uuid<t.uuid)return 1;if(e.uuid>t.uuid)return-1;return 0}function rr(e){return`${e.source.uuid}:${e.colorSpace}`}function _c(e){let t=new Set,r=[];for(let o=0,n=e.length;o<n;o++){let i=e[o],s=rr(i);if(!t.has(s))t.add(s),r.push(i)}return r}function ln(e){let t=e.map((o)=>o.iesMap||null).filter((o)=>o),r=new Set(t);return Array.from(r).sort(di)}function un(e){let t=new Set;for(let o=0,n=e.length;o<n;o++){let i=e[o];for(let s in i){let l=i[s];if(l&&l.isTexture)t.add(l)}}let r=Array.from(t);return _c(r).sort(di)}function fn(e){let t=[];return e.traverseVisible((r)=>{if(r.isRectAreaLight||r.isSpotLight||r.isPointLight||r.isDirectionalLight)t.push(r)}),t.sort(di)}var ir=47,dn=ir*4;class pn{constructor(){this._features={}}isUsed(e){return e in this._features}setUsed(e,t=!0){if(t===!1)delete this._features[e];else this._features[e]=!0}reset(){this._features={}}}class pi extends Ac{constructor(){super(new Float32Array(4),1,1);this.format=Ic,this.type=Rc,this.wrapS=mn,this.wrapT=mn,this.minFilter=hn,this.magFilter=hn,this.generateMipmaps=!1,this.features=new pn}updateFrom(e,t){function r(h,g,d=-1){if(g in h&&h[g]){let b=rr(h[g]);return u[b]}else return d}function o(h,g,d){return g in h?h[g]:d}function n(h,g,d,b){let T=h[g]&&h[g].isTexture?h[g]:null;if(T){if(T.matrixAutoUpdate)T.updateMatrix();let p=T.matrix.elements,x=0;d[b+x++]=p[0],d[b+x++]=p[3],d[b+x++]=p[6],x++,d[b+x++]=p[1],d[b+x++]=p[4],d[b+x++]=p[7],x++}return 8}let i=0,s=e.length*ir,l=Math.ceil(Math.sqrt(s))||1,{image:c,features:m}=this,u={};for(let h=0,g=t.length;h<g;h++)u[rr(t[h])]=h;if(c.width!==l)this.dispose(),c.data=new Float32Array(l*l*4),c.width=l,c.height=l;let a=c.data;m.reset();for(let h=0,g=e.length;h<g;h++){let d=e[h];if(d.isFogVolumeMaterial){m.setUsed("FOG");for(let p=0;p<dn;p++)a[i+p]=0;a[i+0+0]=d.color.r,a[i+0+1]=d.color.g,a[i+0+2]=d.color.b,a[i+8+3]=o(d,"emissiveIntensity",0),a[i+12+0]=d.emissive.r,a[i+12+1]=d.emissive.g,a[i+12+2]=d.emissive.b,a[i+52+1]=d.density,a[i+52+3]=0,a[i+56+2]=4,i+=dn;continue}if(a[i++]=d.color.r,a[i++]=d.color.g,a[i++]=d.color.b,a[i++]=r(d,"map"),a[i++]=o(d,"metalness",0),a[i++]=r(d,"metalnessMap"),a[i++]=o(d,"roughness",0),a[i++]=r(d,"roughnessMap"),a[i++]=o(d,"ior",1.5),a[i++]=o(d,"transmission",0),a[i++]=r(d,"transmissionMap"),a[i++]=o(d,"emissiveIntensity",0),"emissive"in d)a[i++]=d.emissive.r,a[i++]=d.emissive.g,a[i++]=d.emissive.b;else a[i++]=0,a[i++]=0,a[i++]=0;if(a[i++]=r(d,"emissiveMap"),a[i++]=r(d,"normalMap"),"normalScale"in d)a[i++]=d.normalScale.x,a[i++]=d.normalScale.y;else a[i++]=1,a[i++]=1;if(a[i++]=o(d,"clearcoat",0),a[i++]=r(d,"clearcoatMap"),a[i++]=o(d,"clearcoatRoughness",0),a[i++]=r(d,"clearcoatRoughnessMap"),a[i++]=r(d,"clearcoatNormalMap"),"clearcoatNormalScale"in d)a[i++]=d.clearcoatNormalScale.x,a[i++]=d.clearcoatNormalScale.y;else a[i++]=1,a[i++]=1;if(i++,a[i++]=o(d,"sheen",0),"sheenColor"in d)a[i++]=d.sheenColor.r,a[i++]=d.sheenColor.g,a[i++]=d.sheenColor.b;else a[i++]=0,a[i++]=0,a[i++]=0;a[i++]=r(d,"sheenColorMap"),a[i++]=o(d,"sheenRoughness",0),a[i++]=r(d,"sheenRoughnessMap"),a[i++]=r(d,"iridescenceMap"),a[i++]=r(d,"iridescenceThicknessMap"),a[i++]=o(d,"iridescence",0),a[i++]=o(d,"iridescenceIOR",1.3);let b=o(d,"iridescenceThicknessRange",[100,400]);if(a[i++]=b[0],a[i++]=b[1],"specularColor"in d)a[i++]=d.specularColor.r,a[i++]=d.specularColor.g,a[i++]=d.specularColor.b;else a[i++]=1,a[i++]=1,a[i++]=1;a[i++]=r(d,"specularColorMap"),a[i++]=o(d,"specularIntensity",1),a[i++]=r(d,"specularIntensityMap");let T=o(d,"thickness",0)===0&&o(d,"attenuationDistance",1/0)===1/0;if(a[i++]=Number(T),i++,"attenuationColor"in d)a[i++]=d.attenuationColor.r,a[i++]=d.attenuationColor.g,a[i++]=d.attenuationColor.b;else a[i++]=1,a[i++]=1,a[i++]=1;if(a[i++]=o(d,"attenuationDistance",1/0),a[i++]=r(d,"alphaMap"),a[i++]=d.opacity,a[i++]=d.alphaTest,!T&&d.transmission>0)a[i++]=0;else switch(d.side){case Pc:a[i++]=1;break;case Fc:a[i++]=-1;break;case Mc:a[i++]=0;break}a[i++]=Number(o(d,"matte",!1)),a[i++]=Number(o(d,"castShadow",!0)),a[i++]=Number(d.vertexColors)|Number(d.flatShading)<<1,a[i++]=Number(d.transparent),i+=n(d,"map",a,i),i+=n(d,"metalnessMap",a,i),i+=n(d,"roughnessMap",a,i),i+=n(d,"transmissionMap",a,i),i+=n(d,"emissiveMap",a,i),i+=n(d,"normalMap",a,i),i+=n(d,"clearcoatMap",a,i),i+=n(d,"clearcoatNormalMap",a,i),i+=n(d,"clearcoatRoughnessMap",a,i),i+=n(d,"sheenColorMap",a,i),i+=n(d,"sheenRoughnessMap",a,i),i+=n(d,"iridescenceMap",a,i),i+=n(d,"iridescenceThicknessMap",a,i),i+=n(d,"specularColorMap",a,i),i+=n(d,"specularIntensityMap",a,i),i+=n(d,"alphaMap",a,i)}let f=qe(a.buffer);if(this.hash!==f)return this.hash=f,this.needsUpdate=!0,!0;return!1}}import{WebGLArrayRenderTarget as Dc,RGBAFormat as Cc,UnsignedByteType as Ec,Color as Bc,RepeatWrapping as gn,LinearFilter as vn,NoToneMapping as Nc,ShaderMaterial as Lc}from"./datacenter-engine.mjs";var xn=new Bc;function Oc(e){return e?`${e.uuid}:${e.version}`:null}function zc(e,t){for(let r in t)if(r in e)e[r]=t[r]}class or extends Dc{constructor(e,t,r){let o={format:Cc,type:Ec,minFilter:vn,magFilter:vn,wrapS:gn,wrapT:gn,generateMipmaps:!1,...r};super(e,t,1,o);zc(this.texture,o),this.texture.setTextures=(...i)=>{this.setTextures(...i)},this.hashes=[null];let n=new Z(new yn);this.fsQuad=n}setTextures(e,t,r=this.width,o=this.height){let n=e.getRenderTarget(),i=e.toneMapping,s=e.getClearAlpha();e.getClearColor(xn);let l=t.length||1;if(r!==this.width||o!==this.height||this.depth!==l)this.setSize(r,o,l),this.hashes=Array(l).fill(null);e.setClearColor(0,0),e.toneMapping=Nc;let c=this.fsQuad,m=this.hashes,u=!1;for(let a=0,f=l;a<f;a++){let h=t[a],g=Oc(h);if(h&&(m[a]!==g||h.isWebGLRenderTarget))h.matrixAutoUpdate=!1,h.matrix.identity(),c.material.map=h,e.setRenderTarget(this,a),c.render(e),h.updateMatrix(),h.matrixAutoUpdate=!0,m[a]=g,u=!0}return c.material.map=null,e.setClearColor(xn,s),e.setRenderTarget(n),e.toneMapping=i,u}dispose(){super.dispose(),this.fsQuad.dispose()}}class yn extends Lc{get map(){return this.uniforms.map.value}set map(e){this.uniforms.map.value=e}constructor(){super({uniforms:{map:{value:null}},vertexShader:`
				varying vec2 vUv;
				void main() {

					vUv = uv;
					gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

				}
			`,fragmentShader:`
				uniform sampler2D map;
				varying vec2 vUv;
				void main() {

					gl_FragColor = texture2D( map, vUv );

				}
			`})}}import{DataTexture as Hc,FloatType as Uc,NearestFilter as bn,RGBAFormat as Vc}from"./datacenter-engine.mjs";function kc(e,t=Math.random()){for(let r=e.length-1;r>0;r--){let o=Math.floor(t()*(r+1)),n=e[r];e[r]=e[o],e[o]=n}return e}class gi{constructor(e,t,r=Math.random){let o=e**t,n=new Uint16Array(o),i=o;for(let s=0;s<o;s++)n[s]=s;this.samples=new Float32Array(t),this.strataCount=e,this.reset=function(){for(let s=0;s<o;s++)n[s]=s;i=0},this.reshuffle=function(){i=0},this.next=function(){let{samples:s}=this;if(i>=n.length)kc(n,r),this.reshuffle();let l=n[i++];for(let c=0;c<t;c++)s[c]=(l%e+r())/e,l=Math.floor(l/e);return s}}}class vi{constructor(e,t,r=Math.random){let o=0;for(let l of t)o+=l;let n=new Float32Array(o),i=[],s=0;for(let l of t){let c=new gi(e,l,r);c.samples=new Float32Array(n.buffer,s,c.samples.length),s+=c.samples.length*4,i.push(c)}this.samples=n,this.strataCount=e,this.next=function(){for(let l of i)l.next();return n},this.reshuffle=function(){for(let l of i)l.reshuffle()},this.reset=function(){for(let l of i)l.reset()}}}class Tn{constructor(e=0){this.m=2147483648,this.a=1103515245,this.c=12345,this.seed=e}nextInt(){return this.seed=(this.a*this.seed+this.c)%this.m,this.seed}nextFloat(){return this.nextInt()/(this.m-1)}}class xi extends Hc{constructor(e=1,t=1,r=8){super(new Float32Array(1),1,1,Vc,Uc);this.minFilter=bn,this.magFilter=bn,this.strata=r,this.sampler=null,this.generator=new Tn,this.stableNoise=!1,this.random=()=>{if(this.stableNoise)return this.generator.nextFloat();else return Math.random()},this.init(e,t,r)}init(e=this.image.height,t=this.image.width,r=this.strata){let{image:o}=this;if(o.width===t&&o.height===e&&this.sampler!==null)return;let n=Array(e*t).fill(4),i=new vi(r,n,this.random);o.width=t,o.height=e,o.data=i.samples,this.sampler=i,this.dispose(),this.next()}next(){this.sampler.next(),this.needsUpdate=!0}reset(){this.sampler.reset(),this.generator.seed=0}}import{DataTexture as Wc,FloatType as Gc,NearestFilter as _n,RGBAFormat as An,RGFormat as qc,RedFormat as Yc}from"./datacenter-engine.mjs";function wn(e,t=Math.random){for(let r=e.length-1;r>0;r--){let o=~~((t()-0.000001)*r),n=e[r];e[r]=e[o],e[o]=n}}function Sn(e,t){e.fill(0);for(let r=0;r<t;r++)e[r]=1}class nr{constructor(e){this.count=0,this.size=-1,this.sigma=-1,this.radius=-1,this.lookupTable=null,this.score=null,this.binaryPattern=null,this.resize(e),this.setSigma(1.5)}findVoid(){let{score:e,binaryPattern:t}=this,r=1/0,o=-1;for(let n=0,i=t.length;n<i;n++){if(t[n]!==0)continue;let s=e[n];if(s<r)r=s,o=n}return o}findCluster(){let{score:e,binaryPattern:t}=this,r=-1/0,o=-1;for(let n=0,i=t.length;n<i;n++){if(t[n]!==1)continue;let s=e[n];if(s>r)r=s,o=n}return o}setSigma(e){if(e===this.sigma)return;let t=~~(Math.sqrt(20*e**2)+1),r=2*t+1,o=new Float32Array(r*r),n=e*e;for(let i=-t;i<=t;i++)for(let s=-t;s<=t;s++){let l=(t+s)*r+i+t,c=i*i+s*s;o[l]=Math.E**(-c/(2*n))}this.lookupTable=o,this.sigma=e,this.radius=t}resize(e){if(this.size!==e)this.size=e,this.score=new Float32Array(e*e),this.binaryPattern=new Uint8Array(e*e)}invert(){let{binaryPattern:e,score:t,size:r}=this;t.fill(0);for(let o=0,n=e.length;o<n;o++)if(e[o]===0){let i=~~(o/r),s=o-i*r;this.updateScore(s,i,1),e[o]=1}else e[o]=0}updateScore(e,t,r){let{size:o,score:n,lookupTable:i}=this,s=this.radius,l=2*s+1;for(let c=-s;c<=s;c++)for(let m=-s;m<=s;m++){let u=(s+m)*l+c+s,a=i[u],f=e+c;f=f<0?o+f:f%o;let h=t+m;h=h<0?o+h:h%o;let g=h*o+f;n[g]+=r*a}}addPointIndex(e){this.binaryPattern[e]=1;let t=this.size,r=~~(e/t),o=e-r*t;this.updateScore(o,r,1),this.count++}removePointIndex(e){this.binaryPattern[e]=0;let t=this.size,r=~~(e/t),o=e-r*t;this.updateScore(o,r,-1),this.count--}copy(e){this.resize(e.size),this.score.set(e.score),this.binaryPattern.set(e.binaryPattern),this.setSigma(e.sigma),this.count=e.count}}class yi{constructor(){this.random=Math.random,this.sigma=1.5,this.size=64,this.majorityPointsRatio=0.1,this.samples=new nr(1),this.savedSamples=new nr(1)}generate(){let{samples:e,savedSamples:t,sigma:r,majorityPointsRatio:o,size:n}=this;e.resize(n),e.setSigma(r);let i=Math.floor(n*n*o),s=e.binaryPattern;Sn(s,i),wn(s,this.random);for(let u=0,a=s.length;u<a;u++)if(s[u]===1)e.addPointIndex(u);while(!0){let u=e.findCluster();e.removePointIndex(u);let a=e.findVoid();if(u===a){e.addPointIndex(u);break}e.addPointIndex(a)}let l=new Uint32Array(n*n);t.copy(e);let c;c=e.count-1;while(c>=0){let u=e.findCluster();e.removePointIndex(u),l[u]=c,c--}let m=n*n;c=t.count;while(c<m/2){let u=t.findVoid();t.addPointIndex(u),l[u]=c,c++}t.invert();while(c<m){let u=t.findCluster();t.removePointIndex(u),l[u]=c,c++}return{data:l,maxValue:m}}}function $c(e){if(e>=3)return 4;else return e}function Xc(e){switch(e){case 1:return Yc;case 2:return qc;default:return An}}class bi extends Wc{constructor(e=64,t=1){super(new Float32Array(4),1,1,An,Gc);this.minFilter=_n,this.magFilter=_n,this.size=e,this.channels=t,this.update()}update(){let e=this.channels,t=this.size,r=new yi;r.channels=e,r.size=t;let o=$c(e),n=Xc(o);if(this.image.width!==t||n!==this.format)this.image.width=t,this.image.height=t,this.image.data=new Float32Array(t**2*o),this.format=n,this.dispose();let i=this.image.data;for(let s=0,l=e;s<l;s++){let c=r.generate(),m=c.data,u=c.maxValue;for(let a=0,f=m.length;a<f;a++){let h=m[a]/u;i[a*o+s]=h}}this.needsUpdate=!0}}var In=`

	struct PhysicalCamera {

		float focusDistance;
		float anamorphicRatio;
		float bokehSize;
		int apertureBlades;
		float apertureRotation;

	};

`;var Rn=`

	struct EquirectHdrInfo {

		sampler2D marginalWeights;
		sampler2D conditionalWeights;
		sampler2D map;

		float totalSum;

	};

`;var Pn=`

	#define RECT_AREA_LIGHT_TYPE 0
	#define CIRC_AREA_LIGHT_TYPE 1
	#define SPOT_LIGHT_TYPE 2
	#define DIR_LIGHT_TYPE 3
	#define POINT_LIGHT_TYPE 4

	struct LightsInfo {

		sampler2D tex;
		uint count;

	};

	struct Light {

		vec3 position;
		int type;

		vec3 color;
		float intensity;

		vec3 u;
		vec3 v;
		float area;

		// spot light fields
		float radius;
		float near;
		float decay;
		float distance;
		float coneCos;
		float penumbraCos;
		int iesProfile;

	};

	Light readLightInfo( sampler2D tex, uint index ) {

		uint i = index * 6u;

		vec4 s0 = texelFetch1D( tex, i + 0u );
		vec4 s1 = texelFetch1D( tex, i + 1u );
		vec4 s2 = texelFetch1D( tex, i + 2u );
		vec4 s3 = texelFetch1D( tex, i + 3u );

		Light l;
		l.position = s0.rgb;
		l.type = int( round( s0.a ) );

		l.color = s1.rgb;
		l.intensity = s1.a;

		l.u = s2.rgb;
		l.v = s3.rgb;
		l.area = s3.a;

		if ( l.type == SPOT_LIGHT_TYPE || l.type == POINT_LIGHT_TYPE ) {

			vec4 s4 = texelFetch1D( tex, i + 4u );
			vec4 s5 = texelFetch1D( tex, i + 5u );
			l.radius = s4.r;
			l.decay = s4.g;
			l.distance = s4.b;
			l.coneCos = s4.a;

			l.penumbraCos = s5.r;
			l.iesProfile = int( round( s5.g ) );

		} else {

			l.radius = 0.0;
			l.decay = 0.0;
			l.distance = 0.0;

			l.coneCos = 0.0;
			l.penumbraCos = 0.0;
			l.iesProfile = - 1;

		}

		return l;

	}

`;var Fn=`

	struct Material {

		vec3 color;
		int map;

		float metalness;
		int metalnessMap;

		float roughness;
		int roughnessMap;

		float ior;
		float transmission;
		int transmissionMap;

		float emissiveIntensity;
		vec3 emissive;
		int emissiveMap;

		int normalMap;
		vec2 normalScale;

		float clearcoat;
		int clearcoatMap;
		int clearcoatNormalMap;
		vec2 clearcoatNormalScale;
		float clearcoatRoughness;
		int clearcoatRoughnessMap;

		int iridescenceMap;
		int iridescenceThicknessMap;
		float iridescence;
		float iridescenceIor;
		float iridescenceThicknessMinimum;
		float iridescenceThicknessMaximum;

		vec3 specularColor;
		int specularColorMap;

		float specularIntensity;
		int specularIntensityMap;
		bool thinFilm;

		vec3 attenuationColor;
		float attenuationDistance;

		int alphaMap;

		bool castShadow;
		float opacity;
		float alphaTest;

		float side;
		bool matte;

		float sheen;
		vec3 sheenColor;
		int sheenColorMap;
		float sheenRoughness;
		int sheenRoughnessMap;

		bool vertexColors;
		bool flatShading;
		bool transparent;
		bool fogVolume;

		mat3 mapTransform;
		mat3 metalnessMapTransform;
		mat3 roughnessMapTransform;
		mat3 transmissionMapTransform;
		mat3 emissiveMapTransform;
		mat3 normalMapTransform;
		mat3 clearcoatMapTransform;
		mat3 clearcoatNormalMapTransform;
		mat3 clearcoatRoughnessMapTransform;
		mat3 sheenColorMapTransform;
		mat3 sheenRoughnessMapTransform;
		mat3 iridescenceMapTransform;
		mat3 iridescenceThicknessMapTransform;
		mat3 specularColorMapTransform;
		mat3 specularIntensityMapTransform;
		mat3 alphaMapTransform;

	};

	mat3 readTextureTransform( sampler2D tex, uint index ) {

		mat3 textureTransform;

		vec4 row1 = texelFetch1D( tex, index );
		vec4 row2 = texelFetch1D( tex, index + 1u );

		textureTransform[0] = vec3(row1.r, row2.r, 0.0);
		textureTransform[1] = vec3(row1.g, row2.g, 0.0);
		textureTransform[2] = vec3(row1.b, row2.b, 1.0);

		return textureTransform;

	}

	Material readMaterialInfo( sampler2D tex, uint index ) {

		uint i = index * uint( MATERIAL_PIXELS );

		vec4 s0 = texelFetch1D( tex, i + 0u );
		vec4 s1 = texelFetch1D( tex, i + 1u );
		vec4 s2 = texelFetch1D( tex, i + 2u );
		vec4 s3 = texelFetch1D( tex, i + 3u );
		vec4 s4 = texelFetch1D( tex, i + 4u );
		vec4 s5 = texelFetch1D( tex, i + 5u );
		vec4 s6 = texelFetch1D( tex, i + 6u );
		vec4 s7 = texelFetch1D( tex, i + 7u );
		vec4 s8 = texelFetch1D( tex, i + 8u );
		vec4 s9 = texelFetch1D( tex, i + 9u );
		vec4 s10 = texelFetch1D( tex, i + 10u );
		vec4 s11 = texelFetch1D( tex, i + 11u );
		vec4 s12 = texelFetch1D( tex, i + 12u );
		vec4 s13 = texelFetch1D( tex, i + 13u );
		vec4 s14 = texelFetch1D( tex, i + 14u );

		Material m;
		m.color = s0.rgb;
		m.map = int( round( s0.a ) );

		m.metalness = s1.r;
		m.metalnessMap = int( round( s1.g ) );
		m.roughness = s1.b;
		m.roughnessMap = int( round( s1.a ) );

		m.ior = s2.r;
		m.transmission = s2.g;
		m.transmissionMap = int( round( s2.b ) );
		m.emissiveIntensity = s2.a;

		m.emissive = s3.rgb;
		m.emissiveMap = int( round( s3.a ) );

		m.normalMap = int( round( s4.r ) );
		m.normalScale = s4.gb;

		m.clearcoat = s4.a;
		m.clearcoatMap = int( round( s5.r ) );
		m.clearcoatRoughness = s5.g;
		m.clearcoatRoughnessMap = int( round( s5.b ) );
		m.clearcoatNormalMap = int( round( s5.a ) );
		m.clearcoatNormalScale = s6.rg;

		m.sheen = s6.a;
		m.sheenColor = s7.rgb;
		m.sheenColorMap = int( round( s7.a ) );
		m.sheenRoughness = s8.r;
		m.sheenRoughnessMap = int( round( s8.g ) );

		m.iridescenceMap = int( round( s8.b ) );
		m.iridescenceThicknessMap = int( round( s8.a ) );
		m.iridescence = s9.r;
		m.iridescenceIor = s9.g;
		m.iridescenceThicknessMinimum = s9.b;
		m.iridescenceThicknessMaximum = s9.a;

		m.specularColor = s10.rgb;
		m.specularColorMap = int( round( s10.a ) );

		m.specularIntensity = s11.r;
		m.specularIntensityMap = int( round( s11.g ) );
		m.thinFilm = bool( s11.b );

		m.attenuationColor = s12.rgb;
		m.attenuationDistance = s12.a;

		m.alphaMap = int( round( s13.r ) );

		m.opacity = s13.g;
		m.alphaTest = s13.b;
		m.side = s13.a;

		m.matte = bool( s14.r );
		m.castShadow = bool( s14.g );
		m.vertexColors = bool( int( s14.b ) & 1 );
		m.flatShading = bool( int( s14.b ) & 2 );
		m.fogVolume = bool( int( s14.b ) & 4 );
		m.transparent = bool( s14.a );

		uint firstTextureTransformIdx = i + 15u;

		// mat3( 1.0 ) is an identity matrix
		m.mapTransform = m.map == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx );
		m.metalnessMapTransform = m.metalnessMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 2u );
		m.roughnessMapTransform = m.roughnessMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 4u );
		m.transmissionMapTransform = m.transmissionMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 6u );
		m.emissiveMapTransform = m.emissiveMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 8u );
		m.normalMapTransform = m.normalMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 10u );
		m.clearcoatMapTransform = m.clearcoatMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 12u );
		m.clearcoatNormalMapTransform = m.clearcoatNormalMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 14u );
		m.clearcoatRoughnessMapTransform = m.clearcoatRoughnessMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 16u );
		m.sheenColorMapTransform = m.sheenColorMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 18u );
		m.sheenRoughnessMapTransform = m.sheenRoughnessMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 20u );
		m.iridescenceMapTransform = m.iridescenceMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 22u );
		m.iridescenceThicknessMapTransform = m.iridescenceThicknessMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 24u );
		m.specularColorMapTransform = m.specularColorMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 26u );
		m.specularIntensityMapTransform = m.specularIntensityMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 28u );
		m.alphaMapTransform = m.alphaMap == - 1 ? mat3( 1.0 ) : readTextureTransform( tex, firstTextureTransformIdx + 30u );

		return m;

	}

`;var Mn=`

	struct SurfaceRecord {

		// surface type
		bool volumeParticle;

		// geometry
		vec3 faceNormal;
		bool frontFace;
		vec3 normal;
		mat3 normalBasis;
		mat3 normalInvBasis;

		// cached properties
		float eta;
		float f0;

		// material
		float roughness;
		float filteredRoughness;
		float metalness;
		vec3 color;
		vec3 emission;

		// transmission
		float ior;
		float transmission;
		bool thinFilm;
		vec3 attenuationColor;
		float attenuationDistance;

		// clearcoat
		vec3 clearcoatNormal;
		mat3 clearcoatBasis;
		mat3 clearcoatInvBasis;
		float clearcoat;
		float clearcoatRoughness;
		float filteredClearcoatRoughness;

		// sheen
		float sheen;
		vec3 sheenColor;
		float sheenRoughness;

		// iridescence
		float iridescence;
		float iridescenceIor;
		float iridescenceThickness;

		// specular
		vec3 specularColor;
		float specularIntensity;
	};

	struct ScatterRecord {
		float specularPdf;
		float pdf;
		vec3 direction;
		vec3 color;
	};

`;var Dn=`

	// samples the the given environment map in the given direction
	vec3 sampleEquirectColor( sampler2D envMap, vec3 direction ) {

		return texture2D( envMap, equirectDirectionToUv( direction ) ).rgb;

	}

	// gets the pdf of the given direction to sample
	float equirectDirectionPdf( vec3 direction ) {

		vec2 uv = equirectDirectionToUv( direction );
		float theta = uv.y * PI;
		float sinTheta = sin( theta );
		if ( sinTheta == 0.0 ) {

			return 0.0;

		}

		return 1.0 / ( 2.0 * PI * PI * sinTheta );

	}

	// samples the color given env map with CDF and returns the pdf of the direction
	float sampleEquirect( vec3 direction, inout vec3 color ) {

		float totalSum = envMapInfo.totalSum;
		if ( totalSum == 0.0 ) {

			color = vec3( 0.0 );
			return 1.0;

		}

		vec2 uv = equirectDirectionToUv( direction );
		color = texture2D( envMapInfo.map, uv ).rgb;

		float lum = luminance( color );
		ivec2 resolution = textureSize( envMapInfo.map, 0 );
		float pdf = lum / totalSum;

		return float( resolution.x * resolution.y ) * pdf * equirectDirectionPdf( direction );

	}

	// samples a direction of the envmap with color and retrieves pdf
	float sampleEquirectProbability( vec2 r, inout vec3 color, inout vec3 direction ) {

		// sample env map cdf
		float v = texture2D( envMapInfo.marginalWeights, vec2( r.x, 0.0 ) ).x;
		float u = texture2D( envMapInfo.conditionalWeights, vec2( r.y, v ) ).x;
		vec2 uv = vec2( u, v );

		vec3 derivedDirection = equirectUvToDirection( uv );
		direction = derivedDirection;
		color = texture2D( envMapInfo.map, uv ).rgb;

		float totalSum = envMapInfo.totalSum;
		float lum = luminance( color );
		ivec2 resolution = textureSize( envMapInfo.map, 0 );
		float pdf = lum / totalSum;

		return float( resolution.x * resolution.y ) * pdf * equirectDirectionPdf( direction );

	}
`;var Cn=`

	float getSpotAttenuation( const in float coneCosine, const in float penumbraCosine, const in float angleCosine ) {

		return smoothstep( coneCosine, penumbraCosine, angleCosine );

	}

	float getDistanceAttenuation( const in float lightDistance, const in float cutoffDistance, const in float decayExponent ) {

		// based upon Frostbite 3 Moving to Physically-based Rendering
		// page 32, equation 26: E[window1]
		// https://seblagarde.files.wordpress.com/2015/07/course_notes_moving_frostbite_to_pbr_v32.pdf
		float distanceFalloff = 1.0 / max( pow( lightDistance, decayExponent ), EPSILON );

		if ( cutoffDistance > 0.0 ) {

			distanceFalloff *= pow2( saturate( 1.0 - pow4( lightDistance / cutoffDistance ) ) );

		}

		return distanceFalloff;

	}

	float getPhotometricAttenuation( sampler2DArray iesProfiles, int iesProfile, vec3 posToLight, vec3 lightDir, vec3 u, vec3 v ) {

		float cosTheta = dot( posToLight, lightDir );
		float angle = acos( cosTheta ) / PI;

		return texture2D( iesProfiles, vec3( angle, 0.0, iesProfile ) ).r;

	}

	struct LightRecord {

		float dist;
		vec3 direction;
		float pdf;
		vec3 emission;
		int type;

	};

	bool intersectLightAtIndex( sampler2D lights, vec3 rayOrigin, vec3 rayDirection, uint l, inout LightRecord lightRec ) {

		bool didHit = false;
		Light light = readLightInfo( lights, l );

		vec3 u = light.u;
		vec3 v = light.v;

		// check for backface
		vec3 normal = normalize( cross( u, v ) );
		if ( dot( normal, rayDirection ) > 0.0 ) {

			u *= 1.0 / dot( u, u );
			v *= 1.0 / dot( v, v );

			float dist;

			// MIS / light intersection is not supported for punctual lights.
			if(
				( light.type == RECT_AREA_LIGHT_TYPE && intersectsRectangle( light.position, normal, u, v, rayOrigin, rayDirection, dist ) ) ||
				( light.type == CIRC_AREA_LIGHT_TYPE && intersectsCircle( light.position, normal, u, v, rayOrigin, rayDirection, dist ) )
			) {

				float cosTheta = dot( rayDirection, normal );
				didHit = true;
				lightRec.dist = dist;
				lightRec.pdf = ( dist * dist ) / ( light.area * cosTheta );
				lightRec.emission = light.color * light.intensity;
				lightRec.direction = rayDirection;
				lightRec.type = light.type;

			}

		}

		return didHit;

	}

	LightRecord randomAreaLightSample( Light light, vec3 rayOrigin, vec2 ruv ) {

		vec3 randomPos;
		if( light.type == RECT_AREA_LIGHT_TYPE ) {

			// rectangular area light
			randomPos = light.position + light.u * ( ruv.x - 0.5 ) + light.v * ( ruv.y - 0.5 );

		} else if( light.type == CIRC_AREA_LIGHT_TYPE ) {

			// circular area light
			float r = 0.5 * sqrt( ruv.x );
			float theta = ruv.y * 2.0 * PI;
			float x = r * cos( theta );
			float y = r * sin( theta );

			randomPos = light.position + light.u * x + light.v * y;

		}

		vec3 toLight = randomPos - rayOrigin;
		float lightDistSq = dot( toLight, toLight );
		float dist = sqrt( lightDistSq );
		vec3 direction = toLight / dist;
		vec3 lightNormal = normalize( cross( light.u, light.v ) );

		LightRecord lightRec;
		lightRec.type = light.type;
		lightRec.emission = light.color * light.intensity;
		lightRec.dist = dist;
		lightRec.direction = direction;

		// TODO: the denominator is potentially zero
		lightRec.pdf = lightDistSq / ( light.area * dot( direction, lightNormal ) );

		return lightRec;

	}

	LightRecord randomSpotLightSample( Light light, sampler2DArray iesProfiles, vec3 rayOrigin, vec2 ruv ) {

		float radius = light.radius * sqrt( ruv.x );
		float theta = ruv.y * 2.0 * PI;
		float x = radius * cos( theta );
		float y = radius * sin( theta );

		vec3 u = light.u;
		vec3 v = light.v;
		vec3 normal = normalize( cross( u, v ) );

		float angle = acos( light.coneCos );
		float angleTan = tan( angle );
		float startDistance = light.radius / max( angleTan, EPSILON );

		vec3 randomPos = light.position - normal * startDistance + u * x + v * y;
		vec3 toLight = randomPos - rayOrigin;
		float lightDistSq = dot( toLight, toLight );
		float dist = sqrt( lightDistSq );

		vec3 direction = toLight / max( dist, EPSILON );
		float cosTheta = dot( direction, normal );

		float spotAttenuation = light.iesProfile != - 1 ?
			getPhotometricAttenuation( iesProfiles, light.iesProfile, direction, normal, u, v ) :
			getSpotAttenuation( light.coneCos, light.penumbraCos, cosTheta );

		float distanceAttenuation = getDistanceAttenuation( dist, light.distance, light.decay );
		LightRecord lightRec;
		lightRec.type = light.type;
		lightRec.dist = dist;
		lightRec.direction = direction;
		lightRec.emission = light.color * light.intensity * distanceAttenuation * spotAttenuation;
		lightRec.pdf = 1.0;

		return lightRec;

	}

	LightRecord randomLightSample( sampler2D lights, sampler2DArray iesProfiles, uint lightCount, vec3 rayOrigin, vec3 ruv ) {

		LightRecord result;

		// pick a random light
		uint l = uint( ruv.x * float( lightCount ) );
		Light light = readLightInfo( lights, l );

		if ( light.type == SPOT_LIGHT_TYPE ) {

			result = randomSpotLightSample( light, iesProfiles, rayOrigin, ruv.yz );

		} else if ( light.type == POINT_LIGHT_TYPE ) {

			vec3 lightRay = light.u - rayOrigin;
			float lightDist = length( lightRay );
			float cutoffDistance = light.distance;
			float distanceFalloff = 1.0 / max( pow( lightDist, light.decay ), 0.01 );
			if ( cutoffDistance > 0.0 ) {

				distanceFalloff *= pow2( saturate( 1.0 - pow4( lightDist / cutoffDistance ) ) );

			}

			LightRecord rec;
			rec.direction = normalize( lightRay );
			rec.dist = length( lightRay );
			rec.pdf = 1.0;
			rec.emission = light.color * light.intensity * distanceFalloff;
			rec.type = light.type;
			result = rec;

		} else if ( light.type == DIR_LIGHT_TYPE ) {

			LightRecord rec;
			rec.dist = 1e10;
			rec.direction = light.u;
			rec.pdf = 1.0;
			rec.emission = light.color * light.intensity;
			rec.type = light.type;

			result = rec;

		} else {

			// sample the light
			result = randomAreaLightSample( light, rayOrigin, ruv.yz );

		}

		return result;

	}

`;var En=`

	vec3 sampleHemisphere( vec3 n, vec2 uv ) {

		// https://www.rorydriscoll.com/2009/01/07/better-sampling/
		// https://graphics.pixar.com/library/OrthonormalB/paper.pdf
		float sign = n.z == 0.0 ? 1.0 : sign( n.z );
		float a = - 1.0 / ( sign + n.z );
		float b = n.x * n.y * a;
		vec3 b1 = vec3( 1.0 + sign * n.x * n.x * a, sign * b, - sign * n.x );
		vec3 b2 = vec3( b, sign + n.y * n.y * a, - n.y );

		float r = sqrt( uv.x );
		float theta = 2.0 * PI * uv.y;
		float x = r * cos( theta );
		float y = r * sin( theta );
		return x * b1 + y * b2 + sqrt( 1.0 - uv.x ) * n;

	}

	vec2 sampleTriangle( vec2 a, vec2 b, vec2 c, vec2 r ) {

		// get the edges of the triangle and the diagonal across the
		// center of the parallelogram
		vec2 e1 = a - b;
		vec2 e2 = c - b;
		vec2 diag = normalize( e1 + e2 );

		// pick the point in the parallelogram
		if ( r.x + r.y > 1.0 ) {

			r = vec2( 1.0 ) - r;

		}

		return e1 * r.x + e2 * r.y;

	}

	vec2 sampleCircle( vec2 uv ) {

		float angle = 2.0 * PI * uv.x;
		float radius = sqrt( uv.y );
		return vec2( cos( angle ), sin( angle ) ) * radius;

	}

	vec3 sampleSphere( vec2 uv ) {

		float u = ( uv.x - 0.5 ) * 2.0;
		float t = uv.y * PI * 2.0;
		float f = sqrt( 1.0 - u * u );

		return vec3( f * cos( t ), f * sin( t ), u );

	}

	vec2 sampleRegularPolygon( int sides, vec3 uvw ) {

		sides = max( sides, 3 );

		vec3 r = uvw;
		float anglePerSegment = 2.0 * PI / float( sides );
		float segment = floor( float( sides ) * r.x );

		float angle1 = anglePerSegment * segment;
		float angle2 = angle1 + anglePerSegment;
		vec2 a = vec2( sin( angle1 ), cos( angle1 ) );
		vec2 b = vec2( 0.0, 0.0 );
		vec2 c = vec2( sin( angle2 ), cos( angle2 ) );

		return sampleTriangle( a, b, c, r.yz );

	}

	// samples an aperture shape with the given number of sides. 0 means circle
	vec2 sampleAperture( int blades, vec3 uvw ) {

		return blades == 0 ?
			sampleCircle( uvw.xy ) :
			sampleRegularPolygon( blades, uvw );

	}


`;var Bn=`

	bool totalInternalReflection( float cosTheta, float eta ) {

		float sinTheta = sqrt( 1.0 - cosTheta * cosTheta );
		return eta * sinTheta > 1.0;

	}

	// https://google.github.io/filament/Filament.md.html#materialsystem/diffusebrdf
	float schlickFresnel( float cosine, float f0 ) {

		return f0 + ( 1.0 - f0 ) * pow( 1.0 - cosine, 5.0 );

	}

	vec3 schlickFresnel( float cosine, vec3 f0 ) {

		return f0 + ( 1.0 - f0 ) * pow( 1.0 - cosine, 5.0 );

	}

	vec3 schlickFresnel( float cosine, vec3 f0, vec3 f90 ) {

		return f0 + ( f90 - f0 ) * pow( 1.0 - cosine, 5.0 );

	}

	float dielectricFresnel( float cosThetaI, float eta ) {

		// https://schuttejoe.github.io/post/disneybsdf/
		float ni = eta;
		float nt = 1.0;

		// Check for total internal reflection
		float sinThetaISq = 1.0f - cosThetaI * cosThetaI;
		float sinThetaTSq = eta * eta * sinThetaISq;
		if( sinThetaTSq >= 1.0 ) {

			return 1.0;

		}

		float sinThetaT = sqrt( sinThetaTSq );

		float cosThetaT = sqrt( max( 0.0, 1.0f - sinThetaT * sinThetaT ) );
		float rParallel = ( ( nt * cosThetaI ) - ( ni * cosThetaT ) ) / ( ( nt * cosThetaI ) + ( ni * cosThetaT ) );
		float rPerpendicular = ( ( ni * cosThetaI ) - ( nt * cosThetaT ) ) / ( ( ni * cosThetaI ) + ( nt * cosThetaT ) );
		return ( rParallel * rParallel + rPerpendicular * rPerpendicular ) / 2.0;

	}

	// https://raytracing.github.io/books/RayTracingInOneWeekend.html#dielectrics/schlickapproximation
	float iorRatioToF0( float eta ) {

		return pow( ( 1.0 - eta ) / ( 1.0 + eta ), 2.0 );

	}

	vec3 evaluateFresnel( float cosTheta, float eta, vec3 f0, vec3 f90 ) {

		if ( totalInternalReflection( cosTheta, eta ) ) {

			return f90;

		}

		return schlickFresnel( cosTheta, f0, f90 );

	}

	// TODO: disney fresnel was removed and replaced with this fresnel function to better align with
	// the glTF but is causing blown out pixels. Should be revisited
	// float evaluateFresnelWeight( float cosTheta, float eta, float f0 ) {

	// 	if ( totalInternalReflection( cosTheta, eta ) ) {

	// 		return 1.0;

	// 	}

	// 	return schlickFresnel( cosTheta, f0 );

	// }

	// https://schuttejoe.github.io/post/disneybsdf/
	float disneyFresnel( vec3 wo, vec3 wi, vec3 wh, float f0, float eta, float metalness ) {

		float dotHV = dot( wo, wh );
		if ( totalInternalReflection( dotHV, eta ) ) {

			return 1.0;

		}

		float dotHL = dot( wi, wh );
		float dielectricFresnel = dielectricFresnel( abs( dotHV ), eta );
		float metallicFresnel = schlickFresnel( dotHL, f0 );

		return mix( dielectricFresnel, metallicFresnel, metalness );

	}

`;var Nn=`

	// Fast arccos approximation used to remove banding artifacts caused by numerical errors in acos.
	// This is a cubic Lagrange interpolating polynomial for x = [-1, -1/2, 0, 1/2, 1].
	// For more information see: https://github.com/gkjohnson/three-gpu-pathtracer/pull/171#issuecomment-1152275248
	float acosApprox( float x ) {

		x = clamp( x, -1.0, 1.0 );
		return ( - 0.69813170079773212 * x * x - 0.87266462599716477 ) * x + 1.5707963267948966;

	}

	// An acos with input values bound to the range [-1, 1].
	float acosSafe( float x ) {

		return acos( clamp( x, -1.0, 1.0 ) );

	}

	float saturateCos( float val ) {

		return clamp( val, 0.001, 1.0 );

	}

	float square( float t ) {

		return t * t;

	}

	vec2 square( vec2 t ) {

		return t * t;

	}

	vec3 square( vec3 t ) {

		return t * t;

	}

	vec4 square( vec4 t ) {

		return t * t;

	}

	vec2 rotateVector( vec2 v, float t ) {

		float ac = cos( t );
		float as = sin( t );
		return vec2(
			v.x * ac - v.y * as,
			v.x * as + v.y * ac
		);

	}

	// forms a basis with the normal vector as Z
	mat3 getBasisFromNormal( vec3 normal ) {

		vec3 other;
		if ( abs( normal.x ) > 0.5 ) {

			other = vec3( 0.0, 1.0, 0.0 );

		} else {

			other = vec3( 1.0, 0.0, 0.0 );

		}

		vec3 ortho = normalize( cross( normal, other ) );
		vec3 ortho2 = normalize( cross( normal, ortho ) );
		return mat3( ortho2, ortho, normal );

	}

`;var Ln=`

	// Finds the point where the ray intersects the plane defined by u and v and checks if this point
	// falls in the bounds of the rectangle on that same plane.
	// Plane intersection: https://lousodrome.net/blog/light/2020/07/03/intersection-of-a-ray-and-a-plane/
	bool intersectsRectangle( vec3 center, vec3 normal, vec3 u, vec3 v, vec3 rayOrigin, vec3 rayDirection, inout float dist ) {

		float t = dot( center - rayOrigin, normal ) / dot( rayDirection, normal );

		if ( t > EPSILON ) {

			vec3 p = rayOrigin + rayDirection * t;
			vec3 vi = p - center;

			// check if p falls inside the rectangle
			float a1 = dot( u, vi );
			if ( abs( a1 ) <= 0.5 ) {

				float a2 = dot( v, vi );
				if ( abs( a2 ) <= 0.5 ) {

					dist = t;
					return true;

				}

			}

		}

		return false;

	}

	// Finds the point where the ray intersects the plane defined by u and v and checks if this point
	// falls in the bounds of the circle on that same plane. See above URL for a description of the plane intersection algorithm.
	bool intersectsCircle( vec3 position, vec3 normal, vec3 u, vec3 v, vec3 rayOrigin, vec3 rayDirection, inout float dist ) {

		float t = dot( position - rayOrigin, normal ) / dot( rayDirection, normal );

		if ( t > EPSILON ) {

			vec3 hit = rayOrigin + rayDirection * t;
			vec3 vi = hit - position;

			float a1 = dot( u, vi );
			float a2 = dot( v, vi );

			if( length( vec2( a1, a2 ) ) <= 0.5 ) {

				dist = t;
				return true;

			}

		}

		return false;

	}

`;var On=`

	// add texel fetch functions for texture arrays
	vec4 texelFetch1D( sampler2DArray tex, int layer, uint index ) {

		uint width = uint( textureSize( tex, 0 ).x );
		uvec2 uv;
		uv.x = index % width;
		uv.y = index / width;

		return texelFetch( tex, ivec3( uv, layer ), 0 );

	}

	vec4 textureSampleBarycoord( sampler2DArray tex, int layer, vec3 barycoord, uvec3 faceIndices ) {

		return
			barycoord.x * texelFetch1D( tex, layer, faceIndices.x ) +
			barycoord.y * texelFetch1D( tex, layer, faceIndices.y ) +
			barycoord.z * texelFetch1D( tex, layer, faceIndices.z );

	}

`;var sr=`

	// TODO: possibly this should be renamed something related to material or path tracing logic

	#ifndef RAY_OFFSET
	#define RAY_OFFSET 1e-4
	#endif

	// adjust the hit point by the surface normal by a factor of some offset and the
	// maximum component-wise value of the current point to accommodate floating point
	// error as values increase.
	vec3 stepRayOrigin( vec3 rayOrigin, vec3 rayDirection, vec3 offset, float dist ) {

		vec3 point = rayOrigin + rayDirection * dist;
		vec3 absPoint = abs( point );
		float maxPoint = max( absPoint.x, max( absPoint.y, absPoint.z ) );
		return point + offset * ( maxPoint + 1.0 ) * RAY_OFFSET;

	}

	// https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_materials_volume/README.md#attenuation
	vec3 transmissionAttenuation( float dist, vec3 attColor, float attDist ) {

		vec3 ot = - log( attColor ) / attDist;
		return exp( - ot * dist );

	}

	vec3 getHalfVector( vec3 wi, vec3 wo, float eta ) {

		// get the half vector - assuming if the light incident vector is on the other side
		// of the that it's transmissive.
		vec3 h;
		if ( wi.z > 0.0 ) {

			h = normalize( wi + wo );

		} else {

			// Scale by the ior ratio to retrieve the appropriate half vector
			// From Section 2.2 on computing the transmission half vector:
			// https://blog.selfshadow.com/publications/s2015-shading-course/burley/s2015_pbs_disney_bsdf_notes.pdf
			h = normalize( wi + wo * eta );

		}

		h *= sign( h.z );
		return h;

	}

	vec3 getHalfVector( vec3 a, vec3 b ) {

		return normalize( a + b );

	}

	// The discrepancy between interpolated surface normal and geometry normal can cause issues when a ray
	// is cast that is on the top side of the geometry normal plane but below the surface normal plane. If
	// we find a ray like that we ignore it to avoid artifacts.
	// This function returns if the direction is on the same side of both planes.
	bool isDirectionValid( vec3 direction, vec3 surfaceNormal, vec3 geometryNormal ) {

		bool aboveSurfaceNormal = dot( direction, surfaceNormal ) > 0.0;
		bool aboveGeometryNormal = dot( direction, geometryNormal ) > 0.0;
		return aboveSurfaceNormal == aboveGeometryNormal;

	}

	// ray sampling x and z are swapped to align with expected background view
	vec2 equirectDirectionToUv( vec3 direction ) {

		// from Spherical.setFromCartesianCoords
		vec2 uv = vec2( atan( direction.z, direction.x ), acos( direction.y ) );
		uv /= vec2( 2.0 * PI, PI );

		// apply adjustments to get values in range [0, 1] and y right side up
		uv.x += 0.5;
		uv.y = 1.0 - uv.y;
		return uv;

	}

	vec3 equirectUvToDirection( vec2 uv ) {

		// undo above adjustments
		uv.x -= 0.5;
		uv.y = 1.0 - uv.y;

		// from Vector3.setFromSphericalCoords
		float theta = uv.x * 2.0 * PI;
		float phi = uv.y * PI;

		float sinPhi = sin( phi );

		return vec3( sinPhi * cos( theta ), cos( phi ), sinPhi * sin( theta ) );

	}

	// power heuristic for multiple importance sampling
	float misHeuristic( float a, float b ) {

		float aa = a * a;
		float bb = b * b;
		return aa / ( aa + bb );

	}

	// tentFilter from Peter Shirley's 'Realistic Ray Tracing (2nd Edition)' book, pg. 60
	// erichlof/THREE.js-PathTracing-Renderer/
	float tentFilter( float x ) {

		return x < 0.5 ? sqrt( 2.0 * x ) - 1.0 : 1.0 - sqrt( 2.0 - ( 2.0 * x ) );

	}
`;var Ti=`

	// https://www.shadertoy.com/view/wltcRS
	uvec4 WHITE_NOISE_SEED;

	void rng_initialize( vec2 p, int frame ) {

		// white noise seed
		WHITE_NOISE_SEED = uvec4( p, uint( frame ), uint( p.x ) + uint( p.y ) );

	}

	// https://www.pcg-random.org/
	void pcg4d( inout uvec4 v ) {

		v = v * 1664525u + 1013904223u;
		v.x += v.y * v.w;
		v.y += v.z * v.x;
		v.z += v.x * v.y;
		v.w += v.y * v.z;
		v = v ^ ( v >> 16u );
		v.x += v.y*v.w;
		v.y += v.z*v.x;
		v.z += v.x*v.y;
		v.w += v.y*v.z;

	}

	// returns [ 0, 1 ]
	float pcgRand() {

		pcg4d( WHITE_NOISE_SEED );
		return float( WHITE_NOISE_SEED.x ) / float( 0xffffffffu );

	}

	vec2 pcgRand2() {

		pcg4d( WHITE_NOISE_SEED );
		return vec2( WHITE_NOISE_SEED.xy ) / float(0xffffffffu);

	}

	vec3 pcgRand3() {

		pcg4d( WHITE_NOISE_SEED );
		return vec3( WHITE_NOISE_SEED.xyz ) / float( 0xffffffffu );

	}

	vec4 pcgRand4() {

		pcg4d( WHITE_NOISE_SEED );
		return vec4( WHITE_NOISE_SEED ) / float( 0xffffffffu );

	}
`;var zn=`

	uniform sampler2D stratifiedTexture;
	uniform sampler2D stratifiedOffsetTexture;

	uint sobolPixelIndex = 0u;
	uint sobolPathIndex = 0u;
	uint sobolBounceIndex = 0u;
	vec4 pixelSeed = vec4( 0 );

	vec4 rand4( int v ) {

		ivec2 uv = ivec2( v, sobolBounceIndex );
		vec4 stratifiedSample = texelFetch( stratifiedTexture, uv, 0 );
		return fract( stratifiedSample + pixelSeed.r ); // blue noise + stratified samples

	}

	vec3 rand3( int v ) {

		return rand4( v ).xyz;

	}

	vec2 rand2( int v ) {

		return rand4( v ).xy;

	}

	float rand( int v ) {

		return rand4( v ).x;

	}

	void rng_initialize( vec2 screenCoord, int frame ) {

		// tile the small noise texture across the entire screen
		ivec2 noiseSize = ivec2( textureSize( stratifiedOffsetTexture, 0 ) );
		ivec2 pixel = ivec2( screenCoord.xy ) % noiseSize;
		vec2 pixelWidth = 1.0 / vec2( noiseSize );
		vec2 uv = vec2( pixel ) * pixelWidth + pixelWidth * 0.5;

		// note that using "texelFetch" here seems to break Android for some reason
		pixelSeed = texture( stratifiedOffsetTexture, uv );

	}

`;var kn=`

	// diffuse
	float diffuseEval( vec3 wo, vec3 wi, vec3 wh, SurfaceRecord surf, inout vec3 color ) {

		// https://schuttejoe.github.io/post/disneybsdf/
		float fl = schlickFresnel( wi.z, 0.0 );
		float fv = schlickFresnel( wo.z, 0.0 );

		float metalFactor = ( 1.0 - surf.metalness );
		float transFactor = ( 1.0 - surf.transmission );
		float rr = 0.5 + 2.0 * surf.roughness * fl * fl;
		float retro = rr * ( fl + fv + fl * fv * ( rr - 1.0f ) );
		float lambert = ( 1.0f - 0.5f * fl ) * ( 1.0f - 0.5f * fv );

		// TODO: subsurface approx?

		// float F = evaluateFresnelWeight( dot( wo, wh ), surf.eta, surf.f0 );
		float F = disneyFresnel( wo, wi, wh, surf.f0, surf.eta, surf.metalness );
		color = ( 1.0 - F ) * transFactor * metalFactor * wi.z * surf.color * ( retro + lambert ) / PI;

		return wi.z / PI;

	}

	vec3 diffuseDirection( vec3 wo, SurfaceRecord surf ) {

		vec3 lightDirection = sampleSphere( rand2( 11 ) );
		lightDirection.z += 1.0;
		lightDirection = normalize( lightDirection );

		return lightDirection;

	}

	// specular
	float specularEval( vec3 wo, vec3 wi, vec3 wh, SurfaceRecord surf, inout vec3 color ) {

		// if roughness is set to 0 then D === NaN which results in black pixels
		float metalness = surf.metalness;
		float roughness = surf.filteredRoughness;

		float eta = surf.eta;
		float f0 = surf.f0;

		vec3 f0Color = mix( f0 * surf.specularColor * surf.specularIntensity, surf.color, surf.metalness );
		vec3 f90Color = vec3( mix( surf.specularIntensity, 1.0, surf.metalness ) );
		vec3 F = evaluateFresnel( dot( wo, wh ), eta, f0Color, f90Color );

		vec3 iridescenceF = evalIridescence( 1.0, surf.iridescenceIor, dot( wi, wh ), surf.iridescenceThickness, f0Color );
		F = mix( F, iridescenceF,  surf.iridescence );

		// PDF
		// See 14.1.1 Microfacet BxDFs in https://www.pbr-book.org/
		float incidentTheta = acos( wo.z );
		float G = ggxShadowMaskG2( wi, wo, roughness );
		float D = ggxDistribution( wh, roughness );
		float G1 = ggxShadowMaskG1( incidentTheta, roughness );
		float ggxPdf = D * G1 * max( 0.0, abs( dot( wo, wh ) ) ) / abs ( wo.z );

		color = wi.z * F * G * D / ( 4.0 * abs( wi.z * wo.z ) );
		return ggxPdf / ( 4.0 * dot( wo, wh ) );

	}

	vec3 specularDirection( vec3 wo, SurfaceRecord surf ) {

		// sample ggx vndf distribution which gives a new normal
		float roughness = surf.filteredRoughness;
		vec3 halfVector = ggxDirection(
			wo,
			vec2( roughness ),
			rand2( 12 )
		);

		// apply to new ray by reflecting off the new normal
		return - reflect( wo, halfVector );

	}


	// transmission
	/*
	float transmissionEval( vec3 wo, vec3 wi, vec3 wh, SurfaceRecord surf, inout vec3 color ) {

		// See section 4.2 in https://www.cs.cornell.edu/~srm/publications/EGSR07-btdf.pdf

		float filteredRoughness = surf.filteredRoughness;
		float eta = surf.eta;
		bool frontFace = surf.frontFace;
		bool thinFilm = surf.thinFilm;

		color = surf.transmission * surf.color;

		float denom = pow( eta * dot( wi, wh ) + dot( wo, wh ), 2.0 );
		return ggxPDF( wo, wh, filteredRoughness ) / denom;

	}

	vec3 transmissionDirection( vec3 wo, SurfaceRecord surf ) {

		float filteredRoughness = surf.filteredRoughness;
		float eta = surf.eta;
		bool frontFace = surf.frontFace;

		// sample ggx vndf distribution which gives a new normal
		vec3 halfVector = ggxDirection(
			wo,
			vec2( filteredRoughness ),
			rand2( 13 )
		);

		vec3 lightDirection = refract( normalize( - wo ), halfVector, eta );
		if ( surf.thinFilm ) {

			lightDirection = - refract( normalize( - lightDirection ), - vec3( 0.0, 0.0, 1.0 ), 1.0 / eta );

		}

		return normalize( lightDirection );

	}
	*/

	// TODO: This is just using a basic cosine-weighted specular distribution with an
	// incorrect PDF value at the moment. Update it to correctly use a GGX distribution
	float transmissionEval( vec3 wo, vec3 wi, vec3 wh, SurfaceRecord surf, inout vec3 color ) {

		color = surf.transmission * surf.color;

		// PDF
		// float F = evaluateFresnelWeight( dot( wo, wh ), surf.eta, surf.f0 );
		// float F = disneyFresnel( wo, wi, wh, surf.f0, surf.eta, surf.metalness );
		// if ( F >= 1.0 ) {

		// 	return 0.0;

		// }

		// return 1.0 / ( 1.0 - F );

		// reverted to previous to transmission. The above was causing black pixels
		float eta = surf.eta;
		float f0 = surf.f0;
		float cosTheta = min( wo.z, 1.0 );
		float sinTheta = sqrt( 1.0 - cosTheta * cosTheta );
		float reflectance = schlickFresnel( cosTheta, f0 );
		bool cannotRefract = eta * sinTheta > 1.0;
		if ( cannotRefract ) {

			return 0.0;

		}

		return 1.0 / ( 1.0 - reflectance );

	}

	vec3 transmissionDirection( vec3 wo, SurfaceRecord surf ) {

		float roughness = surf.filteredRoughness;
		float eta = surf.eta;
		vec3 halfVector = normalize( vec3( 0.0, 0.0, 1.0 ) + sampleSphere( rand2( 13 ) ) * roughness );
		vec3 lightDirection = refract( normalize( - wo ), halfVector, eta );

		if ( surf.thinFilm ) {

			lightDirection = - refract( normalize( - lightDirection ), - vec3( 0.0, 0.0, 1.0 ), 1.0 / eta );

		}
		return normalize( lightDirection );

	}

	// clearcoat
	float clearcoatEval( vec3 wo, vec3 wi, vec3 wh, SurfaceRecord surf, inout vec3 color ) {

		float ior = 1.5;
		float f0 = iorRatioToF0( ior );
		bool frontFace = surf.frontFace;
		float roughness = surf.filteredClearcoatRoughness;

		float eta = frontFace ? 1.0 / ior : ior;
		float G = ggxShadowMaskG2( wi, wo, roughness );
		float D = ggxDistribution( wh, roughness );
		float F = schlickFresnel( dot( wi, wh ), f0 );

		float fClearcoat = F * D * G / ( 4.0 * abs( wi.z * wo.z ) );
		color = color * ( 1.0 - surf.clearcoat * F ) + fClearcoat * surf.clearcoat * wi.z;

		// PDF
		// See equation (27) in http://jcgt.org/published/0003/02/03/
		return ggxPDF( wo, wh, roughness ) / ( 4.0 * dot( wi, wh ) );

	}

	vec3 clearcoatDirection( vec3 wo, SurfaceRecord surf ) {

		// sample ggx vndf distribution which gives a new normal
		float roughness = surf.filteredClearcoatRoughness;
		vec3 halfVector = ggxDirection(
			wo,
			vec2( roughness ),
			rand2( 14 )
		);

		// apply to new ray by reflecting off the new normal
		return - reflect( wo, halfVector );

	}

	// sheen
	vec3 sheenColor( vec3 wo, vec3 wi, vec3 wh, SurfaceRecord surf ) {

		float cosThetaO = saturateCos( wo.z );
		float cosThetaI = saturateCos( wi.z );
		float cosThetaH = wh.z;

		float D = velvetD( cosThetaH, surf.sheenRoughness );
		float G = velvetG( cosThetaO, cosThetaI, surf.sheenRoughness );

		// See equation (1) in http://www.aconty.com/pdf/s2017_pbs_imageworks_sheen.pdf
		vec3 color = surf.sheenColor;
		color *= D * G / ( 4.0 * abs( cosThetaO * cosThetaI ) );

		return color;

	}

	// bsdf
	void getLobeWeights(
		vec3 wo, vec3 wi, vec3 wh, vec3 clearcoatWo, SurfaceRecord surf,
		inout float diffuseWeight, inout float specularWeight, inout float transmissionWeight, inout float clearcoatWeight
	) {

		float metalness = surf.metalness;
		float transmission = surf.transmission;
		// float fEstimate = evaluateFresnelWeight( dot( wo, wh ), surf.eta, surf.f0 );
		float fEstimate = disneyFresnel( wo, wi, wh, surf.f0, surf.eta, surf.metalness );

		float transSpecularProb = mix( max( 0.25, fEstimate ), 1.0, metalness );
		float diffSpecularProb = 0.5 + 0.5 * metalness;

		diffuseWeight = ( 1.0 - transmission ) * ( 1.0 - diffSpecularProb );
		specularWeight = transmission * transSpecularProb + ( 1.0 - transmission ) * diffSpecularProb;
		transmissionWeight = transmission * ( 1.0 - transSpecularProb );
		clearcoatWeight = surf.clearcoat * schlickFresnel( clearcoatWo.z, 0.04 );

		float totalWeight = diffuseWeight + specularWeight + transmissionWeight + clearcoatWeight;
		diffuseWeight /= totalWeight;
		specularWeight /= totalWeight;
		transmissionWeight /= totalWeight;
		clearcoatWeight /= totalWeight;
	}

	float bsdfEval(
		vec3 wo, vec3 clearcoatWo, vec3 wi, vec3 clearcoatWi, SurfaceRecord surf,
		float diffuseWeight, float specularWeight, float transmissionWeight, float clearcoatWeight, inout float specularPdf, inout vec3 color
	) {

		float metalness = surf.metalness;
		float transmission = surf.transmission;

		float spdf = 0.0;
		float dpdf = 0.0;
		float tpdf = 0.0;
		float cpdf = 0.0;
		color = vec3( 0.0 );

		vec3 halfVector = getHalfVector( wi, wo, surf.eta );

		// diffuse
		if ( diffuseWeight > 0.0 && wi.z > 0.0 ) {

			dpdf = diffuseEval( wo, wi, halfVector, surf, color );
			color *= 1.0 - surf.transmission;

		}

		// ggx specular
		if ( specularWeight > 0.0 && wi.z > 0.0 ) {

			vec3 outColor;
			spdf = specularEval( wo, wi, getHalfVector( wi, wo ), surf, outColor );
			color += outColor;

		}

		// transmission
		if ( transmissionWeight > 0.0 && wi.z < 0.0 ) {

			tpdf = transmissionEval( wo, wi, halfVector, surf, color );

		}

		// sheen
		color *= mix( 1.0, sheenAlbedoScaling( wo, wi, surf ), surf.sheen );
		color += sheenColor( wo, wi, halfVector, surf ) * surf.sheen;

		// clearcoat
		if ( clearcoatWi.z >= 0.0 && clearcoatWeight > 0.0 ) {

			vec3 clearcoatHalfVector = getHalfVector( clearcoatWo, clearcoatWi );
			cpdf = clearcoatEval( clearcoatWo, clearcoatWi, clearcoatHalfVector, surf, color );

		}

		float pdf =
			dpdf * diffuseWeight
			+ spdf * specularWeight
			+ tpdf * transmissionWeight
			+ cpdf * clearcoatWeight;

		// retrieve specular rays for the shadows flag
		specularPdf = spdf * specularWeight + cpdf * clearcoatWeight;

		return pdf;

	}

	float bsdfResult( vec3 worldWo, vec3 worldWi, SurfaceRecord surf, inout vec3 color ) {

		if ( surf.volumeParticle ) {

			color = surf.color / ( 4.0 * PI );
			return 1.0 / ( 4.0 * PI );

		}

		vec3 wo = normalize( surf.normalInvBasis * worldWo );
		vec3 wi = normalize( surf.normalInvBasis * worldWi );

		vec3 clearcoatWo = normalize( surf.clearcoatInvBasis * worldWo );
		vec3 clearcoatWi = normalize( surf.clearcoatInvBasis * worldWi );

		vec3 wh = getHalfVector( wo, wi, surf.eta );
		float diffuseWeight;
		float specularWeight;
		float transmissionWeight;
		float clearcoatWeight;
		getLobeWeights( wo, wi, wh, clearcoatWo, surf, diffuseWeight, specularWeight, transmissionWeight, clearcoatWeight );

		float specularPdf;
		return bsdfEval( wo, clearcoatWo, wi, clearcoatWi, surf, diffuseWeight, specularWeight, transmissionWeight, clearcoatWeight, specularPdf, color );

	}

	ScatterRecord bsdfSample( vec3 worldWo, SurfaceRecord surf ) {

		if ( surf.volumeParticle ) {

			ScatterRecord sampleRec;
			sampleRec.specularPdf = 0.0;
			sampleRec.pdf = 1.0 / ( 4.0 * PI );
			sampleRec.direction = sampleSphere( rand2( 16 ) );
			sampleRec.color = surf.color / ( 4.0 * PI );
			return sampleRec;

		}

		vec3 wo = normalize( surf.normalInvBasis * worldWo );
		vec3 clearcoatWo = normalize( surf.clearcoatInvBasis * worldWo );
		mat3 normalBasis = surf.normalBasis;
		mat3 invBasis = surf.normalInvBasis;
		mat3 clearcoatNormalBasis = surf.clearcoatBasis;
		mat3 clearcoatInvBasis = surf.clearcoatInvBasis;

		float diffuseWeight;
		float specularWeight;
		float transmissionWeight;
		float clearcoatWeight;
		// using normal and basically-reflected ray since we don't have proper half vector here
		getLobeWeights( wo, wo, vec3( 0, 0, 1 ), clearcoatWo, surf, diffuseWeight, specularWeight, transmissionWeight, clearcoatWeight );

		float pdf[4];
		pdf[0] = diffuseWeight;
		pdf[1] = specularWeight;
		pdf[2] = transmissionWeight;
		pdf[3] = clearcoatWeight;

		float cdf[4];
		cdf[0] = pdf[0];
		cdf[1] = pdf[1] + cdf[0];
		cdf[2] = pdf[2] + cdf[1];
		cdf[3] = pdf[3] + cdf[2];

		if( cdf[3] != 0.0 ) {

			float invMaxCdf = 1.0 / cdf[3];
			cdf[0] *= invMaxCdf;
			cdf[1] *= invMaxCdf;
			cdf[2] *= invMaxCdf;
			cdf[3] *= invMaxCdf;

		} else {

			cdf[0] = 1.0;
			cdf[1] = 0.0;
			cdf[2] = 0.0;
			cdf[3] = 0.0;

		}

		vec3 wi;
		vec3 clearcoatWi;

		float r = rand( 15 );
		if ( r <= cdf[0] ) { // diffuse

			wi = diffuseDirection( wo, surf );
			clearcoatWi = normalize( clearcoatInvBasis * normalize( normalBasis * wi ) );

		} else if ( r <= cdf[1] ) { // specular

			wi = specularDirection( wo, surf );
			clearcoatWi = normalize( clearcoatInvBasis * normalize( normalBasis * wi ) );

		} else if ( r <= cdf[2] ) { // transmission / refraction

			wi = transmissionDirection( wo, surf );
			clearcoatWi = normalize( clearcoatInvBasis * normalize( normalBasis * wi ) );

		} else if ( r <= cdf[3] ) { // clearcoat

			clearcoatWi = clearcoatDirection( clearcoatWo, surf );
			wi = normalize( invBasis * normalize( clearcoatNormalBasis * clearcoatWi ) );

		}

		ScatterRecord result;
		result.pdf = bsdfEval( wo, clearcoatWo, wi, clearcoatWi, surf, diffuseWeight, specularWeight, transmissionWeight, clearcoatWeight, result.specularPdf, result.color );
		result.direction = normalize( surf.normalBasis * wi );

		return result;

	}

`;var Hn=`

	// returns the hit distance given the material density
	float intersectFogVolume( Material material, float u ) {

		// https://raytracing.github.io/books/RayTracingTheNextWeek.html#volumes/constantdensitymediums
		return material.opacity == 0.0 ? INFINITY : ( - 1.0 / material.opacity ) * log( u );

	}

	ScatterRecord sampleFogVolume( SurfaceRecord surf, vec2 uv ) {

		ScatterRecord sampleRec;
		sampleRec.specularPdf = 0.0;
		sampleRec.pdf = 1.0 / ( 2.0 * PI );
		sampleRec.direction = sampleSphere( uv );
		sampleRec.color = surf.color;
		return sampleRec;

	}

`;var Un=`

	// The GGX functions provide sampling and distribution information for normals as output so
	// in order to get probability of scatter direction the half vector must be computed and provided.
	// [0] https://www.cs.cornell.edu/~srm/publications/EGSR07-btdf.pdf
	// [1] https://hal.archives-ouvertes.fr/hal-01509746/document
	// [2] http://jcgt.org/published/0007/04/01/
	// [4] http://jcgt.org/published/0003/02/03/

	// trowbridge-reitz === GGX === GTR

	vec3 ggxDirection( vec3 incidentDir, vec2 roughness, vec2 uv ) {

		// TODO: try GGXVNDF implementation from reference [2], here. Needs to update ggxDistribution
		// function below, as well

		// Implementation from reference [1]
		// stretch view
		vec3 V = normalize( vec3( roughness * incidentDir.xy, incidentDir.z ) );

		// orthonormal basis
		vec3 T1 = ( V.z < 0.9999 ) ? normalize( cross( V, vec3( 0.0, 0.0, 1.0 ) ) ) : vec3( 1.0, 0.0, 0.0 );
		vec3 T2 = cross( T1, V );

		// sample point with polar coordinates (r, phi)
		float a = 1.0 / ( 1.0 + V.z );
		float r = sqrt( uv.x );
		float phi = ( uv.y < a ) ? uv.y / a * PI : PI + ( uv.y - a ) / ( 1.0 - a ) * PI;
		float P1 = r * cos( phi );
		float P2 = r * sin( phi ) * ( ( uv.y < a ) ? 1.0 : V.z );

		// compute normal
		vec3 N = P1 * T1 + P2 * T2 + V * sqrt( max( 0.0, 1.0 - P1 * P1 - P2 * P2 ) );

		// unstretch
		N = normalize( vec3( roughness * N.xy, max( 0.0, N.z ) ) );

		return N;

	}

	// Below are PDF and related functions for use in a Monte Carlo path tracer
	// as specified in Appendix B of the following paper
	// See equation (34) from reference [0]
	float ggxLamda( float theta, float roughness ) {

		float tanTheta = tan( theta );
		float tanTheta2 = tanTheta * tanTheta;
		float alpha2 = roughness * roughness;

		float numerator = - 1.0 + sqrt( 1.0 + alpha2 * tanTheta2 );
		return numerator / 2.0;

	}

	// See equation (34) from reference [0]
	float ggxShadowMaskG1( float theta, float roughness ) {

		return 1.0 / ( 1.0 + ggxLamda( theta, roughness ) );

	}

	// See equation (125) from reference [4]
	float ggxShadowMaskG2( vec3 wi, vec3 wo, float roughness ) {

		float incidentTheta = acos( wi.z );
		float scatterTheta = acos( wo.z );
		return 1.0 / ( 1.0 + ggxLamda( incidentTheta, roughness ) + ggxLamda( scatterTheta, roughness ) );

	}

	// See equation (33) from reference [0]
	float ggxDistribution( vec3 halfVector, float roughness ) {

		float a2 = roughness * roughness;
		a2 = max( EPSILON, a2 );
		float cosTheta = halfVector.z;
		float cosTheta4 = pow( cosTheta, 4.0 );

		if ( cosTheta == 0.0 ) return 0.0;

		float theta = acosSafe( halfVector.z );
		float tanTheta = tan( theta );
		float tanTheta2 = pow( tanTheta, 2.0 );

		float denom = PI * cosTheta4 * pow( a2 + tanTheta2, 2.0 );
		return ( a2 / denom );

	}

	// See equation (3) from reference [2]
	float ggxPDF( vec3 wi, vec3 halfVector, float roughness ) {

		float incidentTheta = acos( wi.z );
		float D = ggxDistribution( halfVector, roughness );
		float G1 = ggxShadowMaskG1( incidentTheta, roughness );

		return D * G1 * max( 0.0, dot( wi, halfVector ) ) / wi.z;

	}

`;var Vn=`

	// XYZ to sRGB color space
	const mat3 XYZ_TO_REC709 = mat3(
		3.2404542, -0.9692660,  0.0556434,
		-1.5371385,  1.8760108, -0.2040259,
		-0.4985314,  0.0415560,  1.0572252
	);

	vec3 fresnel0ToIor( vec3 fresnel0 ) {

		vec3 sqrtF0 = sqrt( fresnel0 );
		return ( vec3( 1.0 ) + sqrtF0 ) / ( vec3( 1.0 ) - sqrtF0 );

	}

	// Conversion FO/IOR
	vec3 iorToFresnel0( vec3 transmittedIor, float incidentIor ) {

		return square( ( transmittedIor - vec3( incidentIor ) ) / ( transmittedIor + vec3( incidentIor ) ) );

	}

	// ior is a value between 1.0 and 3.0. 1.0 is air interface
	float iorToFresnel0( float transmittedIor, float incidentIor ) {

		return square( ( transmittedIor - incidentIor ) / ( transmittedIor + incidentIor ) );

	}

	// Fresnel equations for dielectric/dielectric interfaces. See https://belcour.github.io/blog/research/2017/05/01/brdf-thin-film.html
	vec3 evalSensitivity( float OPD, vec3 shift ) {

		float phase = 2.0 * PI * OPD * 1.0e-9;

		vec3 val = vec3( 5.4856e-13, 4.4201e-13, 5.2481e-13 );
		vec3 pos = vec3( 1.6810e+06, 1.7953e+06, 2.2084e+06 );
		vec3 var = vec3( 4.3278e+09, 9.3046e+09, 6.6121e+09 );

		vec3 xyz = val * sqrt( 2.0 * PI * var ) * cos( pos * phase + shift ) * exp( - square( phase ) * var );
		xyz.x += 9.7470e-14 * sqrt( 2.0 * PI * 4.5282e+09 ) * cos( 2.2399e+06 * phase + shift[ 0 ] ) * exp( - 4.5282e+09 * square( phase ) );
		xyz /= 1.0685e-7;

		vec3 srgb = XYZ_TO_REC709 * xyz;
		return srgb;

	}

	// See Section 4. Analytic Spectral Integration, A Practical Extension to Microfacet Theory for the Modeling of Varying Iridescence, https://hal.archives-ouvertes.fr/hal-01518344/document
	vec3 evalIridescence( float outsideIOR, float eta2, float cosTheta1, float thinFilmThickness, vec3 baseF0 ) {

		vec3 I;

		// Force iridescenceIor -> outsideIOR when thinFilmThickness -> 0.0
		float iridescenceIor = mix( outsideIOR, eta2, smoothstep( 0.0, 0.03, thinFilmThickness ) );

		// Evaluate the cosTheta on the base layer (Snell law)
		float sinTheta2Sq = square( outsideIOR / iridescenceIor ) * ( 1.0 - square( cosTheta1 ) );

		// Handle TIR:
		float cosTheta2Sq = 1.0 - sinTheta2Sq;
		if ( cosTheta2Sq < 0.0 ) {

			return vec3( 1.0 );

		}

		float cosTheta2 = sqrt( cosTheta2Sq );

		// First interface
		float R0 = iorToFresnel0( iridescenceIor, outsideIOR );
		float R12 = schlickFresnel( cosTheta1, R0 );
		float R21 = R12;
		float T121 = 1.0 - R12;
		float phi12 = 0.0;
		if ( iridescenceIor < outsideIOR ) {

			phi12 = PI;

		}

		float phi21 = PI - phi12;

		// Second interface
		vec3 baseIOR = fresnel0ToIor( clamp( baseF0, 0.0, 0.9999 ) ); // guard against 1.0
		vec3 R1 = iorToFresnel0( baseIOR, iridescenceIor );
		vec3 R23 = schlickFresnel( cosTheta2, R1 );
		vec3 phi23 = vec3( 0.0 );
		if ( baseIOR[0] < iridescenceIor ) {

			phi23[ 0 ] = PI;

		}

		if ( baseIOR[1] < iridescenceIor ) {

			phi23[ 1 ] = PI;

		}

		if ( baseIOR[2] < iridescenceIor ) {

			phi23[ 2 ] = PI;

		}

		// Phase shift
		float OPD = 2.0 * iridescenceIor * thinFilmThickness * cosTheta2;
		vec3 phi = vec3( phi21 ) + phi23;

		// Compound terms
		vec3 R123 = clamp( R12 * R23, 1e-5, 0.9999 );
		vec3 r123 = sqrt( R123 );
		vec3 Rs = square( T121 ) * R23 / ( vec3( 1.0 ) - R123 );

		// Reflectance term for m = 0 (DC term amplitude)
		vec3 C0 = R12 + Rs;
		I = C0;

		// Reflectance term for m > 0 (pairs of diracs)
		vec3 Cm = Rs - T121;
		for ( int m = 1; m <= 2; ++ m ) {

			Cm *= r123;
			vec3 Sm = 2.0 * evalSensitivity( float( m ) * OPD, float( m ) * phi );
			I += Cm * Sm;

		}

		// Since out of gamut colors might be produced, negative color values are clamped to 0.
		return max( I, vec3( 0.0 ) );

	}

`;var Wn=`

	// See equation (2) in http://www.aconty.com/pdf/s2017_pbs_imageworks_sheen.pdf
	float velvetD( float cosThetaH, float roughness ) {

		float alpha = max( roughness, 0.07 );
		alpha = alpha * alpha;

		float invAlpha = 1.0 / alpha;

		float sqrCosThetaH = cosThetaH * cosThetaH;
		float sinThetaH = max( 1.0 - sqrCosThetaH, 0.001 );

		return ( 2.0 + invAlpha ) * pow( sinThetaH, 0.5 * invAlpha ) / ( 2.0 * PI );

	}

	float velvetParamsInterpolate( int i, float oneMinusAlphaSquared ) {

		const float p0[5] = float[5]( 25.3245, 3.32435, 0.16801, -1.27393, -4.85967 );
		const float p1[5] = float[5]( 21.5473, 3.82987, 0.19823, -1.97760, -4.32054 );

		return mix( p1[i], p0[i], oneMinusAlphaSquared );

	}

	float velvetL( float x, float alpha ) {

		float oneMinusAlpha = 1.0 - alpha;
		float oneMinusAlphaSquared = oneMinusAlpha * oneMinusAlpha;

		float a = velvetParamsInterpolate( 0, oneMinusAlphaSquared );
		float b = velvetParamsInterpolate( 1, oneMinusAlphaSquared );
		float c = velvetParamsInterpolate( 2, oneMinusAlphaSquared );
		float d = velvetParamsInterpolate( 3, oneMinusAlphaSquared );
		float e = velvetParamsInterpolate( 4, oneMinusAlphaSquared );

		return a / ( 1.0 + b * pow( abs( x ), c ) ) + d * x + e;

	}

	// See equation (3) in http://www.aconty.com/pdf/s2017_pbs_imageworks_sheen.pdf
	float velvetLambda( float cosTheta, float alpha ) {

		return abs( cosTheta ) < 0.5 ? exp( velvetL( cosTheta, alpha ) ) : exp( 2.0 * velvetL( 0.5, alpha ) - velvetL( 1.0 - cosTheta, alpha ) );

	}

	// See Section 3, Shadowing Term, in http://www.aconty.com/pdf/s2017_pbs_imageworks_sheen.pdf
	float velvetG( float cosThetaO, float cosThetaI, float roughness ) {

		float alpha = max( roughness, 0.07 );
		alpha = alpha * alpha;

		return 1.0 / ( 1.0 + velvetLambda( cosThetaO, alpha ) + velvetLambda( cosThetaI, alpha ) );

	}

	float directionalAlbedoSheen( float cosTheta, float alpha ) {

		cosTheta = saturate( cosTheta );

		float c = 1.0 - cosTheta;
		float c3 = c * c * c;

		return 0.65584461 * c3 + 1.0 / ( 4.16526551 + exp( -7.97291361 * sqrt( alpha ) + 6.33516894 ) );

	}

	float sheenAlbedoScaling( vec3 wo, vec3 wi, SurfaceRecord surf ) {

		float alpha = max( surf.sheenRoughness, 0.07 );
		alpha = alpha * alpha;

		float maxSheenColor = max( max( surf.sheenColor.r, surf.sheenColor.g ), surf.sheenColor.b );

		float eWo = directionalAlbedoSheen( saturateCos( wo.z ), alpha );
		float eWi = directionalAlbedoSheen( saturateCos( wi.z ), alpha );

		return min( 1.0 - maxSheenColor * eWo, 1.0 - maxSheenColor * eWi );

	}

	// See Section 5, Layering, in http://www.aconty.com/pdf/s2017_pbs_imageworks_sheen.pdf
	float sheenAlbedoScaling( vec3 wo, SurfaceRecord surf ) {

		float alpha = max( surf.sheenRoughness, 0.07 );
		alpha = alpha * alpha;

		float maxSheenColor = max( max( surf.sheenColor.r, surf.sheenColor.g ), surf.sheenColor.b );

		float eWo = directionalAlbedoSheen( saturateCos( wo.z ), alpha );

		return 1.0 - maxSheenColor * eWo;

	}

`;var Gn=`

#ifndef FOG_CHECK_ITERATIONS
#define FOG_CHECK_ITERATIONS 30
#endif

// returns whether the given material is a fog material or not
bool isMaterialFogVolume( sampler2D materials, uint materialIndex ) {

	uint i = materialIndex * uint( MATERIAL_PIXELS );
	vec4 s14 = texelFetch1D( materials, i + 14u );
	return bool( int( s14.b ) & 4 );

}

// returns true if we're within the first fog volume we hit
bool bvhIntersectFogVolumeHit(
	vec3 rayOrigin, vec3 rayDirection,
	usampler2D materialIndexAttribute, sampler2D materials,
	inout Material material
) {

	material.fogVolume = false;

	for ( int i = 0; i < FOG_CHECK_ITERATIONS; i ++ ) {

		// find nearest hit
		uvec4 faceIndices = uvec4( 0u );
		vec3 faceNormal = vec3( 0.0, 0.0, 1.0 );
		vec3 barycoord = vec3( 0.0 );
		float side = 1.0;
		float dist = 0.0;
		bool hit = bvhIntersectFirstHit( bvh, rayOrigin, rayDirection, faceIndices, faceNormal, barycoord, side, dist );
		if ( hit ) {

			// if it's a fog volume return whether we hit the front or back face
			uint materialIndex = uTexelFetch1D( materialIndexAttribute, faceIndices.x ).r;
			if ( isMaterialFogVolume( materials, materialIndex ) ) {

				material = readMaterialInfo( materials, materialIndex );
				return side == - 1.0;

			} else {

				// move the ray forward
				rayOrigin = stepRayOrigin( rayOrigin, rayDirection, - faceNormal, dist );

			}

		} else {

			return false;

		}

	}

	return false;

}

`;var qn=`

	// step through multiple surface hits and accumulate color attenuation based on transmissive surfaces
	// returns true if a solid surface was hit
	bool attenuateHit(
		RenderState state,
		Ray ray, float rayDist,
		out vec3 color
	) {

		// store the original bounce index so we can reset it after
		uint originalBounceIndex = sobolBounceIndex;

		int traversals = state.traversals;
		int transmissiveTraversals = state.transmissiveTraversals;
		bool isShadowRay = state.isShadowRay;
		Material fogMaterial = state.fogMaterial;

		vec3 startPoint = ray.origin;

		// hit results
		SurfaceHit surfaceHit;

		color = vec3( 1.0 );

		bool result = true;
		for ( int i = 0; i < traversals; i ++ ) {

			sobolBounceIndex ++;

			int hitType = traceScene( ray, fogMaterial, surfaceHit );

			if ( hitType == FOG_HIT ) {

				result = true;
				break;

			} else if ( hitType == SURFACE_HIT ) {

				float totalDist = distance( startPoint, ray.origin + ray.direction * surfaceHit.dist );
				if ( totalDist > rayDist ) {

					result = false;
					break;

				}

				// TODO: attenuate the contribution based on the PDF of the resulting ray including refraction values
				// Should be able to work using the material BSDF functions which will take into account specularity, etc.
				// TODO: should we account for emissive surfaces here?

				uint materialIndex = uTexelFetch1D( materialIndexAttribute, surfaceHit.faceIndices.x ).r;
				Material material = readMaterialInfo( materials, materialIndex );

				// adjust the ray to the new surface
				bool isEntering = surfaceHit.side == 1.0;
				ray.origin = stepRayOrigin( ray.origin, ray.direction, - surfaceHit.faceNormal, surfaceHit.dist );

				#if FEATURE_FOG

				if ( material.fogVolume ) {

					fogMaterial = material;
					fogMaterial.fogVolume = surfaceHit.side == 1.0;
					i -= sign( transmissiveTraversals );
					transmissiveTraversals --;
					continue;

				}

				#endif

				if ( ! material.castShadow && isShadowRay ) {

					continue;

				}

				vec2 uv = textureSampleBarycoord( attributesArray, ATTR_UV, surfaceHit.barycoord, surfaceHit.faceIndices.xyz ).xy;
				vec4 vertexColor = textureSampleBarycoord( attributesArray, ATTR_COLOR, surfaceHit.barycoord, surfaceHit.faceIndices.xyz );

				// albedo
				vec4 albedo = vec4( material.color, material.opacity );
				if ( material.map != - 1 ) {

					vec3 uvPrime = material.mapTransform * vec3( uv, 1 );
					albedo *= texture2D( textures, vec3( uvPrime.xy, material.map ) );

				}

				if ( material.vertexColors ) {

					albedo *= vertexColor;

				}

				// alphaMap
				if ( material.alphaMap != - 1 ) {

					vec3 uvPrime = material.alphaMapTransform * vec3( uv, 1 );
					albedo.a *= texture2D( textures, vec3( uvPrime.xy, material.alphaMap ) ).x;

				}

				// transmission
				float transmission = material.transmission;
				if ( material.transmissionMap != - 1 ) {

					vec3 uvPrime = material.transmissionMapTransform * vec3( uv, 1 );
					transmission *= texture2D( textures, vec3( uvPrime.xy, material.transmissionMap ) ).r;

				}

				// metalness
				float metalness = material.metalness;
				if ( material.metalnessMap != - 1 ) {

					vec3 uvPrime = material.metalnessMapTransform * vec3( uv, 1 );
					metalness *= texture2D( textures, vec3( uvPrime.xy, material.metalnessMap ) ).b;

				}

				float alphaTest = material.alphaTest;
				bool useAlphaTest = alphaTest != 0.0;
				float transmissionFactor = ( 1.0 - metalness ) * transmission;
				if (
					transmissionFactor < rand( 9 ) && ! (
						// material sidedness
						material.side != 0.0 && surfaceHit.side == material.side

						// alpha test
						|| useAlphaTest && albedo.a < alphaTest

						// opacity
						|| material.transparent && ! useAlphaTest && albedo.a < rand( 10 )
					)
				) {

					result = true;
					break;

				}

				if ( surfaceHit.side == 1.0 && isEntering ) {

					// only attenuate by surface color on the way in
					color *= mix( vec3( 1.0 ), albedo.rgb, transmissionFactor );

				} else if ( surfaceHit.side == - 1.0 ) {

					// attenuate by medium once we hit the opposite side of the model
					color *= transmissionAttenuation( surfaceHit.dist, material.attenuationColor, material.attenuationDistance );

				}

				bool isTransmissiveRay = dot( ray.direction, surfaceHit.faceNormal * surfaceHit.side ) < 0.0;
				if ( ( isTransmissiveRay || isEntering ) && transmissiveTraversals > 0 ) {

					i -= sign( transmissiveTraversals );
					transmissiveTraversals --;

				}

			} else {

				result = false;
				break;

			}

		}

		// reset the bounce index
		sobolBounceIndex = originalBounceIndex;
		return result;

	}

`;var Yn=`

	vec3 ndcToRayOrigin( vec2 coord ) {

		vec4 rayOrigin4 = cameraWorldMatrix * invProjectionMatrix * vec4( coord, - 1.0, 1.0 );
		return rayOrigin4.xyz / rayOrigin4.w;
	}

	Ray getCameraRay() {

		vec2 ssd = vec2( 1.0 ) / resolution;

		// Jitter the camera ray by finding a uv coordinate at a random sample
		// around this pixel's UV coordinate for AA
		vec2 ruv = rand2( 0 );
		vec2 jitteredUv = vUv + vec2( tentFilter( ruv.x ) * ssd.x, tentFilter( ruv.y ) * ssd.y );
		Ray ray;

		#if CAMERA_TYPE == 2

			// Equirectangular projection
			vec4 rayDirection4 = vec4( equirectUvToDirection( jitteredUv ), 0.0 );
			vec4 rayOrigin4 = vec4( 0.0, 0.0, 0.0, 1.0 );

			rayDirection4 = cameraWorldMatrix * rayDirection4;
			rayOrigin4 = cameraWorldMatrix * rayOrigin4;

			ray.direction = normalize( rayDirection4.xyz );
			ray.origin = rayOrigin4.xyz / rayOrigin4.w;

		#else

			// get [- 1, 1] normalized device coordinates
			vec2 ndc = 2.0 * jitteredUv - vec2( 1.0 );
			ray.origin = ndcToRayOrigin( ndc );

			#if CAMERA_TYPE == 1

				// Orthographic projection
				ray.direction = ( cameraWorldMatrix * vec4( 0.0, 0.0, - 1.0, 0.0 ) ).xyz;
				ray.direction = normalize( ray.direction );

			#else

				// Perspective projection
				ray.direction = normalize( mat3( cameraWorldMatrix ) * ( invProjectionMatrix * vec4( ndc, 0.0, 1.0 ) ).xyz );

			#endif

		#endif

		#if FEATURE_DOF
		{

			// depth of field
			vec3 focalPoint = ray.origin + normalize( ray.direction ) * physicalCamera.focusDistance;

			// get the aperture sample
			// if blades === 0 then we assume a circle
			vec3 shapeUVW= rand3( 1 );
			int blades = physicalCamera.apertureBlades;
			float anamorphicRatio = physicalCamera.anamorphicRatio;
			vec2 apertureSample = sampleAperture( blades, shapeUVW );
			apertureSample *= physicalCamera.bokehSize * 0.5 * 1e-3;

			// rotate the aperture shape
			apertureSample =
				rotateVector( apertureSample, physicalCamera.apertureRotation ) *
				saturate( vec2( anamorphicRatio, 1.0 / anamorphicRatio ) );

			// create the new ray
			ray.origin += ( cameraWorldMatrix * vec4( apertureSample, 0.0, 0.0 ) ).xyz;
			ray.direction = focalPoint - ray.origin;

		}
		#endif

		ray.direction = normalize( ray.direction );

		return ray;

	}

`;var $n=`

	vec3 directLightContribution( vec3 worldWo, SurfaceRecord surf, RenderState state, vec3 rayOrigin ) {

		vec3 result = vec3( 0.0 );

		// uniformly pick a light or environment map
		if( lightsDenom != 0.0 && rand( 5 ) < float( lights.count ) / lightsDenom ) {

			// sample a light or environment
			LightRecord lightRec = randomLightSample( lights.tex, iesProfiles, lights.count, rayOrigin, rand3( 6 ) );

			bool isSampleBelowSurface = ! surf.volumeParticle && dot( surf.faceNormal, lightRec.direction ) < 0.0;
			if ( isSampleBelowSurface ) {

				lightRec.pdf = 0.0;

			}

			// check if a ray could even reach the light area
			Ray lightRay;
			lightRay.origin = rayOrigin;
			lightRay.direction = lightRec.direction;
			vec3 attenuatedColor;
			if (
				lightRec.pdf > 0.0 &&
				isDirectionValid( lightRec.direction, surf.normal, surf.faceNormal ) &&
				! attenuateHit( state, lightRay, lightRec.dist, attenuatedColor )
			) {

				// get the material pdf
				vec3 sampleColor;
				float lightMaterialPdf = bsdfResult( worldWo, lightRec.direction, surf, sampleColor );
				bool isValidSampleColor = all( greaterThanEqual( sampleColor, vec3( 0.0 ) ) );
				if ( lightMaterialPdf > 0.0 && isValidSampleColor ) {

					// weight the direct light contribution
					float lightPdf = lightRec.pdf / lightsDenom;
					float misWeight = lightRec.type == SPOT_LIGHT_TYPE || lightRec.type == DIR_LIGHT_TYPE || lightRec.type == POINT_LIGHT_TYPE ? 1.0 : misHeuristic( lightPdf, lightMaterialPdf );
					result = attenuatedColor * lightRec.emission * state.throughputColor * sampleColor * misWeight / lightPdf;

				}

			}

		} else if ( envMapInfo.totalSum != 0.0 && environmentIntensity != 0.0 ) {

			// find a sample in the environment map to include in the contribution
			vec3 envColor, envDirection;
			float envPdf = sampleEquirectProbability( rand2( 7 ), envColor, envDirection );
			envDirection = invEnvRotation3x3 * envDirection;

			// this env sampling is not set up for transmissive sampling and yields overly bright
			// results so we ignore the sample in this case.
			// TODO: this should be improved but how? The env samples could traverse a few layers?
			bool isSampleBelowSurface = ! surf.volumeParticle && dot( surf.faceNormal, envDirection ) < 0.0;
			if ( isSampleBelowSurface ) {

				envPdf = 0.0;

			}

			// check if a ray could even reach the surface
			Ray envRay;
			envRay.origin = rayOrigin;
			envRay.direction = envDirection;
			vec3 attenuatedColor;
			if (
				envPdf > 0.0 &&
				isDirectionValid( envDirection, surf.normal, surf.faceNormal ) &&
				! attenuateHit( state, envRay, INFINITY, attenuatedColor )
			) {

				// get the material pdf
				vec3 sampleColor;
				float envMaterialPdf = bsdfResult( worldWo, envDirection, surf, sampleColor );
				bool isValidSampleColor = all( greaterThanEqual( sampleColor, vec3( 0.0 ) ) );
				if ( envMaterialPdf > 0.0 && isValidSampleColor ) {

					// weight the direct light contribution
					envPdf /= lightsDenom;
					float misWeight = misHeuristic( envPdf, envMaterialPdf );
					result = attenuatedColor * environmentIntensity * envColor * state.throughputColor * sampleColor * misWeight / envPdf;

				}

			}

		}

		// Function changed to have a single return statement to potentially help with crashes on Mac OS.
		// See issue #470
		return result;

	}

`;var Xn=`

	#define SKIP_SURFACE 0
	#define HIT_SURFACE 1
	int getSurfaceRecord(
		Material material, SurfaceHit surfaceHit, sampler2DArray attributesArray,
		float accumulatedRoughness,
		inout SurfaceRecord surf
	) {

		if ( material.fogVolume ) {

			vec3 normal = vec3( 0, 0, 1 );

			SurfaceRecord fogSurface;
			fogSurface.volumeParticle = true;
			fogSurface.color = material.color;
			fogSurface.emission = material.emissiveIntensity * material.emissive;
			fogSurface.normal = normal;
			fogSurface.faceNormal = normal;
			fogSurface.clearcoatNormal = normal;

			surf = fogSurface;
			return HIT_SURFACE;

		}

		// uv coord for textures
		vec2 uv = textureSampleBarycoord( attributesArray, ATTR_UV, surfaceHit.barycoord, surfaceHit.faceIndices.xyz ).xy;
		vec4 vertexColor = textureSampleBarycoord( attributesArray, ATTR_COLOR, surfaceHit.barycoord, surfaceHit.faceIndices.xyz );

		// albedo
		vec4 albedo = vec4( material.color, material.opacity );
		if ( material.map != - 1 ) {

			vec3 uvPrime = material.mapTransform * vec3( uv, 1 );
			albedo *= texture2D( textures, vec3( uvPrime.xy, material.map ) );

		}

		if ( material.vertexColors ) {

			albedo *= vertexColor;

		}

		// alphaMap
		if ( material.alphaMap != - 1 ) {

			vec3 uvPrime = material.alphaMapTransform * vec3( uv, 1 );
			albedo.a *= texture2D( textures, vec3( uvPrime.xy, material.alphaMap ) ).x;

		}

		// possibly skip this sample if it's transparent, alpha test is enabled, or we hit the wrong material side
		// and it's single sided.
		// - alpha test is disabled when it === 0
		// - the material sidedness test is complicated because we want light to pass through the back side but still
		// be able to see the front side. This boolean checks if the side we hit is the front side on the first ray
		// and we're rendering the other then we skip it. Do the opposite on subsequent bounces to get incoming light.
		float alphaTest = material.alphaTest;
		bool useAlphaTest = alphaTest != 0.0;
		if (
			// material sidedness
			material.side != 0.0 && surfaceHit.side != material.side

			// alpha test
			|| useAlphaTest && albedo.a < alphaTest

			// opacity
			|| material.transparent && ! useAlphaTest && albedo.a < rand( 3 )
		) {

			return SKIP_SURFACE;

		}

		// fetch the interpolated smooth normal
		vec3 normal = normalize( textureSampleBarycoord(
			attributesArray,
			ATTR_NORMAL,
			surfaceHit.barycoord,
			surfaceHit.faceIndices.xyz
		).xyz );

		// roughness
		float roughness = material.roughness;
		if ( material.roughnessMap != - 1 ) {

			vec3 uvPrime = material.roughnessMapTransform * vec3( uv, 1 );
			roughness *= texture2D( textures, vec3( uvPrime.xy, material.roughnessMap ) ).g;

		}

		// metalness
		float metalness = material.metalness;
		if ( material.metalnessMap != - 1 ) {

			vec3 uvPrime = material.metalnessMapTransform * vec3( uv, 1 );
			metalness *= texture2D( textures, vec3( uvPrime.xy, material.metalnessMap ) ).b;

		}

		// emission
		vec3 emission = material.emissiveIntensity * material.emissive;
		if ( material.emissiveMap != - 1 ) {

			vec3 uvPrime = material.emissiveMapTransform * vec3( uv, 1 );
			emission *= texture2D( textures, vec3( uvPrime.xy, material.emissiveMap ) ).xyz;

		}

		// transmission
		float transmission = material.transmission;
		if ( material.transmissionMap != - 1 ) {

			vec3 uvPrime = material.transmissionMapTransform * vec3( uv, 1 );
			transmission *= texture2D( textures, vec3( uvPrime.xy, material.transmissionMap ) ).r;

		}

		// normal
		if ( material.flatShading ) {

			// if we're rendering a flat shaded object then use the face normals - the face normal
			// is provided based on the side the ray hits the mesh so flip it to align with the
			// interpolated vertex normals.
			normal = surfaceHit.faceNormal * surfaceHit.side;

		}

		vec3 baseNormal = normal;
		if ( material.normalMap != - 1 ) {

			vec4 tangentSample = textureSampleBarycoord(
				attributesArray,
				ATTR_TANGENT,
				surfaceHit.barycoord,
				surfaceHit.faceIndices.xyz
			);

			// some provided tangents can be malformed (0, 0, 0) causing the normal to be degenerate
			// resulting in NaNs and slow path tracing.
			if ( length( tangentSample.xyz ) > 0.0 ) {

				vec3 tangent = normalize( tangentSample.xyz );
				vec3 bitangent = normalize( cross( normal, tangent ) * tangentSample.w );
				mat3 vTBN = mat3( tangent, bitangent, normal );

				vec3 uvPrime = material.normalMapTransform * vec3( uv, 1 );
				vec3 texNormal = texture2D( textures, vec3( uvPrime.xy, material.normalMap ) ).xyz * 2.0 - 1.0;
				texNormal.xy *= material.normalScale;
				normal = vTBN * texNormal;

			}

		}

		normal *= surfaceHit.side;

		// clearcoat
		float clearcoat = material.clearcoat;
		if ( material.clearcoatMap != - 1 ) {

			vec3 uvPrime = material.clearcoatMapTransform * vec3( uv, 1 );
			clearcoat *= texture2D( textures, vec3( uvPrime.xy, material.clearcoatMap ) ).r;

		}

		// clearcoatRoughness
		float clearcoatRoughness = material.clearcoatRoughness;
		if ( material.clearcoatRoughnessMap != - 1 ) {

			vec3 uvPrime = material.clearcoatRoughnessMapTransform * vec3( uv, 1 );
			clearcoatRoughness *= texture2D( textures, vec3( uvPrime.xy, material.clearcoatRoughnessMap ) ).g;

		}

		// clearcoatNormal
		vec3 clearcoatNormal = baseNormal;
		if ( material.clearcoatNormalMap != - 1 ) {

			vec4 tangentSample = textureSampleBarycoord(
				attributesArray,
				ATTR_TANGENT,
				surfaceHit.barycoord,
				surfaceHit.faceIndices.xyz
			);

			// some provided tangents can be malformed (0, 0, 0) causing the normal to be degenerate
			// resulting in NaNs and slow path tracing.
			if ( length( tangentSample.xyz ) > 0.0 ) {

				vec3 tangent = normalize( tangentSample.xyz );
				vec3 bitangent = normalize( cross( clearcoatNormal, tangent ) * tangentSample.w );
				mat3 vTBN = mat3( tangent, bitangent, clearcoatNormal );

				vec3 uvPrime = material.clearcoatNormalMapTransform * vec3( uv, 1 );
				vec3 texNormal = texture2D( textures, vec3( uvPrime.xy, material.clearcoatNormalMap ) ).xyz * 2.0 - 1.0;
				texNormal.xy *= material.clearcoatNormalScale;
				clearcoatNormal = vTBN * texNormal;

			}

		}

		clearcoatNormal *= surfaceHit.side;

		// sheenColor
		vec3 sheenColor = material.sheenColor;
		if ( material.sheenColorMap != - 1 ) {

			vec3 uvPrime = material.sheenColorMapTransform * vec3( uv, 1 );
			sheenColor *= texture2D( textures, vec3( uvPrime.xy, material.sheenColorMap ) ).rgb;

		}

		// sheenRoughness
		float sheenRoughness = material.sheenRoughness;
		if ( material.sheenRoughnessMap != - 1 ) {

			vec3 uvPrime = material.sheenRoughnessMapTransform * vec3( uv, 1 );
			sheenRoughness *= texture2D( textures, vec3( uvPrime.xy, material.sheenRoughnessMap ) ).a;

		}

		// iridescence
		float iridescence = material.iridescence;
		if ( material.iridescenceMap != - 1 ) {

			vec3 uvPrime = material.iridescenceMapTransform * vec3( uv, 1 );
			iridescence *= texture2D( textures, vec3( uvPrime.xy, material.iridescenceMap ) ).r;

		}

		// iridescence thickness
		float iridescenceThickness = material.iridescenceThicknessMaximum;
		if ( material.iridescenceThicknessMap != - 1 ) {

			vec3 uvPrime = material.iridescenceThicknessMapTransform * vec3( uv, 1 );
			float iridescenceThicknessSampled = texture2D( textures, vec3( uvPrime.xy, material.iridescenceThicknessMap ) ).g;
			iridescenceThickness = mix( material.iridescenceThicknessMinimum, material.iridescenceThicknessMaximum, iridescenceThicknessSampled );

		}

		iridescence = iridescenceThickness == 0.0 ? 0.0 : iridescence;

		// specular color
		vec3 specularColor = material.specularColor;
		if ( material.specularColorMap != - 1 ) {

			vec3 uvPrime = material.specularColorMapTransform * vec3( uv, 1 );
			specularColor *= texture2D( textures, vec3( uvPrime.xy, material.specularColorMap ) ).rgb;

		}

		// specular intensity
		float specularIntensity = material.specularIntensity;
		if ( material.specularIntensityMap != - 1 ) {

			vec3 uvPrime = material.specularIntensityMapTransform * vec3( uv, 1 );
			specularIntensity *= texture2D( textures, vec3( uvPrime.xy, material.specularIntensityMap ) ).a;

		}

		surf.volumeParticle = false;

		surf.faceNormal = surfaceHit.faceNormal;
		surf.normal = normal;

		surf.metalness = metalness;
		surf.color = albedo.rgb;
		surf.emission = emission;

		surf.ior = material.ior;
		surf.transmission = transmission;
		surf.thinFilm = material.thinFilm;
		surf.attenuationColor = material.attenuationColor;
		surf.attenuationDistance = material.attenuationDistance;

		surf.clearcoatNormal = clearcoatNormal;
		surf.clearcoat = clearcoat;

		surf.sheen = material.sheen;
		surf.sheenColor = sheenColor;

		surf.iridescence = iridescence;
		surf.iridescenceIor = material.iridescenceIor;
		surf.iridescenceThickness = iridescenceThickness;

		surf.specularColor = specularColor;
		surf.specularIntensity = specularIntensity;

		// apply perceptual roughness factor from gltf. sheen perceptual roughness is
		// applied by its brdf function
		// https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#microfacet-surfaces
		surf.roughness = roughness * roughness;
		surf.clearcoatRoughness = clearcoatRoughness * clearcoatRoughness;
		surf.sheenRoughness = sheenRoughness;

		// frontFace is used to determine transmissive properties and PDF. If no transmission is used
		// then we can just always assume this is a front face.
		surf.frontFace = surfaceHit.side == 1.0 || transmission == 0.0;
		surf.eta = material.thinFilm || surf.frontFace ? 1.0 / material.ior : material.ior;
		surf.f0 = iorRatioToF0( surf.eta );

		// Compute the filtered roughness value to use during specular reflection computations.
		// The accumulated roughness value is scaled by a user setting and a "magic value" of 5.0.
		// If we're exiting something transmissive then scale the factor down significantly so we can retain
		// sharp internal reflections
		surf.filteredRoughness = applyFilteredGlossy( surf.roughness, accumulatedRoughness );
		surf.filteredClearcoatRoughness = applyFilteredGlossy( surf.clearcoatRoughness, accumulatedRoughness );

		// get the normal frames
		surf.normalBasis = getBasisFromNormal( surf.normal );
		surf.normalInvBasis = inverse( surf.normalBasis );

		surf.clearcoatBasis = getBasisFromNormal( surf.clearcoatNormal );
		surf.clearcoatInvBasis = inverse( surf.clearcoatBasis );

		return HIT_SURFACE;

	}
`;var jn=`

	struct Ray {

		vec3 origin;
		vec3 direction;

	};

	struct SurfaceHit {

		uvec4 faceIndices;
		vec3 barycoord;
		vec3 faceNormal;
		float side;
		float dist;

	};

	struct RenderState {

		bool firstRay;
		bool transmissiveRay;
		bool isShadowRay;
		float accumulatedRoughness;
		int transmissiveTraversals;
		int traversals;
		uint depth;
		vec3 throughputColor;
		Material fogMaterial;

	};

	RenderState initRenderState() {

		RenderState result;
		result.firstRay = true;
		result.transmissiveRay = true;
		result.isShadowRay = false;
		result.accumulatedRoughness = 0.0;
		result.transmissiveTraversals = 0;
		result.traversals = 0;
		result.throughputColor = vec3( 1.0 );
		result.depth = 0u;
		result.fogMaterial.fogVolume = false;
		return result;

	}

`;var Kn=`

	#define NO_HIT 0
	#define SURFACE_HIT 1
	#define LIGHT_HIT 2
	#define FOG_HIT 3

	// Passing the global variable 'lights' into this function caused shader program errors.
	// So global variables like 'lights' and 'bvh' were moved out of the function parameters.
	// For more information, refer to: https://github.com/gkjohnson/three-gpu-pathtracer/pull/457
	int traceScene(
		Ray ray, Material fogMaterial, inout SurfaceHit surfaceHit
	) {

		int result = NO_HIT;
		bool hit = bvhIntersectFirstHit( bvh, ray.origin, ray.direction, surfaceHit.faceIndices, surfaceHit.faceNormal, surfaceHit.barycoord, surfaceHit.side, surfaceHit.dist );

		#if FEATURE_FOG

		if ( fogMaterial.fogVolume ) {

			// offset the distance so we don't run into issues with particles on the same surface
			// as other objects
			float particleDist = intersectFogVolume( fogMaterial, rand( 1 ) );
			if ( particleDist + RAY_OFFSET < surfaceHit.dist ) {

				surfaceHit.side = 1.0;
				surfaceHit.faceNormal = normalize( - ray.direction );
				surfaceHit.dist = particleDist;
				return FOG_HIT;

			}

		}

		#endif

		if ( hit ) {

			result = SURFACE_HIT;

		}

		return result;

	}

`;class wi extends _e{onBeforeRender(){this.setDefine("FEATURE_DOF",this.physicalCamera.bokehSize===0?0:1),this.setDefine("FEATURE_BACKGROUND_MAP",this.backgroundMap?1:0),this.setDefine("FEATURE_FOG",this.materials.features.isUsed("FOG")?1:0)}constructor(e){super({transparent:!0,depthWrite:!1,defines:{FEATURE_MIS:1,FEATURE_RUSSIAN_ROULETTE:1,FEATURE_DOF:1,FEATURE_BACKGROUND_MAP:0,FEATURE_FOG:1,RANDOM_TYPE:2,CAMERA_TYPE:0,DEBUG_MODE:0,ATTR_NORMAL:0,ATTR_TANGENT:1,ATTR_UV:2,ATTR_COLOR:3,MATERIAL_PIXELS:ir},uniforms:{resolution:{value:new Qc},opacity:{value:1},bounces:{value:10},transmissiveBounces:{value:10},filterGlossyFactor:{value:0},physicalCamera:{value:new si},cameraWorldMatrix:{value:new ar},invProjectionMatrix:{value:new ar},bvh:{value:new qr},attributesArray:{value:new hi},materialIndexAttribute:{value:new pt},materials:{value:new pi},textures:{value:new or().texture},lights:{value:new fi},iesProfiles:{value:new or(360,180,{type:Kc,wrapS:Qn,wrapT:Qn}).texture},environmentIntensity:{value:1},environmentRotation:{value:new ar},envMapInfo:{value:new li},backgroundBlur:{value:0},backgroundMap:{value:null},backgroundAlpha:{value:1},backgroundIntensity:{value:1},backgroundRotation:{value:new ar},seed:{value:0},sobolTexture:{value:null},stratifiedTexture:{value:new xi},stratifiedOffsetTexture:{value:new bi(64,1)}},vertexShader:`

				varying vec2 vUv;
				void main() {

					vec4 mvPosition = vec4( position, 1.0 );
					mvPosition = modelViewMatrix * mvPosition;
					gl_Position = projectionMatrix * mvPosition;

					vUv = uv;

				}

			`,fragmentShader:`
				#define RAY_OFFSET 1e-4
				#define INFINITY 1e20

				precision highp isampler2D;
				precision highp usampler2D;
				precision highp sampler2DArray;
				vec4 envMapTexelToLinear( vec4 a ) { return a; }
				#include <common>

				// bvh intersection
				${ye.common_functions}
				${ye.bvh_struct_definitions}
				${ye.bvh_ray_functions}

				// uniform structs
				${In}
				${Pn}
				${Rn}
				${Fn}
				${Mn}

				// random
				#if RANDOM_TYPE == 2 	// Stratified List

					${zn}

				#elif RANDOM_TYPE == 1 	// Sobol

					${Ti}
					${er}
					${Zo}

					#define rand(v) sobol(v)
					#define rand2(v) sobol2(v)
					#define rand3(v) sobol3(v)
					#define rand4(v) sobol4(v)

				#else 					// PCG

				${Ti}

					// Using the sobol functions seems to break the the compiler on MacOS
					// - specifically the "sobolReverseBits" function.
					uint sobolPixelIndex = 0u;
					uint sobolPathIndex = 0u;
					uint sobolBounceIndex = 0u;

					#define rand(v) pcgRand()
					#define rand2(v) pcgRand2()
					#define rand3(v) pcgRand3()
					#define rand4(v) pcgRand4()

				#endif

				// common
				${On}
				${Bn}
				${sr}
				${Nn}
				${Ln}

				// environment
				uniform EquirectHdrInfo envMapInfo;
				uniform mat4 environmentRotation;
				uniform float environmentIntensity;

				// lighting
				uniform sampler2DArray iesProfiles;
				uniform LightsInfo lights;

				// background
				uniform float backgroundBlur;
				uniform float backgroundAlpha;
				#if FEATURE_BACKGROUND_MAP

				uniform sampler2D backgroundMap;
				uniform mat4 backgroundRotation;
				uniform float backgroundIntensity;

				#endif

				// camera
				uniform mat4 cameraWorldMatrix;
				uniform mat4 invProjectionMatrix;
				#if FEATURE_DOF

				uniform PhysicalCamera physicalCamera;

				#endif

				// geometry
				uniform sampler2DArray attributesArray;
				uniform usampler2D materialIndexAttribute;
				uniform sampler2D materials;
				uniform sampler2DArray textures;
				uniform BVH bvh;

				// path tracer
				uniform int bounces;
				uniform int transmissiveBounces;
				uniform float filterGlossyFactor;
				uniform int seed;

				// image
				uniform vec2 resolution;
				uniform float opacity;

				varying vec2 vUv;

				// globals
				mat3 envRotation3x3;
				mat3 invEnvRotation3x3;
				float lightsDenom;

				// sampling
				${En}
				${Dn}
				${Cn}

				${Gn}
				${Un}
				${Wn}
				${Vn}
				${Hn}
				${kn}

				float applyFilteredGlossy( float roughness, float accumulatedRoughness ) {

					return clamp(
						max(
							roughness,
							accumulatedRoughness * filterGlossyFactor * 5.0 ),
						0.0,
						1.0
					);

				}

				vec3 sampleBackground( vec3 direction, vec2 uv ) {

					vec3 sampleDir = sampleHemisphere( direction, uv ) * 0.5 * backgroundBlur;

					#if FEATURE_BACKGROUND_MAP

					sampleDir = normalize( mat3( backgroundRotation ) * direction + sampleDir );
					return backgroundIntensity * sampleEquirectColor( backgroundMap, sampleDir );

					#else

					sampleDir = normalize( envRotation3x3 * direction + sampleDir );
					return environmentIntensity * sampleEquirectColor( envMapInfo.map, sampleDir );

					#endif

				}

				${jn}
				${Yn}
				${Kn}
				${qn}
				${$n}
				${Xn}

				void main() {

					// init
					rng_initialize( gl_FragCoord.xy, seed );
					sobolPixelIndex = ( uint( gl_FragCoord.x ) << 16 ) | uint( gl_FragCoord.y );
					sobolPathIndex = uint( seed );

					// get camera ray
					Ray ray = getCameraRay();

					// inverse environment rotation
					envRotation3x3 = mat3( environmentRotation );
					invEnvRotation3x3 = inverse( envRotation3x3 );
					lightsDenom =
						( environmentIntensity == 0.0 || envMapInfo.totalSum == 0.0 ) && lights.count != 0u ?
							float( lights.count ) :
							float( lights.count + 1u );

					// final color
					gl_FragColor = vec4( 0, 0, 0, 1 );

					// surface results
					SurfaceHit surfaceHit;
					ScatterRecord scatterRec;

					// path tracing state
					RenderState state = initRenderState();
					state.transmissiveTraversals = transmissiveBounces;
					#if FEATURE_FOG

					state.fogMaterial.fogVolume = bvhIntersectFogVolumeHit(
						ray.origin, - ray.direction,
						materialIndexAttribute, materials,
						state.fogMaterial
					);

					#endif

					for ( int i = 0; i < bounces; i ++ ) {

						sobolBounceIndex ++;

						state.depth ++;
						state.traversals = bounces - i;
						state.firstRay = i == 0 && state.transmissiveTraversals == transmissiveBounces;

						int hitType = traceScene( ray, state.fogMaterial, surfaceHit );

						// check if we intersect any lights and accumulate the light contribution
						// TODO: we can add support for light surface rendering in the else condition if we
						// add the ability to toggle visibility of the the light
						if ( ! state.firstRay && ! state.transmissiveRay ) {

							LightRecord lightRec;
							float lightDist = hitType == NO_HIT ? INFINITY : surfaceHit.dist;
							for ( uint i = 0u; i < lights.count; i ++ ) {

								if (
									intersectLightAtIndex( lights.tex, ray.origin, ray.direction, i, lightRec ) &&
									lightRec.dist < lightDist
								) {

									#if FEATURE_MIS

									// weight the contribution
									// NOTE: Only area lights are supported for forward sampling and can be hit
									float misWeight = misHeuristic( scatterRec.pdf, lightRec.pdf / lightsDenom );
									gl_FragColor.rgb += lightRec.emission * state.throughputColor * misWeight;

									#else

									gl_FragColor.rgb += lightRec.emission * state.throughputColor;

									#endif

								}

							}

						}

						if ( hitType == NO_HIT ) {

							if ( state.firstRay || state.transmissiveRay ) {

								gl_FragColor.rgb += sampleBackground( ray.direction, rand2( 2 ) ) * state.throughputColor;
								gl_FragColor.a = backgroundAlpha;

							} else {

								#if FEATURE_MIS

								// get the PDF of the hit envmap point
								vec3 envColor;
								float envPdf = sampleEquirect( envRotation3x3 * ray.direction, envColor );
								envPdf /= lightsDenom;

								// and weight the contribution
								float misWeight = misHeuristic( scatterRec.pdf, envPdf );
								gl_FragColor.rgb += environmentIntensity * envColor * state.throughputColor * misWeight;

								#else

								gl_FragColor.rgb +=
									environmentIntensity *
									sampleEquirectColor( envMapInfo.map, envRotation3x3 * ray.direction ) *
									state.throughputColor;

								#endif

							}
							break;

						}

						uint materialIndex = uTexelFetch1D( materialIndexAttribute, surfaceHit.faceIndices.x ).r;
						Material material = readMaterialInfo( materials, materialIndex );

						#if FEATURE_FOG

						if ( hitType == FOG_HIT ) {

							material = state.fogMaterial;
							state.accumulatedRoughness += 0.2;

						} else if ( material.fogVolume ) {

							state.fogMaterial = material;
							state.fogMaterial.fogVolume = surfaceHit.side == 1.0;

							ray.origin = stepRayOrigin( ray.origin, ray.direction, - surfaceHit.faceNormal, surfaceHit.dist );

							i -= sign( state.transmissiveTraversals );
							state.transmissiveTraversals -= sign( state.transmissiveTraversals );
							continue;

						}

						#endif

						// early out if this is a matte material
						if ( material.matte && state.firstRay ) {

							gl_FragColor = vec4( 0.0 );
							break;

						}

						// if we've determined that this is a shadow ray and we've hit an item with no shadow casting
						// then skip it
						if ( ! material.castShadow && state.isShadowRay ) {

							ray.origin = stepRayOrigin( ray.origin, ray.direction, - surfaceHit.faceNormal, surfaceHit.dist );
							continue;

						}

						SurfaceRecord surf;
						if (
							getSurfaceRecord(
								material, surfaceHit, attributesArray, state.accumulatedRoughness,
								surf
							) == SKIP_SURFACE
						) {

							// only allow a limited number of transparency discards otherwise we could
							// crash the context with too long a loop.
							i -= sign( state.transmissiveTraversals );
							state.transmissiveTraversals -= sign( state.transmissiveTraversals );

							ray.origin = stepRayOrigin( ray.origin, ray.direction, - surfaceHit.faceNormal, surfaceHit.dist );
							continue;

						}

						scatterRec = bsdfSample( - ray.direction, surf );
						state.isShadowRay = scatterRec.specularPdf < rand( 4 );

						bool isBelowSurface = ! surf.volumeParticle && dot( scatterRec.direction, surf.faceNormal ) < 0.0;
						vec3 hitPoint = stepRayOrigin( ray.origin, ray.direction, isBelowSurface ? - surf.faceNormal : surf.faceNormal, surfaceHit.dist );

						// next event estimation
						#if FEATURE_MIS

						gl_FragColor.rgb += directLightContribution( - ray.direction, surf, state, hitPoint );

						#endif

						// accumulate a roughness value to offset diffuse, specular, diffuse rays that have high contribution
						// to a single pixel resulting in fireflies
						// TODO: handle transmissive surfaces
						if ( ! surf.volumeParticle && ! isBelowSurface ) {

							// determine if this is a rough normal or not by checking how far off straight up it is
							vec3 halfVector = normalize( - ray.direction + scatterRec.direction );
							state.accumulatedRoughness += max(
								sin( acosApprox( dot( halfVector, surf.normal ) ) ),
								sin( acosApprox( dot( halfVector, surf.clearcoatNormal ) ) )
							);

							state.transmissiveRay = false;

						}

						// accumulate emissive color
						gl_FragColor.rgb += ( surf.emission * state.throughputColor );

						// skip the sample if our PDF or ray is impossible
						if ( scatterRec.pdf <= 0.0 || ! isDirectionValid( scatterRec.direction, surf.normal, surf.faceNormal ) ) {

							break;

						}

						// if we're bouncing around the inside a transmissive material then decrement
						// perform this separate from a bounce
						bool isTransmissiveRay = ! surf.volumeParticle && dot( scatterRec.direction, surf.faceNormal * surfaceHit.side ) < 0.0;
						if ( ( isTransmissiveRay || isBelowSurface ) && state.transmissiveTraversals > 0 ) {

							state.transmissiveTraversals --;
							i --;

						}

						//

						// handle throughput color transformation
						// attenuate the throughput color by the medium color
						if ( ! surf.frontFace ) {

							state.throughputColor *= transmissionAttenuation( surfaceHit.dist, surf.attenuationColor, surf.attenuationDistance );

						}

						#if FEATURE_RUSSIAN_ROULETTE

						// russian roulette path termination
						// https://www.arnoldrenderer.com/research/physically_based_shader_design_in_arnold.pdf
						uint minBounces = 3u;
						float depthProb = float( state.depth < minBounces );

						float rrProb = luminance( state.throughputColor * scatterRec.color / scatterRec.pdf );
						rrProb /= luminance( state.throughputColor );
						rrProb = sqrt( rrProb );
						rrProb = max( rrProb, depthProb );
						rrProb = min( rrProb, 1.0 );
						if ( rand( 8 ) > rrProb ) {

							break;

						}

						// perform sample clamping here to avoid bright pixels
						state.throughputColor *= min( 1.0 / rrProb, 20.0 );

						#endif

						// adjust the throughput and discard and exit if we find discard the sample if there are any NaNs
						state.throughputColor *= scatterRec.color / scatterRec.pdf;
						if ( any( isnan( state.throughputColor ) ) || any( isinf( state.throughputColor ) ) ) {

							break;

						}

						//

						// prepare for next ray
						ray.direction = scatterRec.direction;
						ray.origin = hitPoint;

					}

					gl_FragColor.a *= opacity;

					#if DEBUG_MODE == 1

					// output the number of rays checked in the path and number of
					// transmissive rays encountered.
					gl_FragColor.rgb = vec3(
						float( state.depth ),
						transmissiveBounces - state.transmissiveTraversals,
						0.0
					);
					gl_FragColor.a = 1.0;

					#endif

				}

			`});this.setValues(e)}}function*rl(){let{_renderer:e,_fsQuad:t,_blendQuad:r,_primaryTarget:o,_blendTargets:n,_sobolTarget:i,_subframe:s,alpha:l,material:c}=this,m=new Ii,u=new Ii,a=r.material,[f,h]=n;while(!0){if(l)a.opacity=this._opacityFactor/(this.samples+1),c.blending=el,c.opacity=1;else c.opacity=this._opacityFactor/(this.samples+1),c.blending=tl;let[g,d,b,T]=s,p=o.width,x=o.height;c.resolution.set(p*b,x*T),c.sobolTexture=i.texture,c.stratifiedTexture.init(20,c.bounces+c.transmissiveBounces+5),c.stratifiedTexture.next(),c.seed++;let v=this.tiles.x||1,y=this.tiles.y||1,w=v*y,S=Math.ceil(p*b),I=Math.ceil(x*T),R=Math.floor(g*p),A=Math.floor(d*x),P=Math.ceil(S/v),_=Math.ceil(I/y);for(let F=0;F<y;F++)for(let M=0;M<v;M++){let D=e.getRenderTarget(),V=e.autoClear,Re=e.getScissorTest();e.getScissor(m),e.getViewport(u);let Pe=M,Qe=F;if(!this.stableTiles){let he=this._currentTile%(v*y);Pe=he%v,Qe=~~(he/v),this._currentTile=he+1}let Fe=y-Qe-1;if(o.scissor.set(R+Pe*P,A+Fe*_,Math.min(P,S-Pe*P),Math.min(_,I-Fe*_)),o.viewport.set(R,A,S,I),e.setRenderTarget(o),e.setScissorTest(!0),e.autoClear=!1,t.render(e),e.setViewport(u),e.setScissor(m),e.setScissorTest(Re),e.setRenderTarget(D),e.autoClear=V,l)a.target1=f.texture,a.target2=o.texture,e.setRenderTarget(h),r.render(e),e.setRenderTarget(D);if(this.samples+=1/w,M===v-1&&F===y-1)this.samples=Math.round(this.samples);yield}[f,h]=[h,f]}}var Zn=new Zc;class cr{get material(){return this._fsQuad.material}set material(e){this._fsQuad.material.removeEventListener("recompilation",this._compileFunction),e.addEventListener("recompilation",this._compileFunction),this._fsQuad.material=e}get target(){return this._alpha?this._blendTargets[1]:this._primaryTarget}set alpha(e){if(this._alpha===e)return;if(!e)this._blendTargets[0].dispose(),this._blendTargets[1].dispose();this._alpha=e,this.reset()}get alpha(){return this._alpha}get isCompiling(){return Boolean(this._compilePromise)}constructor(e){this.camera=null,this.tiles=new Jc(3,3),this.stableNoise=!1,this.stableTiles=!0,this.samples=0,this._subframe=new Ii(0,0,1,1),this._opacityFactor=1,this._renderer=e,this._alpha=!1,this._fsQuad=new Z(new wi),this._blendQuad=new Z(new ii),this._task=null,this._currentTile=0,this._compilePromise=null,this._sobolTarget=new oi().generate(e),this._primaryTarget=new Ai(1,1,{format:Si,type:_i,magFilter:je,minFilter:je}),this._blendTargets=[new Ai(1,1,{format:Si,type:_i,magFilter:je,minFilter:je}),new Ai(1,1,{format:Si,type:_i,magFilter:je,minFilter:je})],this._compileFunction=()=>{let t=this.compileMaterial(this._fsQuad._mesh);t.then(()=>{if(this._compilePromise===t)this._compilePromise=null}),this._compilePromise=t},this.material.addEventListener("recompilation",this._compileFunction)}compileMaterial(){return this._renderer.compileAsync(this._fsQuad._mesh)}setCamera(e){let{material:t}=this;t.cameraWorldMatrix.copy(e.matrixWorld),t.invProjectionMatrix.copy(e.projectionMatrixInverse),t.physicalCamera.updateFrom(e);let r=0;if(e.projectionMatrix.elements[15]>0)r=1;if(e.isEquirectCamera)r=2;t.setDefine("CAMERA_TYPE",r),this.camera=e}setSize(e,t){if(e=Math.ceil(e),t=Math.ceil(t),this._primaryTarget.width===e&&this._primaryTarget.height===t)return;this._primaryTarget.setSize(e,t),this._blendTargets[0].setSize(e,t),this._blendTargets[1].setSize(e,t),this.reset()}getSize(e){e.x=this._primaryTarget.width,e.y=this._primaryTarget.height}dispose(){this._primaryTarget.dispose(),this._blendTargets[0].dispose(),this._blendTargets[1].dispose(),this._sobolTarget.dispose(),this._fsQuad.dispose(),this._blendQuad.dispose(),this._task=null}reset(){let{_renderer:e,_primaryTarget:t,_blendTargets:r}=this,o=e.getRenderTarget(),n=e.getClearAlpha();if(e.getClearColor(Zn),e.setRenderTarget(t),e.setClearColor(0,0),e.clearColor(),e.setRenderTarget(r[0]),e.setClearColor(0,0),e.clearColor(),e.setRenderTarget(r[1]),e.setClearColor(0,0),e.clearColor(),e.setClearColor(Zn,n),e.setRenderTarget(o),this.samples=0,this._task=null,this.material.stratifiedTexture.stableNoise=this.stableNoise,this.stableNoise)this.material.seed=0,this.material.stratifiedTexture.reset()}update(){if(this.material.onBeforeRender(),this.isCompiling)return;if(!this._task)this._task=rl.call(this);this._task.next()}}import{Color as rs,Vector3 as fl}from"./datacenter-engine.mjs";import{ClampToEdgeWrapping as il,Color as ol,DataTexture as nl,DataUtils as lr,EquirectangularReflectionMapping as sl,HalfFloatType as al,LinearFilter as Jn,RepeatWrapping as cl,RGBAFormat as ll,Spherical as ul,Vector2 as ts}from"./datacenter-engine.mjs";var Ie=new ts,es=new ts,ur=new ul,fr=new ol;class Ri extends nl{constructor(e=512,t=512){super(new Uint16Array(e*t*4),e,t,ll,al,sl,cl,il,Jn,Jn);this.generationCallback=null}update(){this.dispose(),this.needsUpdate=!0;let{data:e,width:t,height:r}=this.image;for(let o=0;o<t;o++)for(let n=0;n<r;n++){es.set(t,r),Ie.set(o/t,n/r),Ie.x-=0.5,Ie.y=1-Ie.y,ur.theta=Ie.x*2*Math.PI,ur.phi=Ie.y*Math.PI,ur.radius=1,this.generationCallback(ur,Ie,es,fr);let s=4*(n*t+o);e[s+0]=lr.toHalfFloat(fr.r),e[s+1]=lr.toHalfFloat(fr.g),e[s+2]=lr.toHalfFloat(fr.b),e[s+3]=lr.toHalfFloat(1)}}copy(e){return super.copy(e),this.generationCallback=e.generationCallback,this}}var is=new fl;class Pi extends Ri{constructor(e=512){super(e,e);this.topColor=new rs().set(16777215),this.bottomColor=new rs().set(0),this.exponent=2,this.generationCallback=(t,r,o,n)=>{is.setFromSpherical(t);let i=is.y*0.5+0.5;n.lerpColors(this.bottomColor,this.topColor,i**this.exponent)}}copy(e){return super.copy(e),this.topColor.copy(e.topColor),this.bottomColor.copy(e.bottomColor),this}}import{ShaderMaterial as ml}from"./datacenter-engine.mjs";class Fi extends ml{get map(){return this.uniforms.map.value}set map(e){this.uniforms.map.value=e}get opacity(){return this.uniforms.opacity.value}set opacity(e){if(this.uniforms)this.uniforms.opacity.value=e}constructor(e){super({uniforms:{map:{value:null},opacity:{value:1}},vertexShader:`
				varying vec2 vUv;
				void main() {

					vUv = uv;
					gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

				}
			`,fragmentShader:`
				uniform sampler2D map;
				uniform float opacity;
				varying vec2 vUv;

				vec4 clampedTexelFatch( sampler2D map, ivec2 px, int lod ) {

					vec4 res = texelFetch( map, ivec2( px.x, px.y ), 0 );

					#if defined( TONE_MAPPING )

					res.xyz = toneMapping( res.xyz );

					#endif

			  		return linearToOutputTexel( res );

				}

				void main() {

					vec2 size = vec2( textureSize( map, 0 ) );
					vec2 pxUv = vUv * size;
					vec2 pxCurr = floor( pxUv );
					vec2 pxFrac = fract( pxUv ) - 0.5;
					vec2 pxOffset;
					pxOffset.x = pxFrac.x > 0.0 ? 1.0 : - 1.0;
					pxOffset.y = pxFrac.y > 0.0 ? 1.0 : - 1.0;

					vec2 pxNext = clamp( pxOffset + pxCurr, vec2( 0.0 ), size - 1.0 );
					vec2 alpha = abs( pxFrac );

					vec4 p1 = mix(
						clampedTexelFatch( map, ivec2( pxCurr.x, pxCurr.y ), 0 ),
						clampedTexelFatch( map, ivec2( pxNext.x, pxCurr.y ), 0 ),
						alpha.x
					);

					vec4 p2 = mix(
						clampedTexelFatch( map, ivec2( pxCurr.x, pxNext.y ), 0 ),
						clampedTexelFatch( map, ivec2( pxNext.x, pxNext.y ), 0 ),
						alpha.x
					);

					gl_FragColor = mix( p1, p2, alpha.y );
					gl_FragColor.a *= opacity;
					#include <premultiplied_alpha_fragment>

				}
			`});this.setValues(e)}}import{DataTexture as hl,DataUtils as dl,EquirectangularReflectionMapping as pl,FloatType as gl,HalfFloatType as vl,LinearFilter as xl,LinearMipMapLinearFilter as yl,RGBAFormat as bl,RepeatWrapping as os,ShaderMaterial as Tl,WebGLRenderTarget as wl}from"./datacenter-engine.mjs";class ns extends Tl{constructor(){super({uniforms:{envMap:{value:null},flipEnvMap:{value:-1}},vertexShader:`
				varying vec2 vUv;
				void main() {

					vUv = uv;
					gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

				}`,fragmentShader:`
				#define ENVMAP_TYPE_CUBE_UV

				uniform samplerCube envMap;
				uniform float flipEnvMap;
				varying vec2 vUv;

				#include <common>
				#include <cube_uv_reflection_fragment>

				${sr}

				void main() {

					vec3 rayDirection = equirectUvToDirection( vUv );
					rayDirection.x *= flipEnvMap;
					gl_FragColor = textureCube( envMap, rayDirection );

				}`});this.depthWrite=!1,this.depthTest=!1}}class mr{constructor(e){this._renderer=e,this._quad=new Z(new ns)}generate(e,t=null,r=null){if(!e.isCubeTexture)throw Error("CubeToEquirectMaterial: Source can only be cube textures.");let o=e.images[0],n=this._renderer,i=this._quad;if(t===null)t=4*o.height;if(r===null)r=2*o.height;let s=new wl(t,r,{type:gl,colorSpace:o.colorSpace}),l=o.height,c=Math.log2(l)-2,m=1/l,u=1/(3*Math.max(Math.pow(2,c),112));i.material.defines.CUBEUV_MAX_MIP=`${c}.0`,i.material.defines.CUBEUV_TEXEL_WIDTH=u,i.material.defines.CUBEUV_TEXEL_HEIGHT=m,i.material.uniforms.envMap.value=e,i.material.uniforms.flipEnvMap.value=e.isRenderTargetTexture?1:-1,i.material.needsUpdate=!0;let a=n.getRenderTarget(),f=n.autoClear;n.autoClear=!0,n.setRenderTarget(s),i.render(n),n.setRenderTarget(a),n.autoClear=f;let h=new Uint16Array(t*r*4),g=new Float32Array(t*r*4);n.readRenderTargetPixels(s,0,0,t,r,g),s.dispose();for(let b=0,T=g.length;b<T;b++)h[b]=dl.toHalfFloat(g[b]);let d=new hl(h,t,r,bl,vl);return d.minFilter=yl,d.magFilter=xl,d.wrapS=os,d.wrapT=os,d.mapping=pl,d.needsUpdate=!0,d}dispose(){this._quad.dispose()}}function Pl(e){return e.extensions.get("EXT_float_blend")}var Ke=new as;class Fl{get multipleImportanceSampling(){return Boolean(this._pathTracer.material.defines.FEATURE_MIS)}set multipleImportanceSampling(e){this._pathTracer.material.setDefine("FEATURE_MIS",e?1:0)}get transmissiveBounces(){return this._pathTracer.material.transmissiveBounces}set transmissiveBounces(e){this._pathTracer.material.transmissiveBounces=e}get bounces(){return this._pathTracer.material.bounces}set bounces(e){this._pathTracer.material.bounces=e}get filterGlossyFactor(){return this._pathTracer.material.filterGlossyFactor}set filterGlossyFactor(e){this._pathTracer.material.filterGlossyFactor=e}get samples(){return this._pathTracer.samples}get target(){return this._pathTracer.target}get tiles(){return this._pathTracer.tiles}get stableNoise(){return this._pathTracer.stableNoise}set stableNoise(e){this._pathTracer.stableNoise=e}get isCompiling(){return Boolean(this._pathTracer.isCompiling)}constructor(e){console.warn('WebGLPathTracer: This class has been deprecated and will be removed in a future release. Use "WebGPUPathTracer" instead.'),this._renderer=e,this._generator=new ri,this._pathTracer=new cr(e),this._queueReset=!1,this._clock=new Al,this._compilePromise=null,this._lowResPathTracer=new cr(e),this._lowResPathTracer.tiles.set(1,1),this._quad=new Z(new Fi({map:null,transparent:!0,blending:ss,premultipliedAlpha:e.getContextAttributes().premultipliedAlpha})),this._materials=null,this._previousEnvironment=null,this._previousBackground=null,this._internalBackground=null,this.renderDelay=100,this.minSamples=5,this.fadeDuration=500,this.enablePathTracing=!0,this.pausePathTracing=!1,this.dynamicLowRes=!1,this.lowResScale=0.25,this.renderScale=1,this.synchronizeRenderSize=!0,this.rasterizeScene=!0,this.renderToCanvas=!0,this.textureSize=new as(1024,1024),this.rasterizeSceneCallback=(t,r)=>{this._renderer.render(t,r)},this.renderToCanvasCallback=(t,r,o)=>{let n=r.autoClear;r.autoClear=!1,o.render(r),r.autoClear=n},this.setScene(new _l,new Sl)}setBVHWorker(e){this._generator.setBVHWorker(e)}setScene(e,t,r={}){e.updateMatrixWorld(!0),t.updateMatrixWorld();let o=this._generator;if(o.setObjects(e),this._buildAsync)return o.generateAsync(r.onProgress).then((n)=>this._updateFromResults(e,t,n));else{let n=o.generate();return this._updateFromResults(e,t,n)}}setSceneAsync(...e){this._buildAsync=!0;let t=this.setScene(...e);return this._buildAsync=!1,t}setCamera(e){this.camera=e,this.updateCamera()}updateCamera(){let e=this.camera;e.updateMatrixWorld(),this._pathTracer.setCamera(e),this._lowResPathTracer.setCamera(e),this.reset()}updateMaterials(){let e=this._pathTracer.material,t=this._renderer,r=this._materials,o=this.textureSize,n=un(r);e.textures.setTextures(t,n,o.x,o.y),e.materials.updateFrom(r,n),this.reset()}updateLights(){let e=this.scene,t=this._renderer,r=this._pathTracer.material,o=fn(e),n=ln(o);r.lights.updateFrom(o,n),r.iesProfiles.setTextures(t,n),this.reset()}updateEnvironment(){let e=this.scene,t=this._pathTracer.material;if(this._internalBackground)this._internalBackground.dispose(),this._internalBackground=null;if(t.backgroundBlur=e.backgroundBlurriness,t.backgroundIntensity=e.backgroundIntensity??1,t.backgroundRotation.makeRotationFromEuler(e.backgroundRotation).invert(),e.background===null)t.backgroundMap=null,t.backgroundAlpha=0;else if(e.background.isColor){this._colorBackground=this._colorBackground||new Pi(16);let r=this._colorBackground;if(!r.topColor.equals(e.background))r.topColor.set(e.background),r.bottomColor.set(e.background),r.update();t.backgroundMap=r,t.backgroundAlpha=1}else if(e.background.isCubeTexture){if(e.background!==this._previousBackground){let r=new mr(this._renderer).generate(e.background);this._internalBackground=r,t.backgroundMap=r,t.backgroundAlpha=1}}else t.backgroundMap=e.background,t.backgroundAlpha=1;if(t.environmentIntensity=e.environment!==null?e.environmentIntensity??1:0,t.environmentRotation.makeRotationFromEuler(e.environmentRotation).invert(),this._previousEnvironment!==e.environment){if(e.environment!==null)if(e.environment.isCubeTexture){let r=new mr(this._renderer).generate(e.environment);t.envMapInfo.updateFrom(r)}else t.envMapInfo.updateFrom(e.environment)}this._previousEnvironment=e.environment,this._previousBackground=e.background,this.reset()}_updateFromResults(e,t,r){let{materials:o,geometry:n,bvh:i,bvhChanged:s,needsMaterialIndexUpdate:l}=r;this._materials=o;let m=this._pathTracer.material;if(s)m.bvh.updateFrom(i),m.attributesArray.updateFrom(n.attributes.normal,n.attributes.tangent,n.attributes.uv,n.attributes.color);if(l)m.materialIndexAttribute.updateFrom(n.attributes.materialIndex);return this._previousScene=e,this.scene=e,this.camera=t,this.updateCamera(),this.updateMaterials(),this.updateEnvironment(),this.updateLights(),r}renderSample(){let e=this._lowResPathTracer,t=this._pathTracer,r=this._renderer,o=this._clock,n=this._quad;if(this._updateScale(),this._queueReset)t.reset(),e.reset(),this._queueReset=!1,n.material.opacity=0,o.start();let i=o.getDelta()*1000,s=o.getElapsedTime()*1000;if(!this.pausePathTracing&&this.enablePathTracing&&this.renderDelay<=s&&!this.isCompiling)t.update();if(t.alpha=t.material.backgroundAlpha!==1||!Pl(r),e.alpha=t.alpha,this.renderToCanvas){let l=this._renderer,c=this.minSamples;if(s>=this.renderDelay&&this.samples>=this.minSamples)if(this.fadeDuration!==0)n.material.opacity=Math.min(n.material.opacity+i/this.fadeDuration,1);else n.material.opacity=1;if(!this.enablePathTracing||this.samples<c||n.material.opacity<1){if(this.dynamicLowRes&&!this.isCompiling){if(e.samples<1)e.material=t.material,e.update();let m=n.material.opacity;n.material.opacity=1-n.material.opacity,n.material.map=e.target.texture,n.render(l),n.material.opacity=m}if(!this.dynamicLowRes&&this.rasterizeScene||this.dynamicLowRes&&this.isCompiling)this.rasterizeSceneCallback(this.scene,this.camera)}if(this.enablePathTracing&&n.material.opacity>0){if(n.material.opacity<1)n.material.blending=this.dynamicLowRes?Rl:Il;n.material.map=t.target.texture,this.renderToCanvasCallback(t.target,l,n),n.material.blending=ss}}}reset(){this._queueReset=!0,this._pathTracer.samples=0}dispose(){this._quad.dispose(),this._quad.material.dispose(),this._pathTracer.dispose()}_updateScale(){if(this.synchronizeRenderSize){this._renderer.getDrawingBufferSize(Ke);let e=Math.floor(this.renderScale*Ke.x),t=Math.floor(this.renderScale*Ke.y);if(this._pathTracer.getSize(Ke),Ke.x!==e||Ke.y!==t){let r=this.lowResScale;this._pathTracer.setSize(e,t),this._lowResPathTracer.setSize(Math.floor(e*r),Math.floor(t*r))}}}getRenderTime(){return this._clock.getElapsedTime()*1000}}export{Fl as WebGLPathTracer};
