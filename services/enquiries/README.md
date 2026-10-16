# Private enquiries

A stateless Cloud Run service that turns the question sheet's brief into one email to the studio inbox. It stores nothing. The studio replies from its own inbox, because the email's reply-to is the visitor.

```
browser ── POST /enquiries ──> origin + JSON + 32 KiB cap ──> validation ──> Turnstile siteverify ──> one Resend send ──> hello@mothandgravel.com
```

- `POST /enquiries` takes `{id, name, email, brief, turnstileToken, website}`. `id` is a UUID v4 that the browser generates. `website` is a honeypot: when it is filled, the service answers `{ok:true}` and sends nothing.
- The service refuses any `Origin` other than an exact match from `ALLOWED_ORIGINS`. CORS headers are sent only to that origin.
- Name: 1–120 characters, with no control characters (so no CR/LF). Email: at most 254 characters and one plain address. Brief: 1–20,000 characters.
- Turnstile is verified server-side with canonical siteverify. The service requires `success === true`, action `enquiry`, and a `hostname` from `TURNSTILE_HOSTNAMES`. Tokens are single-use: the browser resets its widget after every attempt, but keeps the same id for unchanged words.
- The service makes one `resend.emails.send` with `idempotencyKey: 'enquiry/' + id`. A retry with the same words cannot send the enquiry twice within Resend's 24-hour window.
- Subject: `Enquiry — {name}: {first non-empty brief line, at most 60 characters}`. The body is plain text.
- Responses are `{ok:true}`, or `{ok:false,error}` with one of: `disabled` (503), `origin` (403), `content_type` (415), `too_large` (413), `invalid_*` (400), `challenge` (403), `busy` (503, Resend rate limit), `in_progress` / `changed_after_send` (409), or `send_failed` (502).
- Logs hold only the Resend error name and status. They never contain bodies, addresses or tokens. `NODE_ENV=production` also silences the SDK's own error logging.
- `GET /health` returns `{ok:true}`.

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `ENQUIRIES_ENABLED` | unset | Anything other than `true` makes `POST` return 503. The service also stays disabled if either secret is missing. |
| `RESEND_API_KEY` | — | Secret Manager `mothandgravel-resend-api-key` (project `navivra`): a dedicated Resend key with Sending access restricted to `mail.mothandgravel.com`. |
| `TURNSTILE_SECRET` | — | Secret Manager `mothandgravel-turnstile-secret`. |
| `ALLOWED_ORIGINS` | `https://mothandgravel.com` | Comma-separated list of exact origins. |
| `TURNSTILE_HOSTNAMES` | `mothandgravel.com` | Comma-separated list of approved frontend hostnames. Never include `localhost` in production. |
| `ENQUIRY_FROM` | `Moth & Gravel <enquiries@mail.mothandgravel.com>` | |
| `ENQUIRY_TO` | `hello@mothandgravel.com` | |

The Cloud Run service, its service account and the two secrets (created without values) are defined in `navivra/navivra-infra` (`infra/stacks/dev/mothandgravel-enquiries.tf`, project `navivra`, region `europe-north1`).

## Local checks

```sh
npm ci --ignore-scripts
npm test                      # node --test, with fetch mocked for Turnstile and Resend
docker build -t mg-enquiries . && docker run --rm -p 127.0.0.1:8080:8080 mg-enquiries
```

## Deploying an image

Infra owns the env and secrets and ignores the image, so a deploy changes only the image:

```sh
TAG=europe-north1-docker.pkg.dev/navivra/navivra-images-dev/mothandgravel-enquiries:$(git rev-parse --short HEAD)
gcloud builds submit services/enquiries --tag "$TAG" --project navivra --region europe-north1
gcloud run deploy mothandgravel-enquiries --image "$TAG" --region europe-north1 --project navivra
```

## Turning it on for visitors

`docs/assets/enquiry-config.json` already holds the Turnstile site key `0x4AAAAAAFYPyz1sDAQn9kl9`. To go live, set `"enabled":true` and `"endpoint":"https://mothandgravel-enquiries-743719878722.europe-north1.run.app/enquiries"`. The question sheet then shows name, email, the Turnstile check and **Send** on its last step. If anything fails, the page offers a prefilled `mailto:` link instead. While the config is disabled, the page is unchanged.

## Sending domain

The Resend sending domain is `mail.mothandgravel.com`, and its DNS records at OVH are already in place. They sit under `mail.`, so the root `MX` (OVH mail for hello@) is unaffected. No CNAME is needed for the run.app endpoint.
