"""Caption a finished MP3 through Google Speech-to-Text V2, without resynthesis."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html import escape
from pathlib import Path
from urllib import error, parse, request

from field_notes_audio import spend_guard
from field_notes_audio.audio import access_token, digest, http_diagnostic, write_json
from field_notes_audio.auth import invalidate_token
from field_notes_audio.diagnostics import http_meaning, http_uncertain, stop_and_wait
from field_notes_audio.locks import run_lock
from field_notes_audio.progress import raise_if_stopped, report, timed
from field_notes_audio.storage import digest_file, read_object


class CloudError(RuntimeError):
    def __init__(self, diagnostic, message: str | None = None):
        self.diagnostic = diagnostic
        self.code = diagnostic["http_status"]
        detail = diagnostic.get("provider_message") or diagnostic.get("provider_status", "")
        super().__init__(message or f"Google HTTP {self.code}: {detail}")


def add_arguments(commands: argparse._SubParsersAction) -> None:
    sub = commands.add_parser(
        "captions", help="Transcribe an existing MP3 into SRT, VTT and a listening review"
    )
    sub.add_argument(
        "audio", help="Episode ID or MP3 path; episode IDs find the latest saved recording"
    )
    sub.add_argument("--project")
    sub.add_argument(
        "--bucket", help="Private working bucket; otherwise use saved settings or create one"
    )
    sub.add_argument("--location", choices=("us", "eu", "global"))
    sub.add_argument("--model", choices=("chirp_3", "long"))
    sub.add_argument("--language", choices=("en-US", "en-GB", "fi-FI"))
    import argparse

    sub.add_argument(
        "--diarize",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Detect speakers automatically for English two-voice episodes; IDs are not identities",
    )
    sub.add_argument("--auth", choices=("gcloud", "adc"))
    sub.add_argument(
        "--script",
        type=Path,
        help="Optional input script; defaults to the neighboring transcript.txt",
    )
    sub.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect locally; no authentication, upload or paid job",
    )
    sub.add_argument(
        "--wait",
        type=int,
        default=900,
        help="Wait up to this many seconds (0–3600); default 15 minutes",
    )
    sub.add_argument(
        "--no-open", action="store_true", help="Do not open the completed listening page"
    )
    sub.add_argument(
        "--retry-uncertain",
        action="store_true",
        help="Allow a new submission after a lost acknowledgement",
    )
    sub.add_argument(
        "--restart-failed",
        action="store_true",
        help="Start a new job after repairing a confirmed failed job",
    )
    spend_guard.add_override_argument(sub)


def cloud_json(
    url: str, project: str, auth: str, data: bytes | dict | None = None, media: bool = False
) -> dict:
    token = access_token(auth)
    req = request.Request(
        url,
        method="POST" if data is not None else "GET",
        data=data if media else json.dumps(data).encode() if data is not None else None,
        headers={
            "Authorization": "Bearer " + token,
            "x-goog-user-project": project,
            "Content-Type": "audio/mpeg" if media else "application/json",
        },
    )
    try:
        stage = (
            "stt_submit"
            if ":batchRecognize" in url
            else "cloud_read"
            if data is None
            else "cloud_write"
        )
        with timed(stage), request.urlopen(req, timeout=60) as response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise ValueError("Google returned a JSON response that is not an object")
        return result
    except error.HTTPError as exc:
        if exc.code == 401:
            invalidate_token(token)
        try:
            diagnostic = http_diagnostic(exc, token)
        except (OSError, ValueError, TypeError):
            diagnostic = {"http_status": exc.code}
        raise CloudError(diagnostic) from None


def poll_operation(url: str, project: str, auth: str) -> dict:
    """Retry only reads: polling cannot create another billable transcription job."""
    for attempt in range(4):
        try:
            return cloud_json(url, project, auth)
        except (CloudError, error.URLError, TimeoutError) as exc:  # noqa: PERF203 - retry only independent reads
            retryable = (
                not isinstance(exc, CloudError)
                or exc.code in {401, 408, 429}
                or 500 <= exc.code <= 599
            )
            if not retryable or attempt == 3:
                raise
            report(
                f"Polling interrupted; retrying in {2**attempt} seconds. Saved job will be reused.",
                flush=True,
            )
            time.sleep(2**attempt)


def probe_audio(path: Path) -> float:
    if not shutil.which("ffprobe"):
        raise ValueError("Captioning requires ffprobe, included with FFmpeg")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise ValueError("The input could not be read as audio")
    info = json.loads(result.stdout)
    duration = float(info["format"]["duration"])
    if not math.isfinite(duration) or not 0 < duration <= 1200:
        raise ValueError("This caption pilot accepts recordings up to 20 minutes")
    if not any(s.get("codec_type") == "audio" for s in info.get("streams", [])):
        raise ValueError("The input has no audio stream")
    return duration


def recognition_request(uri: str, model: str, language: str, diarize: bool) -> dict:
    features = {"enableWordTimeOffsets": True, "enableAutomaticPunctuation": True}
    if diarize:
        features["diarizationConfig"] = {}
    return {
        "files": [{"uri": uri}],
        "config": {
            "autoDecodingConfig": {},
            "model": model,
            "languageCodes": [language],
            "features": features,
        },
        "recognitionOutputConfig": {
            "inlineResponseConfig": {},
            "outputFormatConfig": {"native": {}, "srt": {}, "vtt": {}},
        },
    }


def ensure_upload(
    content: bytes, bucket: str, object_name: str, project: str, auth: str
) -> str | None:
    """Reuse matching content; a create-only precondition prevents overwriting objects."""
    bucket_info = cloud_json(
        f"https://storage.googleapis.com/storage/v1/b/{bucket}?fields=iamConfiguration",
        project,
        auth,
    )
    if bucket_info.get("iamConfiguration", {}).get("publicAccessPrevention") != "enforced":
        raise ValueError(
            "Use a working bucket with public access prevention enforced; see the caption setup guide"
        )
    object_url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{parse.quote(object_name, safe='')}"
    expected_md5 = base64.b64encode(hashlib.md5(content).digest()).decode()
    try:
        metadata = cloud_json(object_url, project, auth)
    except CloudError as exc:
        if exc.code != 404:
            raise
        query = parse.urlencode(
            {"uploadType": "media", "name": object_name, "ifGenerationMatch": "0"}
        )
        try:
            metadata = cloud_json(
                f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o?{query}",
                project,
                auth,
                content,
                media=True,
            )
        except CloudError as upload_error:
            if upload_error.code != 412:
                raise
            metadata = cloud_json(object_url, project, auth)
    if str(metadata.get("size")) != str(len(content)) or metadata.get("md5Hash") != expected_md5:
        raise ValueError(
            "The existing Cloud Storage object does not match this recording; nothing was overwritten"
        )
    return metadata.get("generation")


def operation_url(name: str, location: str, project: str) -> str:
    found = re.fullmatch(
        r"projects/([a-zA-Z0-9-]+)/locations/(us|eu|global)/operations/([a-zA-Z0-9_-]+)", name or ""
    )
    if not found or found[2] != location or (found[1] != project and not found[1].isdigit()):
        raise ValueError("Google returned an unexpected operation name")
    host = "speech.googleapis.com" if location == "global" else f"{location}-speech.googleapis.com"
    return f"https://{host}/v2/{name}"


def seconds(value: object) -> float:
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d{1,9})?s", value):
        raise ValueError("Invalid word offset from Google")
    return float(value[:-1])


def caption_time(value: str) -> float:
    found = re.fullmatch(r"(?:(\d{2,}):)?(\d{2}):(\d{2})[.,](\d{3})", value)
    if not found or int(found[2]) >= 60 or int(found[3]) >= 60:
        raise ValueError("Invalid caption timestamp")
    return int(found[1] or 0) * 3600 + int(found[2]) * 60 + int(found[3]) + int(found[4]) / 1000


def parse_captions(
    text: str, duration: float, vtt: bool = False, recover_timing: bool = False
) -> list[dict]:
    """Keep numeric timing faults for extract_recognition's bounded recovery."""
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
        content = "\n".join(lines[timing + 1 :]).strip()
        if not content or start < 0:
            raise ValueError("Empty caption or timing outside the finished recording")
        if not recover_timing and not 0 <= start < end <= duration + 0.5:
            raise ValueError("Empty caption or timing outside the finished recording")
        if cues:
            if start <= cues[-1]["start"]:
                raise ValueError("Caption cues are out of order or have duplicate starts")
            if not recover_timing and start < cues[-1]["end"] - 0.001:
                raise ValueError("Caption cues overlap or are out of order")
        cues.append({"start": start, "end": end, "text": content})
    if not cues:
        raise ValueError("Google returned no caption cues")
    return cues


