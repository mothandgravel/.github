#!/usr/bin/env python3
"""Prepare and synthesize reviewed Field Notes scripts using Google Cloud TTS.

Python's standard library is sufficient. Paid generation is an explicit command;
plan/check never authenticate, make network requests or change the public site.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import shutil
import subprocess
import time
import uuid
import wave
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib import error, request

from field_notes_audio import auth as google_auth
from field_notes_audio.locks import run_lock
from field_notes_audio.progress import raise_if_stopped, report, stage, timed
from field_notes_audio.storage import digest_file, read_object, write_json

ROOT = Path(__file__).resolve().parents[1]
# Transport policy is not narration content: never include it in cache fingerprints.
# urllib applies this to blocking socket operations, not a total request deadline.
TTS_TIMEOUT_SECONDS = 600
LEGACY_TTS_TIMEOUT_SECONDS = 180


def validate_tts_timeout(value: object) -> int:
    if type(value) is not int or not 60 <= value <= 900:
        raise ValueError("Narration socket timeout must be an integer from 60 to 900 seconds")
    return value


MODELS = {"gemini-2.5-flash-tts": 10, "gemini-2.5-pro-tts": 20}
ENDPOINTS = {
    "eu": "eu-texttospeech.googleapis.com",
    "us": "us-texttospeech.googleapis.com",
    "global": "texttospeech.googleapis.com",
}
VOICES = set(
    "Achernar Achird Algenib Algieba Alnilam Aoede Autonoe Callirrhoe Charon "
    "Despina Enceladus Erinome Fenrir Gacrux Iapetus Kore Laomedeia Leda Orus "
    "Pulcherrima Puck Rasalgethi Sadachbia Sadaltager Schedar Sulafat "
    "Umbriel Vindemiatrix Zephyr Zubenelgenubi".split()
)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def source_article(root: Path, note: dict) -> str:
    if not re.fullmatch(r"\d{3,}-[a-z0-9-]+\.html", note["slug"]):
        raise ValueError("Invalid source note path")
    html = (root / "docs/notes" / note["slug"]).read_text(encoding="utf-8")
    found = list(re.finditer(r'<article class="note-prose">(.*?)</article>', html, re.S))
    if not found:
        raise ValueError(f"Missing article body in note {note['id']}")
    # A design study can have multiple prose blocks and specimens between them.
    # Keep the original single-block fingerprint so existing recordings still match.
    return html[found[0].start(1) : found[-1].end(1)]


class ProseReader(HTMLParser):
    """Extract a script candidate; visual passages still need editorial review."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"svg", "script", "style"}:
            self.hidden += 1
        if not self.hidden and tag in {"p", "h2", "h3", "li", "blockquote", "figcaption"}:
            self.parts.append("\n\n")
        if not self.hidden and tag == "br":
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"svg", "script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in {"p", "h2", "h3", "li", "blockquote", "figcaption"}:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    def text(self) -> str:
        return "\n\n".join(
            re.sub(r"\s+", " ", p).strip()
            for p in re.split(r"\n\s*\n", "".join(self.parts))
            if p.strip()
        )


def catalog(root: Path) -> dict[str, dict]:
    notes = json.loads((root / "docs/assets/notes.json").read_text(encoding="utf-8"))
    return {n["id"]: n for n in notes}


