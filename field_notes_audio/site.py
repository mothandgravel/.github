"""Build note listening controls and a separate podcast RSS from real media only."""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from field_notes_audio.audio import digest, source_article
from field_notes_audio.captions import parse_captions, probe_audio
from field_notes_audio.storage import digest_file

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "https://mothandgravel.com"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "podcast": "https://podcastindex.org/namespace/1.0",
}


def caption_text(value: str) -> str:
    class Reader(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data)

    reader = Reader()
    reader.feed(value)
    reader.close()
    return " ".join("".join(reader.parts).split())


def media_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not re.fullmatch(
        r"assets/audio/[a-z0-9-]+\.(mp3|srt|vtt|txt|json)", relative
    ):
        raise ValueError("Published audio assets must live under docs/assets/audio")
    path = root / "docs" / relative
    if not path.is_file():
        raise ValueError(f"Missing published audio asset: {relative}")
    return path


def load_entries(root: Path = ROOT) -> list[dict]:
    path = root / "docs/assets/audio/episodes.json"
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if not isinstance(entries, list) or len({e["id"] for e in entries}) != len(entries):
        raise ValueError("Invalid or duplicate published episode IDs")
    notes = {
        n["id"]: n
        for n in json.loads((root / "docs/assets/notes.json").read_text(encoding="utf-8"))
    }
    if entries:
        cover = (root / "docs/assets/podcast-cover.png").read_bytes()
        if cover[:8] != b"\x89PNG\r\n\x1a\n" or len(cover) < 24:
            raise ValueError("Podcast artwork must be a PNG")
        width, height = struct.unpack(">II", cover[16:24])
        if width != height or not 1400 <= width <= 3000:
            raise ValueError("Podcast artwork must be square, 1400–3000 pixels")
    primary = set()
    for e in entries:
        if (
            not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", e["id"])
            or not e["title"]
            or e["kind"] not in {"note", "conversation", "comparison"}
        ):
            raise ValueError("Invalid published episode")
        duration = e["duration_seconds"]
        if (
            type(duration) not in (int, float)
            or not math.isfinite(duration)
            or not 0 < duration <= 1200
        ):
            raise ValueError("Invalid measured episode duration")
        if e["kind"] == "note":
            if e["note_id"] not in notes or e["note_id"] in primary:
                raise ValueError("Each note can have one primary audio edition")
            primary.add(e["note_id"])
        if not e.get("source_sha256"):
            raise ValueError("Published audio needs source fingerprints")
        for identifier, fingerprint in e["source_sha256"].items():
            if (
                identifier not in notes
                or digest(source_article(root, notes[identifier]).encode()) != fingerprint
            ):
                raise ValueError(
                    f"Published episode {e['id']} has a changed source note; review it before rebuilding"
                )
        audio = media_path(root, e["audio"])
        if audio.stat().st_size != e["bytes"] or digest_file(audio) != e["audio_sha256"]:
            raise ValueError(f"Published MP3 changed: {e['id']}")
        if abs(probe_audio(audio) - duration) > 0.05:
            raise ValueError("Published duration differs from the actual recording")
        for kind in ("srt", "vtt", "transcript", "cues"):
            file = media_path(root, e[kind])
            if digest_file(file) != e["files_sha256"][kind]:
                raise ValueError(f"Published {kind} changed: {e['id']}")
        srt = parse_captions(media_path(root, e["srt"]).read_text(encoding="utf-8"), duration)
        vtt = parse_captions(
            media_path(root, e["vtt"]).read_text(encoding="utf-8"), duration, vtt=True
        )
        if len(srt) != len(vtt) or any(
            abs(a[key] - b[key]) > 0.01 or caption_text(a["text"]) != caption_text(b["text"])
            for a, b in zip(srt, vtt, strict=False)
            for key in ("start", "end")
        ):
            raise ValueError("Published SRT/VTT captions disagree")
        cues = json.loads(media_path(root, e["cues"]).read_text(encoding="utf-8"))
        if (
            not isinstance(cues, list)
            or len(cues) != len(srt)
            or any(
                a["text"] != b["text"]
                or abs(a["start"] - b["start"]) > 0.01
                or abs(a["end"] - b["end"]) > 0.01
                for a, b in zip(cues, vtt, strict=False)
            )
        ):
            raise ValueError("Published transcript cues disagree with subtitles")
        date = datetime.fromisoformat(e["published_at"])
        if date.tzinfo is None:
            raise ValueError("Episode publication timestamp needs a timezone")
    order = {"note": 0, "conversation": 1, "comparison": 2}
    return sorted(entries, key=lambda e: (order[e["kind"]], e.get("note_id", ""), e["id"]))


def minutes(entry: dict) -> int:
    return max(1, math.ceil(entry["duration_seconds"] / 60))


def clock(value: float) -> str:
    return f"{int(value // 60)}:{int(value % 60):02d}"


def speed_control() -> str:
    return '<label hidden>Playback speed <select data-audio-speed aria-label="Playback speed"><option value="1">1×</option><option value="1.15" selected>1.15×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option></select></label>'