def render_captions(cues: list[dict], vtt: bool = False) -> str:
    def timestamp(value):
        milliseconds = round(value * 1000)
        seconds, fraction = divmod(milliseconds, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}{'.' if vtt else ','}{fraction:03d}"

    blocks = [
        f"{index}\n{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{cue['text']}"
        for index, cue in enumerate(cues, 1)
    ]
    return ("WEBVTT\n\n" if vtt else "") + "\n\n".join(blocks) + "\n"


def extract_recognition(operation: dict, uri: str, duration: float) -> dict:
    if not operation.get("done") or operation.get("error"):
        raise ValueError("The transcription operation has not completed successfully")
    file_result = operation.get("response", {}).get("results", {}).get(uri)
    if not isinstance(file_result, dict):
        raise ValueError("The transcription response does not contain the submitted audio URI")
    if file_result.get("error", {}).get("code", 0):
        raise ValueError(
            f"Google failed this file: {file_result['error'].get('message', 'unknown error')}"
        )
    inline = file_result.get("inlineResult", {})
    words, passages, timing_issues = [], [], []
    for result_index, result in enumerate(inline.get("transcript", {}).get("results", [])):
        alternatives = result.get("alternatives", [])
        if not alternatives:
            continue
        top = alternatives[0]
        if top.get("transcript"):
            passages.append(top["transcript"].strip())
        for word_index, word in enumerate(top.get("words", [])):
            try:
                start = seconds(word.get("startOffset", "0s"))
                end = seconds(word.get("endOffset", "0s"))
                text = word.get("word", "")
                if (
                    not isinstance(text, str)
                    or not text.strip()
                    or not 0 <= start <= end <= duration + 0.5
                ):
                    raise ValueError("Invalid recognized word or timing")
                if words and start < words[-1]["start"]:
                    raise ValueError("Word timings are out of order")
            except ValueError as exc:
                # Chirp can return corrupt word offsets alongside valid caption cues.
                # Preserve its evidence; never guess replacement word timestamps.
                timing_issues.append(
                    {
                        "result_index": result_index,
                        "word_index": word_index,
                        "reason": str(exc),
                        "word": word,
                    }
                )
                continue
            speaker = word.get("speakerLabel")
            words.append(
                {
                    "text": text,
                    "start": start,
                    "end": end,
                    "speaker": str(speaker) if speaker is not None else None,
                }
            )
    if not passages:
        raise ValueError(
            "Google returned no transcript; the saved response can be inspected offline"
        )
    srt, vtt = inline.get("srtCaptions", ""), inline.get("vttCaptions", "")
    srt_cues = parse_captions(srt, duration, recover_timing=True)
    cues = parse_captions(vtt, duration, vtt=True, recover_timing=True)
    if len(srt_cues) != len(cues) or any(
        abs(a["start"] - b["start"]) > 0.01 or abs(a["end"] - b["end"]) > 0.01
        for a, b in zip(srt_cues, cues, strict=False)
    ):
        raise ValueError("SRT and WebVTT timings differ")
    # A trailing recognition artifact cannot be played after the measured EOF.
    # Do not move it into the recording or remove its text from the transcript.
    # Validate ordering and cross-format agreement before excluding this suffix.
    caption_omissions = []
    while cues and cues[-1]["start"] >= duration + 0.5 and cues[-1]["end"] > cues[-1]["start"]:
        cue = cues.pop()
        srt_cues.pop()
        caption_omissions.append(
            {
                "cue_index": len(cues),
                **cue,
                "reason": "caption starts after the finished recording",
            }
        )
    if not cues:
        raise ValueError("No caption cues occur within the finished recording")
    caption_omissions.reverse()
    caption_adjustments = []
    for index, cue in enumerate(cues):
        following = cues[index + 1] if index + 1 < len(cues) else None
        invalid_end = not cue["start"] < cue["end"] <= duration + 0.5
        overlaps = following is not None and cue["end"] > following["start"]
        if invalid_end or overlaps:
            if following is None:
                raise ValueError(
                    "Invalid final caption end; no following caption start can bound it"
                )
            # Bound the earlier cue by the next observed onset, not guessed word times.
            caption_adjustments.append(
                {
                    "cue_index": index,
                    "original_end": cue["end"],
                    "end": following["start"],
                    "reason": "invalid caption end" if invalid_end else "overlaps next caption",
                }
            )
            cue["end"] = following["start"]
            srt_cues[index]["end"] = following["start"]
    if caption_adjustments or caption_omissions:
        srt, vtt = render_captions(srt_cues), render_captions(cues, vtt=True)
        parse_captions(srt, duration)
        parse_captions(vtt, duration, vtt=True)
    timing_status = "unavailable" if not words else "partial" if timing_issues else "complete"
    for cue in cues:
        # Partial word offsets cannot establish all speakers in a caption.
        cue["speakers"] = []
        if timing_status == "complete":
            cue["speakers"] = sorted(
                {
                    w["speaker"]
                    for w in words
                    if w["speaker"] is not None
                    and w["end"] > cue["start"]
                    and w["start"] < cue["end"]
                }
            )
    return {
        "transcript": "\n\n".join(passages),
        "words": words,
        "cues": cues,
        "srt": srt,
        "vtt": vtt,
        "word_timing_status": timing_status,
        "word_timing_issues": timing_issues,
        "caption_timing_adjustments": caption_adjustments,
        "caption_timing_omissions": caption_omissions,
    }


