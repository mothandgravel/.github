// Optional private sending for the question sheet. Without a live config, the page keeps its own routes.
const INBOX = 'hello@mothandgravel.com';
const BRIEF_LIMIT = 20000;
const BODY_LIMIT = 32 * 1024;
const TURNSTILE = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

async function readConfig() {
  try {
    const response = await fetch(new URL('./enquiry-config.json', import.meta.url), { cache: 'no-cache' });
    const config = response.ok ? await response.json() : null;
    const live = config?.enabled === true && /^https:\/\//.test(config.endpoint) && typeof config.turnstileSiteKey === 'string' && config.turnstileSiteKey;
    return live ? config : null;
  } catch { return null; }
}

function mailto(brief) {
  const subject = 'A loose end for Moth & Gravel';
  let body = brief;
  // Long mail links fail silently in some clients; point to the full copy instead.
  if (encodeURIComponent(body).length > 6000) body = brief.slice(0, 1200).trimEnd() + '\n\n[Shortened. The full brief is in the question sheet: copy or download it and paste it here.]';
  return `mailto:${INBOX}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

function loadTurnstile() {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = TURNSTILE; script.async = true;
    script.onload = () => window.turnstile ? resolve(window.turnstile) : reject(new Error('Turnstile unavailable'));
    script.onerror = () => reject(new Error('Turnstile unavailable'));
    document.head.append(script);
  });
}

function build() {
  const form = document.createElement('form');
  form.className = 'enquiry-send'; form.noValidate = true; form.setAttribute('aria-labelledby', 'enquiry-heading');
  form.innerHTML = `<p class="mono">IF YOU’RE READY / SEND IT PRIVATELY</p><h3 id="enquiry-heading" tabindex="-1">Send the brief to Moth &amp; Gravel.</h3>
    <p class="question-help">The brief above goes to the studio inbox with your name and email, and we reply by email. Nothing is published.</p>
    <label for="enquiry-name">Your name</label><input id="enquiry-name" name="name" type="text" autocomplete="name" maxlength="120" required aria-describedby="enquiry-name-error">
    <p id="enquiry-name-error" class="question-error" hidden>Add the name we should use when we reply.</p>
    <label for="enquiry-email">Your email</label><input id="enquiry-email" name="email" type="email" autocomplete="email" maxlength="254" required spellcheck="false" aria-describedby="enquiry-email-error">
    <p id="enquiry-email-error" class="question-error" hidden>Add an email address we can reply to, like name@example.com.</p>
    <div class="enquiry-trap" aria-hidden="true"><label for="enquiry-website">Leave this empty</label><input id="enquiry-website" name="website" type="text" tabindex="-1" autocomplete="off"></div>
    <div class="enquiry-challenge" id="enquiry-challenge"></div>
    <div class="journey-actions"><button class="button button-brass" type="submit">Send</button></div>
    <p class="question-feedback" id="enquiry-status" role="status"></p>`;
  return form;
}

async function start() {
  const brief = document.getElementById('brief-text');
  const keep = brief?.closest('.brief-keep');
  if (!keep || !globalThis.crypto?.randomUUID) return;
  const config = await readConfig();
  if (!config) return;

  const form = build();
  keep.after(form);
  const link = document.createElement('link');
  link.rel = 'stylesheet'; link.href = new URL('./enquiry.css?v=1', import.meta.url).href;
  document.head.append(link);

  const name = form.querySelector('#enquiry-name');
  const email = form.querySelector('#enquiry-email');
  const status = form.querySelector('#enquiry-status');
  const button = form.querySelector('button[type="submit"]');
  const holder = form.querySelector('#enquiry-challenge');
  let token = '';
  let widget = null;
  let attempt = { key: '', id: '' };
  let sending = false;
  let themeWatch = null;

  const say = (text, fallback = false) => {
    status.replaceChildren(text);
    if (fallback) {
      const anchor = document.createElement('a');
      anchor.href = mailto(brief.value); anchor.textContent = `email the brief to ${INBOX} instead`;
      status.append(' ', anchor, '.');
    }
  };
  const theme = () => document.documentElement.dataset.theme === 'afterlight' ? 'light' : 'dark';
  function render(turnstile) {
    if (widget !== null) turnstile.remove(widget);
    widget = turnstile.render(holder, {
      sitekey: config.turnstileSiteKey, action: 'enquiry', theme: theme(),
      callback: value => { token = value; },
      'expired-callback': () => { token = ''; },
      'error-callback': () => { token = ''; say('The privacy check could not load. You can', true); },
    });
  }
  let turnstileReady = null;
  function prepare() {
    turnstileReady ??= loadTurnstile().then(turnstile => {
      render(turnstile);
      // Follow the room light, unless the visitor has already passed the check.
      themeWatch = new MutationObserver(() => { if (!token) render(turnstile); });
      themeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
      return turnstile;
    }).catch(() => { say('The privacy check could not load. You can', true); return null; });
    return turnstileReady;
  }
  // Load the third-party check only once the visitor reaches the brief.
  const step = form.closest('[data-step]');
  if (step && step.hidden) {
    const watch = new MutationObserver(() => { if (!step.hidden) { watch.disconnect(); prepare(); } });
    watch.observe(step, { attributes: true, attributeFilter: ['hidden'] });
  } else prepare();

  function check(field, error, valid) {
    form.querySelector(`#${error}`).hidden = valid;
    if (valid) field.removeAttribute('aria-invalid'); else field.setAttribute('aria-invalid', 'true');
    return valid;
  }

  // A corrected field drops its error as soon as it is valid again.
  name.addEventListener('input', () => { if (name.hasAttribute('aria-invalid') && name.value.trim()) check(name, 'enquiry-name-error', true); });
  email.addEventListener('input', () => { if (email.hasAttribute('aria-invalid') && email.checkValidity()) check(email, 'enquiry-email-error', true); });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (sending) return;
    const nameOk = check(name, 'enquiry-name-error', Boolean(name.value.trim()) && name.value.length <= 120);
    const emailOk = check(email, 'enquiry-email-error', Boolean(email.value.trim()) && email.checkValidity());
    if (!nameOk || !emailOk) { (nameOk ? email : name).focus(); say(''); return; }
    const words = brief.value;
    if (!words.trim()) { brief.focus(); say('The brief is empty. Rebuild it from your answers, or write a few words.'); return; }
    if (words.length > BRIEF_LIMIT) { brief.focus(); say(`The brief is longer than this form can carry (${BRIEF_LIMIT.toLocaleString('en')} characters). Shorten it, or`, true); return; }
    const turnstile = await prepare();
    if (!turnstile) return;
    if (!token) { say('Complete the privacy check above, then send.'); holder.scrollIntoView({ block: 'nearest' }); return; }

    // The same words keep the same id, so a retry can never send the enquiry twice.
    const key = JSON.stringify([name.value.trim(), email.value.trim(), words]);
    if (attempt.key !== key) attempt = { key, id: crypto.randomUUID() };
    const body = JSON.stringify({ id: attempt.id, name: name.value.trim(), email: email.value.trim(), brief: words, turnstileToken: token, website: form.querySelector('#enquiry-website').value });
    if (new TextEncoder().encode(body).length > BODY_LIMIT) { say('The brief is too long to send here. Shorten it, or', true); return; }

    sending = true; button.disabled = true; say('Sending…');
    let result;
    try {
      const response = await fetch(config.endpoint, { method: 'POST', headers: { 'content-type': 'application/json' }, body, mode: 'cors', credentials: 'omit' });
      result = await response.json().catch(() => ({ ok: false }));
    } catch {
      result = null;
    }
    sending = false; button.disabled = false;
    // Turnstile tokens are single-use: every completed attempt resets this widget before a retry.
    // The id stays the same for unchanged words, so Resend still sends at most once.
    if (result?.ok !== true) { token = ''; turnstile.reset(widget); }
    if (result === null) { say('We could not reach the studio. Your words are still here; check your connection, let the check finish, then press Send again.'); return; }
    if (result?.ok === true) {
      const done = document.createElement('p');
      done.className = 'enquiry-sent'; done.tabIndex = -1;
      // TODO(owner): add the reply-time promise here once it is decided, e.g. "…usually within two working days."
      done.textContent = `Sent. We’ll reply to ${email.value.trim()} from ${INBOX}.`;
      themeWatch?.disconnect(); turnstile.remove(widget);
      form.replaceChildren(done);
      done.focus();
      return;
    }
    if (result?.error === 'in_progress') { say('Still sending. Wait a moment, let the check finish, then press Send again.'); return; }
    say('This did not go through. You can', true);
  });
}

start();
