import { Resend } from 'resend';
export function provider(config) {
  const resend=new Resend(config.apiKey);
  // Per-request abort, including a lost response. The outbox keeps the same key.
  const options=()=>({signal:AbortSignal.timeout(12000)});
  return {
    send:(payload,key)=>resend.emails.send(payload,{...options(),idempotencyKey:key}),
    received:id=>resend.emails.receiving.get(id,{},options()),
    verify:(raw,headers)=>resend.webhooks.verify({payload:raw,headers:{id:headers['svix-id'],timestamp:headers['svix-timestamp'],signature:headers['svix-signature']},webhookSecret:config.webhookSecret})
  };
}
