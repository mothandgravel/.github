import { createServer } from 'node:http';
import { createHmac } from 'node:crypto';
import { isIP } from 'node:net';
import { pathToFileURL } from 'node:url';
import { configuration,emailPattern } from './config.mjs';
import { Store,Conflict,idPattern,tokenPattern,sameToken } from './store.mjs';
import { Worker } from './worker.mjs';
import { provider } from './provider.mjs';

export function validInput(value) {
  return value&&typeof value==='object'&&!Array.isArray(value)&&typeof value.id==='string'&&typeof value.token==='string'&&idPattern.test(value.id)&&tokenPattern.test(value.token)&&
    typeof value.name==='string'&&value.name.trim().length>0&&value.name.length<=120&&!/[\r\n]/.test(value.name)&&
    typeof value.email==='string'&&value.email.length<=254&&emailPattern.test(value.email)&&
    typeof value.brief==='string'&&value.brief.trim().length>0&&value.brief.length<=24000&&
    (value.website===undefined||value.website==='');
}
async function body(req) {
  const parts=[];let size=0;
  for await(const part of req) {size+=part.length;if(size>163840)throw Object.assign(new Error(),{status:413});parts.push(part);}
  return Buffer.concat(parts).toString('utf8');
}
export function service(config,store,adapter,now=Date.now) {
  const worker=new Worker(store,adapter,config,now);
  const server=createServer(async(req,res)=>{
    const origin=req.headers.origin;
    res.setHeader('Cache-Control','no-store');res.setHeader('X-Robots-Tag','noindex');res.setHeader('X-Content-Type-Options','nosniff');
    res.setHeader('Vary','Origin');
    if(origin===config.origin)res.setHeader('Access-Control-Allow-Origin',origin);
    const send=(status,value)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
    try {
      const path=new URL(req.url,'http://localhost').pathname;
      if(req.method==='GET'&&path==='/health')return send(200,{ok:true,accepting:config.enabled});
      if(req.method==='GET'&&path==='/config')return send(200,{accepting:config.enabled,contract:1});
      if(req.method==='OPTIONS'&&origin===config.origin) {
        res.setHeader('Access-Control-Allow-Methods','GET,POST,OPTIONS');res.setHeader('Access-Control-Allow-Headers','Content-Type,Authorization');return send(204,{});
      }
      if(!config.enabled)return send(503,{error:'unavailable'});
      if(req.method==='POST'&&path==='/webhooks/resend') {
        const raw=await body(req);let event;
        try {event=adapter.verify(raw,req.headers);}catch{return send(400,{error:'invalid_signature'});}
        const eventId=req.headers['svix-id'];
        if(typeof eventId!=='string'||eventId.length>200||!event||typeof event.type!=='string')return send(400,{error:'invalid_event'});
        store.enqueueEvent(eventId,raw,event);return send(200,{received:true});
      }
      if(origin!==config.origin)return send(403,{error:'origin_not_allowed'});
      if(req.method==='POST'&&path==='/enquiries') {
        if(!/^application\/json(?:;|$)/i.test(req.headers['content-type']||''))return send(415,{error:'json_required'});
        let input;try{input=JSON.parse(await body(req));}catch(error){return send(error.status||400,{error:'invalid_body'});}
        if(!validInput(input))return send(400,{error:'invalid_enquiry'});
        // Trust a single configured peer only. Its proxy must overwrite X-Real-IP.
        let address=req.socket.remoteAddress||'unknown';
        if(config.proxyIp&&address===config.proxyIp) {
          const forwarded=req.headers['x-real-ip'];
          if(typeof forwarded!=='string'||!isIP(forwarded))return send(400,{error:'proxy_address_required'});
          address=forwarded;
        }
        const peer=createHmac('sha256',config.rateSecret).update(address).digest('hex');
        if(!store.get(input.id)&&!store.limit(peer,now()))return send(429,{error:'slow_down'});
        const saved=store.receive(input,config,now());
        return send(200,{id:saved.id,receivedAt:new Date(saved.created).toISOString(),receipt:'saved',notification:store.notification(saved.id).state});
      }
      const match=path.match(/^\/enquiries\/([0-9a-f-]+)$/);
      if(req.method==='GET'&&match&&idPattern.test(match[1])) {
        const saved=store.get(match[1]),token=req.headers.authorization?.replace(/^Bearer /,'');
        if(!saved||!sameToken(saved.token_hash,token))return send(404,{error:'not_found'});
        return send(200,{id:saved.id,receivedAt:new Date(saved.created).toISOString(),receipt:'saved',notification:store.notification(saved.id).state});
      }
      send(404,{error:'not_found'});
    } catch(error) {send(error instanceof Conflict?409:error.status||500,{error:error instanceof Conflict?'request_conflict':'request_failed'});}
  });
  server.requestTimeout=15000;server.headersTimeout=10000;
  return {server,worker};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) {
  process.umask(0o077);
  const config=configuration();
  // Disabled service does not need a database volume or provider credentials.
  const store=new Store(config.enabled?config.database:':memory:');
  const adapter=config.enabled?provider(config):{};
  const {server,worker}=service(config,store,adapter);
  const timer=config.enabled?setInterval(()=>{worker.tick().catch(()=>console.error('Background processing failed'));},1000):null;
  server.listen(config.port,'0.0.0.0',()=>console.log('Enquiry service listening; accepting='+config.enabled));
  for(const signal of ['SIGTERM','SIGINT'])process.once(signal,()=>{
    clearInterval(timer);server.close(async()=>{while(worker.running)await new Promise(resolve=>setTimeout(resolve,50));store.close();});
  });
}
