# Private enquiries / Resend handoff

**Prepared, not activated.** Static config and container default to disabled. No provider credentials or verified addresses are in this repository. GitHub Pages continues to host the studio; this Node 24 service runs separately on an existing host behind HTTPS with one persistent SQLite volume and **one replica**. It is not a client portal or an authenticated account system.

A browser receipt means the reviewed name, email and brief were committed to private storage together with an email job. It does not promise email delivery, a human read, studio availability or an agreed project. Resend acceptance and verified mail-server delivery remain separate states. No automatic confirmation email is sent to an unverified visitor address.

## Local verification

```sh
npm ci --ignore-scripts
npm test
ENQUIRIES_ENABLED=false node server.mjs
```

The tests use temporary SQLite and fake send/retrieval adapters; signature checks use the real SDK and a test signing secret. They make no email API calls. Node 24's SQLite API is used; a durable volume is required for live operation.

## Host setup, when ready

1. Verify a sending domain in Resend, choose its sender address and the real studio inbox. Provision a server-side API key that permits sending and received-email retrieval when receiving is enabled. Keep keys out of `docs/`, git, client JavaScript and access logs.
2. Supply the `.env.example` variables through the host's secret manager or a private environment file. Generate `RATE_LIMIT_SECRET` from at least 32 random bytes. The real `SITE_ORIGIN` must be the exact HTTPS origin. Mount writable `/data` owned by container user `node` (uid 1000); secure the host volume and backups. A read-only/ephemeral volume is not sufficient.
3. Build `docker build -t mg-enquiries services/enquiries`. Run **one container**, persist `/data`, bind port 8787 to a private interface and terminate HTTPS at the existing host. Do not deploy this local SQLite model to an ephemeral or multi-replica service.
4. Configure the proxy to limit body size to 160 KiB, apply per-visitor rate limits, and omit request bodies, Authorization and webhook signature headers from logs. The built-in limit is 10 new enquiries per hour per direct peer. If a proxy sits in front, set `TRUSTED_PROXY_IP` to its exact socket peer address and make it **overwrite** `X-Real-IP` with the visitor IP. Never trust a client-provided forwarded header. Without this setting visitors behind one proxy share the built-in quota. Restrict origin/CDN access at the host; CORS is not a bot defence.
5. Add a Resend webhook pointing to `https://YOUR-HOST/webhooks/resend`, subscribe to `email.delivered`, `email.bounced`, `email.failed`, `email.complained` and, for receiving, `email.received`. Supply its `whsec_` signing secret. Enable the service only after these values and the volume are correct. Check `/health` and `/config`.
6. For replies, verify a **dedicated receiving subdomain** and its MX records in Resend; use it as `INBOUND_DOMAIN`. Do not replace existing studio-inbox MX records accidentally. A blank inbound domain disables reply routing. The opaque address identifies a thread; it does not authenticate a person. Received content remains untrusted. Only matching sender/thread plain text up to 24,000 characters is kept; no HTML, links or attachments are opened. Unmatched mail remains in Resend for operator review.
7. Run a controlled live rehearsal using addresses you own: send one brief, inspect the saved record, observe delivery, queue one reply, reply to its route and inspect the inbound text. Verify host restart, proxy limits, CORS and backups. **This rehearsal has not happened yet.**
8. Only then set `docs/assets/enquiry-config.json` to `{"enabled":true,"endpoint":"https://YOUR-HOST"}` in a separate reviewed change. The browser asks `/config` before revealing contact fields. If unavailable, the local brief/download flow remains usable. No DNS/host/address is assumed here.

## API boundary

- `POST /enquiries`: JSON `{id,token,name,email,brief,website}`; UUID v4, random 32-byte hex capability, name ≤120, one email ≤254, brief ≤24,000, empty honeypot. Exact allowed Origin required. One transaction saves the immutable snapshot and outbox. Repeat with identical ID/token/content returns the original receipt; changed content/token returns 409. Metadata receipt only.
- `GET /enquiries/UUID`: exact Origin and `Authorization: Bearer TOKEN`. Returns receipt metadata and notification state, never the brief or contact. Missing/wrong capability returns 404. Responses are `no-store`; tokens are never URL parameters. This is a receipt capability, not login.
- `POST /webhooks/resend`: raw-body SDK signature and timestamp verification, durable event deduplication by Svix ID before acknowledgement. Replay is harmless; conflicting payload is rejected. Processing happens after persistence. Completed payloads are redacted while the hash remains for deduplication.
- `GET /health`, `/config`: non-sensitive readiness. Disabled mode accepts nothing and needs no credentials or durable DB.

The browser freezes and reviews the exact contact/brief before an explicit Send. It stores the pending reference/capability in same-tab session storage before the first attempt, reuses them on retries, and checks for an existing receipt first. Network loss is **uncertain**, not success or failure. An uncertain attempt cannot be replaced with a new reference in the UI. If browser storage is blocked, the state only survives that visit; keep the tab and a downloaded brief. Clearing a local draft does not delete a submitted record.

## Outbox and recovery

The frozen payload and `notify/UUID` or `reply/UUID` key survive restarts. Transient/ambiguous send failures back off; a 60-second lease recovers an interrupted worker. Each provider request aborts after 12 seconds. Resend retains idempotency keys for 24 hours; this service stops automatic ambiguous retries after **23 hours** and marks the job `unknown`. Do not blindly create a new key. Inspect provider history and reconcile manually first. A database backup restored far behind reality needs the same reconciliation before workers resume; deduplication is not permanent exactly-once delivery.

A `failed` email state does not erase the saved enquiry. Bounces/complaints remain visible if an earlier delivery is replayed. There is no read tracking and no public reply endpoint.

## Operator actions and private records

Run these only on the host with access to the private database and service environment. `show` prints private content; do not paste it into CI logs, issues or the public site.

```sh
node inspect.mjs list
node inspect.mjs show ENQUIRY_UUID
node inspect.mjs reply ENQUIRY_UUID NEW_REPLY_UUID /private/reply.txt
node inspect.mjs delete ENQUIRY_UUID
```

`reply` is an explicit studio action; it queues the file as plain text to the stored contact and uses the private thread route as Reply-To. Reusing its UUID with different content is rejected. Stop the worker before record deletion; an in-flight send must be resolved first. Deletion removes local enquiry, queued mail and received text; remove related provider records/backups separately. No retention promise is invented: choose and publish the studio's retention/contact policy before activation, establish periodic removal and limit backup retention. Pending inbound events can retain metadata while retrying; inspect these and provider retention as part of that policy.

Back up SQLite using its online backup API or a consistent stopped-service snapshot including WAL; copying only the `.sqlite` file while it is running is unsafe. Test restoration on a private host. Monitor queue age, failed/unknown outbox states and pending events without logging briefs or tokens. Disk-full/write failures must return an error, never a receipt. Reducing public config to disabled hides the form; disabling the service stops all new intake/worker sends. Reconcile any in-flight provider attempt before resuming.

Primary contracts: [idempotency window](https://resend.com/docs/dashboard/emails/idempotency-keys), [raw webhook verification](https://resend.com/docs/webhooks/verify-webhooks-requests), [received body retrieval](https://resend.com/docs/api-reference/emails/retrieve-received-email), [mail-server delivery](https://resend.com/docs/webhooks/emails/delivered).
