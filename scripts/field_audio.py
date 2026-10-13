#!/usr/bin/env python3
"""Prepare and synthesize reviewed Field Notes scripts using Google Cloud TTS.

Python's standard library is sufficient. Paid generation is an explicit command;
plan/check never authenticate, make network requests or change the public site.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from urllib import error, request
import wave

ROOT = Path(__file__).resolve().parents[1]
MODELS = {"gemini-2.5-flash-tts": 10, "gemini-2.5-pro-tts": 20}
ENDPOINTS = {"eu": "eu-texttospeech.googleapis.com", "us": "us-texttospeech.googleapis.com",
             "global": "texttospeech.googleapis.com"}
VOICES = set("Achernar Achird Algenib Algieba Alnilam Aoede Autonoe Callirrhoe Charon "
             "Despina Enceladus Erinome Fenrir Gacrux Iapetus Kore Laomedeia Leda Orus "
             "Pulcherrima Puck Rasalgethi Sadachbia Sadaltager Schedar Sulafat "
             "Umbriel Vindemiatrix Zephyr Zubenelgenubi".split())


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_article(root: Path, note: dict) -> str:
    html = (root / "docs/notes" / note["slug"]).read_text(encoding="utf-8")
    found = re.search(r'<article class="note-prose">(.*?)</article>', html, re.S)
    if not found:
        raise ValueError(f"Missing article body in note {note['id']}")
    return found[1]


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
        return "\n\n".join(re.sub(r"\s+", " ", p).strip() for p in
                          re.split(r"\n\s*\n", "".join(self.parts)) if p.strip())


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
    notes = catalog(root)
    if not episode["notes"] or set(episode["source_sha256"]) != set(episode["notes"]):
        raise ValueError("Every source note must have an article fingerprint")
    for identifier in episode["notes"]:
        if identifier not in notes:
            raise ValueError(f"Source note {identifier} is not published")
        actual = digest(source_article(root, notes[identifier]).encode("utf-8"))
        if actual != episode["source_sha256"][identifier]:
            raise ValueError(f"Note {identifier} changed. Review the script before refreshing its fingerprint.")
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
        voice["multiSpeakerVoiceConfig"] = {"speakerVoiceConfigs": [
            {"speakerAlias": s["alias"], "speakerId": s["voice"]} for s in episode["speakers"]]}
    return {"input": {"prompt": episode["prompt"], "text": text}, "voice": voice,
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}}


def make_plan(identifier: str, model: str, endpoint: str, root: Path = ROOT) -> dict:
    episode, text = load_episode(identifier, root)
    chunks = chunk_script(episode, text)
    words = len(re.findall(r"\b[\w’'-]+\b", text))
    minutes = words / 140
    requests = [payload(episode, c, model) for c in chunks]
    fingerprint = digest(json.dumps({"endpoint": endpoint, "requests": requests,
                                    "source_sha256": episode["source_sha256"]},
                                   sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return {"episode": episode, "script": text, "script_sha256": digest(text.encode("utf-8")),
            "fingerprint": fingerprint, "model": model, "endpoint": endpoint,
            "word_count": words, "estimated_minutes_at_140_wpm": round(minutes, 2),
            "estimated_output_cost_usd": round(minutes * 60 * 25 * MODELS[model] / 1_000_000, 4),
            "requests": requests}


def summarize(plan: dict) -> None:
    print(f"{plan['episode']['id']}: {plan['episode']['title']}")
    print(f"{plan['word_count']} words; about {plan['estimated_minutes_at_140_wpm']} minutes at 140 wpm")
    print(f"{len(plan['requests'])} bounded requests; {plan['model']}; endpoint {plan['endpoint']}")
    print(f"Estimated speech output: ${plan['estimated_output_cost_usd']:.4f} USD (text input and retries extra)")
    print("Estimate is based on script length, not a measured duration or a spending cap.")


def access_token(auth: str) -> str:
    command = ["gcloud", "auth"]
    if auth == "adc":
        command.append("application-default")
    command.append("print-access-token")
    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError("Google authentication failed. Authorize Cloud Shell, or run gcloud auth login locally.")
    # The token stays in memory. Never print it or include it in request artifacts.
    return result.stdout.strip()


def synthesize(data: dict, project: str, endpoint: str, token: str) -> bytes:
    req = request.Request(f"https://{ENDPOINTS[endpoint]}/v1/text:synthesize",
                          data=json.dumps(data).encode("utf-8"), method="POST",
                          headers={"Authorization": "Bearer " + token,
                                   "x-goog-user-project": project, "Content-Type": "application/json"})
    with request.urlopen(req, timeout=180) as response:
        result = json.load(response)
    try:
        audio = base64.b64decode(result["audioContent"], validate=True)
    except (KeyError, ValueError) as exc:
        raise RuntimeError("Google returned no valid audio content") from exc
    validate_wav(audio)
    return audio


def validate_wav(audio: bytes) -> float:
    with wave.open(io.BytesIO(audio), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 24000, "NONE"):
            raise ValueError("Expected uncompressed 24 kHz mono 16-bit WAV")
        frames = wav.readframes(wav.getnframes())
        if not wav.getnframes() or len(frames) != wav.getnframes() * 2:
            raise ValueError("Empty or incomplete WAV response")
        return wav.getnframes() / 24000


def combine_wavs(paths: list[Path], target: Path) -> float:
    duration = 0.0
    with wave.open(str(target), "wb") as combined:
        combined.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        for index, path in enumerate(paths):
            data = path.read_bytes()
            duration += validate_wav(data)
            if index:
                combined.writeframes(b"\0" * 9600)  # 200 ms at a section boundary
                duration += .2
            with wave.open(io.BytesIO(data), "rb") as part:
                combined.writeframes(part.readframes(part.getnframes()))
    return duration


def generate(args) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", args.project or ""):
        raise ValueError("Provide a valid Google Cloud project ID with --project (not its display name or number)")
    if not all(shutil.which(name) for name in ("gcloud", "ffmpeg", "ffprobe")):
        raise ValueError("Generation requires gcloud, ffmpeg and ffprobe; see audio/README.md")
    plan = make_plan(args.episode, args.model, args.endpoint)
    summarize(plan)
    directory = ROOT / "artifacts/audio" / args.episode / plan["fingerprint"][:16]
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "plan.json", plan)
    paths = []
    for index, data in enumerate(plan["requests"], start=1):
        wav_path = directory / f"chunk-{index:03d}.wav"
        state_path = directory / f"chunk-{index:03d}.json"
        expected = digest(json.dumps(data, sort_keys=True).encode("utf-8"))
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        if state.get("request_sha256") == expected and state.get("status") == "complete":
            if not wav_path.exists() or digest(wav_path.read_bytes()) != state["audio_sha256"]:
                raise ValueError(f"Cached audio chunk {index} is missing or changed; move this run aside to regenerate")
            validate_wav(wav_path.read_bytes())
            print(f"Chunk {index}/{len(plan['requests'])}: reuse saved audio")
        else:
            if state.get("status") in {"requesting", "uncertain"} and not args.retry_uncertain:
                raise ValueError(f"Chunk {index} has an uncertain prior attempt. --retry-uncertain can incur another charge.")
            token = access_token(args.auth)
            write_json(state_path, {"status": "requesting", "request_sha256": expected})
            print(f"Chunk {index}/{len(plan['requests'])}: generate", flush=True)
            try:
                audio = synthesize(data, args.project, args.endpoint, token)
                wav_path.write_bytes(audio)
                write_json(state_path, {"status": "complete", "request_sha256": expected,
                                       "audio_sha256": digest(audio), "duration_seconds": validate_wav(audio)})
            except error.HTTPError as exc:
                status = "failed" if 400 <= exc.code < 500 and exc.code not in {408, 429} else "uncertain"
                write_json(state_path, {"status": status, "request_sha256": expected, "http_status": exc.code})
                raise RuntimeError(f"Google returned HTTP {exc.code}. Check API enablement, billing, permissions and quota; see audio/README.md.") from None
            except Exception:
                write_json(state_path, {"status": "uncertain", "request_sha256": expected})
                raise RuntimeError("No completed audio was saved. Re-run to inspect state; an uncertain retry can incur another charge.") from None
        paths.append(wav_path)
    duration = combine_wavs(paths, directory / "master.wav")
    result = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", str(directory / "master.wav"),
                             "-af", "loudnorm=I=-19:TP=-1.5:LRA=7:print_format=json", "-ar", "24000",
                             "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k", str(directory / "episode.tmp.mp3")],
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError("Audio encoding failed. Saved WAV chunks can be reused on the next run.")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "json", str(directory / "episode.tmp.mp3")],
                           capture_output=True, text=True, timeout=30)
    if probe.returncode:
        raise RuntimeError("The encoded MP3 could not be inspected. Saved WAV chunks can be reused.")
    mp3_duration = float(json.loads(probe.stdout)["format"]["duration"])
    if abs(mp3_duration - duration) > .3:
        raise RuntimeError("The encoded MP3 duration differs from its source audio. Saved WAV chunks can be reused.")
    (directory / "episode.tmp.mp3").replace(directory / "episode.mp3")
    (directory / "normalization.log").write_text(result.stderr, encoding="utf-8")
    (directory / "transcript.txt").write_text(plan["script"] + "\n", encoding="utf-8")
    audio = (directory / "episode.mp3").read_bytes()
    write_json(directory / "episode.json", {"version": 1, "id": args.episode,
               "title": plan["episode"]["title"], "generated_at": datetime.now(timezone.utc).isoformat(),
               "model": args.model, "endpoint": args.endpoint, "speakers": plan["episode"]["speakers"],
               "source_sha256": plan["episode"]["source_sha256"], "script_sha256": plan["script_sha256"],
               "audio_sha256": digest(audio), "bytes": len(audio), "duration_seconds": round(mp3_duration, 3),
               "wav_duration_seconds": round(duration, 3),
               "fingerprint": plan["fingerprint"], "listening_review": "pending"})
    print(f"Ready to listen: {directory.relative_to(ROOT)}/episode.mp3")
    print("Source script is saved as transcript.txt; it has not been verified against the generated speech.")
    print("Nothing has been uploaded or published. Listen before choosing a voice or publishing.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Validate all source fingerprints, scripts and request boundaries offline")
    for name in ("plan", "generate"):
        sub = commands.add_parser(name)
        sub.add_argument("episode")
        sub.add_argument("--model", choices=MODELS, default="gemini-2.5-pro-tts")
        sub.add_argument("--endpoint", choices=ENDPOINTS, default="eu")
        if name == "plan":
            sub.add_argument("--json", action="store_true", help="Print the bounded requests; contains no credentials")
        else:
            sub.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"))
            sub.add_argument("--auth", choices=("gcloud", "adc"), default="gcloud")
            sub.add_argument("--retry-uncertain", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            episodes = json.loads((ROOT / "audio/episodes.json").read_text(encoding="utf-8"))
            for episode in episodes:
                plan = make_plan(episode["id"], "gemini-2.5-pro-tts", "eu")
                for data in plan["requests"]:
                    assert len(data["input"]["text"].encode("utf-8")) <= 3000
                    assert sum(len(v.encode("utf-8")) for v in data["input"].values()) <= 4000
                summarize(plan)
            print(f"Checked {len(episodes)} pilot scripts; no Google requests made.")
        elif args.command == "plan":
            plan = make_plan(args.episode, args.model, args.endpoint)
            if args.json:
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                summarize(plan)
                print("Dry run only; no Google requests made.")
        else:
            generate(args)
        return 0
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError, wave.Error) as exc:
        print(f"Audio setup: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
