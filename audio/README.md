# Field Notes audio

For local intro/outro music, baked pacing and animated YouTube editions, see
[automated production](production/README.md). `python3 -m field_notes_audio produce note-001`
finishes existing narration without an editor or new Cloud jobs.

`python3 -m field_notes_audio release all` also prepares clearly named YouTube
upload folders, including titles, descriptions and tags. See the
[ongoing release workflow](production/PUBLISHING.md) for new notes, listening
review and promotion of finished audio to the website/feed.

## Generate the collection and add it to the website

With the project already saved from the successful listening run:

```bash
git pull --ff-only
python3 -m field_notes_audio make-all --publish
```

This covers every published Field Note and every configured episode, including
new notes added to the archive, the two-voice conversation and the brisk comparison. It reuses completed recordings
and transcription jobs, generates and subtitles the rest, then commits and pushes
only the prepared listening files to the current PR branch. It does not push to
`main`. Merge the completed publication PR when ready to put the audio online.
Google generation/transcription runs in your authenticated WSL or Cloud Shell
session. The website hosts the small first collection through GitHub Pages;
there is no additional public Cloud bucket to configure.

Each note gets **“Listen to this note · N min”** below its introduction, with the
actual recording duration, an **AI-narrated** badge, native audio controls and an
expandable timed transcript. Playback defaults to **1.15×**, with a speed control
and optional transcript following. The archive gets **“Listen through the
archive”**, a queue, Previous/Next and a switch for continuing to the next note.
Without JavaScript, audio, transcripts and episode links remain available.

The archive's listening edition opens on request so the writing remains easy to
browse. Choose an episode, read its corresponding note, or open its timed
transcript. Closing the player pauses playback. Metadata loads when the player
opens; the archive transcript loads when requested and retains a readable
download if its timed version cannot load. Downloads are grouped beside the
article player. See the [audio design sprint](../design/field-notes-audio-sprint.md)
for the critique, before/after captures and validation.

**“Subscribe to the podcast”** links to a distinct feed at
`https://mothandgravel.com/notes/podcast.xml`. The written-notes feed stays at
`/notes/feed.xml`. The podcast uses stable episode GUIDs, content-addressed MP3
URLs, real byte lengths and duration, square studio artwork and transcript links.
The feed and players advertise only completed assets. No dummy episode URLs or
estimated listen labels are added while the collection is empty.

