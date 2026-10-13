import { isAbsolute } from 'node:path';
import { isIP } from 'node:net';
export const emailPattern = /^[^\s<>@,;\r\n]+@[^\s<>@,;\r\n]+\.[^\s<>@,;\r\n]+$/;
export function configuration(env=process.env) {
  const config={enabled:env.ENQUIRIES_ENABLED==='true',port:Number(env.PORT||8787),
    origin:env.SITE_ORIGIN||'https://mothandgravel.com',database:env.DATABASE_PATH||'/data/enquiries.sqlite',
    from:env.RESEND_FROM_EMAIL,inbox:env.STUDIO_INBOX_EMAIL,apiKey:env.RESEND_API_KEY,
    webhookSecret:env.RESEND_WEBHOOK_SECRET,rateSecret:env.RATE_LIMIT_SECRET,
    inboundDomain:(env.INBOUND_DOMAIN||'').toLowerCase(),proxyIp:env.TRUSTED_PROXY_IP||''};
  if(!Number.isInteger(config.port)||config.port<1||config.port>65535)throw new Error('Invalid PORT');
  if(config.enabled) {
    if(![config.from,config.inbox].every(v=>typeof v==='string'&&v.length<=254&&emailPattern.test(v)))throw new Error('Configure verified sender and studio inbox');
    if(!config.apiKey||!config.webhookSecret?.startsWith('whsec_')||config.rateSecret?.length<32||!config.rateSecret)throw new Error('Configure provider and rate-limit secrets');
    const origin=new URL(config.origin);
    if(origin.origin!==config.origin||origin.protocol!=='https:')throw new Error('SITE_ORIGIN must be an HTTPS origin');
    if(!isAbsolute(config.database))throw new Error('DATABASE_PATH must be absolute');
    if(config.proxyIp&&!isIP(config.proxyIp))throw new Error('TRUSTED_PROXY_IP must be one exact peer IP');
    if(config.inboundDomain&&!/^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$/.test(config.inboundDomain))throw new Error('Invalid INBOUND_DOMAIN');
  }
  return config;
}
