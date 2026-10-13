# Field Notes audio pilot

Two listening experiments, using the published website as their source:

| Episode | Format | Sources | Initial voices |
| --- | --- | --- | --- |
| `note-001` | Narrated edition of *Curiosity with calluses* | 001 | Charon |
| `workbench-001` | *What does the interface let you believe?* | 005, 006, 007 | Explore: Kore; Question: Charon |

The scripts are ready for a first listening experiment. Audio has **not** been
generated or auditioned yet. The dialogue is an editorial adaptation, not a
conversation with project authors. Its opening discloses the AI format. Neither
pilot adds claims of measured usability, reliability or live robot observations.

## First run in Google Cloud Shell

Google Workspace is your account environment. Speech generation additionally
requires a Google Cloud project with billing enabled, the relevant APIs enabled,
and permissions for the account making the calls. A Workspace subscription alone
does not provide these Cloud API permissions or speech credits.

1. Open [Google Cloud Console](https://console.cloud.google.com/), select the
   intended existing project, and open **Activate Cloud Shell** (`>_`). Use the
   intended Workspace account. When Google asks to authorize Cloud Shell, approve
   that session within Google's own interface.
2. Run the following, replacing `YOUR_PROJECT_ID` with the project ID, not the
   display name or numeric project number:

   ```bash
   export FIELD_AUDIO_PROJECT='YOUR_PROJECT_ID'
   gcloud config set project "$FIELD_AUDIO_PROJECT"
   gcloud auth list --filter=status:ACTIVE --format='value(account)'
   gcloud billing projects describe "$FIELD_AUDIO_PROJECT" --format='value(billingEnabled)'
   ```

   Confirm that the account/project are correct and that billing reports `True`.
   A billing permission error is not proof that billing is disabled: check the
   selected project's Billing page or ask its billing administrator.
3. Enable the APIs in that project:

   ```bash
   gcloud services enable texttospeech.googleapis.com aiplatform.googleapis.com --project="$FIELD_AUDIO_PROJECT"
   ```

   Google documents `aiplatform.endpoints.predict` as required for Gemini TTS,
   including calls through Cloud Text-to-Speech. If it is missing, a project
   administrator can grant **Vertex AI User** (`roles/aiplatform.user`) to the
   account you confirmed above. The caller also needs permission to use the
   project's enabled services (`serviceusage.services.use`), typically supplied
   by **Service Usage Consumer**. Enabling APIs requires an administrator with
   `serviceusage.services.enable`. Do not grant Owner just to generate audio.
4. Open this branch in a separate checkout:

   ```bash
   git clone --branch studio/field-notes-audio --single-branch https://github.com/mothandgravel/.github.git mothandgravel-audio
   cd mothandgravel-audio
   python3 scripts/field_audio.py check
   python3 scripts/field_audio.py plan note-001
   ```

   The checks and plan are offline. They require no credentials and make no paid
   requests. If the directory already exists, use that checkout rather than
   cloning over it. After this PR is merged, clone `main` instead.
5. Generation requires FFmpeg. If `command -v ffmpeg` finds nothing, install it:

   ```bash
   sudo apt-get update
   sudo apt-get install -y ffmpeg
   ```

6. Generate the short narration first:

   ```bash
   python3 scripts/field_audio.py generate note-001 --project "$FIELD_AUDIO_PROJECT"
   ```

   The runner defaults to **Gemini 2.5 Pro TTS**, English and the **EU** speech
   endpoint. It prints the MP3 path when complete. In Cloud Shell Editor, locate
   that file under `artifacts/audio/note-001/` and download it to listen locally.
   Download the neighboring `transcript.txt` and `episode.json` as well. The full
   path is also accepted by Cloud Shell's **More → Download** file action.
7. Try the conversation once the narration works:

   ```bash
   python3 scripts/field_audio.py plan workbench-001
   python3 scripts/field_audio.py generate workbench-001 --project "$FIELD_AUDIO_PROJECT"
   ```

No API keys or service-account key files are needed for this first run. The runner
gets a short-lived token from `gcloud`, keeps it in memory, and sends it only to
the selected Google API. Do not paste tokens or credential files into chat or Git.

## What to listen for

- Does the narrator sound like the studio's writing: calm, curious and precise?
- Are the pauses natural, including transitions between generated chunks?
- Do names such as Geaidnu, Ajo, Paja and Kitronik need pronunciation directions?
- Are numbers, negations and qualifications spoken completely and correctly?
- Does the two-voice conversation hold attention without sounding theatrical?
- Does the final sentence finish? An MP3 file existing does not establish script
  fidelity, pronunciation quality or completeness of the generated speech.

The neighboring transcript is the **input script**, not a speech-to-text verified
transcript. `episode.json` records listening review as pending. Keep the scripts'
spoken uncertainty and source limitations when making editorial revisions.

## Cost, request limits and interrupted runs

`plan` estimates speech output at 140 words per minute, 25 audio tokens per second
and Google's listed Gemini 2.5 rates: $20/million audio tokens for Pro or
$10/million for Flash. Text input, retries, taxes and future hosting are additional.
It is an estimate, not a cap; actual speech duration and charges can differ.

Requests keep each text chunk below 3,000 UTF-8 bytes and prompt plus text below
4,000. They therefore fit both individual field limits and the stricter prose
description in Google's dialogue documentation. Small chunks also avoid the
approximately 655-second output ceiling. No words or dialogue speaker identities
are intentionally dropped to satisfy a limit.

Each completed chunk has a fingerprint and audio hash. Re-run the **same command**
to reuse those chunks. Changing a voice, script, model, delivery prompt, endpoint
or source article creates a separate run. Network errors or interruptions that
leave the outcome uncertain stop the run instead of automatically repeating a
paid request. After inspecting the saved run, `--retry-uncertain` explicitly
allows repeating that chunk and may incur an additional charge.

WAV chunks are joined with a 200 ms section pause. FFmpeg applies mono podcast
loudness processing targeting -19 LUFS / -1.5 dBTP and encodes a 96 kbps MP3.
The processing log is retained. These settings do not replace listening review.

For a cheaper model comparison, use `--model gemini-2.5-flash-tts` with both `plan`
and `generate`. To compare voices, edit `audio/episodes.json`, run `check`, then
generate again. Generation is manual; ordinary CI never calls Google or bills
the project. Newer Gemini 3.8 TTS preview models use a different API and are not
accepted by this Cloud Text-to-Speech pilot runner.

## Local WSL alternative

Install the [Google Cloud CLI](https://docs.cloud.google.com/sdk/docs/install),
FFmpeg and Python 3.10 or later. Run `gcloud auth login` with your intended Google
account, then use the same project/API/check/generation steps above. If you prefer
Application Default Credentials, run `gcloud auth application-default login`,
set its quota project, and pass `--auth adc`. The REST runner does not require a
Python Google SDK or an OpenAI account/key.

## Troubleshooting the first request

| Result | Check |
| --- | --- |
| Authentication failed / 401 | Authorize the Cloud Shell session; locally sign into the intended account. |
| 403 | Correct project, linked billing, enabled APIs, permission to use project services, and `aiplatform.endpoints.predict`. Organization policies may require an administrator. |
| 400 | Inspect the credential-free requests with `plan EPISODE --json`; verify model, language, voices and EU endpoint availability against current Google docs. |
| 429 | Inspect quota in Google Cloud. Avoid rapidly repeating a paid run; saved completed chunks are reusable. |
| 500 / 502 / 503 / 504 | The service or an upstream gateway failed. After a short pause, repeat the same command with `--retry-uncertain`. This response alone does not establish a billing/IAM issue. Provider status/message is saved in the chunk JSON without credentials. |
| Interrupted request | Inspect the chunk state. An explicit uncertain retry may produce another billable generation. |
| Note changed | Re-read the updated article and revise the audio script. Refresh its article hash only after review; do not suppress the stale-source check. |

For example, retry a failed first narration on the same EU endpoint:

```bash
python3 scripts/field_audio.py generate note-001 --project "$FIELD_AUDIO_PROJECT" --retry-uncertain
```

If the EU endpoint repeatedly returns a gateway/server failure, one diagnostic
alternative is `--endpoint global`. It uses a different processing location and
a separate output/cache directory; it does not silently replace EU processing.
Use that option only when global processing is appropriate for the sources.
Both an uncertain retry and a different-endpoint attempt can incur another charge.

Set a small billing alert in the selected project if useful. Google Cloud budget
alerts notify; they **do not** cap spending.

## Publication after the listening pilot

The first two MP3s stay in ignored `artifacts/`; nothing changes the live site.
Choose the format, voices and any pronunciation fixes after listening. The next
site change can then add real audio rather than empty controls:

- A native per-note player with `preload="none"`, duration, AI narration disclosure
  and the reviewed transcript.
- An archive listening queue and a separate `notes/podcast.xml` containing only
  reviewed, complete episodes. Keep the article RSS feed available.
- Stable episode GUIDs, MP3 enclosure URLs/byte lengths/media types and square
  podcast artwork. Verify HEAD and byte-range requests on the actual media host.
- Record script, source and audio fingerprints in episode metadata; flag revised
  source articles for editorial review before regenerating.

For this tiny pilot, local generation plus manual publishing is sufficient. Cloud
Storage and a GitHub Actions identity can follow once the listening experience is
chosen. Use Workload Identity Federation for CI instead of a long-lived JSON key.
Do not put Google authentication or generation calls in visitor-facing code.

## Sources checked for this setup

- [Gemini TTS: APIs, permissions, EU endpoint, models and byte limits](https://docs.cloud.google.com/text-to-speech/docs/gemini-tts)
- [Authenticate to Cloud Text-to-Speech](https://docs.cloud.google.com/text-to-speech/docs/authentication)
- [Google model API guidance for transient server errors and retries](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/retry-strategy)
- [Authorize Cloud Shell](https://docs.cloud.google.com/shell/docs/auth)
- [Speech pricing](https://cloud.google.com/text-to-speech/pricing)
- [Budget alerts do not cap spending](https://docs.cloud.google.com/billing/docs/how-to/budgets)
- [Podcast RSS requirements](https://podcasters.apple.com/support/823-podcast-requirements)
