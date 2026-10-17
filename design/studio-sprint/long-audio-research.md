# Long Audio Synthesis vs Gemini TTS for field_notes_audio (desk research, 2026-10-17)

No API calls made; docs only. [UNVERIFIED] marks gaps.

## 1. Does Long Audio Synthesis (synthesizeLongAudio) support Gemini-TTS / Charon?
- Not documented. The how-to page (https://docs.cloud.google.com/text-to-speech/docs/create-audio-text-long-audio-synthesis) names no voice family; all examples use a Standard voice (en-US-Standard-A). It is labelled Pre-GA. Output: LINEAR16 .wav to a GCS URI. Input up to ~1 MB. Locations in samples: "global" (REST) and "us-central1" (Python); no region list given.
- Release notes: launched 16 Mar 2023 (texts >5 KB); 24 Oct 2023 added SSML and Studio voice support. No release note adds Gemini-TTS or Chirp 3 HD to it (https://docs.cloud.google.com/text-to-speech/docs/release-notes).
- Gemini-TTS page (https://docs.cloud.google.com/text-to-speech/docs/gemini-tts) documents only unary and streaming; no long-audio/batch mode. The voices overview does not list Gemini in its voice-type table.
- Conclusion: no evidence Gemini voices (incl. Charon) work with synthesizeLongAudio. [UNVERIFIED: only a real call would settle it; I could not run one.] Treat as unsupported.
- Note: Chirp 3: HD does have a "Charon" voice (en-US-Chirp3-HD-Charon), and the Chirp 3 HD GA note (2 Apr 2025) says "real-time streaming and batch processing"; whether that means synthesizeLongAudio is [UNVERIFIED]. It is a different model from Gemini Charon, so the sound will differ.

## 2. Batch/async for Gemini TTS
- Gemini API Batch API (https://ai.google.dev/gemini-api/docs/batch-api): 50% of interactive price; 24 h target, expires after 48 h; inline <20 MB, JSONL file <=2 GB; results kept 6 weeks; cancel by name; states PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED/EXPIRED; batchStats gives failedRequestCount. The page does not mention TTS models explicitly.
- Pricing page (https://ai.google.dev/gemini-api/docs/pricing) lists batch rates for TTS models, so batch for TTS is priced and implied supported:
  - 2.5 Flash Preview TTS: std $0.50 in / $10 out per 1M tok; batch $0.25 / $5.00
  - 2.5 Pro Preview TTS: std $1 / $20; batch $0.50 / $10
  - 3.1 Flash TTS Preview: std $1 / $20; batch $0.50 / $10
  - Audio = 25 tokens per second.
- This is the Gemini Developer API (API key), not Vertex/Cloud TTS. Our pipeline uses our own Cloud project with a global endpoint; moving to batch means the Gemini API surface or Vertex batch prediction. [UNVERIFIED: Vertex AI batch prediction support for TTS models; did not find a doc.] 24 h latency suits a nightly job, not interactive.
- Cloud TTS Gemini limits: 4,000 bytes text + 4,000 prompt (8,000 combined), output truncated at ~655 s; quotas 150 QPM (2.5 flash), 125 QPM (2.5 pro); 3.1 flash dynamic. Vertex: 8,000 bytes contents. Output on Vertex is raw 24 kHz 16-bit PCM, no WAV header.

## 3. Billing semantics
- No Google doc I found states that failed/cancelled TTS requests are or are not billed (Cloud TTS quotas page and pricing page silent; Batch API page silent apart from failedRequestCount). [UNVERIFIED for sync and async.] General principle for token billing: tokens are charged on usage returned; a 502/499/timeout with no response likely yields no usage record, but a server that generated audio before the client gave up could still bill. Cannot be proven from docs. Settle via Cloud Billing export / the console usage report for the 17 Oct window, or Google support.
- Long Audio operation model (documented): POST returns operation name with done:false; GET operation to poll; list operations per project; failure -> read error from operation, fix, resubmit. Quota 100 requests/min for create and for query. No documented idempotency key or request ID. Idempotency would be ours: deterministic output_gcs_uri per chunk/hash, skip if object exists.
- Gemini Batch API: job name, status polling, cancel, per-request failure stats; keys per request in JSONL allow our own dedupe.

## 4. Options compared (cost per minute of output, 25 tok/s = 1500 audio tok/min)
| Option | Output quality / style | Approx cost per output minute | Code change |
|---|---|---|---|
| A. Current: Gemini 2.5 Flash TTS sync | Charon, prompt-based tone/pace, tags | $0.015 out + small text input (~$0.0004 for ~900 chars) ~ $0.0155 | none |
| A'. 2.5 Pro TTS sync | same, higher quality | ~$0.031 | model id |
| B. Gemini Batch API, Flash | same model/voice/prompting | ~$0.0078 (half) | new batch submit + poll + result parse; PCM to WAV/MP3 as today; hours of latency |
| C. Long Audio, Chirp 3 HD Charon (if supported) | no free-form style prompt; pace via speaking_rate; SSML supported (Oct 2025); LINEAR16 wav only | $30/1M chars; ~900-1000 chars/min -> ~$0.027-0.03 (my char estimate, 150 wpm) | drop chunking (1 MB input), synthesizeLongAudio + operation poll, GCS output, transcode; different voice timbre |
| D. Long Audio, Studio/Neural2 | no Gemini prompting | Studio ~$160/1M chars per memory, not verified on page [UNVERIFIED] | as C |

Price for Cloud TTS Gemini matches the AI Studio rates per the pricing page (2.5 Flash $0.50/$10). Long Audio's own rate: not found [UNVERIFIED]. Chirp 3 HD $30/1M chars from Cloud pricing page snippet.

## 5. Recommendation
- Do not migrate to Long Audio Synthesis: no documented Gemini support, it would change the voice and drop prompting, and it costs about 2x per minute (Chirp 3 HD) versus Flash.
- Stay sync and harden now: spend guard, per-chunk deterministic cache key in GCS (idempotent skip), bounded retries with backoff and jitter, shorter client timeout (a 600 s timeout on a <=8 KB chunk is a hang, not work), keep chunks small enough to stay under ~655 s truncation, record request IDs and attempt counts so billing can be reconciled against the console.
- Optional hybrid later: put non-urgent bulk renders on Gemini Batch API (half price, resumable by job name) after a one-chunk pilot confirms TTS works in batch and confirms the billing treatment of failed items. Pilot cost is cents.
- First action to resolve the open question: pull today's usage from Cloud Billing (SKU/usage report for our project, Text-to-Speech/Vertex) and compare with the count of successful chunks.

## Sources
- https://docs.cloud.google.com/text-to-speech/docs/create-audio-text-long-audio-synthesis
- https://docs.cloud.google.com/text-to-speech/docs/gemini-tts
- https://docs.cloud.google.com/text-to-speech/docs/release-notes
- https://docs.cloud.google.com/text-to-speech/quotas
- https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types
- https://cloud.google.com/text-to-speech/pricing (page body not retrievable; figures via search snippets)
- https://ai.google.dev/gemini-api/docs/batch-api
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/speech-generation