`make-all` without `--publish` prepares the collection locally for review.
`publish` pushes a completed preparation later. Existing unrelated Git changes
are excluded: save or commit them before using `--publish`. Partial Cloud failures
preserve progress and prevent a partial collection from being pushed. Saved work
is reused on the next run. If any issue says **billing unknown**, stop and wait
before running it again; an uncertain paid submission still requires an explicit
`--retry-uncertain`, and the [spend guard](#uncertain-spend-guard) applies.

As new notes enter the published catalog, `make-all` prepares their complete prose
scripts automatically. `sync` performs that step offline. Existing source changes
still require script review; their fingerprints are never silently refreshed.
Design studies with several prose blocks include the intervening study sections.
The source prose itself stays intact when players are built.

After merging and waiting for GitHub Pages deployment, validate the actual host:

```bash
python3 -m field_notes_audio verify-live
```

This checks the deployed feed against the prepared collection, each MP3's HEAD,
byte length, media type and byte-range response, plus transcript/artwork links.
Podcast app registration is separate from supplying a usable RSS subscription.

## Make or subtitle one episode

In your existing checkout, update the branch with `git pull --ff-only`. Then:

```bash
python3 -m field_notes_audio setup --project "$FIELD_AUDIO_PROJECT"
python3 -m field_notes_audio make workbench-001
```

`setup` remembers your project, verifies authentication and checks billing when
readable. It enables the four Google APIs and creates or verifies a private
working bucket in that project. It makes no speech requests. The defaults are
**global TTS** (the endpoint that worked in the first listening run) and **US
Chirp 3 transcription**. These are separate processing locations.

`make` generates or reuses the audio, uploads that recording to the private
bucket, creates subtitles and a synchronized transcript, and waits automatically
for up to 15 minutes. Two-voice English recordings request speaker detection
automatically. On a desktop or WSL it attempts to open the listening page. The
page defaults to 1.15× and also offers 1×, 1.25× and 1.5× playback, clickable captions and downloads.

The portable result has a stable path:

```text
artifacts/audio/workbench-001/episode.zip
```

Unzip it and open `listen.html`; keep the neighboring files together. In Cloud
Shell, use **More → Download** for this ZIP. It contains the MP3, SRT, WebVTT,
recognized transcript, original input script, timings and review metadata.

To subtitle the narration you have already generated, without making new audio:

```bash
python3 -m field_notes_audio captions note-001
```

Episode IDs find the latest completed recording. You no longer need to find its
hashed output directory, repeat the project/bucket flags, add a diarization flag,
or rerun a command every 45 seconds. An explicit MP3 path still works if you
want to choose an older recording. When `make` or `captions` has no prepared
settings, it performs setup automatically, using the project from your flags,
environment, saved settings or current `gcloud` configuration.

If interrupted or still running after the wait limit, repeat the same command.
Completed speech chunks and MP3s are reused; saved transcription operations are
polled, rather than submitted again. Transient polling errors retry safely.
An uncertain **paid submission** still requires `--retry-uncertain`, since another
submission can incur another charge. Never run it in a loop or from a script.
Confirmed failed transcription jobs require `--restart-failed` after repairing the
cause.

## Episodes and listening review

| Episode | Format | Sources | Voices |
| --- | --- | --- | --- |
| `note-001` | *Curiosity with calluses*, original narration | 001 | Charon |
| `note-001-brisk` | Same narration, compact pauses and 170 wpm delivery request | 001 | Charon |
| `note-002`–`note-011` | Narrated editions of the remaining published notes | 002–011 | Charon |
| `workbench-001` | *What does the interface let you believe?*, conversation | 005, 006, 007 | Explore: Kore; Question: Charon |

The first user-run narration succeeded globally after repeated EU HTTP 502s.
It sounded too slow. Try faster playback in the listening page, or generate the
brisk comparison with `python3 -m field_notes_audio make note-001-brisk`.
Delivery pace is a request, not an enforced timing constraint. New runs print
actual duration and average script words per minute, including pauses.

The conversation is an editorial adaptation with an AI-format disclosure in its
opening. It is not a conversation with project authors and adds no claims of
measured usability, reliability or live robot observations.

Listen for complete sentences, names, numbers, negations, qualifications, natural
pauses and the final ending. Detected speakers remain **Speaker 1 / Speaker 2**;
they are not automatically identified as Explore / Question. Pronunciation and
speaker identities need listening review.

The source recording's `transcript.txt` is the **input script**. The caption
folder's `transcript.txt` is **recognized speech**. The comparison highlights
substantive differences without silently rewriting the captions. Case,
punctuation and `&`/`and` are normalized for comparison. Similarity is not proof
that the audio said the right words; review stays pending even for a match.

Chirp can return trailing caption cues entirely after the measured recording
ends. If SRT and WebVTT timings agree and the cues form an ordered suffix, those
cues are excluded from playback and retained with their original text and times
in `cues.json` (`timing_omissions`) and `captions.json`
(`caption_timing_omissions`). The listening page and terminal report the omission.
The original `operation.json` and recognized transcript text remain unchanged for
review. Cues that straddle the recording's end, reversed or unordered starts, and
responses without any usable in-recording cues still block export. Resuming a
saved completed job performs this recovery locally, without another Cloud call.

Individual `make` and `captions` commands do not publish. `make-all` prepares
completed site assets; `--publish` or `publish` explicitly pushes them to a PR.
Original recordings, job state and Cloud settings stay in ignored `artifacts/`.

## Script and transcript checks (AI judge)

Two checks run without any setup, from simple rules:

- **Script check**, before paid narration (`plan`, `make`, Studio's
  **Make episode** summary and `make-episode`). Code fences, curly braces, JSON
  keys, `def`/`import` lines and markup block paid narration until you fix the
  script or accept it explicitly: `make ID --accept-script "reason"`,
  `make-episode ID --confirm DIGEST --accept-script "reason"`, or the reason field
  in Studio. URLs, a missing or doubled intro/outro, and passages that differ from
  the article beyond the script rules (sidebars omitted, `×` → by, `px` → pixels,
  `ms` → milliseconds) are shown but do not block.
- **Transcript check**, before approval (`review` and Studio's Review stage). If
  the script's last words are not at the end of the recognized transcript, or a
  long passage near the end is not heard, approval is blocked until you give a
  reason: `review ID --approve --reviewer NAME --override-judge "reason"`, or the
  reason field in Studio. The reason is saved in `review.json`.

With a Claude API key, a model also classifies each script/transcript difference
as harmless, mis-hearing, missing content or extra content, and reviews the script
for text that should not be read aloud. To enable it:

1. In the [Claude Console](https://platform.claude.com/), create an API key for
   this project and set a **monthly spend limit** on its workspace.
2. Install the SDK once: `uv sync --group judge` (or `python3 -m pip install "anthropic>=1.15,<2"`).
3. Export the key in the shell that runs the pipeline or Studio. Do not put it in
   a file in this checkout:

   ```bash
   export FIELD_AUDIO_ANTHROPIC_API_KEY=...
   ```

Without the key (or the SDK) the checks say **AI check skipped (no key)** and the
rule checks still run; nothing fails. The default model is `claude-haiku-5-5`
(`FIELD_AUDIO_JUDGE_MODEL` changes it); `--judge deep` uses `claude-sonnet-5-5`
and `--judge off` skips the model. Each call is capped at 4,000 output tokens with
one retry, and is logged with its tokens, estimated cost and latency in
`artifacts/audio/judge-calls.jsonl`. Results are cached by content in
`artifacts/audio/judge/`, so looking again costs nothing. A Haiku check costs
well under a cent per episode. Script and transcript text is passed to the model
as untrusted data, never as instructions. The judge is not a paid speech step, so
the spend guard does not apply to it.

`plan` is still a dry run for Google: it sends no Google requests, but when the
key is set it may run the Anthropic script check (cached, so a repeat costs
nothing). Use `plan ID --judge off` to send nothing at all. Override and accept
reasons must be 8–300 characters on one line.

## Requirements and saved settings

Python 3.10+, Google Cloud CLI, FFmpeg and ffprobe are required. No Python packages,
API keys or service-account key files are needed. If FFmpeg is missing on WSL or
Cloud Shell, install it with `sudo apt-get update && sudo apt-get install -y ffmpeg`.
Locally, sign into the intended account with `gcloud auth login`; in Cloud Shell,
authorize the session in Google's interface. Setup does not choose a new account,
attach a billing account or grant broad IAM roles.

A Workspace subscription does not supply Cloud API billing or permissions.
Billing must already be linked to the chosen project. An unreadable billing
status is reported but does not imply billing is disabled. If billing is explicitly
disabled, setup links to that project's Billing page and stops.

Settings are saved at `artifacts/audio/settings.json`, without credentials.
Project precedence: `--project`, `FIELD_AUDIO_PROJECT`, `GOOGLE_CLOUD_PROJECT`,
saved project, current `gcloud` project. Bucket precedence: `--bucket`,
`FIELD_AUDIO_BUCKET`, saved bucket in the same project, generated bucket name.
Changing project does not borrow the previous project's saved bucket.

To save different defaults:

```bash
python3 -m field_notes_audio setup --project "$FIELD_AUDIO_PROJECT" --endpoint eu --location eu
```

EU setup chooses a separate `-eu` bucket and requires European storage. An
existing bucket is reused only if it belongs to the selected project and has
public access prevention enforced. Setup does not change an existing bucket's
policy or remove its data; choose a new `--bucket` name if necessary.

The caller needs API-enablement permission for setup, permission to use the
project's services, `aiplatform.endpoints.predict` for Gemini TTS, Cloud Speech
Client permissions for transcription and operation reads, and bucket/object
read and object-create permissions. Vertex AI User and Service Usage Consumer
are typical least-privilege roles for generation. A project administrator can
grant missing permissions. Do not grant Owner just to run this pilot.

The Speech service agent must also be able to read the input MP3. Its managed
Speech service-agent role includes storage access; using a bucket in the same
project simplifies the setup. If a completed job reports input access denied,
check that service agent's permissions before starting a replacement job.

## Advanced commands and limits

```bash
python3 -m field_notes_audio check
python3 -m field_notes_audio plan workbench-001
python3 -m field_notes_audio generate workbench-001
python3 -m field_notes_audio captions note-001 --dry-run
```

`check` and `plan` are offline: no authentication, uploads or paid requests.
`generate` makes audio only, using your saved defaults. `captions --dry-run`
inspects a recording locally without Cloud setup, authentication or mutations;
project settings must already be saved or provided in the environment/flags.

Flags override defaults for that invocation: `--model` and `--endpoint` for
synthesis; `--model`, `--location`, `--language` and `--diarize`/`--no-diarize`
for captions. `--auth adc` uses an existing Application Default Credentials
login. `--no-open` prevents launching the listening page. `--wait 0` submits or
checks once and returns; other wait limits accept 0–3600 seconds.

The caption default is Chirp 3, with word offsets and native Google SRT/WebVTT
outputs. One caption job takes up to 20 minutes, so a longer recording is split
locally at a pause into parts of at most 19 minutes (or at 19:00 with a 5-second
overlap). Each part is its own paid job with its own spend-guard attempt, and the parts
are joined into one set of captions. The MP3 must stay within 100 MB. `--model long
--location global --no-diarize` is an optional caption alternative. Transcription
and private storage have separate charges from synthesis.

Speech plans estimate output at the script's target pace, 25 audio tokens per
second and Google's listed Gemini 2.5 rates: $20/million audio tokens for Pro,
$10/million for Flash. Text input, retries, taxes and storage are additional.
Estimates and budget alerts are not spending caps.

Requests preserve words and dialogue speaker labels, keeping text below 3,000
UTF-8 bytes and prompt plus text below 4,000. Completed chunks have request and
audio hashes. Changes to voice, script, model, prompt, endpoint or source article
create separate runs. Source edits block stale-script generation until reviewed.
Concurrent generation or caption commands cannot submit the same run twice.

FFmpeg joins WAV chunks with a 200 ms section pause, applies mono podcast
loudness processing targeting -19 LUFS / -1.5 dBTP and encodes a 96 kbps MP3.
Processing logs, provenance and measured duration remain beside the recording.
Repeating a completed run verifies and reuses its MP3 without reencoding it.

## Troubleshooting and recovery

| Result | Next step |
| --- | --- |
| Authentication / 401 | Authorize Cloud Shell or run `gcloud auth login` locally. |
| 403 | Inspect the saved diagnostic; check selected project, API and IAM permissions. |
| 400 | Inspect `plan EPISODE --json` and model/language/voice support. |
| TTS 5xx, 408, 429, 499 or a timeout | **Billing unknown.** Stop; do not repeat the command in a loop. Wait at least 30 minutes, check the Google Cloud status page and billing report, then try that part once by hand with `--retry-uncertain` if you accept another possible charge. For 429 check quota first. 499 is CANCELLED; Google advises never retrying it automatically. |
| Interrupted paid submission | Inspect saved state and the attempt count in the message, then decide whether one `--retry-uncertain` run is appropriate. |
| Spend guard refused | The part or episode reached its uncertain-attempt limit. Wait for the 24 h window, or run one command with `--allow-spend-over-limit "reason" --spend-token TOKEN` from the refusal. |
| Transcription still running | Repeat the same command; the existing operation resumes. Increase `--wait` if desired. |
| Confirmed failed transcription | Repair the cause, then repeat with `--restart-failed`; a new job is billable. |
| Source note changed | Review/revise the script before updating its article fingerprint. |
| Working bucket unavailable | Run `setup` again with a new dedicated `--bucket`. |

Provider diagnostics are bounded and stripped of credentials. Server errors do
not establish a billing or IAM problem. Automatic retries apply only to operation
reads, never uncertain speech synthesis or transcription submissions.

### Uncertain-spend guard

Every paid narration request and caption submission gets an attempt ID. Before
the request is sent, a line with the time, episode, part and attempt ID is
appended to `artifacts/audio/attempts.jsonl` and flushed to disk; its outcome and
any provider request ID follow afterwards. The log belongs to the checkout, also
when you caption an MP3 kept elsewhere. It is never rewritten, so it can be
reconciled against the Cloud billing report. Failure messages show the attempt ID.

An attempt is **uncertain** when it may have been billed but no result was saved:
5xx, 408, 429, 499/CANCELLED, client timeouts, lost connections and crashes. This
is deliberately conservative. A request that failed offline before reaching Google,
or a response that arrived but could not be decoded or saved, is also counted and
labelled *billing unknown*, because the client cannot tell. Older receipts are
imported once from the cache. Times come from this computer's clock; imported
receipts are dated by their file modification time, which a copy or restore can
change.

By default `generate`, `make`, `make-all`, `captions` and Studio refuse another
paid request once a part has **2** uncertain attempts, or an episode has **4**, in
a rolling **24 h**. Checking the limit and logging the start are one locked step,
so parallel runs cannot both pass it. Every paid command prints the limits in
force. The refusal gives the counts, the possible spend (an upper-bound
speech-output estimate; caption submissions have no local estimate) and a spend
token.

To spend anyway, run **one** command by hand with
`--allow-spend-over-limit "reason" --spend-token TOKEN`, using the token from the
refusal. Any newer uncertain attempt changes the token, so repeating the command
is refused, and a part can be overridden at most once per window. Within one
run, the same token covers each remaining blocked part of that episode once, as
long as no new uncertain attempt changes it; the first uncertain result stops the
run. `make-all` never accepts an override. Studio asks for the same override and reason and binds
it to the attempts it showed. Each override is logged with its reason and token.

`artifacts/audio/spend-guard.json`
(`{"part_limit": 2, "episode_limit": 4, "window_hours": 24}`) and
`FIELD_AUDIO_UNCERTAIN_PART_LIMIT`, `FIELD_AUDIO_UNCERTAIN_EPISODE_LIMIT` and
`FIELD_AUDIO_UNCERTAIN_WINDOW_HOURS` can only make the guard stricter: fewer
attempts, or a window of 24 h or longer. Looser values are refused. When the file
and an environment variable both set a value, the stricter one applies (the lower
count, the longer window). Stricter
limits are logged. The narration client timeout is 360 s per chunk; change it
with `--tts-timeout-seconds` or `FIELD_AUDIO_TTS_TIMEOUT_SECONDS`.

**Repairing the log.** A crash during a write can leave an unfinished last line.
The next write starts a new line, and the damaged line counts as one uncertain
attempt, at its recorded time when readable and otherwise now, so the guard
errs towards stopping. To repair it, copy `attempts.jsonl` aside for the record,
check the billing report, then correct or delete only that line. A refusal names
any damaged lines it counted. Never delete `attempts.lock`: it is the lock that
keeps parallel runs from passing the limit together, and it holds no data.

An attempt that fails locally after its start was logged but before the request
was made (for example, the receipt could not be written) is settled as
`failed` with *not sent: local error before request*, so it does not count.

Completed captions are re-exported locally from the saved Google response.
Repeating replaces generated caption files; keep editorial corrections in a
separate copy. `operation.json` and `state.json` retain resumable provider state.
Raw recognition output stays available when caption validation fails.

If Google returns invalid word offsets, the exporter retains those entries in
`words.json` and uses the validated caption cues for playback. Transcript text
is preserved; speaker labels are omitted when word timing is incomplete. If an
otherwise ordered caption has a reversed, out-of-range or overlapping end, its
end is bounded by the next recorded caption start. Adjustments appear in
`cues.json`, `captions.json` and the listening review; the original
`operation.json` is unchanged. Invalid starts, disagreement between SRT/WebVTT
timing, or a bad final end without a following caption still block export.
After pulling a parser fix, repeat the command to re-export the saved completed
response locally; do not restart transcription for a local export failure.

The private content-addressed input is retained until you choose to remove the
exact URI printed by the script. No bucket or unrelated objects are deleted.
Keep input while its job runs and through listening review.

Offline tests use documented Google response shapes and synthetic audio. They
cover source preservation, timings, privacy, saved settings, caching and recovery.
The first collection has been generated and transcribed in the authenticated user
session: 13 real episodes, including all 11 Field Notes. Listening review remains
pending; Cloud success is not a claim of word-for-word narration accuracy.

## Publication files and validation

Public files live under `docs/assets/audio/`: MP3, SRT, VTT, recognized transcript,
cue timings and a manifest containing fingerprints and measured duration. Private
Cloud input URIs, operation IDs, saved settings and credentials are not copied.
Caption text remains machine-generated and review stays pending; publication does
not manufacture a claim that a human verified every word or speaker identity.

`build_notes.py` also builds the article controls, archive queue and separate
podcast feed. Its `--check` verifies media hashes, actual audio duration, subtitle
consistency, current source fingerprints and square podcast artwork. The existing
article RSS is unchanged. New audio versions get new asset URLs, while an episode's
podcast GUID and publication date remain stable.

The duration comparison allows at most 100 milliseconds for MP3 delay/padding
differences between FFmpeg releases. The first real collection reports 50–66 ms
differences with identical file hashes and lengths. Larger duration differences
still fail, and byte lengths and SHA-256 hashes must match exactly. Saved public
durations, recording bytes and caption timestamps are not rewritten for this
compatibility allowance.

Offline Python tests cover generation, caching, all-note publication, new-note
scripts, completeness, provenance, corruption, RSS metadata and interrupted jobs.
The browser audit builds an ignored fixture using synthetic clips; it checks
native playback, default speed, cue seeking, queue advancement, stopping, keyboard
use, both appearances, narrow layouts and no-JavaScript access. CI never calls
Google or generates paid speech.

Live audio must be generated in the authenticated local/Cloud Shell session. If
publication is interrupted after the local commit, repeat `publish` to retry the
push without regenerating speech. If the push reports diverging branch history,
resolve that Git divergence before retrying; completed media remains saved.

## Sources checked for this setup

- [Gemini TTS: APIs, permissions, EU endpoint, models and byte limits](https://docs.cloud.google.com/text-to-speech/docs/gemini-tts)
- [Authenticate to Cloud Text-to-Speech](https://docs.cloud.google.com/text-to-speech/docs/authentication)
- [Google model API guidance for transient server errors and retries](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/retry-strategy)
- [Authorize Cloud Shell](https://docs.cloud.google.com/shell/docs/auth)
- [Speech pricing](https://cloud.google.com/text-to-speech/pricing)
- [Budget alerts do not cap spending](https://docs.cloud.google.com/billing/docs/how-to/budgets)
- [Podcast RSS requirements](https://podcasters.apple.com/support/823-podcast-requirements)
- [Google SRT and WebVTT caption outputs](https://docs.cloud.google.com/speech-to-text/docs/caption-support)
- [BatchRecognize REST request and inline output](https://docs.cloud.google.com/speech-to-text/docs/reference/rest/v2/projects.locations.recognizers/batchRecognize)
- [Chirp 3 regions, word offsets and diarization](https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3)
- [Speech permissions and service-agent Cloud Storage access](https://docs.cloud.google.com/iam/docs/roles-permissions/speech)
- [Create a private working bucket](https://docs.cloud.google.com/sdk/gcloud/reference/storage/buckets/create)
- [Cloud Storage bucket resource and privacy settings](https://docs.cloud.google.com/storage/docs/json_api/v1/buckets)
- [Create a bucket through the JSON API](https://docs.cloud.google.com/storage/docs/json_api/v1/buckets/insert)


## Processing speed and measurement

`make-all` uses three local workers by default. `--jobs 1` reduces local concurrency;
`--jobs 4` increases it (maximum 8). Each episode's chunks stay ordered and its
recording lock remains exclusive. Caption jobs are submitted with no blocking
wait while subsequent recordings are synthesized. The collection then resumes
the saved jobs and exports their results; this phase never calls synthesis.
Publication still requires every configured episode to complete.

Google access tokens are reused only in memory, separately for gcloud and ADC,
with a five-minute refresh interval and invalidation after an authentication
rejection. A rejected paid submission is not automatically resent. Read-only
operation polling can refresh authentication and retry safely. Interrupting a
batch cancels queued work; active requests finish and save their outcomes.

After each completed processing pass (including an incomplete collection),
`artifacts/audio/processing-times.json` records wall time and elapsed stages for
authentication, synthesis requests, Cloud reads/writes, encoding and captions.
Stages are nested: do not add stage totals as if they were separate wall time.
The file contains no tokens, request text or Cloud URIs. Network failures retain
their exception class and elapsed attempt time in the existing chunk state.

The current default model remains unchanged to preserve cached recordings.
Google describes `gemini-2.5-flash-tts` as optimized for lower latency, whereas Pro
targets control over structured audio. Switching `--model` creates different
recording fingerprints and can generate new billable audio; compare a short
sample before switching an archive. Streaming is a separate option for earlier
playback, not a guarantee that the entire collection and subtitles finish sooner.
The current transcription requests use normal processing, not discounted
dynamic batching (which can wait up to 24 hours).

Sources: [Gemini-TTS models and streaming](https://docs.cloud.google.com/text-to-speech/docs/gemini-tts),
[TTS quotas](https://docs.cloud.google.com/text-to-speech/quotas), and
[transcription processing strategies](https://docs.cloud.google.com/speech-to-text/docs/reference/rest/v2/projects.locations.recognizers/batchRecognize).

## Python development and layout

The runtime uses Python 3.10+ and the standard library. From the repository root,
run `python3 -m field_notes_audio`; the existing
`python3 scripts/field_audio.py` launcher remains compatible and needs no package
installation. Saved settings, recordings, fingerprints and operation journals
stay under `artifacts/audio/`; scripts and source hashes under `audio/` keep their
identity when implementation files move.

| Location | Responsibility |
| --- | --- |
| `field_notes_audio/` | Importable synthesis, captions, workflow, release and site modules |
| `field_notes_audio/cli.py` | Argument parsing and command dispatch |
| `field_notes_audio/storage.py` / `locks.py` | Atomic state, streaming hashes and process ownership |
| `tests/audio/` | Offline unit, recovery and publication checks |
| `tools/check_audio.py` | Contributor quality gate |
| `scripts/field_audio.py` / `build_audio.py` | Compatibility launchers for existing commands and editorial builds |
| `audio/` | Reviewed narration scripts, catalog and workflow documentation |

```bash
uv sync --locked --dev
uv run python tools/check_audio.py
```

The gate checks Ruff formatting and idioms, offline tests, request bounds and
generated audio site slots. The pinned development tool is optional for running
the audio CLI. Hosted CI also checks the browser interface with synthetic media.
State reads reject duplicate fields and nonobject JSON; failed state replacement
keeps the previous outcome. Media hashing and PCM assembly use bounded buffers.
Broad request catches remain only where an interrupted acknowledgement must
preserve an uncertain outcome; they do not authorize a paid retry.