def load_episode(identifier: str, root: Path = ROOT) -> tuple[dict, str]:
    episodes = json.loads((root / "audio/episodes.json").read_text(encoding="utf-8"))
    if len({e["id"] for e in episodes}) != len(episodes):
        raise ValueError("Duplicate episode identifier")
    episode = next((e for e in episodes if e["id"] == identifier), None)
    if episode is None:
        raise ValueError(f"Unknown episode: {identifier}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier):
        raise ValueError("Invalid episode identifier")
    script = (root / "audio" / episode["script"]).resolve()
    if not script.is_relative_to((root / "audio/scripts").resolve()):
        raise ValueError("Script must live under audio/scripts/")
    text = script.read_text(encoding="utf-8").strip()
    if not text or len(text.encode("utf-8")) > 100_000:
        raise ValueError("Script must contain 1–100,000 UTF-8 bytes")
    if episode["language"] not in {"en-US", "en-GB", "fi-FI"}:
        raise ValueError("Unsupported language in this pilot")
    speakers = episode["speakers"]
    if len(speakers) not in {1, 2} or len({s["alias"] for s in speakers}) != len(speakers):
        raise ValueError("Use one or two unique speakers")
    for speaker in speakers:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", speaker["alias"]):
            raise ValueError("Speaker aliases must be alphanumeric")
        if speaker["voice"] not in VOICES:
            raise ValueError("Unknown prebuilt voice")
    if not 0 < len(episode["prompt"].encode("utf-8")) <= 1000:
        raise ValueError("Delivery prompt must fit in 1,000 UTF-8 bytes")
    target_wpm = episode.get("target_wpm", 140)
    if type(target_wpm) is not int or not 100 <= target_wpm <= 220:
        raise ValueError("The planning pace must be an integer from 100 to 220 words per minute")
    notes = catalog(root)
    if not episode["notes"] or set(episode["source_sha256"]) != set(episode["notes"]):
        raise ValueError("Every source note must have an article fingerprint")
    for identifier in episode["notes"]:
        if identifier not in notes:
            raise ValueError(f"Source note {identifier} is not published")
        actual = digest(source_article(root, notes[identifier]).encode("utf-8"))
        if actual != episode["source_sha256"][identifier]:
            raise ValueError(
                f"Note {identifier} changed. Review the script before refreshing its fingerprint."
            )
    return episode, text


def split_units(text: str, maximum: int) -> list[str]:
    """Split on sentences/words without slicing a UTF-8 character or dropping text."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    units: list[str] = []
    for sentence in sentences:
        if len(sentence.encode("utf-8")) <= maximum:
            units.append(sentence)
            continue
        current = ""
        for word in sentence.split():
            if len(word.encode("utf-8")) > maximum:
                raise ValueError("A single script word exceeds the request limit")
            proposed = (current + " " + word).strip()
            if len(proposed.encode("utf-8")) > maximum:
                units.append(current)
                current = word
            else:
                current = proposed
        if current:
            units.append(current)
    return units


def chunk_script(episode: dict, text: str) -> list[str]:
    # Deliberately stay below 4,000 combined bytes, also satisfying the stricter
    # prose note in Google's multi-speaker documentation and the 4,000 text cap.
    maximum = min(3000, 3900 - len(episode["prompt"].encode("utf-8")))
    units: list[str] = []
    if len(episode["speakers"]) == 1:
        for paragraph in re.split(r"\n\s*\n", text):
            if len(paragraph.encode("utf-8")) <= maximum:
                units.append(paragraph.strip())
            else:
                units.extend(split_units(paragraph, maximum))
    else:
        aliases = {s["alias"] for s in episode["speakers"]}
        seen = set()
        for line in text.splitlines():
            if not line.strip():
                continue
            match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*):\s*(\S.*)", line)
            if not match or match[1] not in aliases:
                raise ValueError("Every dialogue line must start with a configured speaker alias")
            seen.add(match[1])
            prefix = match[1] + ": "
            if len(line.encode("utf-8")) <= maximum:
                units.append(line)
            else:
                units.extend(prefix + part for part in split_units(match[2], maximum - len(prefix)))
        if seen != aliases:
            raise ValueError("The dialogue must include both configured speakers")
    chunks: list[str] = []
    current = ""
    for unit in units:
        proposed = (current + "\n\n" + unit).strip()
        if len(proposed.encode("utf-8")) > maximum:
            chunks.append(current)
            current = unit
        else:
            current = proposed
    if current:
        chunks.append(current)
    return chunks


def payload(episode: dict, text: str, model: str) -> dict:
    voice = {"languageCode": episode["language"], "modelName": model}
    if len(episode["speakers"]) == 1:
        voice["name"] = episode["speakers"][0]["voice"]
    else:
        voice["multiSpeakerVoiceConfig"] = {
            "speakerVoiceConfigs": [
                {"speakerAlias": s["alias"], "speakerId": s["voice"]} for s in episode["speakers"]
            ]
        }
    return {
        "input": {"prompt": episode["prompt"], "text": text},
        "voice": voice,
        "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000},
    }


def make_plan(identifier: str, model: str, endpoint: str, root: Path = ROOT) -> dict:
    episode, text = load_episode(identifier, root)
    chunks = chunk_script(episode, text)
    spoken_text = (
        text
        if len(episode["speakers"]) == 1
        else re.sub(r"(?m)^[A-Za-z][A-Za-z0-9]*:\s*", "", text)
    )
    words = len(re.findall(r"\b[\w’'-]+\b", spoken_text))
    target_wpm = episode.get("target_wpm", 140)
    minutes = words / target_wpm
    requests = [payload(episode, c, model) for c in chunks]
    fingerprint = digest(
        json.dumps(
            {"endpoint": endpoint, "requests": requests, "source_sha256": episode["source_sha256"]},
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    )
    return {
        "episode": episode,
        "script": text,
        "script_sha256": digest(text.encode("utf-8")),
        "fingerprint": fingerprint,
        "model": model,
        "endpoint": endpoint,
        "word_count": words,
        "target_wpm": target_wpm,
        "estimated_minutes": round(minutes, 2),
        "estimated_output_cost_usd": round(minutes * 60 * 25 * MODELS[model] / 1_000_000, 4),
        "requests": requests,
    }


def summarize(plan: dict) -> None:
    report(f"{plan['episode']['id']}: {plan['episode']['title']}")
    report(
        f"{plan['word_count']} script words; about {plan['estimated_minutes']} minutes at the {plan['target_wpm']} wpm target"
    )
    report(
        f"{len(plan['requests'])} bounded requests; {plan['model']}; endpoint {plan['endpoint']}"
    )
    report(
        f"Estimated speech output: ${plan['estimated_output_cost_usd']:.4f} USD (text input and retries extra)"
    )
    report(
        "Pace is a delivery request, not an enforced timing constraint. Duration and cost are estimates."
    )


def access_token(auth: str) -> str:
    return google_auth.access_token(auth)


def synthesize(
    data: dict,
    project: str,
    endpoint: str,
    token: str,
    *,
    timeout_seconds: int = TTS_TIMEOUT_SECONDS,
) -> bytes:
    timeout_seconds = validate_tts_timeout(timeout_seconds)
    req = request.Request(
        f"https://{ENDPOINTS[endpoint]}/v1/text:synthesize",
        data=json.dumps(data).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "x-goog-user-project": project,
            "Content-Type": "application/json",
        },
    )
    try:
        with timed("tts_request"), request.urlopen(req, timeout=timeout_seconds) as response:
            result = json.load(response)
    except error.HTTPError as exc:
        if exc.code == 401:
            google_auth.invalidate_token(token)
        raise
    try:
        audio = base64.b64decode(result["audioContent"], validate=True)
    except (KeyError, ValueError) as exc:
        raise RuntimeError("Google returned no valid audio content") from exc
    validate_wav(audio)
    return audio


def validate_wav(audio: bytes) -> float:
    with wave.open(io.BytesIO(audio), "rb") as wav:
        return _transfer_pcm(wav)


def _transfer_pcm(source: wave.Wave_read, target: wave.Wave_write | None = None) -> float:
    """Validate and optionally copy PCM in bounded blocks, preserving every frame."""
    if (
        source.getnchannels(),
        source.getsampwidth(),
        source.getframerate(),
        source.getcomptype(),
    ) != (
        1,
        2,
        24000,
        "NONE",
    ):
        raise ValueError("Expected uncompressed 24 kHz mono 16-bit WAV")
    expected = source.getnframes() * 2
    size = 0
    while frames := source.readframes(48000):
        size += len(frames)
        if target is not None:
            target.writeframesraw(frames)
    if not expected or size != expected:
        raise ValueError("Empty or incomplete WAV response")
    return source.getnframes() / 24000


def combine_wavs(paths: list[Path], target: Path) -> float:
    duration = 0.0
    with wave.open(str(target), "wb") as combined:
        combined.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        for index, path in enumerate(paths):
            if index:
                combined.writeframes(b"\0" * 9600)  # 200 ms at a section boundary
                duration += 0.2
            with wave.open(str(path), "rb") as part:
                duration += _transfer_pcm(part, combined)
    return duration


def http_diagnostic(exc: error.HTTPError, token: str) -> dict:
    """Keep bounded provider diagnostics, never request headers or credentials."""
    result = {"http_status": exc.code}
    raw = exc.read(8192).decode("utf-8", errors="replace")
    try:
        body = json.loads(raw)
        provider = body.get("error", {}) if isinstance(body, dict) else {}
        if not isinstance(provider, dict):
            provider = {}
        status = provider.get("status", "")
        if isinstance(status, str) and re.fullmatch(r"[A-Z_]{1,64}", status):
            result["provider_status"] = status
        message = provider.get("message", "")
    except ValueError:
        # Gateways can return HTML or plain text rather than Google's JSON error.
        message = re.sub(r"<[^>]*>", " ", raw)
    if isinstance(message, str) and message:
        message = message.replace(token, "[redacted]") if token else message
        message = re.sub(r"(?i)Bearer\s+\S+", "Bearer [redacted]", message)
        message = re.sub(
            r"(?i)(access_token|refresh_token|api_key|authorization)\s*[:=]\s*\S+",
            r"\1=[redacted]",
            message,
        )
        result["provider_message"] = re.sub(r"\s+", " ", message).strip()[:500]
    return result


def http_guidance(code: int, episode: str) -> str:
    if 500 <= code <= 599:
        return (
            "The service or an upstream gateway failed; this response does not establish a billing or IAM problem. "
            "No completed audio was saved for this chunk. After a short pause, repeat the same generate command "
            "with --retry-uncertain. A retry can incur another charge."
        )
    if code in {408, 429}:
        return (
            "The request timed out or capacity/quota was unavailable. Wait before retrying, then repeat the same "
            "generate command with --retry-uncertain. A retry can incur another charge; inspect quota if 429 persists."
        )
    if code == 401:
        return (
            "Authorize Cloud Shell or sign into the intended Google account with gcloud auth login."
        )
    if code == 403:
        return "Check the selected project, API enablement, billing and permissions; see audio/README.md."
    if code == 400:
        return f"Inspect the bounded request with plan {episode} --json; check model, language and voice support."
    return "Inspect the saved provider diagnostic and audio/README.md before repeating the request."


def generate(args: argparse.Namespace) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", args.project or ""):
        raise ValueError(
            "Provide a valid Google Cloud project ID with --project (not its display name or number)"
        )
    if not all(shutil.which(name) for name in ("gcloud", "ffmpeg", "ffprobe")):
        raise ValueError("Generation requires gcloud, ffmpeg and ffprobe; see audio/README.md")
    plan = make_plan(args.episode, args.model, args.endpoint)
    summarize(plan)
    directory = ROOT / "artifacts/audio" / args.episode / plan["fingerprint"][:16]
    directory.mkdir(parents=True, exist_ok=True)
    with run_lock(directory, "audio"):
        return generate_locked(args, plan, directory)


def generate_locked(
    args: argparse.Namespace, plan: dict, directory: Path, *, root: Path | None = None
) -> Path:
    root = ROOT if root is None else root
    timeout_seconds = validate_tts_timeout(
        getattr(args, "tts_timeout_seconds", TTS_TIMEOUT_SECONDS)
    )
    write_json(directory / "plan.json", plan)
    paths = []
    for index, data in enumerate(plan["requests"], start=1):
        raise_if_stopped(args)
        wav_path = directory / f"chunk-{index:03d}.wav"
        state_path = directory / f"chunk-{index:03d}.json"
        expected = digest(json.dumps(data, sort_keys=True).encode("utf-8"))
        raw = state_path.read_bytes() if state_path.exists() else b""
        state = json.loads(raw) if raw else {}
        receipt = getattr(args, "retry_receipts", {}).get(str(index))
        if receipt and not (
            state.get("request_sha256") == expected and state.get("status") == "complete"
        ):
            if (
                digest(raw) != receipt
                or state.get("request_sha256") != expected
                or state.get("status") not in {"requesting", "uncertain"}
            ):
                raise ValueError(
                    f"Chunk {index} recovery receipt changed or disappeared. Inspect recovery again; no replacement was sent."
                )
        if state.get("request_sha256") == expected and state.get("status") == "complete":
            if not wav_path.exists() or digest_file(wav_path) != state["audio_sha256"]:
                raise ValueError(
                    f"Cached audio chunk {index} is missing or changed; move this run aside to regenerate"
                )
            validate_wav(wav_path.read_bytes())
            report(f"Chunk {index}/{len(plan['requests'])}: reuse saved audio")
        else:
            if (
                state.get("status") in {"requesting", "uncertain"}
                and not args.retry_uncertain
                and not receipt
            ):
                raise ValueError(
                    f"Chunk {index} has an uncertain prior attempt. --retry-uncertain can incur another charge."
                )
            stage(
                f"narration-{index}-of-{len(plan['requests'])}",
                f"Narration chunk {index}/{len(plan['requests'])}: contacting the service; "
                f"client socket timeout {timeout_seconds}s. No automatic resend; earlier completed chunks are retained.",
            )
            token = access_token(args.auth)
            raise_if_stopped(args)
            if receipt:
                # Preserve the diagnostic that was authorized before replacing its state.
                archive = directory / f"recovery-{index:03d}-{receipt}.json"
                if not archive.exists():
                    write_json(archive, state)
                elif read_object(archive) != state:
                    raise ValueError("Saved recovery evidence changed; inspect before retrying")
            attempt_id = uuid.uuid4().hex
            write_json(
                state_path,
                {
                    "status": "requesting",
                    "request_sha256": expected,
                    "attempt_id": attempt_id,
                    "timeout_seconds": timeout_seconds,
                },
            )
            report(f"Chunk {index}/{len(plan['requests'])}: generate", flush=True)
            attempt_start = time.perf_counter()
            failure_phase = "narration_request"
            try:
                audio = synthesize(
                    data, args.project, args.endpoint, token, timeout_seconds=timeout_seconds
                )
                failure_phase = "local_save"
                wav_path.write_bytes(audio)
                write_json(
                    state_path,
                    {
                        "status": "complete",
                        "request_sha256": expected,
                        "audio_sha256": digest(audio),
                        "duration_seconds": validate_wav(audio),
                        "attempt_id": attempt_id,
                        "timeout_seconds": timeout_seconds,
                        "attempt_seconds": round(time.perf_counter() - attempt_start, 4),
                    },
                )
            except error.HTTPError as exc:
                status = (
                    "failed"
                    if 400 <= exc.code < 500 and exc.code not in {408, 429}
                    else "uncertain"
                )
                try:
                    diagnostic = http_diagnostic(exc, token)
                except (OSError, ValueError, TypeError):
                    diagnostic = {"http_status": exc.code}
                write_json(
                    state_path,
                    {
                        "status": status,
                        "request_sha256": expected,
                        "attempt_id": attempt_id,
                        "timeout_seconds": timeout_seconds,
                        "attempt_seconds": round(time.perf_counter() - attempt_start, 4),
                        **diagnostic,
                    },
                )
                detail = diagnostic.get("provider_status") or diagnostic.get("provider_message")
                label = f" ({detail})" if detail else ""
                raise RuntimeError(
                    f"Narration chunk {index}/{len(plan['requests'])}: Google returned HTTP {exc.code}{label}. {http_guidance(exc.code, args.episode)} "
                    f"Diagnostic: {state_path.relative_to(root)}"
                ) from None
            except Exception as exc:
                elapsed = time.perf_counter() - attempt_start
                timed_out = failure_phase == "narration_request" and (
                    isinstance(exc, TimeoutError)
                    or (isinstance(exc, error.URLError) and isinstance(exc.reason, TimeoutError))
                )
                kind = "TimeoutError" if timed_out else type(exc).__name__
                write_json(
                    state_path,
                    {
                        "status": "uncertain",
                        "request_sha256": expected,
                        "attempt_id": attempt_id,
                        "failure_kind": kind,
                        "failure_phase": failure_phase,
                        "timeout_seconds": timeout_seconds,
                        "attempt_seconds": round(elapsed, 4),
                    },
                )
                timing = (
                    f"Client wait for narration timed out (socket timeout {timeout_seconds}s); "
                    "remote processing and billing are unknown. "
                    if timed_out
                    else ""
                )
                raise RuntimeError(
                    f"Narration chunk {index}/{len(plan['requests'])}: {kind} after {elapsed:.1f}s. "
                    + timing
                    + "No completed audio was confirmed locally. Inspect recovery; resending this chunk can incur another charge. "
                    f"Diagnostic: {state_path.relative_to(root)}"
                ) from None
        paths.append(wav_path)
        # Outside the request exception handler: a late stop must not turn saved audio uncertain.
        stage(
            f"narration-{index}-of-{len(plan['requests'])}-complete",
            f"Narration chunk {index}/{len(plan['requests'])}: verified audio saved.",
        )
    metadata_path = directory / "episode.json"
    mp3_path = directory / "episode.mp3"
    if metadata_path.exists() and mp3_path.exists():
        metadata = read_object(metadata_path)
        if metadata.get("fingerprint") != plan["fingerprint"] or metadata.get(
            "audio_sha256"
        ) != digest_file(mp3_path):
            raise ValueError("Cached MP3 is missing or changed; move this run aside to regenerate")
        if (
            not (directory / "transcript.txt").exists()
            or digest((directory / "transcript.txt").read_text(encoding="utf-8").strip().encode())
            != plan["script_sha256"]
        ):
            raise ValueError(
                "Cached input script is missing or changed; move this run aside to regenerate"
            )
        report(f"Reuse completed recording: {mp3_path.relative_to(root)}")
        return mp3_path
    with timed("audio_assembly"):
        duration = combine_wavs(paths, directory / "master.wav")
    with timed("mp3_encoding"):
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-i",
                str(directory / "master.wav"),
                "-af",
                "loudnorm=I=-19:TP=-1.5:LRA=7:print_format=json",
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "96k",
                str(directory / "episode.tmp.mp3"),
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
    if result.returncode:
        raise RuntimeError("Audio encoding failed. Saved WAV chunks can be reused on the next run.")
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(directory / "episode.tmp.mp3"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if probe.returncode:
        raise RuntimeError(
            "The encoded MP3 could not be inspected. Saved WAV chunks can be reused."
        )
    mp3_duration = float(json.loads(probe.stdout)["format"]["duration"])
    if abs(mp3_duration - duration) > 0.3:
        raise RuntimeError(
            "The encoded MP3 duration differs from its source audio. Saved WAV chunks can be reused."
        )
    (directory / "episode.tmp.mp3").replace(directory / "episode.mp3")
    (directory / "normalization.log").write_text(result.stderr, encoding="utf-8")
    (directory / "transcript.txt").write_text(plan["script"] + "\n", encoding="utf-8")
    audio = (directory / "episode.mp3").read_bytes()
    write_json(
        directory / "episode.json",
        {
            "version": 1,
            "id": args.episode,
            "title": plan["episode"]["title"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": args.model,
            "endpoint": args.endpoint,
            "speakers": plan["episode"]["speakers"],
            "language": plan["episode"]["language"],
            "source_sha256": plan["episode"]["source_sha256"],
            "script_sha256": plan["script_sha256"],
            "audio_sha256": digest(audio),
            "bytes": len(audio),
            "duration_seconds": round(mp3_duration, 3),
            "wav_duration_seconds": round(duration, 3),
            "script_word_count": plan["word_count"],
            "target_wpm": plan["target_wpm"],
            "average_script_words_per_minute": round(plan["word_count"] * 60 / mp3_duration, 1),
            "fingerprint": plan["fingerprint"],
            "listening_review": "pending",
        },
    )
    report(f"Ready to listen: {directory.relative_to(root)}/episode.mp3")
    report(
        f"Generated duration: {int(mp3_duration // 60)}:{int(mp3_duration % 60):02d}; "
        f"average {plan['word_count'] * 60 / mp3_duration:.0f} script words per minute, including pauses"
    )
    report(
        "Source script is saved as transcript.txt; it has not been verified against the generated speech."
    )
    report("Nothing has been uploaded or published. Listen before choosing a voice or publishing.")
    return directory / "episode.mp3"
