import { DatabaseSync } from 'node:sqlite';
import { createHash, timingSafeEqual, randomBytes } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
export const digest = text => createHash('sha256').update(text).digest('hex');
export const idPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
export const tokenPattern = /^[0-9a-f]{64}$/;
export function sameToken(hash, token) {
  return tokenPattern.test(token || '') && timingSafeEqual(Buffer.from(hash,'hex'), Buffer.from(digest(token),'hex'));
}
export class Conflict extends Error {}

export class Store {
  constructor(path) {
    if (path !== ':memory:') mkdirSync(dirname(path), { recursive:true, mode:0o700 });
    this.db = new DatabaseSync(path);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA busy_timeout=5000;
      CREATE TABLE IF NOT EXISTS enquiries(id TEXT PRIMARY KEY, token_hash TEXT NOT NULL,
        snapshot TEXT NOT NULL, snapshot_hash TEXT NOT NULL, route_token TEXT UNIQUE NOT NULL, created INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, enquiry_id TEXT NOT NULL, payload TEXT NOT NULL,
        state TEXT NOT NULL, provider_id TEXT, first_attempt INTEGER, lease_until INTEGER DEFAULT 0,
        next_attempt INTEGER DEFAULT 0, attempts INTEGER DEFAULT 0, error_code TEXT);
      CREATE UNIQUE INDEX IF NOT EXISTS outbox_provider ON outbox(provider_id) WHERE provider_id IS NOT NULL;
      CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, hash TEXT NOT NULL, payload TEXT NOT NULL,
        state TEXT NOT NULL, next_attempt INTEGER DEFAULT 0, attempts INTEGER DEFAULT 0, reason TEXT);
      CREATE TABLE IF NOT EXISTS messages(provider_id TEXT PRIMARY KEY, enquiry_id TEXT NOT NULL,
        sender TEXT NOT NULL, subject TEXT NOT NULL, text TEXT NOT NULL, created INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY, window INTEGER NOT NULL, count INTEGER NOT NULL);`);
  }
  transaction(fn) {
    this.db.exec('BEGIN IMMEDIATE');
    try { const value=fn(); this.db.exec('COMMIT'); return value; }
    catch(error) { this.db.exec('ROLLBACK'); throw error; }
  }
  get(id) { return this.db.prepare('SELECT * FROM enquiries WHERE id=?').get(id); }
  notification(id) { return this.db.prepare('SELECT * FROM outbox WHERE id=?').get('notify/'+id); }
  receive(input, config, now) {
    const snapshot=JSON.stringify({name:input.name,email:input.email,brief:input.brief});
    return this.transaction(()=>{
      const previous=this.get(input.id);
      if(previous) {
        if(!sameToken(previous.token_hash,input.token)||previous.snapshot_hash!==digest(snapshot)) throw new Conflict();
        return previous;
      }
      const route=randomBytes(24).toString('hex');
      this.db.prepare('INSERT INTO enquiries VALUES(?,?,?,?,?,?)').run(input.id,digest(input.token),snapshot,digest(snapshot),route,now);
      // Frozen payload: retries must not change when server configuration changes.
      const payload={from:config.from,to:[config.inbox],replyTo:input.email,
        subject:'A loose end / '+input.id,
        text:'A private question for Moth & Gravel\n\nFrom: '+input.name+' <'+input.email+'>\nReference: '+input.id+'\n\n'+input.brief};
      this.db.prepare('INSERT INTO outbox(id,enquiry_id,payload,state) VALUES(?,?,?,?)').run('notify/'+input.id,input.id,JSON.stringify(payload),'pending');
      return this.get(input.id);
    });
  }
  limit(key, now, maximum=10) {
    const window=Math.floor(now/3600000);
    return this.transaction(()=>{
      const row=this.db.prepare('SELECT * FROM limits WHERE key=?').get(key);
      const count=row?.window===window ? row.count+1 : 1;
      if(count>maximum) return false;
      this.db.prepare('INSERT INTO limits VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET window=excluded.window,count=excluded.count').run(key,window,count);
      this.db.prepare('DELETE FROM limits WHERE window<?').run(window-24);
      return true;
    });
  }
  claimMail(now) {
    return this.transaction(()=>{
      // Leave old ambiguous sends unresolved beyond the provider's deduplication window.
      this.db.prepare("UPDATE outbox SET state='unknown',error_code='idempotency_window_elapsed' WHERE state IN ('pending','sending') AND first_attempt IS NOT NULL AND first_attempt<=?").run(now-23*3600000);
      const row=this.db.prepare("SELECT * FROM outbox WHERE (state='pending' OR (state='sending' AND lease_until<?)) AND next_attempt<=? ORDER BY rowid LIMIT 1").get(now,now);
      if(!row)return null;
      this.db.prepare("UPDATE outbox SET state='sending',first_attempt=COALESCE(first_attempt,?),lease_until=?,attempts=attempts+1 WHERE id=?").run(now,now+60000,row.id);
      return this.db.prepare('SELECT * FROM outbox WHERE id=?').get(row.id);
    });
  }
  sent(id, providerId) {
    // A verified webhook may have arrived while the send response was in flight.
    this.db.prepare("UPDATE outbox SET state=CASE WHEN state IN ('delivered','failed') THEN state ELSE 'accepted' END,provider_id=?,error_code=NULL WHERE id=?").run(providerId,id);
  }
  retryMail(row, now, code, definitive=false) {
    this.db.prepare("UPDATE outbox SET state=?,next_attempt=?,lease_until=0,error_code=? WHERE id=? AND state NOT IN ('delivered','failed')").run(definitive?'failed':'pending',now+Math.min(300000,1000*2**Math.min(row.attempts,8)),code,row.id);
  }
  enqueueEvent(id, raw, event) {
    return this.transaction(()=>{
      const old=this.db.prepare('SELECT * FROM events WHERE id=?').get(id);
      if(old) { if(old.hash!==digest(raw))throw new Conflict();return false; }
      this.db.prepare('INSERT INTO events(id,hash,payload,state) VALUES(?,?,?,?)').run(id,digest(raw),JSON.stringify(event),'pending');return true;
    });
  }
  event(now) { return this.db.prepare("SELECT * FROM events WHERE state='pending' AND next_attempt<=? ORDER BY rowid LIMIT 1").get(now); }
  finishEvent(id, reason='handled') { this.db.prepare("UPDATE events SET state='done',reason=?,payload='{}' WHERE id=?").run(reason,id); }
  retryEvent(row, now) {
    this.db.prepare("UPDATE events SET attempts=attempts+1,next_attempt=? WHERE id=?").run(now+Math.min(300000,1000*2**Math.min(row.attempts,8)),row.id);
  }
  delivery(providerId, state) {
    const row=this.db.prepare('SELECT * FROM outbox WHERE provider_id=?').get(providerId);
    if(!row)return false;
    // Failures (bounce/complaint) remain visible even if an earlier delivery is replayed.
    this.db.prepare("UPDATE outbox SET state=? WHERE id=? AND (state!='failed' OR ?='failed')").run(state,row.id,state);
    return true;
  }
  route(token) { return this.db.prepare('SELECT * FROM enquiries WHERE route_token=?').get(token); }
  hasMessage(providerId) { return !!this.db.prepare('SELECT provider_id FROM messages WHERE provider_id=?').get(providerId); }
  message(input, now) {
    this.db.prepare('INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?,?)').run(input.providerId,input.enquiryId,input.sender,input.subject,input.text,now);
  }
  reply(id, replyId, text, config) {
    return this.transaction(()=>{
      const enquiry=this.get(id);if(!enquiry)throw new Error('Unknown enquiry');
      const contact=JSON.parse(enquiry.snapshot);
      const payload=JSON.stringify({from:config.from,to:[contact.email],replyTo:enquiry.route_token+'@'+config.inboundDomain,
        subject:'Re: A loose end / '+id,text});
      const key='reply/'+replyId;
      const previous=this.db.prepare('SELECT * FROM outbox WHERE id=?').get(key);
      if(previous) {if(previous.payload!==payload||previous.enquiry_id!==id)throw new Conflict();return key;}
      this.db.prepare('INSERT INTO outbox(id,enquiry_id,payload,state) VALUES(?,?,?,?)').run(key,id,payload,'pending');return key;
    });
  }
  close() { this.db.close(); }
}
