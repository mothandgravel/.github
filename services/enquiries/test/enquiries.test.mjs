import { test, beforeEach, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { createHandler, subject, validate } from '../server.mjs';

process.env.NODE_ENV = 'production';
const realFetch = globalThis.fetch;
const ORIGIN = 'https://mothandgravel.com';
const ID = '6f1c1f0e-8d1a-4c47-9a7e-2f5b8d1e4a10';
const ENV = { ENQUIRIES_ENABLED: 'true', RESEND_API_KEY: 're_test', TURNSTILE_SECRET: 'ts_secret' };
const valid = () => ({ id: ID, name: 'Aino Example', email: 'aino@example.fi', brief: 'A repair note nobody reads.\nMore detail.', turnstileToken: 'tok', website: '' });

let calls; let turnstile; let resend;
beforeEach(() => {
  calls = { turnstile: [], resend: [] };
  turnstile = () => Response.json({ success: true, hostname: 'mothandgravel.com' });
  resend = () => Response.json({ id: 'email_1' });
});
globalThis.fetch = async (url, init = {}) => {
  const href = String(url);
  if (href.startsWith('https://challenges.cloudflare.com/')) { calls.turnstile.push(Object.fromEntries(new URLSearchParams(init.body))); return turnstile(); }
  if (href.startsWith('https://api.resend.com/')) { calls.resend.push({ headers: new Headers(init.headers), body: JSON.parse(init.body) }); return resend(); }
  if (href.startsWith('http://127.0.0.1')) return realFetch(url, init);
  throw new Error(`unexpected fetch ${href}`);
};
after(() => { globalThis.fetch = realFetch; });

async function post(body, { env = ENV, headers = {}, method = 'POST', path = '/enquiries' } = {}) {
  const server = createServer(createHandler(env));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const response = await fetch(`http://127.0.0.1:${server.address().port}${path}`, {
      method, headers: { origin: ORIGIN, 'content-type': 'application/json', ...headers },
      body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body),
    });
    const text = await response.text();
    return { status: response.status, headers: response.headers, json: text ? JSON.parse(text) : null };
  } finally { server.close(); }
}

test('sends one email with the visitor as reply-to and the client id as idempotency key', async () => {
  const res = await post(valid());
  assert.equal(res.status, 200);
  assert.deepEqual(res.json, { ok: true });
  assert.equal(res.headers.get('access-control-allow-origin'), ORIGIN);
  assert.equal(calls.resend.length, 1);
  const [{ headers, body }] = calls.resend;
  assert.equal(headers.get('idempotency-key'), `enquiry/${ID}`);
  assert.equal(body.from, 'Moth & Gravel <enquiries@send.mothandgravel.com>');
  assert.deepEqual(body.to, ['hello@mothandgravel.com']);
  assert.equal(body.reply_to, 'aino@example.fi');
  assert.equal(body.subject, 'Enquiry — Aino Example: A repair note nobody reads.');
  assert.match(body.text, /^A repair note nobody reads\.\nMore detail\./);
  assert.equal(body.html, undefined);
});

test('the same id produces the same idempotency key on retry, and Turnstile gets it too', async () => {
  await post(valid()); await post(valid());
  assert.deepEqual(calls.resend.map(c => c.headers.get('idempotency-key')), [`enquiry/${ID}`, `enquiry/${ID}`]);
  assert.deepEqual(calls.turnstile[0], { secret: 'ts_secret', response: 'tok', idempotency_key: ID });
});

test('sender and inbox are configurable', async () => {
  await post(valid(), { env: { ...ENV, ENQUIRY_FROM: 'Studio <a@send.example.com>', ENQUIRY_TO: 'b@example.com' } });
  assert.equal(calls.resend[0].body.from, 'Studio <a@send.example.com>');
  assert.deepEqual(calls.resend[0].body.to, ['b@example.com']);
});

test('only the exact allowed origin is served', async () => {
  for (const origin of ['https://www.mothandgravel.com', 'http://mothandgravel.com', 'https://mothandgravel.com.evil.test', 'null']) {
    const res = await post(valid(), { headers: { origin } });
    assert.equal(res.status, 403, origin);
    assert.equal(res.headers.get('access-control-allow-origin'), null);
  }
  const missing = await post(valid(), { headers: { origin: '' } });
  assert.equal(missing.status, 403);
  assert.equal(calls.resend.length, 0);
});

test('preflight allows the site origin only', async () => {
  const ok = await post(undefined, { method: 'OPTIONS' });
  assert.equal(ok.status, 204);
  assert.equal(ok.headers.get('access-control-allow-origin'), ORIGIN);
  assert.equal(ok.headers.get('access-control-allow-headers'), 'content-type');
  const denied = await post(undefined, { method: 'OPTIONS', headers: { origin: 'https://example.com' } });
  assert.equal(denied.status, 403);
});

test('a filled honeypot returns ok without verifying or sending', async () => {
  const res = await post({ ...valid(), website: 'https://spam.example' });
  assert.deepEqual([res.status, res.json], [200, { ok: true }]);
  assert.equal(calls.turnstile.length + calls.resend.length, 0);
});