def compare_script(script: str, transcript: str, aliases: list[str]) -> dict:
    if aliases:
        script = re.sub(
            r"(?m)^(?:" + "|".join(re.escape(a) for a in aliases) + r"):\s*", "", script
        )

    def tokens(text):
        return re.findall(
            r"\w+(?:['’]\w+)*", text.replace("&", " and ").replace("’", "'").casefold()
        )

    expected, heard = tokens(script), tokens(transcript)
    matcher = SequenceMatcher(None, expected, heard, autojunk=False)
    differences = [
        {
            "kind": tag,
            "script": " ".join(expected[a:b]),
            "recognized": " ".join(heard[c:d]),
            "script_token_range": [a, b],
            "recognized_token_range": [c, d],
        }
        for tag, a, b, c, d in matcher.get_opcodes()
        if tag != "equal"
    ]
    return {
        "review_status": "pending",
        "token_similarity": round(matcher.ratio(), 4),
        "differences": differences,
        "note": "Recognition differences need listening review; similarity is not proof of speech fidelity.",
    }


def listening_preview(
    title: str, cues: list[dict], language: str = "en-US", timing_notice: str = ""
) -> str:
    data = json.dumps(cues, ensure_ascii=False).replace("<", "\\u003c")
    notice = f'<p class="muted">{escape(timing_notice)}</p>' if timing_notice else ""
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
{notice}
<audio id="player" aria-label="Episode audio" controls preload="none" src="audio.mp3"></audio>
<nav aria-label="Downloads"><a href="captions.srt" download>SRT</a><a href="captions.vtt" download>WebVTT</a>
<a href="transcript.txt" download>Transcript</a></nav>
<label><input id="follow" type="checkbox" checked> Follow playback</label>
<label for="speed">Playback speed <select id="speed"><option value="1">1×</option><option value="1.15" selected>1.15×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option></select></label>
<p id="status" role="status">Select a caption to listen from that point.</p>
<div id="transcript" role="region" aria-label="Timed transcript" lang="{escape(language)}"></div>
<noscript><p>Open the <a href="transcript.txt">readable transcript</a> and use the audio controls above.</p></noscript></main>
<script type="application/json" id="cue-data">{data}</script>
<script>
const cues=JSON.parse(document.getElementById('cue-data').textContent);
const player=document.getElementById('player'),list=document.getElementById('transcript');
const follow=document.getElementById('follow'),status=document.getElementById('status');
document.getElementById('speed').addEventListener('change',event=>{{player.playbackRate=Number(event.target.value);}});
player.defaultPlaybackRate=1.15;player.playbackRate=1.15;
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


