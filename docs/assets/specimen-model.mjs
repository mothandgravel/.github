export const returnKey='mg-specimen-return-v1';
export const revisions={
 'host-1':{label:'Host first · revision 1',heading:'Who are you visiting?',options:['Search for your host']},
 'reason-1':{label:'Reason first · revision 1',heading:'What brings you here?',options:['A meeting','A delivery']},
 'reason-2':{label:'Reason first · revision 2',heading:'What brings you here?',options:['A meeting','A delivery','I’m not sure']}
};
export const directions={continue:'Keep reason first as a direction to test',reopen:'Reopen the starting question',open:'Leave the direction unresolved'};
export const empty=()=>({version:1,notes:[],corrections:[],choices:[]});
const text=v=>typeof v==='string'?v.trim().slice(0,1800):'';
export function restore(raw){try{const v=JSON.parse(raw);if(v?.version!==1)return empty();return {version:1,notes:Array.isArray(v.notes)?v.notes.filter(n=>Object.hasOwn(revisions,n?.revision)&&text(n?.text)).slice(-20).map(n=>({revision:n.revision,text:text(n.text)})):[],corrections:Array.isArray(v.corrections)?v.corrections.map(text).filter(Boolean).slice(-20):[],choices:Array.isArray(v.choices)?v.choices.filter(c=>Object.hasOwn(directions,c?.direction)).slice(-20).map(c=>({direction:c.direction,reason:text(c.reason),revision:'reason-2'})):[]};}catch{return empty();}}
export function append(state,kind,value){if(!['notes','corrections','choices'].includes(kind))throw Error('Unknown record');if(state[kind].length>=20)throw Error('This visit has 20 records of this kind. Export it before clearing.');return restore(JSON.stringify({...state,[kind]:[...state[kind],value]}));}