test('disabled mode returns 503 and sends nothing', async () => {
  for (const env of [{ ...ENV, ENQUIRIES_ENABLED: 'false' }, { ...ENV, ENQUIRIES_ENABLED: undefined }, { ...ENV, RESEND_API_KEY: '' }]) {
    const res = await post(valid(), { env });
    assert.deepEqual([res.status, res.json.error], [503, 'disabled']);
  }
  assert.equal(calls.resend.length, 0);
  const health = await post(undefined, { env: {}, method: 'GET', path: '/health' });
  assert.deepEqual([health.status, health.json], [200, { ok: true }]);
});

test('rejects non-JSON bodies, oversized bodies and malformed JSON', async () => {
  assert.equal((await post(valid(), { headers: { 'content-type': 'text/plain' } })).status, 415);
  assert.equal((await post({ ...valid(), brief: 'x'.repeat(33 * 1024) })).status, 413);
  assert.equal((await post('{"id":')).status, 400);
  assert.equal(calls.resend.length, 0);
});

test('validation bounds name, email, brief and id', () => {
  const bad = (patch, error) => assert.equal(validate({ ...valid(), ...patch }).error, error, JSON.stringify(patch).slice(0, 60));
  bad({ id: 'not-a-uuid' }, 'invalid_id');
  bad({ id: '6f1c1f0e-8d1a-1c47-9a7e-2f5b8d1e4a10' }, 'invalid_id');
  bad({ name: '' }, 'invalid_name');
  bad({ name: 'a'.repeat(121) }, 'invalid_name');
  bad({ name: 'Aino\r\nBcc: x@example.com' }, 'invalid_name');
  bad({ name: 'Aino\nX' }, 'invalid_name');
  bad({ email: 'not-an-email' }, 'invalid_email');
  bad({ email: 'a@b.fi\r\nBcc: x@example.com' }, 'invalid_email');
  bad({ email: 'a@b.fi, c@d.fi' }, 'invalid_email');
  bad({ email: `${'a'.repeat(64)}@${'b'.repeat(187)}.fi` }, 'invalid_email');
  bad({ brief: '   ' }, 'invalid_brief');
  bad({ brief: 'x'.repeat(20001) }, 'invalid_brief');
  bad({ turnstileToken: '' }, 'invalid_challenge');
  assert.equal(validate({ ...valid(), name: 'a'.repeat(120), email: `${'a'.repeat(64)}@${'b'.repeat(186)}.fi`, brief: 'x'.repeat(20000) }).error, undefined);
  assert.equal(validate(null).error, 'invalid_body');
});

test('invalid input is reported before Turnstile or Resend are called', async () => {
  const res = await post({ ...valid(), email: 'nope' });
  assert.deepEqual([res.status, res.json], [400, { ok: false, error: 'invalid_email' }]);
  assert.equal(calls.turnstile.length + calls.resend.length, 0);
});

test('subject uses the first non-empty brief line, without control characters, within 60 characters', () => {
  assert.equal(subject('Aino', '\n\n  First line\nsecond'), 'Enquiry — Aino: First line');
  assert.equal(subject('Aino', 'tab\there\u2028and\u0007bell'), 'Enquiry — Aino: tab here and bell');
  const long = subject('Aino', 'ä'.repeat(80));
  const topic = long.slice('Enquiry — Aino: '.length);
  assert.equal([...topic].length, 60);
  assert.ok(topic.endsWith('…'));
  assert.ok(!/[\r\n]/.test(subject('Aino', 'a\r\nBcc: x@example.com')));
});

test('Turnstile failures and hostname mismatches are refused', async () => {
  turnstile = () => Response.json({ success: false, 'error-codes': ['invalid-input-response'] });
  assert.deepEqual((await post(valid())).json, { ok: false, error: 'challenge' });
  turnstile = () => Response.json({ success: true, hostname: 'evil.example' });
  assert.equal((await post(valid())).status, 403);
  turnstile = () => { throw new TypeError('network'); };
  assert.equal((await post(valid())).status, 403);
  assert.equal(calls.resend.length, 0);
});

test('Resend errors map to small codes', async () => {
  const cases = [
    [429, 'rate_limit_exceeded', 503, 'busy'],
    [409, 'concurrent_idempotent_requests', 409, 'in_progress'],
    [409, 'invalid_idempotent_request', 409, 'changed_after_send'],
    [422, 'validation_error', 502, 'send_failed'],
    [401, 'missing_api_key', 502, 'send_failed'],
    [500, 'application_error', 502, 'send_failed'],
  ];
  const errors = []; const original = console.error; console.error = line => errors.push(line);
  try {
    for (const [providerStatus, name, status, error] of cases) {
      resend = () => Response.json({ statusCode: providerStatus, name, message: 'aino@example.fi is mentioned here' }, { status: providerStatus });
      const res = await post(valid());
      assert.deepEqual([res.status, res.json], [status, { ok: false, error }], name);
    }
    resend = () => { throw new TypeError('network'); };
    assert.deepEqual((await post(valid())).json, { ok: false, error: 'send_failed' });
  } finally { console.error = original; }
  assert.ok(errors.length > 0);
  assert.ok(errors.every(line => !String(line).includes('aino@example.fi') && !String(line).includes('repair note')), 'logs must not contain visitor data');
});
