export class Worker {
  constructor(store, provider, config, now=Date.now) { Object.assign(this,{store,provider,config,now});this.running=false; }
  async tick() {
    if(this.running)return;this.running=true;
    try {
      const row=this.store.claimMail(this.now());
      if(row) {
        try {
          const result=await this.provider.send(JSON.parse(row.payload),row.id);
          if(result.error) {
            const name=result.error.name||'provider_error';
            const permanent=['validation_error','missing_required_field','invalid_access','restricted_api_key','invalid_api_key','invalid_idempotent_request'].includes(name);
            this.store.retryMail(row,this.now(),name,permanent);
          } else if(result.data?.id) this.store.sent(row.id,result.data.id);
          else this.store.retryMail(row,this.now(),'unconfirmed_response');
        } catch { this.store.retryMail(row,this.now(),'unconfirmed_response'); }
        return;
      }
      const pending=this.store.event(this.now());if(!pending)return;
      try {
        const event=JSON.parse(pending.payload),id=event.data?.email_id;
        if(['email.delivered','email.bounced','email.failed','email.complained'].includes(event.type)) {
          if(this.store.delivery(id,event.type==='email.delivered'?'delivered':'failed'))this.store.finishEvent(pending.id);
          else if(pending.attempts>=12)this.store.finishEvent(pending.id,'unmatched_delivery');
          else this.store.retryEvent(pending,this.now());
        } else if(event.type==='email.received') await this.inbound(pending,event);
        else this.store.finishEvent(pending.id,'ignored_event_type');
      } catch { this.store.retryEvent(pending,this.now()); }
    } finally {this.running=false;}
  }
  async inbound(pending,event) {
    const id=event.data?.email_id;
    if(typeof id!=='string'||!/^[a-zA-Z0-9-]{1,100}$/.test(id)) {this.store.finishEvent(pending.id,'invalid_email_id');return;}
    if(this.store.hasMessage(id)){this.store.finishEvent(pending.id);return;}
    const recipients=Array.isArray(event.data.to)?event.data.to:[];
    const matches=recipients.flatMap(address=>{
      if(typeof address!=='string')return[];
      const parts=address.toLowerCase().split('@');
      const row=parts.length===2&&parts[1]===this.config.inboundDomain ? this.store.route(parts[0]) : null;
      return row?[row]:[];
    });
    const unique=[...new Map(matches.map(row=>[row.id,row])).values()];
    if(unique.length!==1){this.store.finishEvent(pending.id,'unmatched_recipient');return;}
    const response=await this.provider.received(id);
    if(response.error||!response.data)throw new Error('Retrieval unavailable');
    const mail=response.data,contact=JSON.parse(unique[0].snapshot);
    // Routing identifies a thread, not a person. Received content remains untrusted.
    const sender=typeof mail.from==='string'?mail.from:'';
    const parsed=sender.match(/<([^<>]+)>$/)?.[1]||sender;
    if(parsed.toLowerCase()!==contact.email.toLowerCase()){this.store.finishEvent(pending.id,'sender_mismatch');return;}
    if(!Array.isArray(mail.to)||!mail.to.map(v=>String(v).toLowerCase()).includes(unique[0].route_token+'@'+this.config.inboundDomain)) {
      this.store.finishEvent(pending.id,'recipient_mismatch');return;
    }
    if(typeof mail.text!=='string'||mail.text.length>24000){this.store.finishEvent(pending.id,'unsupported_body');return;}
    this.store.message({providerId:id,enquiryId:unique[0].id,sender,subject:String(mail.subject||'').slice(0,300),text:mail.text},this.now());
    this.store.finishEvent(pending.id);
  }
}