def transcript_html(entry: dict, root: Path) -> str:
    cues = json.loads(media_path(root, entry["cues"]).read_text(encoding="utf-8"))
    return "".join(
        f'<p data-cue-start="{cue["start"]}" data-cue-end="{cue["end"]}"><a href="#listen-note" data-audio-seek="{cue["start"]}" aria-label="Listen from {clock(cue["start"])}">{clock(cue["start"])}</a> <span>{escape(caption_text(cue["text"]))}</span></p>'
        for cue in cues
    )


def note_control(entry: dict, root: Path) -> str:
    return f'''<details class="note-listen" id="listen-note" data-note-player>
  <summary>Listen to this note · {minutes(entry)} min <span class="audio-badge">AI-narrated</span></summary>
  <p class="audio-label mono">AI-narrated <span>· Machine-generated transcript</span></p>
  <audio controls preload="none" aria-label="{escape(entry["title"], quote=True)}" src="../{entry["audio"]}"><track kind="captions" src="../{entry["vtt"]}" srclang="en" label="English"><a href="../{entry["audio"]}">Download audio</a></audio>
  <div class="audio-tools">{speed_control()}<label data-audio-follow-control hidden><input type="checkbox" data-audio-follow checked> Follow transcript</label><a href="../{entry["audio"]}" download>Download audio</a><a href="../{entry["vtt"]}" download>Subtitles</a><a href="./podcast.xml">Subscribe to the podcast</a></div>
  <details class="audio-transcript"><summary>Transcript</summary><p class="audio-caption-note">Transcribed from the recording. Names and speaker boundaries may contain errors.</p><div class="audio-cues" role="region" aria-label="Timed transcript" tabindex="0">{transcript_html(entry, root)}</div><a href="../{entry["transcript"]}" download>Download transcript</a></details>
  <p class="audio-status" data-audio-status role="status"></p>
</details>'''


def archive_control(entries: list[dict], root: Path) -> str:
    if not entries:
        return ""
    first = entries[0]
    notes = {
        n["id"]: n
        for n in json.loads((root / "docs/assets/notes.json").read_text(encoding="utf-8"))
    }
    queue = []
    data = []
    for index, e in enumerate(entries):
        url = (
            "./" + notes[e["note_id"]]["slug"] + "#listen-note"
            if e["kind"] == "note"
            else "../" + e["audio"]
        )
        label = "Field note " + e["note_id"] if e["kind"] == "note" else e["kind"].title()
        queue.append(
            f'<li><button type="button" data-queue-index="{index}" hidden><span class="mono">{label}</span><strong>{escape(e["title"])}</strong><span>{minutes(e)} min</span></button><a class="audio-queue-read" href="{url}">{escape(e["title"])} <span>{minutes(e)} min · {label}</span></a></li>'
        )
        data.append(
            {
                "id": e["id"],
                "title": e["title"],
                "audio": "../" + e["audio"],
                "vtt": "../" + e["vtt"],
                "transcript": "../" + e["transcript"],
                "cues": "../" + e["cues"],
                "url": url,
            }
        )
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return f"""<section class="archive-listen" id="listen-archive" aria-labelledby="listen-title" data-archive-player>
  <div class="audio-section-heading"><div><p class="eyebrow">FIELD NOTES / AUDIO</p><h2 id="listen-title">Listen through the archive</h2><p>One note after another, with room to pause.</p></div><a class="editorial-link" href="./podcast.xml">Subscribe to the podcast <span aria-hidden="true">↗</span></a></div>
  <p class="audio-label mono">AI-narrated · {len(entries)} episodes</p>
  <h3 data-queue-title>{escape(first["title"])}</h3>
  <audio controls preload="none" aria-label="Archive audio" src="../{first["audio"]}"><track kind="captions" src="../{first["vtt"]}" srclang="en" label="English"><a href="../{first["audio"]}">Download the first episode</a></audio>
  <div class="audio-tools"><button type="button" data-queue-start hidden>Listen through the archive</button><button type="button" data-queue-previous hidden disabled>Previous</button><button type="button" data-queue-next hidden>Next</button>{speed_control()}<label data-queue-auto-label hidden><input type="checkbox" data-queue-auto checked> Play the next note</label><a data-queue-transcript href="../{first["transcript"]}">Transcript</a></div>
  <p class="audio-status" data-audio-status role="status"></p>
  <ol class="audio-queue">{"".join(queue)}</ol>
  <script type="application/json" data-queue-data>{payload}</script>
</section>"""


