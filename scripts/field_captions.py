"""Caption a finished MP3 through Google Speech-to-Text V2, without resynthesis."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html import escape
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib import error, parse, request

from field_audio import access_token, digest, http_diagnostic, write_json


class CloudError(RuntimeError):
    def __init__(self, diagnostic):
        self.diagnostic = diagnostic
        self.code = diagnostic["http_status"]
        detail = diagnostic.get("provider_message") or diagnostic.get("provider_status", "")
        super().__init__(f"Google HTTP {self.code}: {detail}")


def add_arguments(commands):
    sub = commands.add_parser("captions", help="Transcribe an existing MP3 into SRT, VTT and a listening review")
    sub.add_argument("audio", help="Episode ID or MP3 path; episode IDs find the latest saved recording")
    sub.add_argument("--project")
    sub.add_argument("--bucket", help="Private working bucket; otherwise use saved settings or create one")
    sub.add_argument("--location", choices=("us", "eu", "global"))
    sub.add_argument("--model", choices=("chirp_3", "long"))
    sub.add_argument("--language", choices=("en-US", "en-GB", "fi-FI"))
    import argparse
    sub.add_argument("--diarize", action=argparse.BooleanOptionalAction, default=None,
                     help="Detect speakers automatically for English two-voice episodes; IDs are not identities")
    sub.add_argument("--auth", choices=("gcloud", "adc"))
    sub.add_argument("--script", type=Path, help="Optional input script; defaults to the neighboring transcript.txt")
    sub.add_argument("--dry-run", action="store_true", help="Inspect locally; no authentication, upload or paid job")
    sub.add_argument("--wait", type=int, default=900, help="Wait up to this many seconds (0–3600); default 15 minutes")
    sub.add_argument("--no-open", action="store_true", help="Do not open the completed listening page")
    sub.add_argument("--retry-uncertain", action="store_true", help="Allow a new submission after a lost acknowledgement")
    sub.add_argument("--restart-failed", action="store_true", help="Start a new job after repairing a confirmed failed job")


def cloud_json(url, project, auth, data=None, media=False):
    token = access_token(auth)
    req = request.Request(url, method="POST" if data is not None else "GET", data=
                          data if media else json.dumps(data).encode() if data is not None else None,
                          headers={"Authorization": "Bearer " + token, "x-goog-user-project": project,
                                   "Content-Type": "audio/mpeg" if media else "application/json"})
    try:
        with request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except error.HTTPError as exc:
        try:
            diagnostic = http_diagnostic(exc, token)
        except (OSError, ValueError, TypeError):
            diagnostic = {"http_status": exc.code}
        raise CloudError(diagnostic) from None


def poll_operation(url, project, auth):
    """Retry only reads: polling cannot create another billable transcription job."""
    for attempt in range(4):
        try:
            return cloud_json(url, project, auth)
        except (CloudError, error.URLError, TimeoutError) as exc:
            retryable = not isinstance(exc, CloudError) or exc.code in {408, 429} or 500 <= exc.code <= 599
            if not retryable or attempt == 3:
                raise
            print(f"Polling interrupted; retrying in {2 ** attempt} seconds. Saved job will be reused.", flush=True)
            time.sleep(2 ** attempt)


def probe_audio(path):
    if not shutil.which("ffprobe"):
        raise ValueError("Captioning requires ffprobe, included with FFmpeg")
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                             "-of", "json", str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError("The input could not be read as audio")
    info = json.loads(result.stdout)
    duration = float(info["format"]["duration"])
    if not math.isfinite(duration) or not 0 < duration <= 1200:
        raise ValueError("This caption pilot accepts recordings up to 20 minutes")
    if not any(s.get("codec_type") == "audio" for s in info.get("streams", [])):
        raise ValueError("The input has no audio stream")
    return duration


def recognition_request(uri, model, language, diarize):
    features = {"enableWordTimeOffsets": True, "enableAutomaticPunctuation": True}
    if diarize:
        features["diarizationConfig"] = {}
    return {"files": [{"uri": uri}], "config": {"autoDecodingConfig": {}, "model": model,
             "languageCodes": [language], "features": features}, "recognitionOutputConfig": {
             "inlineResponseConfig": {}, "outputFormatConfig": {"native": {}, "srt": {}, "vtt": {}}}}


def ensure_upload(content, bucket, object_name, project, auth):
    """Reuse matching content; a create-only precondition prevents overwriting objects."""
    bucket_info = cloud_json(f"https://storage.googleapis.com/storage/v1/b/{bucket}?fields=iamConfiguration", project, auth)
    if bucket_info.get("iamConfiguration", {}).get("publicAccessPrevention") != "enforced":
        raise ValueError("Use a working bucket with public access prevention enforced; see the caption setup guide")
    object_url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{parse.quote(object_name, safe='')}"
    expected_md5 = base64.b64encode(hashlib.md5(content).digest()).decode()
    try:
        metadata = cloud_json(object_url, project, auth)
    except CloudError as exc:
        if exc.code != 404:
            raise
        query = parse.urlencode({"uploadType": "media", "name": object_name, "ifGenerationMatch": "0"})
        try:
            metadata = cloud_json(f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o?{query}",
                                  project, auth, content, media=True)
        except CloudError as upload_error:
            if upload_error.code != 412:
                raise
            metadata = cloud_json(object_url, project, auth)
    if str(metadata.get("size")) != str(len(content)) or metadata.get("md5Hash") != expected_md5:
        raise ValueError("The existing Cloud Storage object does not match this recording; nothing was overwritten")
    return metadata.get("generation")


def operation_url(name, location, project):
    found = re.fullmatch(r"projects/([a-zA-Z0-9-]+)/locations/(us|eu|global)/operations/([a-zA-Z0-9_-]+)", name or "")
    if not found or found[2] != location or (found[1] != project and not found[1].isdigit()):
        raise ValueError("Google returned an unexpected operation name")
    host = "speech.googleapis.com" if location == "global" else f"{location}-speech.googleapis.com"
    return f"https://{host}/v2/{name}"


def seconds(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d{1,9})?s", value):
        raise ValueError("Invalid word offset from Google")
    return float(value[:-1])


def caption_time(value):
    found = re.fullmatch(r"(?:(\d{2,}):)?(\d{2}):(\d{2})[.,](\d{3})", value)
    if not found or int(found[2]) >= 60 or int(found[3]) >= 60:
        raise ValueError("Invalid caption timestamp")
    return int(found[1] or 0) * 3600 + int(found[2]) * 60 + int(found[3]) + int(found[4]) / 1000


def parse_captions(text, duration, vtt=False):
    normalized = text.lstrip("\ufeff").replace("\r\n", "\n").strip()
    if vtt:
        if not re.match(r"^WEBVTT(?:\s|$)", normalized):
            raise ValueError("Missing WebVTT header")
        normalized = normalized.split("\n", 1)[1].strip() if "\n" in normalized else ""
    cues = []
    for block in re.split(r"\n\s*\n", normalized):
        lines = block.splitlines()
        if vtt and lines and lines[0].startswith(("NOTE", "STYLE", "REGION")):
            continue
        timing = next((i for i, line in enumerate(lines) if " --> " in line), None)
        if timing is None:
            raise ValueError("A caption block has no timing")
        match = re.fullmatch(r"(\S+) --> (\S+)(?:\s+.*)?", lines[timing])
        if not match:
            raise ValueError("Invalid caption timing line")
        start, end = caption_time(match[1]), caption_time(match[2])
        content = "\n".join(lines[timing + 1:]).strip()
        if not content or not 0 <= start < end <= duration + .5:
            raise ValueError("Empty caption or timing outside the finished recording")
        if cues and start < cues[-1]["end"] - .001:
            raise ValueError("Caption cues overlap or are out of order")
        cues.append({"start": start, "end": end, "text": content})
    if not cues:
        raise ValueError("Google returned no caption cues")
    return cues


def extract_recognition(operation, uri, duration):
    if not operation.get("done") or operation.get("error"):
        raise ValueError("The transcription operation has not completed successfully")
    file_result = operation.get("response", {}).get("results", {}).get(uri)
    if not isinstance(file_result, dict):
        raise ValueError("The transcription response does not contain the submitted audio URI")
    if file_result.get("error", {}).get("code", 0):
        raise ValueError(f"Google failed this file: {file_result['error'].get('message', 'unknown error')}")
    inline = file_result.get("inlineResult", {})
    words, passages = [], []
    for result in inline.get("transcript", {}).get("results", []):
        alternatives = result.get("alternatives", [])
        if not alternatives:
            continue
        top = alternatives[0]
        if top.get("transcript"):
            passages.append(top["transcript"].strip())
        for word in top.get("words", []):
            start = seconds(word.get("startOffset", "0s"))
            end = seconds(word.get("endOffset", "0s"))
            text = word.get("word", "")
            if not isinstance(text, str) or not text.strip() or not 0 <= start <= end <= duration + .5:
                raise ValueError("Invalid recognized word or timing")
            if words and start < words[-1]["start"]:
                raise ValueError("Word timings are out of order")
            speaker = word.get("speakerLabel")
            words.append({"text": text, "start": start, "end": end,
                          "speaker": str(speaker) if speaker is not None else None})
    if not passages or not words:
        raise ValueError("Google returned no transcript or word offsets; the saved response can be inspected offline")
    srt, vtt = inline.get("srtCaptions", ""), inline.get("vttCaptions", "")
    srt_cues = parse_captions(srt, duration)
    cues = parse_captions(vtt, duration, vtt=True)
    if len(srt_cues) != len(cues) or any(abs(a["start"] - b["start"]) > .01 or
                                      abs(a["end"] - b["end"]) > .01 for a, b in zip(srt_cues, cues)):
        raise ValueError("SRT and WebVTT timings differ")
    for cue in cues:
        cue["speakers"] = sorted({w["speaker"] for w in words if w["speaker"] is not None
                                  and w["end"] > cue["start"] and w["start"] < cue["end"]})
    return {"transcript": "\n\n".join(passages), "words": words, "cues": cues, "srt": srt, "vtt": vtt}


def compare_script(script, transcript, aliases):
    if aliases:
        script = re.sub(r"(?m)^(?:" + "|".join(re.escape(a) for a in aliases) + r"):\s*", "", script)
    def tokens(text):
        return re.findall(r"\w+(?:['’]\w+)*", text.replace("&", " and ").replace("’", "'").casefold())
    expected, heard = tokens(script), tokens(transcript)
    matcher = SequenceMatcher(None, expected, heard, autojunk=False)
    differences = [{"kind": tag, "script": " ".join(expected[a:b]), "recognized": " ".join(heard[c:d]),
                    "script_token_range": [a, b], "recognized_token_range": [c, d]}
                   for tag, a, b, c, d in matcher.get_opcodes() if tag != "equal"]
    return {"review_status": "pending", "token_similarity": round(matcher.ratio(), 4),
            "differences": differences, "note": "Recognition differences need listening review; similarity is not proof of speech fidelity."}


def listening_preview(title, cues, language="en-US"):
    data = json.dumps(cues, ensure_ascii=False).replace("<", "\\u003c")
    return f'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} — Listening review</title>
<style>body{{margin:0;background:#17191b;color:#e8e2d5;font:17px/1.6 system-ui,sans-serif}}
main{{max-width:820px;margin:auto;padding:32px 20px}}h1{{font:clamp(28px,6vw,46px)/1.15 Georgia,serif}}
a{{color:#dfc28a}}audio{{width:100%;margin:16px 0}}.label{{font-size:12px;letter-spacing:.14em}}
.muted{{color:#c0bbaf}}#transcript{{max-height:58vh;overflow:auto;border-top:1px solid #555}}
.cue{{display:block;width:100%;padding:14px 12px;text-align:left;border:0;border-bottom:1px solid #444;
background:transparent;color:inherit;font:inherit;cursor:pointer}}.cue[aria-current=true]{{background:#33312c;border-left:3px solid #dfc28a}}
.cue:focus-visible{{outline:2px solid #dfc28a;outline-offset:-3px}}.stamp{{display:block;font-size:12px;color:#c0bbaf}}
label{{display:inline-block;padding:10px 0;margin-right:16px}}select{{font:inherit;background:#33312c;color:inherit;padding:4px;border:1px solid #c0bbaf}}nav{{display:flex;gap:18px;flex-wrap:wrap}}</style>
<main><p class="label">MOTH &amp; GRAVEL / FIELD NOTES</p><h1>{escape(title)}</h1>
<p class="muted">Listening review. Machine-generated captions; transcription and speaker detection need checking.</p>
<audio id="player" aria-label="Episode audio" controls preload="none" src="audio.mp3"></audio>
<nav aria-label="Downloads"><a href="captions.srt" download>SRT</a><a href="captions.vtt" download>WebVTT</a>
<a href="transcript.txt" download>Transcript</a></nav>
<label><input id="follow" type="checkbox" checked> Follow playback</label>
<label for="speed">Playback speed <select id="speed"><option value="1">1×</option><option value="1.15">1.15×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option></select></label>
<p id="status" role="status">Select a caption to listen from that point.</p>
<div id="transcript" role="region" aria-label="Timed transcript" lang="{escape(language)}"></div>
<noscript><p>Open the <a href="transcript.txt">readable transcript</a> and use the audio controls above.</p></noscript></main>
<script type="application/json" id="cue-data">{data}</script>
<script>
const cues=JSON.parse(document.getElementById('cue-data').textContent);
const player=document.getElementById('player'),list=document.getElementById('transcript');
const follow=document.getElementById('follow'),status=document.getElementById('status');
document.getElementById('speed').addEventListener('change',event=>{{player.playbackRate=Number(event.target.value);}});
const clock=s=>Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0');
const buttons=cues.map(cue=>{{
  const button=document.createElement('button');button.type='button';button.className='cue';
  const stamp=document.createElement('span');stamp.className='stamp';
  stamp.textContent=clock(cue.start)+(cue.speakers.length?' · Speaker '+cue.speakers.join(', '):'');
  button.append(stamp,document.createTextNode(cue.text));
  button.addEventListener('click',()=>{{player.currentTime=cue.start;player.play().catch(()=>{{status.textContent='Press play to continue.';}});}});
  list.append(button);return button;
}});
let active=-1;
player.addEventListener('timeupdate',()=>{{
  const index=cues.findIndex(c=>player.currentTime>=c.start&&player.currentTime<c.end);
  if(index===active)return;
  if(active>=0)buttons[active].removeAttribute('aria-current');active=index;
  if(index>=0){{buttons[index].setAttribute('aria-current','true');if(follow.checked)buttons[index].scrollIntoView({{block:'nearest'}});}}
}});
</script></html>'''


def export_result(directory, operation, plan, script, aliases):
    recognized = extract_recognition(operation, plan["audio_uri"], plan["duration_seconds"])
    (directory / "captions.srt").write_text(recognized["srt"], encoding="utf-8")
    (directory / "captions.vtt").write_text(recognized["vtt"], encoding="utf-8")
    (directory / "transcript.txt").write_text(recognized["transcript"] + "\n", encoding="utf-8")
    write_json(directory / "words.json", {"audio_sha256": plan["audio_sha256"], "words": recognized["words"]})
    write_json(directory / "cues.json", {"audio_sha256": plan["audio_sha256"], "cues": recognized["cues"]})
    comparison = compare_script(script, recognized["transcript"], aliases) if script else {
        "review_status": "pending", "differences": [], "note": "No input script was supplied for comparison."}
    write_json(directory / "comparison.json", comparison)
    write_json(directory / "captions.json", {"version": 1, "audio_sha256": plan["audio_sha256"],
               "script_sha256": digest(script.strip().encode()) if script else None,
               "operation": operation["name"], "model": plan["model"], "location": plan["location"],
               "language": plan.get("language", "en-US"),
               "generated_at": datetime.now(timezone.utc).isoformat(), "review_status": "pending",
               "detected_speaker_ids": sorted({w["speaker"] for w in recognized["words"] if w["speaker"] is not None}),
               "files": {p: digest((directory / p).read_bytes()) for p in
                         ("captions.srt", "captions.vtt", "transcript.txt", "words.json", "cues.json")}})
    (directory / "listen.html").write_text(listening_preview(plan["title"], recognized["cues"],
                                                           plan.get("language", "en-US")), encoding="utf-8")
    print(f"Captions ready: {directory}/captions.srt")
    print(f"Listen with the timed transcript: {directory}/listen.html")
    print(f"Script comparison: {len(comparison['differences'])} differences to review; no text was automatically corrected.")


@contextmanager
def run_lock(directory, label="caption"):
    import fcntl  # Cloud Shell and WSL; OS releases the lock even after interruption.
    with (directory / ".lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(f"Another {label} command is using this recording; wait for it to finish") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def run(args):
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", args.project):
        raise ValueError("Provide the Google Cloud project ID")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,61}[a-z0-9]", args.bucket):
        raise ValueError("Provide a bucket name without gs://, paths or dots")
    if args.model == "chirp_3" and args.location == "global":
        raise ValueError("Chirp 3 transcription uses --location us or eu; this is independent of the TTS endpoint")
    if args.diarize and (args.model != "chirp_3" or args.language == "fi-FI"):
        raise ValueError("This pilot supports diarization with Chirp 3 English recordings")
    if not 0 <= args.wait <= 3600:
        raise ValueError("--wait must be between 0 and 3600 seconds")
    path = args.audio.resolve(strict=True)
    if path.suffix.lower() != ".mp3" or not path.is_file() or not 0 < path.stat().st_size <= 100_000_000:
        raise ValueError("Provide a finished MP3 no larger than 100 MB")
    content = path.read_bytes()
    audio_hash = digest(content)
    metadata_path = path.with_name("episode.json")
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    if metadata.get("audio_sha256") and metadata["audio_sha256"] != audio_hash:
        raise ValueError("This MP3 differs from its episode metadata; identify the correct recording first")
    script_path = args.script or path.with_name("transcript.txt")
    script = script_path.read_text(encoding="utf-8") if script_path.exists() else ""
    if args.script and not script:
        raise ValueError("The supplied script is missing or empty")
    if script and not args.script and metadata.get("script_sha256") and metadata["script_sha256"] != digest(script.strip().encode()):
        raise ValueError("The neighboring input script differs from the script recorded in episode metadata")
    object_name = f"field-notes-input/{audio_hash}.mp3"
    uri = f"gs://{args.bucket}/{object_name}"
    payload = recognition_request(uri, args.model, args.language, args.diarize)
    fingerprint = digest(json.dumps({"request": payload, "project": args.project, "location": args.location},
                                   sort_keys=True).encode())
    directory = path.parent / "captions" / fingerprint[:16]
    duration = probe_audio(path)
    plan = {"audio_sha256": audio_hash, "audio_uri": uri, "duration_seconds": duration,
            "title": metadata.get("title", path.stem), "model": args.model, "location": args.location,
            "language": args.language,
            "request": payload, "fingerprint": fingerprint}
    print(f"Caption existing recording: {duration / 60:.2f} minutes; {args.model}; location {args.location}")
    print("No speech synthesis. Transcription and private Cloud Storage have separate charges.")
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        print("Dry run only; nothing uploaded or submitted.")
        return
    if not shutil.which("gcloud"):
        raise ValueError("Captioning requires an authenticated gcloud session")
    directory.mkdir(parents=True, exist_ok=True)
    with run_lock(directory):
        state_path = directory / "state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        write_json(directory / "plan.json", plan)
        if state.get("status") in {"requesting", "uncertain"} and not args.retry_uncertain:
            raise ValueError("A previous transcription submission has no saved acknowledgement. --retry-uncertain may create another billable job.")
        if args.restart_failed and state.get("status") not in {"running", "complete"}:
            if state.get("status") != "failed":
                raise ValueError("--restart-failed applies only to a saved, confirmed failed job")
            (directory / "failed-operation.json").write_bytes((directory / "operation.json").read_bytes())
            state = {}
        if state.get("status") == "failed":
            raise ValueError("The saved transcription job failed. Repair the reported cause, then use --restart-failed for a new billable job.")
        if state.get("status") == "complete":
            operation = json.loads((directory / "operation.json").read_text())
        else:
            if not state.get("operation"):
                print(f"Upload or reuse private input: {uri}", flush=True)
                generation = ensure_upload(content, args.bucket, object_name, args.project, args.auth)
                (directory / "audio.mp3").write_bytes(content)
                write_json(state_path, {"status": "requesting", "audio_sha256": audio_hash,
                                       "storage_generation": generation})
                host = "speech.googleapis.com" if args.location == "global" else f"{args.location}-speech.googleapis.com"
                url = f"https://{host}/v2/projects/{args.project}/locations/{args.location}/recognizers/_:batchRecognize"
                try:
                    operation = cloud_json(url, args.project, args.auth, payload)
                    operation_url(operation.get("name"), args.location, args.project)
                except CloudError as exc:
                    write_json(state_path, {"status": "rejected" if 400 <= exc.code < 500 and exc.code not in {408, 429}
                                           else "uncertain", "audio_sha256": audio_hash, **exc.diagnostic})
                    raise
                except Exception:
                    write_json(state_path, {"status": "uncertain", "audio_sha256": audio_hash})
                    raise RuntimeError("No valid transcription operation ID was saved. Inspect state.json before an uncertain retry.") from None
                state = {"status": "running", "operation": operation["name"], "audio_sha256": audio_hash,
                         "storage_generation": generation}
                write_json(state_path, state)
            else:
                operation = poll_operation(operation_url(state["operation"], args.location, args.project), args.project, args.auth)
            deadline = time.monotonic() + args.wait
            progress_at = time.monotonic() + 30
            while not operation.get("done"):
                write_json(directory / "operation.json", operation)
                if time.monotonic() >= deadline:
                    print(f"Transcription is running: {state['operation']}")
                    print("Repeat the same command to resume polling; no new job will be submitted.")
                    return
                time.sleep(min(3, max(0, deadline - time.monotonic())))
                operation = poll_operation(operation_url(state["operation"], args.location, args.project), args.project, args.auth)
                if time.monotonic() >= progress_at and not operation.get("done"):
                    print("Transcription is still running; waiting automatically. Ctrl-C saves your place.", flush=True)
                    progress_at = time.monotonic() + 30
            write_json(directory / "operation.json", operation)
            file_error = operation.get("response", {}).get("results", {}).get(uri, {}).get("error", {})
            if operation.get("error") or file_error.get("code", 0):
                write_json(state_path, {**state, "status": "failed", "provider_error": operation.get("error") or file_error})
                raise ValueError("The transcription job failed; inspect operation.json and check Speech-to-Text and bucket permissions")
            write_json(state_path, {**state, "status": "complete"})
        if not (directory / "audio.mp3").exists():
            (directory / "audio.mp3").write_bytes(content)
        aliases = [s["alias"] for s in metadata.get("speakers", [])]
        export_result(directory, operation, plan, script, aliases)
        print(f"Private input is retained at {uri}; keep it until review is complete, then remove it if no longer needed.")
        return directory