def export_result(
    directory: Path, operation: dict, plan: dict, script: str, aliases: list[str]
) -> None:
    recognized = extract_recognition(operation, plan["audio_uri"], plan["duration_seconds"])
    (directory / "captions.srt").write_text(recognized["srt"], encoding="utf-8")
    (directory / "captions.vtt").write_text(recognized["vtt"], encoding="utf-8")
    (directory / "transcript.txt").write_text(recognized["transcript"] + "\n", encoding="utf-8")
    write_json(
        directory / "words.json",
        {
            "audio_sha256": plan["audio_sha256"],
            "words": recognized["words"],
            "timing_status": recognized["word_timing_status"],
            "timing_issues": recognized["word_timing_issues"],
        },
    )
    write_json(
        directory / "cues.json",
        {
            "audio_sha256": plan["audio_sha256"],
            "cues": recognized["cues"],
            "timing_adjustments": recognized["caption_timing_adjustments"],
            "timing_omissions": recognized["caption_timing_omissions"],
        },
    )
    comparison = (
        compare_script(script, recognized["transcript"], aliases)
        if script
        else {
            "review_status": "pending",
            "differences": [],
            "note": "No input script was supplied for comparison.",
        }
    )
    write_json(directory / "comparison.json", comparison)
    write_json(
        directory / "captions.json",
        {
            "version": 1,
            "audio_sha256": plan["audio_sha256"],
            "script_sha256": digest(script.strip().encode()) if script else None,
            "operation": operation["name"],
            "model": plan["model"],
            "location": plan["location"],
            "language": plan.get("language", "en-US"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "review_status": "pending",
            "word_timing_status": recognized["word_timing_status"],
            "word_timing_issue_count": len(recognized["word_timing_issues"]),
            "caption_timing_adjustments": recognized["caption_timing_adjustments"],
            "caption_timing_omissions": recognized["caption_timing_omissions"],
            "detected_speaker_ids": sorted(
                {w["speaker"] for w in recognized["words"] if w["speaker"] is not None}
            ),
            "files": {
                p: digest_file(directory / p)
                for p in (
                    "captions.srt",
                    "captions.vtt",
                    "transcript.txt",
                    "words.json",
                    "cues.json",
                )
            },
        },
    )
    timing_notice = ""
    if recognized["word_timing_status"] != "complete":
        timing_notice = (
            f"Word timing is {recognized['word_timing_status']}: "
            f"{len(recognized['word_timing_issues'])} invalid entries retained in words.json. "
            "Playback uses validated SRT/WebVTT caption timing; transcript text is preserved. "
            "Speaker labels are omitted."
        )
    if recognized["caption_timing_adjustments"]:
        timing_notice += (
            f" {len(recognized['caption_timing_adjustments'])} caption ends adjusted "
            "to the next recorded caption start. Original response retained in operation.json."
        )
    if recognized["caption_timing_omissions"]:
        timing_notice += (
            f" {len(recognized['caption_timing_omissions'])} trailing captions beyond the "
            "finished recording excluded from playback and retained in cues.json for review. "
            "Recognized transcript text and the original response are preserved."
        )
    if timing_notice:
        report(timing_notice.strip())
    (directory / "listen.html").write_text(
        listening_preview(
            plan["title"], recognized["cues"], plan.get("language", "en-US"), timing_notice
        ),
        encoding="utf-8",
    )
    report(f"Captions ready: {directory}/captions.srt")
    report(f"Listen with the timed transcript: {directory}/listen.html")
    report(
        f"Script comparison: {len(comparison['differences'])} differences to review; no text was automatically corrected."
    )


def recording_plan(args: argparse.Namespace) -> tuple[Path, dict, bytes, dict, str]:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", args.project):
        raise ValueError("Provide the Google Cloud project ID")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,61}[a-z0-9]", args.bucket):
        raise ValueError("Provide a bucket name without gs://, paths or dots")
    if args.model == "chirp_3" and args.location == "global":
        raise ValueError(
            "Chirp 3 transcription uses --location us or eu; this is independent of the TTS endpoint"
        )
    if args.diarize and (args.model != "chirp_3" or args.language == "fi-FI"):
        raise ValueError("This pilot supports diarization with Chirp 3 English recordings")
    if not 0 <= args.wait <= 3600:
        raise ValueError("--wait must be between 0 and 3600 seconds")
    path = args.audio.resolve(strict=True)
    if (
        path.suffix.lower() != ".mp3"
        or not path.is_file()
        or not 0 < path.stat().st_size <= 100_000_000
    ):
        raise ValueError("Provide a finished MP3 no larger than 100 MB")
    content = path.read_bytes()
    audio_hash = digest(content)
    metadata_path = path.with_name("episode.json")
    metadata = read_object(metadata_path) if metadata_path.exists() else {}
    if metadata.get("audio_sha256") and metadata["audio_sha256"] != audio_hash:
        raise ValueError(
            "This MP3 differs from its episode metadata; identify the correct recording first"
        )
    script_path = args.script or path.with_name("transcript.txt")
    script = script_path.read_text(encoding="utf-8") if script_path.exists() else ""
    if args.script and not script:
        raise ValueError("The supplied script is missing or empty")
    if (
        script
        and not args.script
        and metadata.get("script_sha256")
        and metadata["script_sha256"] != digest(script.strip().encode())
    ):
        raise ValueError(
            "The neighboring input script differs from the script recorded in episode metadata"
        )
    object_name = f"field-notes-input/{audio_hash}.mp3"
    uri = f"gs://{args.bucket}/{object_name}"
    payload = recognition_request(uri, args.model, args.language, args.diarize)
    fingerprint = digest(
        json.dumps(
            {"request": payload, "project": args.project, "location": args.location}, sort_keys=True
        ).encode()
    )
    directory = path.parent / "captions" / fingerprint[:16]
    duration = probe_audio(path)
    plan = {
        "audio_sha256": audio_hash,
        "audio_uri": uri,
        "duration_seconds": duration,
        "title": metadata.get("title", path.stem),
        "model": args.model,
        "location": args.location,
        "language": args.language,
        "request": payload,
        "fingerprint": fingerprint,
    }
    return directory, plan, content, metadata, script


