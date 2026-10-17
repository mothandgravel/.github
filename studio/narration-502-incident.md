# Note 013: a 502 response after the socket-timeout correction

This record continues the live rehearsal; it does not record successful narration
or publication. Base for the proposed changes: PR #39, `3f232218`.

## Evidence from the operator

Two supplied receipts describe different attempts at the same third narration
request. The older receipt records `TimeoutError` after `180.1715` seconds. The
newer receipt records `timeout_seconds: 600`, `attempt_seconds: 240.2283`, and
`http_status: 502`, with status still `uncertain`. Their request hashes match;
their attempt IDs differ. The newly supplied receipt therefore does not show a
second failure at the old 180-second client limit.

The surrounding operator history previously confirmed saved chunks 1 and 2. The
new third-chunk receipt does not itself validate those WAVs; recovery must still
verify them. It establishes neither provider completion nor billing for chunk 3.
There is no evidence here that a larger client timeout, reauthentication, a new
bucket, different voice, different model, or changed script would fix this 502.
A single response around four minutes is not proof of a fixed server deadline.

The provider message contains an HTML error page's CSS rather than its useful
body text. The previous parser removed tags but retained style/script content,
then truncated the resulting string. The error body is already truncated in the
supplied receipt; its missing text cannot be reconstructed from that file.

HTTP 502 denotes a gateway/proxy receiving an invalid upstream response, per
RFC 9110 section 15.6.3. That status alone does not identify the responsible
component or explain the underlying failure.

## Product corrections in this proposed patch

- Extract visible error text with an inert, bounded HTML parser; discard styles,
  scripts, templates and similar hidden content before limiting the message.
  Preserve structured provider status and redact recognized credentials.
- Include elapsed time and the captured socket-timeout policy in HTTP failure
  messages. A 502 receipt is explicitly distinguished from a client timeout.
- Display a short validated attempt ID and the current receipt path during
  recovery inspection, without rendering arbitrary provider HTML or CSS.
- Identify catalogue failure text as job history from its last refresh, with the
  saved job ID and creation timestamp. It is not a live narration-receipt read.
- Refresh an existing preparation window on explicit reopening. Apply selection
  after the read to avoid a queued Tk selection event discarding the refresh.
- Replace the submitted note's previous failure summary when queueing succeeds;
  do not replace another selected note's content on a late acknowledgement.

No request payload, script, voice, model, endpoint, timeout, billing settings,
cache identity, receipt, or public output is changed by these corrections. There
is no automatic retry or hidden consent. Existing job histories are not rewritten.

## Recovery boundary

Keep the current job stopped while inspecting its evidence. In the existing UI,
**Refresh notes**, then **Inspect script / recovery**, reads the current state.
The current diagnostic should be **HTTP 502**, with a **600s** policy and an
approximately **240.2s** attempt, not the older TimeoutError message.

A further attempt is a new, potentially billable request for the uncertain third
chunk, not retrieval of a saved asynchronous narration result. It needs both
explicit consents bound to the new receipt. The first two chunks remain subject
to ordinary hash verification and reuse. Do not delete the receipt or repeat the
whole episode. A longer timeout is not a remedy established by this evidence.

## Validation scope

Regression tests simulate the sequence: two saved chunks, an uncertain third
chunk at 180s, then a separately authorized third-chunk attempt receiving 502
at 240.2s with a 600s client policy. They assert that the current receipt and job
show 502, the old job remains historical, both saved WAV hashes are preserved,
and old recovery consent is rejected. HTML cleaning, bounded reads, redaction,
and real Tk reopening/acknowledgement behavior are also checked.

All Cloud calls in tests are mocked. Local encoding, receipt handling, journal,
selection controls, and cache validation are real. These tests do not fix the
upstream 502 or demonstrate a successful live retry, voice quality, or release.

Reference: https://www.rfc-editor.org/rfc/rfc9110.html#section-15.6.3

## Follow-up: guidance that invited retries (17 October)

The correction above still told the reader, for any 5xx, to *repeat the same generate
command with --retry-uncertain after a short pause*. On 17 October an unattended loop
followed that text through 502, 499 and 600-second timeouts. That guidance is replaced:

- 5xx, 408, 429, 499 and timeouts now say **billing unknown**, show the attempt count for
  the part across runs and the possible spend, and recommend stopping and waiting before
  one deliberate, manual try. 499 is classified as CANCELLED and stays uncertain.
- An engine spend guard refuses further paid requests past 2 uncertain attempts per part
  or 4 per episode in 24 h, with a logged `--allow-spend-over-limit "reason"` override.
- Each paid request is logged with an attempt ID in `artifacts/audio/attempts.jsonl`.
- New jobs use a 360 s client timeout instead of the 600 s policy described above; the
  600 s receipts in this record remain accurate history.

See the [studio README](README.md#uncertain-spend-guard-and-plain-errors).
