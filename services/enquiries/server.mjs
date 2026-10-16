// One private enquiry in, one email to the studio inbox out. Stateless by design.
import { createServer } from 'node:http';
import { Resend } from 'resend';

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const EMAIL = /^[^\s@<>()[\]\\,;:"]{1,64}@[^\s@<>()[\]\\,;:"]+\.[^\s@<>()[\]\\,;:"]+$/;
const CONTROL = /[\p{Cc}\p{Zl}\p{Zp}]/u;
const SITEVERIFY = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';
export const TURNSTILE_ACTION = 'enquiry';

export function settings(env = process.env) {
  return {
    enabled: env.ENQUIRIES_ENABLED === 'true' && Boolean(env.RESEND_API_KEY && env.TURNSTILE_SECRET),
    origins: new Set((env.ALLOWED_ORIGINS || 'https://mothandgravel.com').split(',').map(s => s.trim()).filter(Boolean)),
    // Production must never list localhost here.
    hostnames: new Set((env.TURNSTILE_HOSTNAMES || 'mothandgravel.com').split(',').map(s => s.trim()).filter(Boolean)),
    from: env.ENQUIRY_FROM || 'Moth & Gravel <enquiries@mail.mothandgravel.com>',
    to: env.ENQUIRY_TO || 'hello@mothandgravel.com',
    maxBytes: Number(env.MAX_BODY_BYTES) || 32 * 1024,
    resendKey: env.RESEND_API_KEY, turnstileSecret: env.TURNSTILE_SECRET,
  };
}

/** Returns a clean enquiry or the name of the first invalid field. */
export function validate(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return { error: 'invalid_body' };
  const { id, name, email, brief, turnstileToken } = body;
  if (typeof id !== 'string' || !UUID_V4.test(id)) return { error: 'invalid_id' };
  if (typeof name !== 'string' || !name.trim() || name.length > 120 || CONTROL.test(name)) return { error: 'invalid_name' };
  if (typeof email !== 'string' || email.length > 254 || CONTROL.test(email) || !EMAIL.test(email)) return { error: 'invalid_email' };
  if (typeof brief !== 'string' || !brief.trim() || brief.length > 20000) return { error: 'invalid_brief' };
  if (typeof turnstileToken !== 'string' || !turnstileToken || turnstileToken.length > 2048) return { error: 'invalid_challenge' };
  return { value: { id: id.toLowerCase(), name: name.trim(), email: email.trim(), brief, turnstileToken } };
}

export function subject(name, brief) {
  const line = (brief.split(/\r\n|\r|\n/).find(l => l.trim()) || '').replace(/[\p{Cc}\p{Zl}\p{Zp}]/gu, ' ').replace(/\s+/g, ' ').trim();
  const topic = [...line].length > 60 ? [...line].slice(0, 59).join('').trimEnd() + '…' : line;
  return `Enquiry — ${name}: ${topic}`;
}

// Canonical siteverify: success, the expected action and an approved frontend hostname.
// Tokens are single-use; the browser resets its widget after every attempt.
// remoteip is optional and is omitted: X-Forwarded-For can be spoofed, and the visitor's IP is not shared.
async function verifyTurnstile(config, token) {
  const form = new URLSearchParams({ secret: config.turnstileSecret, response: token });
  try {
    const response = await fetch(SITEVERIFY, { method: 'POST', body: form, signal: AbortSignal.timeout(8000) });
    if (!response.ok) return false;
    const result = await response.json();
    return result.success === true && result.action === TURNSTILE_ACTION && config.hostnames.has(result.hostname);
  } catch { return false; }
}

// Resend's validation and auth failures mean our configuration is wrong, not the visitor's words.
function sendFailure(error) {
  if (error?.statusCode === 429) return [503, 'busy'];
  if (error?.name === 'concurrent_idempotent_requests') return [409, 'in_progress'];
  if (error?.name === 'invalid_idempotent_request') return [409, 'changed_after_send'];
  return [502, 'send_failed'];
}

export function createHandler(env = process.env) {
  const config = settings(env);
  const mailer = config.enabled ? new Resend(config.resendKey) : null;
  return async function handle(req, res) {
    const origin = req.headers.origin;
    const allowed = typeof origin === 'string' && config.origins.has(origin);
    const reply = (status, payload) => {
      const headers = { 'content-type': 'application/json', 'cache-control': 'no-store', vary: 'Origin' };
      if (allowed) headers['access-control-allow-origin'] = origin;
      res.writeHead(status, headers).end(JSON.stringify(payload));
    };
    const path = new URL(req.url, 'http://localhost').pathname;
    if (path === '/health' && req.method === 'GET') return reply(200, { ok: true });
    if (path !== '/enquiries') return reply(404, { ok: false, error: 'not_found' });
    if (!allowed) return reply(403, { ok: false, error: 'origin' });
    if (req.method === 'OPTIONS') {
      res.writeHead(204, { 'access-control-allow-origin': origin, 'access-control-allow-methods': 'POST',
        'access-control-allow-headers': 'content-type', 'access-control-max-age': '600', vary: 'Origin' }).end();
      return;
    }
    if (req.method !== 'POST') return reply(405, { ok: false, error: 'method' });
    if (!config.enabled) return reply(503, { ok: false, error: 'disabled' });
    if (!/^application\/json(\s*;|$)/i.test(req.headers['content-type'] || '')) return reply(415, { ok: false, error: 'content_type' });
    if (Number(req.headers['content-length']) > config.maxBytes) return reply(413, { ok: false, error: 'too_large' });
    let size = 0; const chunks = [];
    for await (const chunk of req) {
      size += chunk.length;
      if (size > config.maxBytes) return reply(413, { ok: false, error: 'too_large' });
      chunks.push(chunk);
    }
    let body;
    try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return reply(400, { ok: false, error: 'invalid_json' }); }
    if (typeof body?.website === 'string' && body.website.trim()) return reply(200, { ok: true });
    const { value, error } = validate(body);
    if (error) return reply(400, { ok: false, error });
    if (!(await verifyTurnstile(config, value.turnstileToken))) return reply(403, { ok: false, error: 'challenge' });
    try {
      const { error: failure } = await mailer.emails.send({
        from: config.from, to: [config.to], replyTo: value.email, subject: subject(value.name, value.brief),
        text: `${value.brief.trim()}\n\n—\nFrom: ${value.name} <${value.email}>\nSent from the question sheet on mothandgravel.com.\n`,
      }, { idempotencyKey: `enquiry/${value.id}` });
      if (!failure) return reply(200, { ok: true });
      console.error(JSON.stringify({ severity: 'ERROR', message: 'resend rejected', name: failure.name, status: failure.statusCode }));
      const [status, code] = sendFailure(failure);
      return reply(status, { ok: false, error: code });
    } catch (thrown) {
      console.error(JSON.stringify({ severity: 'ERROR', message: 'resend unreachable', name: thrown?.name }));
      return reply(502, { ok: false, error: 'send_failed' });
    }
  };
}

if (import.meta.main) {
  const handle = createHandler();
  const server = createServer((req, res) => handle(req, res).catch(() => { if (!res.headersSent) res.writeHead(500).end(); }));
  server.requestTimeout = 15000;
  process.on('SIGTERM', () => server.close(() => process.exit(0)));
  server.listen(Number(process.env.PORT) || 8080, () => console.log(JSON.stringify({ severity: 'INFO', message: 'enquiries listening', enabled: settings().enabled })));
}
