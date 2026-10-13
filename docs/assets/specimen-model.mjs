export const returnKey='mg-mending-return-v1';
export const revisions={
 'item-1':{label:'Object first · revision 1',heading:'What are you mending?',options:['Name the item']},
 'damage-1':{label:'Damage first · revision 1',heading:'What needs attention?',options:['A tear','A loose seam']},
 'damage-2':{label:'Damage first · revision 2',heading:'What needs attention?',options:['A tear','A loose seam','Show the worn part']}
};
export const directions={continue:'Keep damage first as a direction to test',reopen:'Reopen the starting question',open:'Leave the direction unresolved'};
export const empty=()=>({version:1,notes:[],corrections:[],choices:[]});
const text=v=>typeof v==='string'?v.trim().slice(0,1800):'';
export function restore(raw){try{const v=JSON.parse(raw);if(v?.version!==1)return empty();return {version:1,notes:Array.isArray(v.notes)?v.notes.filter(n=>Object.hasOwn(revisions,n?.revision)&&text(n?.text)).slice(-20).map(n=>({revision:n.revision,text:text(n.text)})):[],corrections:Array.isArray(v.corrections)?v.corrections.map(text).filter(Boolean).slice(-20):[],choices:Array.isArray(v.choices)?v.choices.filter(c=>Object.hasOwn(directions,c?.direction)).slice(-20).map(c=>({direction:c.direction,reason:text(c.reason),revision:'damage-2'})):[]};}catch{return empty();}}
export function append(state,kind,value){if(!['notes','corrections','choices'].includes(kind))throw Error('Unknown record');if(state[kind].length>=20)throw Error('This visit has 20 records of this kind. Export it before clearing.');return restore(JSON.stringify({...state,[kind]:[...state[kind],value]}));}
