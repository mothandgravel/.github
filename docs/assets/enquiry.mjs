// No provider key lives here. Live setup is deliberately disabled in enquiry-config.json.
const root=document.getElementById('private-enquiry');
const key='mg-private-enquiry-v1';
const byId=id=>document.getElementById(id);
const valid=p=>p&&/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(p.id||'')&&/^[0-9a-f]{64}$/.test(p.token||'')&&typeof p.brief==='string'&&p.brief.length<=24000&&typeof p.email==='string'&&typeof p.name==='string';
async function request(url,options={}) {
  const response=await fetch(url,{...options,cache:'no-store',credentials:'omit',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(15000)});
  const data=await response.json();return {response,data};
}
async function initialise() {
  const publicConfig=await (await fetch(new URL('./enquiry-config.json',import.meta.url),{cache:'no-store',credentials:'omit'})).json();
  if(publicConfig.enabled!==true)return;
  const url=new URL(publicConfig.endpoint);
  if(url.username||url.password||url.search||url.hash||url.pathname!=='/'||!(url.protocol==='https:'||(url.protocol==='http:'&&['localhost','127.0.0.1'].includes(url.hostname))))return;
  const endpoint=url.origin;
  const readiness=await request(endpoint+'/config');
  if(!readiness.response.ok||readiness.data.accepting!==true||readiness.data.contract!==1)return;
  const form=byId('enquiry-form'),review=byId('enquiry-review'),status=byId('enquiry-status');
  let pending=null,busy=false;
  try {const saved=JSON.parse(sessionStorage.getItem(key));if(saved?.endpoint===endpoint&&valid(saved.payload)){pending=saved;if(pending.received&&(pending.receipt?.id!==pending.payload.id||pending.receipt?.receipt!=='saved'))pending.received=false;}}catch{}
  root.hidden=false;
  byId('enquiry-boundary').textContent='Your answers stay in this browser until you choose to send the reviewed brief. Sending saves it privately for the studio. Downloading, copying and the example workbench keep their own local drafts.';
  const persist=()=>{try{sessionStorage.setItem(key,JSON.stringify(pending));return true;}catch{return false;}};
  const stateText={pending:'The email is waiting to be sent.',sending:'The email is being handed over.',accepted:'Resend accepted the email. Delivery is not yet confirmed.',delivered:'The studio’s mail server accepted the email. That does not tell us whether someone has read it.',failed:'The email could not complete delivery. The saved question is still available to the studio.',unknown:'The email result is uncertain. The saved question is still available to the studio.'};
  function controls() {
    form.hidden=!!pending;review.hidden=!pending;
    byId('edit-enquiry').hidden=!!pending?.attempted;
    byId('send-enquiry').hidden=!!pending?.attempted;
    byId('check-enquiry').hidden=!pending?.attempted;
    byId('retry-enquiry').hidden=!pending?.attempted||!!pending?.received||!!pending?.conflict;
    byId('new-enquiry').hidden=!pending?.received;
    for(const button of root.querySelectorAll('button'))button.disabled=busy;
    byId('enquiry-consent').textContent=pending?.attempted?'This is the fixed snapshot used for this reference. Changes to the editable brief stay separate.':'Only these words and contact details will leave this browser when you press Send.';
    if(pending){byId('enquiry-contact').textContent=pending.payload.name+' / '+pending.payload.email;byId('enquiry-snapshot').value=pending.payload.brief;}
  }
  function receipt(data) {
    if(data.receipt!=='saved'||data.id!==pending.payload.id||typeof data.receivedAt!=='string')throw new Error('Unconfirmed receipt');
    pending.received=true;pending.receipt=data;const kept=persist();
    status.textContent='Your question is saved privately. Reference '+data.id+'. '+(stateText[data.notification]||'Email delivery is not confirmed.')+(kept?'':' Browser storage is unavailable; this receipt only stays for this visit.');
  }
  function uncertain() {status.textContent='We cannot confirm a receipt yet. Your reviewed words are kept here. Check the receipt or retry this same question; the retry keeps the same reference.';}
  async function check() {
    const {response,data}=await request(endpoint+'/enquiries/'+pending.payload.id,{headers:{Authorization:'Bearer '+pending.payload.token}});
    if(response.ok){receipt(data);return true;}
    if(response.status===404)return false;
    throw new Error('Receipt unavailable');
  }
  async function send() {
    if(busy||!pending||pending.received||pending.conflict)return;
    busy=true;pending.attempted=true;
    const kept=persist();controls();
    status.textContent=kept?'Handing the question over…':'Handing the question over… Browser storage is unavailable; keep this tab open and keep a downloaded brief.';
    try {
      // Check first on retries; a lost POST response must not create another enquiry.
      if(pending.tried&&await check())return;
      pending.tried=true;persist();
      const {response,data}=await request(endpoint+'/enquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pending.payload)});
      if(response.ok)receipt(data);
      else if(response.status===409){pending.conflict=true;persist();status.textContent='This reference conflicts with an earlier request. Keep the brief and contact the studio; a new send has not been confirmed.';}
      else uncertain();
    } catch {if(pending.received)receipt(pending.receipt);else uncertain();}
    finally {busy=false;controls();}
  }
  form.addEventListener('submit',event=>{
    event.preventDefault();
    const brief=byId('brief-text').value;
    if(!brief.trim()){status.textContent='Give the brief a few words before sending.';return;}
    const bytes=crypto.getRandomValues(new Uint8Array(32));
    pending={endpoint,payload:{id:crypto.randomUUID(),token:[...bytes].map(v=>v.toString(16).padStart(2,'0')).join(''),name:byId('enquiry-name').value.trim(),email:byId('enquiry-email').value.trim(),brief,website:byId('enquiry-website').value}};
    controls();byId('enquiry-snapshot').focus();status.textContent='Review these words. Nothing has been sent yet.';
  });
  byId('send-enquiry').addEventListener('click',send);byId('retry-enquiry').addEventListener('click',send);
  byId('edit-enquiry').addEventListener('click',()=>{if(pending?.attempted)return;pending=null;controls();byId('enquiry-name').focus();status.textContent='You can edit the brief and contact details before reviewing again.';});
  byId('check-enquiry').addEventListener('click',async()=>{
    if(busy)return;busy=true;controls();
    try {if(!await check()){if(pending.received)receipt(pending.receipt);else uncertain();}}
    catch {status.textContent=pending.received?'The last receipt confirmed this question was saved. We cannot refresh email status right now.':'Receipt unavailable right now. Keep this tab open and retry the same question when the connection returns.';}
    finally{busy=false;controls();}
  });
  byId('new-enquiry').addEventListener('click',()=>{if(!pending?.received)return;pending=null;try{sessionStorage.removeItem(key);}catch{}controls();status.textContent='The previous question remains saved privately. Review a new brief when you are ready.';byId('enquiry-name').focus();});
  if(pending?.received)receipt(pending.receipt);else if(pending?.attempted)uncertain();controls();
}
if(root)initialise().catch(()=>{}); // Local brief flow remains available if the service cannot be reached.
