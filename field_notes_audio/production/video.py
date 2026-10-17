"""Stage only the episode's local artwork and invoke the pinned Remotion renderer."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

from field_notes_audio.production.renderer_process import renderer_concurrency, run_renderer
from field_notes_audio.storage import read_object, write_json


def visual_assets(root: Path, entry: dict) -> dict[str, Path]:
    assets = {"mark.svg": root / "docs/assets/moth-mark.svg"}
    candidates = []

    class Reader(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "img" and "src" in attributes:
                candidates.append(attributes["src"])

    if entry.get("slug"):
        article = root / "docs/notes" / entry["slug"]
        Reader().feed(article.read_text(encoding="utf-8"))
        for source in candidates:
            if urlparse(source).scheme or urlparse(source).netloc:
                continue
            image = (article.parent / unquote(urlparse(source).path)).resolve()
            if (
                image.is_relative_to((root / "docs/assets/notes").resolve())
                and image.suffix in {".png", ".jpg", ".jpeg", ".webp", ".svg"}
                and image.is_file()
            ):
                assets["artwork" + image.suffix] = image
                break
    if len(assets) == 1:
        assets["artwork.png"] = root / "docs/assets/podcast-cover.png"
    return assets


def render_video(
    root: Path,
    entry: dict,
    edition: Path,
    stage: Path,
    settings: dict,
    args: argparse.Namespace,
    assets: dict[str, Path],
    bundle: Path | None = None,
) -> None:
    public = stage / "public"
    public.mkdir()
    for name, path in assets.items():
        shutil.copyfile(path, public / name)
    # Both locations belong to this locked edition on the same filesystem.
    # A read-only hard link avoids copying hundreds of megabytes per render.
    try:
        (public / "master.wav").hardlink_to(edition / "master.wav")
    except OSError:
        shutil.copyfile(edition / "master.wav", public / "master.wav")
    state = read_object(edition / "production.json")
    props = {
        "title": entry["title"],
        "label": entry["id"].upper(),
        "description": entry["description"],
        "kind": entry["kind"],
        "duration": state["timeline_duration_seconds"],
        "intro": settings["intro_seconds"],
        "outro": settings["outro_seconds"],
        "pages": json.loads((edition / "cues.json").read_text(encoding="utf-8"))["pages"],
        "artwork": next(name for name in assets if name.startswith("artwork")),
        "artworkLabel": "FROM THE WRITTEN NOTE"
        if any(path.parent.name == "notes" for path in assets.values())
        else "STUDIO ARTWORK",
        "video": {
            **settings["video"],
            "concurrency": renderer_concurrency(settings["video"]["concurrency"]),
        },
        "previewSeconds": args.preview_seconds,
    }
    write_json(stage / "props.json", props)
    command = [
        "node",
        str(root / "video/render.mjs"),
        str(stage / "props.json"),
        str(public),
        str(stage),
    ]
    command.append(str(args.browser_executable.resolve()) if args.browser_executable else "")
    if bundle is not None:
        command.append(str(bundle))
    run_renderer(command, root / "video")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            str(stage / "episode.mp4"),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    media = json.loads(result.stdout)
    video = next((s for s in media["streams"] if s["codec_type"] == "video"), {})
    expected = (
        math.ceil(
            min(props["duration"], args.preview_seconds or props["duration"])
            * settings["video"]["fps"]
        )
        / settings["video"]["fps"]
    )
    if (
        video.get("codec_name") != "h264"
        or video.get("width") != settings["video"]["width"]
        or video.get("height") != settings["video"]["height"]
        or video.get("r_frame_rate") != f"{settings['video']['fps']}/1"
        or not any(
            s.get("codec_name") == "aac" and s.get("codec_type") == "audio"
            for s in media["streams"]
        )
        or abs(float(media["format"]["duration"]) - expected) > 0.15
    ):
        raise ValueError(
            "Rendered video has an unexpected codec, dimensions, frame rate or duration"
        )
    # Review directories retain finished output, not a copied browser bundle or WAV.
    shutil.rmtree(public)
    (stage / "props.json").unlink()