def podcast_feed(entries: list[dict]) -> str:
    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    for name, value in (
        ("title", "Moth & Gravel — Field Notes audio"),
        ("link", DOMAIN + "/notes/#listen-archive"),
        (
            "description",
            "AI-narrated Field Notes and conversations from an independent software and design studio.",
        ),
        ("language", "en"),
        ("copyright", "Moth & Gravel"),
    ):
        ET.SubElement(channel, name).text = value
    ET.SubElement(
        channel,
        f"{{{NS['atom']}}}link",
        href=DOMAIN + "/notes/podcast.xml",
        rel="self",
        type="application/rss+xml",
    )
    for tag, text in (("author", "Moth & Gravel"), ("explicit", "false"), ("type", "episodic")):
        ET.SubElement(channel, f"{{{NS['itunes']}}}{tag}").text = text
    ET.SubElement(channel, f"{{{NS['itunes']}}}image", href=DOMAIN + "/assets/podcast-cover.png")
    category = ET.SubElement(channel, f"{{{NS['itunes']}}}category", text="Arts")
    ET.SubElement(category, f"{{{NS['itunes']}}}category", text="Design")
    image = ET.SubElement(channel, "image")
    for tag, value in (
        ("url", DOMAIN + "/assets/podcast-cover.png"),
        ("title", "Moth & Gravel — Field Notes audio"),
        ("link", DOMAIN + "/notes/"),
    ):
        ET.SubElement(image, tag).text = value
    for e in reversed(entries):
        item = ET.SubElement(channel, "item")
        article = (
            DOMAIN + "/notes/" + e["slug"]
            if e["kind"] == "note"
            else DOMAIN + "/notes/#listen-archive"
        )
        for tag, value in (
            ("title", e["title"]),
            ("link", article),
            (
                "description",
                e["description"] + " AI-narrated; machine-generated transcript available.",
            ),
        ):
            ET.SubElement(item, tag).text = value
        ET.SubElement(item, "guid", isPermaLink="false").text = DOMAIN + "/notes/podcast/" + e["id"]
        ET.SubElement(item, "pubDate").text = format_datetime(
            datetime.fromisoformat(e["published_at"]).astimezone(timezone.utc), usegmt=True
        )
        ET.SubElement(
            item,
            "enclosure",
            url=DOMAIN + "/" + e["audio"],
            length=str(e["bytes"]),
            type="audio/mpeg",
        )
        ET.SubElement(item, f"{{{NS['itunes']}}}duration").text = str(
            math.ceil(e["duration_seconds"])
        )
        ET.SubElement(item, f"{{{NS['itunes']}}}explicit").text = "false"
        ET.SubElement(
            item,
            f"{{{NS['podcast']}}}transcript",
            url=DOMAIN + "/" + e["vtt"],
            type="text/vtt",
            language=e["language"],
        )
        ET.SubElement(
            item,
            f"{{{NS['podcast']}}}transcript",
            url=DOMAIN + "/" + e["transcript"],
            type="text/plain",
            language=e["language"],
        )
    ET.indent(rss)
    return ET.tostring(rss, encoding="unicode", xml_declaration=True) + "\n"


def replace_slot(path: Path, name: str, content: str, anchor: str, check: bool) -> None:
    old = path.read_text(encoding="utf-8")
    generated = f"<!-- {name}:start -->\n{content}\n<!-- {name}:end -->"
    if f"<!-- {name}:start -->" in old:
        new, count = re.subn(
            rf"<!-- {name}:start -->.*?<!-- {name}:end -->", lambda _: generated, old, flags=re.S
        )
        if count != 1:
            raise ValueError(f"Duplicate audio slot: {path}")
    else:
        match = re.search(anchor, old)
        if not match:
            raise ValueError(f"Missing audio insertion point: {path}")
        new = old[: match.start()] + generated + "\n" + old[match.start() :]
    if check:
        if old != new:
            raise ValueError(f"Stale listening output: run python3 scripts/build_notes.py ({path})")
    else:
        path.write_text(new)


def build(check: bool = False, root: Path = ROOT) -> list[dict]:
    entries = load_entries(root)
    notes = json.loads((root / "docs/assets/notes.json").read_text(encoding="utf-8"))
    primary = {e["note_id"]: e for e in entries if e["kind"] == "note"}
    for note in notes:
        path = root / "docs/notes" / note["slug"]
        # The introduction owns the listen affordance; the article prose stays intact.
        replace_slot(
            path,
            "note-audio",
            note_control(primary[note["id"]], root) if note["id"] in primary else "",
            r"(?<=</p>)\s*</div>",
            check,
        )
    archive = root / "docs/notes/index.html"
    replace_slot(
        archive,
        "archive-audio",
        archive_control(entries, root),
        r'<div class="collection-count mono">',
        check,
    )
    head = (
        (
            '<link rel="alternate" type="application/rss+xml" title="Moth &amp; Gravel — Field Notes audio" href="./podcast.xml">\n'
            '<link rel="stylesheet" href="../assets/field-audio.css">\n<script type="module" src="../assets/field-listen.mjs"></script>'
        )
        if entries
        else ""
    )
    for path in [archive, *(root / "docs/notes" / n["slug"] for n in notes)]:
        replace_slot(path, "audio-head", head, r"</head>", check)
    feed = podcast_feed(entries)
    path = root / "docs/notes/podcast.xml"
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != feed:
            raise ValueError("Stale podcast feed: run python3 scripts/build_notes.py")
    else:
        path.write_text(feed)
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    build(parser.parse_args().check)


if __name__ == "__main__":
    main()
