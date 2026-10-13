import { readFileSync } from 'node:fs';
import { configuration } from './config.mjs';
import { Store,idPattern } from './store.mjs';
process.umask(0o077);
const config=configuration();
if(!config.enabled)throw new Error('Service is disabled. Configure it before inspecting private records.');
const store=new Store(config.database);
try {
  const [command,id,replyId,file]=process.argv.slice(2);
  if(command==='list')console.log(JSON.stringify(store.db.prepare('SELECT e.id,e.created,o.state FROM enquiries e JOIN outbox o ON o.id=\'notify/\'||e.id ORDER BY e.created DESC').all(),null,2));
  else if(command==='show'&&idPattern.test(id||''))console.log(JSON.stringify({enquiry:store.get(id),messages:store.db.prepare('SELECT * FROM messages WHERE enquiry_id=?').all(id)},null,2));
  else if(command==='reply'&&idPattern.test(id||'')&&idPattern.test(replyId||'')&&file&&config.inboundDomain) {
    const text=readFileSync(file,'utf8');if(!text.trim()||text.length>24000)throw new Error('Reply must contain 1–24000 characters');
    console.log('Queued '+store.reply(id,replyId,text,config));
  } else if(command==='delete'&&idPattern.test(id||'')) {
    store.transaction(()=>{
      if(store.db.prepare("SELECT id FROM outbox WHERE enquiry_id=? AND state='sending'").get(id))throw new Error('Stop the service and resolve any in-flight send before deletion');
      store.db.prepare('DELETE FROM messages WHERE enquiry_id=?').run(id);
      store.db.prepare('DELETE FROM outbox WHERE enquiry_id=?').run(id);
      store.db.prepare('DELETE FROM enquiries WHERE id=?').run(id);
    });console.log('Deleted local record; provider records and backups need separate removal.');
  } else throw new Error('Usage: inspect list | show ID | reply ID REPLY_UUID TEXT_FILE | delete ID');
} finally {store.close();}
