import test from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID,randomBytes,createHmac } from 'node:crypto';
import { mkdtempSync,rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Store,Conflict } from '../store.mjs';
import { Worker } from '../worker.mjs';
import { service,validInput } from '../server.mjs';
import { configuration } from '../config.mjs';
import { provider } from '../provider.mjs';
const config={enabled:true,origin:'https://studio.test',from:'studio@example.test',inbox:'owner@example.test',inboundDomain:'replies.example.test',rateSecret:'x'.repeat(32),webhookSecret:'whsec_'+Buffer.from('test secret not production').toString('base64'),apiKey:'re_test_not_live'};
const input=()=>({id:randomUUID(),token:randomBytes(32).toString('hex'),name:'A visitor',email:'visitor@example.test',brief:'A difficult interface.\n<words stay words>'});
function sign(raw,id='msg_test',timestamp=String(Math.floor(Date.now()/1000))) {
 const signature=createHmac('sha256',Buffer.from(config.webhookSecret.slice(6),'base64')).update(id+'.'+timestamp+'.'+raw).digest('base64');
 return {'svix-id':id,'svix-timestamp':timestamp,'svix-signature':'v1,'+signature};
}
test('Receipt survives process restart, fixes the snapshot and never depends on provider availability',()=>{
 const dir=mkdtempSync(join(tmpdir(),'mg-receipt-')),path=join(dir,'private.sqlite'),p=input();let store=new Store(path);
 try {store.receive(p,config,1);store.close();store=new Store(path);assert.equal(store.get(p.id).snapshot,JSON.stringify({name:p.name,email:p.email,brief:p.brief}));store.receive(p,{...config,inbox:'changed@example.test'},2);assert.equal(store.db.prepare('SELECT count(*) AS n FROM outbox').get().n,1);assert.throws(()=>store.receive({...p,brief:'changed'},config,3),Conflict);assert.throws(()=>store.receive({...p,token:randomBytes(32).toString('hex')},config,3),Conflict);assert.deepEqual(JSON.parse(store.notification(p.id).payload).to,[config.inbox]);}finally{store.close();rmSync(dir,{recursive:true});}
});
test('Lost provider response retries the frozen payload and key, stops before the 24h dedup window',async()=>{
 const store=new Store(':memory:'),p=input();let now=1000;const calls=[];
 const worker=new Worker(store,{send:async(payload,key)=>{calls.push({payload,key});throw new Error('response lost');}},config,()=>now);
 try{store.receive(p,config,now);await worker.tick();assert.equal(store.notification(p.id).state,'pending');now+=4000;await worker.tick();assert.deepEqual(calls[0],calls[1]);now=1000+23*3600000;await worker.tick();assert.equal(calls.length,2);assert.equal(store.notification(p.id).state,'unknown');}finally{store.close();}
});
test('Verified delivery means mail-server acceptance; replay cannot erase a later bounce',async()=>{
 const store=new Store(':memory:'),p=input();const worker=new Worker(store,{send:async()=>({data:{id:'provider-1'}})},config);
 try{store.receive(p,config,Date.now());await worker.tick();assert.equal(store.notification(p.id).state,'accepted');for(const [n,type] of ['email.delivered','email.bounced','email.delivered'].entries()){const raw=JSON.stringify({type,data:{email_id:'provider-1'}});store.enqueueEvent('event-'+n,raw,JSON.parse(raw));await worker.tick();}assert.equal(store.notification(p.id).state,'failed');}finally{store.close();}
});
test('HTTP admission, repeat send, protected receipt, signature and durable replay',async t=>{
 const store=new Store(':memory:'),real=provider(config),app=service(config,store,{...real,send:async()=>({data:{id:'sent-1'}})});await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));
 t.after(()=>{app.server.close();store.close();});const url='http://127.0.0.1:'+app.server.address().port,p=input();
 const post=(value,origin=config.origin)=>fetch(url+'/enquiries',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json'},body:JSON.stringify(value)});
 assert.equal((await post(p,'https://other.test')).status,403);
 const replies=await Promise.all([post(p),post(p)]);assert.ok(replies.every(r=>r.status===200));const receipt=await replies[0].json();assert.equal(receipt.receipt,'saved');assert.equal(receipt.notification,'pending');assert.equal(Object.hasOwn(receipt,'brief'),false);
 assert.equal((await post({...p,brief:'mutated'})).status,409);
 assert.equal((await fetch(url+'/enquiries/'+p.id,{headers:{Origin:config.origin}})).status,404);
 const status=await fetch(url+'/enquiries/'+p.id,{headers:{Origin:config.origin,Authorization:'Bearer '+p.token}});assert.equal(status.status,200);assert.equal(status.headers.get('cache-control'),'no-store');assert.equal((await status.text()).includes(p.email),false);
 const raw=JSON.stringify({type:'email.delivered',data:{email_id:'sent-1'}}),headers=sign(raw);
 const hook=(body,h=headers)=>fetch(url+'/webhooks/resend',{method:'POST',headers:h,body});
 assert.equal((await hook(raw+' ')).status,400);assert.equal((await hook(raw)).status,200);assert.equal((await hook(raw)).status,200);
 const changed=JSON.stringify({type:'email.bounced',data:{email_id:'sent-1'}});assert.equal((await hook(changed,sign(changed))).status,409);
 assert.equal((await hook(raw,sign(raw,'msg_old','1'))).status,400);
 await app.worker.tick();await app.worker.tick();assert.equal(store.notification(p.id).state,'delivered');
 assert.equal((await post({...input(),website:'bot filled'})).status,400);
 assert.equal((await post({...input(),brief:'x'.repeat(24001)})).status,400);
 assert.equal((await fetch(url+'/enquiries',{method:'POST',headers:{Origin:config.origin,'Content-Type':'application/json'},body:'x'.repeat(164000)})).status,413);
});
test('Disabled service rejects sending and config refuses incomplete activation',async t=>{
 assert.equal(configuration({}).enabled,false);assert.throws(()=>configuration({ENQUIRIES_ENABLED:'true'}));
 const store=new Store(':memory:'),app=service({...config,enabled:false},store,{});await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));t.after(()=>{app.server.close();store.close();});const url='http://127.0.0.1:'+app.server.address().port;
 assert.equal((await (await fetch(url+'/config')).json()).accepting,false);assert.equal((await fetch(url+'/enquiries',{method:'POST'})).status,503);assert.equal(store.db.prepare('SELECT count(*) AS n FROM enquiries').get().n,0);
});
test('Inbound replies need one thread and matching sender; plaintext is kept inert, no auto-reply',async()=>{
 const store=new Store(':memory:'),p=input();const row=store.receive(p,config,1),address=row.route_token+'@'+config.inboundDomain;let sender='other@example.test';let sends=0;
 const worker=new Worker(store,{send:async()=>{sends++;return {data:{id:'notification'}};},received:async()=>({data:{from:sender,to:[address],subject:'Reply',text:'<script>inert</script>'}})},config);
 try{await worker.tick();for(let i=0;i<2;i++){const event={type:'email.received',data:{email_id:'incoming-'+i,to:[address]}};store.enqueueEvent('received-'+i,JSON.stringify(event),event);await worker.tick();sender=p.email;}
 assert.equal(store.db.prepare('SELECT count(*) AS n FROM messages').get().n,1);assert.equal(store.db.prepare('SELECT text FROM messages').get().text,'<script>inert</script>');assert.equal(sends,1);
 const replyId=randomUUID();store.reply(p.id,replyId,'A considered answer.',config);store.reply(p.id,replyId,'A considered answer.',config);assert.throws(()=>store.reply(p.id,replyId,'Changed.',config),Conflict);assert.equal(store.db.prepare('SELECT count(*) AS n FROM outbox').get().n,2);await worker.tick();assert.equal(sends,2);
 }finally{store.close();}
});
test('Rate budget and field boundaries reject header injection',()=>{
 const store=new Store(':memory:');try{for(let i=0;i<10;i++)assert.ok(store.limit('peer',1));assert.equal(store.limit('peer',1),false);assert.ok(store.limit('peer',3600001));assert.equal(validInput({...input(),name:'a\r\nb'}),false);assert.equal(validInput({...input(),email:'one@example.test,two@example.test'}),false);}finally{store.close();}
});
test('Storage write failure never returns a saved receipt',async t=>{
 const store=new Store(':memory:'),app=service(config,store,{});store.db.exec('PRAGMA query_only=ON');await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));t.after(()=>{app.server.close();store.close();});
 const response=await fetch('http://127.0.0.1:'+app.server.address().port+'/enquiries',{method:'POST',headers:{Origin:config.origin,'Content-Type':'application/json'},body:JSON.stringify(input())});assert.equal(response.status,500);assert.equal((await response.json()).receipt,undefined);
});

test('Full-length non-Latin brief fits the HTTP body budget without truncation',async t=>{
 const store=new Store(':memory:'),app=service(config,store,{});await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));t.after(()=>{app.server.close();store.close();});const p={...input(),brief:'地'.repeat(24000)};const response=await fetch('http://127.0.0.1:'+app.server.address().port+'/enquiries',{method:'POST',headers:{Origin:config.origin,'Content-Type':'application/json'},body:JSON.stringify(p)});assert.equal(response.status,200);assert.equal(JSON.parse(store.get(p.id).snapshot).brief,p.brief);
});
