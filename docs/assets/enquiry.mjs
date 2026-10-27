// Private sending for the question sheet, loaded only when enquiry-config.json is enabled and the
// visitor reaches the brief. Without it the page keeps its email route exactly as it is.
const INBOX = 'hello@mothandgravel.com';
const BRIEF_LIMIT = 20000;
const BODY_LIMIT = 32 * 1024;
const TURNSTILE = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

export const isLive = config => config?.enabled === true && /^https:\/\//.test(config.endpoint) &&
  typeof config.turnstileSiteKey === 'string' && Boolean(config.turnstileSiteKey);

// The opening copy is true with either delivery route. Only the brief's mail
// help changes once direct inbox sending is available.
function honestCopy() {
  // Previously cached HTML described only the mail-app route. Bring that older
  // copy up to date; current pages already use this route-neutral introduction.
  const boundary = document.querySelector('.question-boundary');
  if (boundary?.textContent.includes('Your mail app sends it;')) boundary.innerHTML = '<strong>A brief to send or keep.</strong> Only your starting question needs an answer. The rest can stay open. Nothing is sent to the studio until you choose to send it.';
  const legacyAside = [...document.querySelectorAll('.journey-aside p')].find(p => p.textContent.includes('nothing leaves this page'));
  if (legacyAside) legacyAside.textContent = 'Your brief is yours to edit, send or keep. Carrying it to the example workbench keeps a draft in this browser tab. Nothing is sent by that handoff.';
  const help = document.getElementById('send-help');
  if (help) help.textContent = `Opens your mail app, addressed to ${INBOX}, with the brief written in.`;
  // #first-work-next already names "Send to Moth & Gravel" or copying into an email, which stays true.
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

// Read the finished words first. Signing and delivery follow the editable brief;
// the name and email still belong to the same form through their form attribute.
function build() {
  const identity = document.createElement('div');
  identity.className = 'enquiry-identity';
  identity.innerHTML = `<p class="mono enquiry-sign-heading">SIGN AND SEND / TO THE STUDIO</p><p class="question-help" id="enquiry-help">Send to Moth &amp; Gravel delivers your edited brief to ${INBOX} with your name and email, so we can reply. Nothing is published.</p>
    <div class="enquiry-field"><label for="enquiry-name">Your name</label><input id="enquiry-name" name="name" type="text" form="enquiry-form" autocomplete="name" maxlength="120" required aria-describedby="enquiry-name-error">
    <p id="enquiry-name-error" class="question-error" hidden>Add the name we should use when we reply.</p></div>
    <div class="enquiry-field"><label for="enquiry-email">Your email</label><input id="enquiry-email" name="email" type="email" form="enquiry-form" autocomplete="email" maxlength="254" required spellcheck="false" aria-describedby="enquiry-email-error">
    <p id="enquiry-email-error" class="question-error" hidden>Add an email address we can reply to, like name@example.com.</p></div>
    <div class="enquiry-trap" aria-hidden="true"><label for="enquiry-website">Leave this empty</label><input id="enquiry-website" name="website" type="text" form="enquiry-form" tabindex="-1" autocomplete="off"></div>`;
  const form = document.createElement('form');
  form.id = 'enquiry-form'; form.className = 'enquiry-send'; form.noValidate = true; form.setAttribute('aria-label', 'Send the brief to Moth & Gravel');
  // Visible feedback only; announcements go through the page's single live region.
  form.innerHTML = `<div class="enquiry-challenge" id="enquiry-challenge"></div>
    <div class="journey-actions brief-send"><button class="button button-brass" type="submit" aria-describedby="enquiry-help">Send to Moth &amp; Gravel</button></div>
    <p class="question-feedback" id="enquiry-status"></p>`;
  return { identity, form };
}

export function start(config) {
  const brief = document.getElementById('brief-text');
  const mail = document.getElementById('send-brief');
  const mailRow = mail?.closest('.brief-send');
  if (!brief || !mailRow || !isLive(config) || !globalThis.crypto?.randomUUID || document.querySelector('.enquiry-send')) return;

  const link = document.createElement('link');
  link.rel = 'stylesheet'; link.href = new URL('./enquiry.css?v=3', import.meta.url).href;
  document.head.append(link);
  const { identity, form } = build();
  mailRow.before(identity, form);
  // The mail route stays, demoted to a quiet fallback; the existing module keeps its href current.
  mailRow.classList.add('enquiry-fallback');
  mail.className = 'enquiry-mail-link';
  mail.textContent = 'Or email us instead ↗';
  honestCopy();

  const name = document.getElementById('enquiry-name');
  const email = document.getElementById('enquiry-email');
  const live = document.getElementById('draft-status');
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
    if (live) live.textContent = fallback ? `${text} email the brief to ${INBOX} instead.` : text;
    if (fallback) {
      // Offer the page's own mail route, with the brief already written in.
      const anchor = document.createElement('a');
      anchor.href = mail.href; anchor.textContent = `email the brief to ${INBOX} instead`;
      status.append(' ', anchor, '.');
    }
  };
  const theme = () => document.documentElement.dataset.theme === 'afterlight' ? 'light' : 'dark';
  function render(turnstile) {
    if (widget !== null) turnstile.remove(widget);
    widget = turnstile.render(holder, {
      sitekey: config.turnstileSiteKey, action: 'enquiry', theme: theme(),
      // The standard widget is 300px wide; a narrow sheet gets the compact one rather than overflowing.
      size: holder.clientWidth < 300 ? 'compact' : 'normal',
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
  // Cloudflare is contacted only once the visitor starts the form, not merely by reaching the brief.
  // Filling in a name and email gives the check time to finish before Send.
  for (const el of [identity, form]) el.addEventListener('focusin', prepare, { once: true });

  function check(field, error, valid) {
    document.getElementById(error).hidden = valid;
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
    const body = JSON.stringify({ id: attempt.id, name: name.value.trim(), email: email.value.trim(), brief: words, turnstileToken: token, website: document.getElementById('enquiry-website').value });
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
    if (result === null) { say('We could not reach the studio. Your words are still here; check your connection, let the check finish, then press Send to Moth & Gravel again.'); return; }
    if (result?.ok === true) {
      const done = document.createElement('p');
      done.className = 'enquiry-sent'; done.tabIndex = -1;
      // TODO(owner): add the reply-time promise here once it is decided, e.g. "…usually within two working days."
      done.textContent = `Sent. We’ll reply to ${email.value.trim()} from ${INBOX}.`;
      themeWatch?.disconnect(); turnstile.remove(widget);
      for (const el of [mailRow, document.getElementById('send-help'), document.getElementById('send-limit')]) if (el) el.hidden = true;
      identity.hidden = true;
      form.replaceChildren(done);
      if (live) live.textContent = done.textContent;
      done.focus();
      return;
    }
    if (result?.error === 'in_progress') { say('Still sending. Wait a moment, let the check finish, then press Send to Moth & Gravel again.'); return; }
    say('This did not go through. You can', true);
  });
}