def caption_log_root(directory: Path) -> Path:
    """The checkout's ``artifacts/audio`` log, also for an MP3 kept elsewhere."""
    from field_notes_audio import audio as audio_module

    return spend_guard.log_root(directory, audio_module.ROOT / "artifacts/audio")


def run(args: argparse.Namespace, *, expected_operation: str | None = None) -> Path | None:
    directory, plan, content, metadata, script = recording_plan(args)
    duration = plan["duration_seconds"]
    audio_hash, uri, payload = plan["audio_sha256"], plan["audio_uri"], plan["request"]
    object_name = f"field-notes-input/{audio_hash}.mp3"
    report(
        f"Caption existing recording: {duration / 60:.2f} minutes; {args.model}; location {args.location}"
    )
    report("No speech synthesis. Transcription and private Cloud Storage have separate charges.")
    if args.dry_run:
        report(json.dumps(plan, ensure_ascii=False, indent=2))
        report("Dry run only; nothing uploaded or submitted.")
        return
    if not shutil.which("gcloud"):
        raise ValueError("Captioning requires an authenticated gcloud session")
    raise_if_stopped(args)
    directory.mkdir(parents=True, exist_ok=True)
    with run_lock(directory):
        state_path = directory / "state.json"
        state = read_object(state_path) if state_path.exists() else {}
        if expected_operation is not None and (
            state.get("operation") != expected_operation
            or state.get("status") not in {"running", "complete"}
            or state.get("audio_sha256") != audio_hash
        ):
            raise ValueError(
                "The saved caption receipt changed or disappeared. Resume will not create a new submission."
            )
        write_json(directory / "plan.json", plan)
        if state.get("status") in {"requesting", "uncertain"} and not args.retry_uncertain:
            raise ValueError(
                "A previous transcription submission has no saved acknowledgement, so billing "
                "is unknown. "
                + spend_guard.describe(
                    caption_log_root(directory),
                    metadata.get("id") or "recording-" + audio_hash[:12],
                    "captions",
                )
                + " Stop and wait before another paid try. Only if you accept another "
                "possible charge, run the same command with --retry-uncertain once by hand."
            )
        if args.restart_failed and state.get("status") not in {"running", "complete"}:
            if state.get("status") != "failed":
                raise ValueError("--restart-failed applies only to a saved, confirmed failed job")
            (directory / "failed-operation.json").write_bytes(
                (directory / "operation.json").read_bytes()
            )
            state = {}
        if state.get("status") == "failed":
            raise ValueError(
                "The saved transcription job failed. Repair the reported cause, then use --restart-failed for a new billable job."
            )
        if state.get("status") == "complete":
            operation = read_object(directory / "operation.json")
        else:
            if not state.get("operation"):
                episode = metadata.get("id") or "recording-" + audio_hash[:12]
                audio_root = caption_log_root(directory)
                retry = (
                    getattr(args, "retry_hint", "") or "run the same command with --retry-uncertain"
                )
                override = getattr(args, "allow_spend_over_limit", None)
                report(spend_guard.limits_text(spend_guard.load_limits(audio_root)))
                # Refuse before any upload; the binding check comes just before submission.
                preview = spend_guard.tally(audio_root, episode, "captions")
                if preview.blocked and override is None:
                    raise spend_guard.SpendLimitReached(
                        spend_guard.refusal(preview, "captions"), preview
                    )
                report(f"Upload or reuse private input: {uri}", flush=True)
                generation = ensure_upload(
                    content, args.bucket, object_name, args.project, args.auth
                )
                raise_if_stopped(args)
                (directory / "audio.mp3").write_bytes(content)
                attempt_id = spend_guard.new_attempt_id()
                guard = spend_guard.reserve(
                    audio_root,
                    episode,
                    "captions",
                    attempt_id=attempt_id,
                    estimate_usd=None,
                    request_sha256=plan["fingerprint"],
                    override=override,
                    token=getattr(args, "spend_token", None),
                    command="captions",
                )
                if guard.blocked:
                    report(
                        "Spend guard override logged: "
                        + guard.sentence()
                        + f" Reason: {spend_guard.validate_reason(override)}",
                        flush=True,
                    )
                write_json(
                    state_path,
                    {
                        "status": "requesting",
                        "audio_sha256": audio_hash,
                        "storage_generation": generation,
                        "attempt_id": attempt_id,
                    },
                )

                def settle(outcome, detail="", ids=None):
                    try:
                        spend_guard.record_outcome(
                            audio_root,
                            episode=episode,
                            part="captions",
                            attempt_id=attempt_id,
                            outcome=outcome,
                            detail=detail,
                            ids=ids,
                        )
                    except OSError as exc:
                        # Never hide the provider's result behind a local log failure.
                        report(f"Warning: the attempt log could not record {outcome!r}: {exc}")

                host = (
                    "speech.googleapis.com"
                    if args.location == "global"
                    else f"{args.location}-speech.googleapis.com"
                )
                url = f"https://{host}/v2/projects/{args.project}/locations/{args.location}/recognizers/_:batchRecognize"
                try:
                    operation = cloud_json(url, args.project, args.auth, payload)
                    operation_url(operation.get("name"), args.location, args.project)
                except CloudError as exc:
                    provider_status = exc.diagnostic.get("provider_status", "")
                    uncertain = http_uncertain(exc.code, provider_status)
                    write_json(
                        state_path,
                        {
                            "status": "uncertain" if uncertain else "rejected",
                            "audio_sha256": audio_hash,
                            "attempt_id": attempt_id,
                            **exc.diagnostic,
                        },
                    )
                    settle(
                        "uncertain" if uncertain else "failed",
                        f"HTTP {exc.code} {provider_status}".strip(),
                    )
                    if not uncertain:
                        raise
                    raise CloudError(
                        exc.diagnostic,
                        f"Caption submission failed: {http_meaning(exc.code, provider_status)} "
                        f"(HTTP {exc.code}). No transcription operation ID was saved. "
                        + spend_guard.describe(audio_root, episode, "captions")
                        + " "
                        + stop_and_wait(exc.code, provider_status, retry=retry)
                        + f" Technical detail: {exc}; attempt {attempt_id}. "
                        f"Diagnostic: {state_path}",
                    ) from None
                except Exception as exc:
                    write_json(
                        state_path,
                        {
                            "status": "uncertain",
                            "audio_sha256": audio_hash,
                            "attempt_id": attempt_id,
                        },
                    )
                    settle("uncertain", type(exc).__name__)
                    raise RuntimeError(
                        "Caption submission failed: no valid transcription operation ID was saved. "
                        + spend_guard.describe(audio_root, episode, "captions")
                        + " "
                        + stop_and_wait(None, retry=retry)
                        + f" Technical detail: {type(exc).__name__}; attempt {attempt_id}. "
                        f"Diagnostic: {state_path}"
                    ) from None
                settle("acknowledged", ids={"operation": str(operation["name"])[:160]})
                state = {
                    "status": "running",
                    "operation": operation["name"],
                    "audio_sha256": audio_hash,
                    "storage_generation": generation,
                }
                write_json(state_path, state)
            else:
                operation = poll_operation(
                    operation_url(state["operation"], args.location, args.project),
                    args.project,
                    args.auth,
                )
            deadline = time.monotonic() + args.wait
            progress_at = time.monotonic() + 30
            while not operation.get("done"):
                raise_if_stopped(args)
                write_json(directory / "operation.json", operation)
                if time.monotonic() >= deadline:
                    report(f"Transcription is running: {state['operation']}")
                    report(
                        "Repeat the same command to resume polling; no new job will be submitted."
                    )
                    return
                time.sleep(min(3, max(0, deadline - time.monotonic())))
                operation = poll_operation(
                    operation_url(state["operation"], args.location, args.project),
                    args.project,
                    args.auth,
                )
                if time.monotonic() >= progress_at and not operation.get("done"):
                    report(
                        "Transcription is still running; waiting automatically. Ctrl-C saves your place.",
                        flush=True,
                    )
                    progress_at = time.monotonic() + 30
            write_json(directory / "operation.json", operation)
            file_error = (
                operation.get("response", {}).get("results", {}).get(uri, {}).get("error", {})
            )
            if operation.get("error") or file_error.get("code", 0):
                write_json(
                    state_path,
                    {
                        **state,
                        "status": "failed",
                        "provider_error": operation.get("error") or file_error,
                    },
                )
                raise ValueError(
                    "The transcription job failed; inspect operation.json and check Speech-to-Text and bucket permissions"
                )
            write_json(state_path, {**state, "status": "complete"})
        if not (directory / "audio.mp3").exists():
            (directory / "audio.mp3").write_bytes(content)
        aliases = [s["alias"] for s in metadata.get("speakers", [])]
        export_result(directory, operation, plan, script, aliases)
        report(
            f"Private input is retained at {uri}; keep it until review is complete, then remove it if no longer needed."
        )
        return directory
