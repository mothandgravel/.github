/** Bind the two actual capture receipts and public media derivatives. */
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const hash=b=>createHash('sha256').update(b).digest('hex');
const still=JSON.parse(await readFile('artifacts/design-review/datacenter/room-capture.json','utf8'));
assert.equal(still.sourceSHA256,hash((await readFile('docs/assets/datacenter-room.mjs','utf8')).replaceAll('\r\n','\n')));
const film=JSON.parse((await readFile('artifacts/design-review/datacenter-film/capture.json','utf8')).replace(/^\uFEFF/,''));delete film.origin;delete film.trim;
const paths=['specimens/data-center/room-cover.jpg','specimens/data-center/recorded-account.mp4','specimens/data-center/recorded-account.webm','specimens/data-center/recorded-account.vtt','notes/016-cover-1600.webp','notes/016-cover-800.webp','notes/016-cover-social.jpg'];
const files=[];
for(const path of paths){let bytes=await readFile(`docs/assets/${path}`);const canonicalLF=path.endsWith('.vtt');if(canonicalLF)bytes=Buffer.from(bytes.toString('utf8').replaceAll('\r\n','\n'));files.push({file:`assets/${path}`,sha256:hash(bytes),bytes:bytes.length,canonicalLF});}
await writeFile('docs/assets/specimens/data-center/capture.json',JSON.stringify({schema:'mg-datacenter-capture-1',still,film,files,scope:'Authored room. Facility observations and counterfactual supply are labelled separately. Stills use progressive light refinement; film uses real-time lighting. No photographed or surveyed ESIF interior is implied.',credit:'Recorded data: DOE/NREL/ALLIANCE; Clark & Strelka; DOI 10.7799/3015212. Room and interface: Moth & Gravel. Environment and normal map: CC0, see assets/data-center/materials.json.'},null,2)+'\n');
