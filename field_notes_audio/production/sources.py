"""Private prepared recordings for production; never a public podcast manifest."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from field_notes_audio import audio, captions, site
from field_notes_audio.locks import run_lock
from field_notes_audio.storage import digest_file, read_object, write_json

MEDIA = {
    "audio": "episode.mp3",
    "srt": "captions.srt",
    "vtt": "captions.vtt",
    "transcript": "transcript.txt",
    "cues": "cues.json",
}


def identity(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def private_path(root: Path, relative: str) -> Path:
    """Reject escapes and symlinked inputs, including intermediate directories."""
    root = root.resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError("Local preparation path escapes the checkout")
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError("Local preparation paths must not contain symbolic links")
    return path


def media_path(root: Path, relative: str) -> Path:
    if isinstance(relative, str) and relative.startswith("studio-prepared/"):
        if not re.fullmatch(
            r"studio-prepared/[a-z0-9]+(?:-[a-z0-9]+)*/[a-f0-9]{64}/"
            r"(?:episode\.mp3|captions\.(?:srt|vtt)|transcript\.txt|cues\.json)",
            relative,
        ):
            raise ValueError("Invalid private prepared-media path")
        path = private_path(root, "artifacts/studio/prepared/" + relative.split("/", 1)[1])
        if not path.is_file():
            raise ValueError("Private prepared media is missing; inspect preparation again")
        return path
    return site.media_path(root, relative)


def _validate(root: Path, entry: dict) -> None:
    if entry.get("local_prepared") is not True or entry.get("review_status") != "pending":
        raise ValueError("Local adoption is not human media approval")
    if "published_at" in entry or "production" in entry:
        raise ValueError("Private preparation must not claim publication or a finished edition")
    episode, text = audio.load_episode(entry["id"], root)
    note_id = episode["publication"].get("note_id")
    note = audio.catalog(root).get(note_id)
    if (
        not note
        or episode["publication"].get("kind") != "note"
        or entry.get("kind") != "note"
        or entry.get("note_id") != note_id
        or entry.get("slug") != note["slug"]
        or entry.get("title") != episode["title"]
        or entry.get("description") != note["summary"]
        or entry.get("language") != episode["language"]
        or entry.get("script_sha256") != audio.digest(text.encode())
        or entry.get("source_sha256") != episode["source_sha256"]
    ):
        raise ValueError("Prepared recording no longer matches the written note and saved script")
    prefix = f"studio-prepared/{entry['id']}/"
    if any(not isinstance(entry.get(k), str) or not entry[k].startswith(prefix) for k in MEDIA):
        raise ValueError("Prepared media must belong to this episode")
    site.validate_recording_media(root, entry, media_path)


def load_entries(root: Path) -> list[dict]:
    public = site.load_entries(root)
    known = {entry["id"] for entry in public}
    parent = private_path(root, "artifacts/studio/prepared")
    local = []
    for pointer in sorted(parent.glob("*/latest.json")):
        private_path(root, str(pointer.relative_to(root)))
        if pointer.parent.name in known:
            # Later public publication is authoritative; never replace it implicitly.
            continue
        saved = read_object(pointer)
        token = saved.get("identity")
        if not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{64}", token):
            raise ValueError("Invalid private recording pointer")
        manifest = pointer.parent / token / "entry.json"
        private_path(root, str(manifest.relative_to(root)))
        entry = read_object(manifest)
        if identity(entry) != saved.get("entry_sha256") or entry.get("id") != pointer.parent.name:
            raise ValueError("Private recording manifest changed")
        if any(
            entry.get(k) != f"studio-prepared/{entry['id']}/{token}/{v}" for k, v in MEDIA.items()
        ):
            raise ValueError("Private recording points outside its captured edition")
        _validate(root, entry)
        local.append(entry)
    return [*public, *local]


def adopt(root: Path, plan: dict, directory: Path) -> Path:
    """Verify completed narration/captions and atomically expose a local source only."""
    root = root.resolve()
    episode = plan["episode"]
    current = audio.make_plan(episode["id"], plan["model"], plan["endpoint"], root)
    if identity(current) != identity(plan):
        raise ValueError("Narration source changed before local adoption")
    recording = private_path(root, f"artifacts/audio/{episode['id']}/{plan['fingerprint'][:16]}")
    if directory.parent != recording / "captions" or not re.fullmatch(
        r"[a-f0-9]{16}", directory.name
    ):
        raise ValueError("Caption result must belong to the captured narration run")
    private_path(root, str(directory.relative_to(root)))
    metadata = read_object(recording / "episode.json")
    capmeta = read_object(directory / "captions.json")
    state = read_object(directory / "state.json")
    source = recording / "episode.mp3"
    digest = digest_file(source)
    if (
        state.get("status") != "complete"
        or metadata.get("id") != episode["id"]
        or metadata.get("fingerprint") != plan["fingerprint"]
        or metadata.get("audio_sha256") != digest
        or capmeta.get("audio_sha256") != digest
        or metadata.get("script_sha256") != plan["script_sha256"]
        or capmeta.get("script_sha256") != plan["script_sha256"]
        or metadata.get("source_sha256") != episode["source_sha256"]
        or audio.digest((recording / "transcript.txt").read_text(encoding="utf-8").strip().encode())
        != plan["script_sha256"]
    ):
        raise ValueError("Narration and caption provenance disagree; nothing was adopted")
    data = {}
    for name in ("captions.srt", "captions.vtt", "transcript.txt", "cues.json", "words.json"):
        path = private_path(root, str((directory / name).relative_to(root)))
        data[name] = path.read_bytes()
        if audio.digest(data[name]) != capmeta.get("files", {}).get(name):
            raise ValueError(f"Caption output changed: {name}; nothing was adopted")
    cues = json.loads(data["cues.json"])
    if cues.get("audio_sha256") != digest:
        raise ValueError("Caption cues belong to another recording")
    data["cues.json"] = (json.dumps(cues["cues"], ensure_ascii=False, indent=2) + "\n").encode()
    duration = captions.probe_audio(source)
    if duration > captions.CAPTION_LIMIT_SECONDS and not capmeta.get("parts"):
        raise ValueError("A recording over one caption job must be captioned in parts")
    token = identity(
        {
            "plan": plan["fingerprint"],
            "audio": digest,
            "captions": {k: audio.digest(v) for k, v in data.items()},
        }
    )
    note = audio.catalog(root)[episode["publication"]["note_id"]]
    entry = {
        "id": episode["id"],
        "title": episode["title"],
        "kind": "note",
        "description": note["summary"],
        "note_id": note["id"],
        "slug": note["slug"],
        "language": episode["language"],
        "bytes": source.stat().st_size,
        "audio_sha256": digest,
        "script_sha256": plan["script_sha256"],
        "source_sha256": episode["source_sha256"],
        "duration_seconds": round(duration, 3),
        "review_status": "pending",
        "narration": "AI-narrated",
        "local_prepared": True,
        **{kind: f"studio-prepared/{episode['id']}/{token}/{name}" for kind, name in MEDIA.items()},
        "files_sha256": {
            kind: audio.digest(data[name]) for kind, name in MEDIA.items() if kind != "audio"
        },
    }
    parent = private_path(root, "artifacts/studio/prepared")
    parent.mkdir(parents=True, exist_ok=True)
    with run_lock(parent, "local recording adoption"):
        if any(e["id"] == episode["id"] for e in site.load_entries(root)):
            raise ValueError("An episode is already public; local preparation will not replace it")
        target = private_path(root, f"artifacts/studio/prepared/{episode['id']}/{token}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with tempfile.TemporaryDirectory(prefix=".adopt-", dir=target.parent) as temporary:
                stage = Path(temporary) / "edition"
                stage.mkdir()
                shutil.copyfile(source, stage / "episode.mp3")
                if digest_file(stage / "episode.mp3") != digest:
                    raise ValueError("Recording changed during local adoption")
                for name in MEDIA.values():
                    if name != "episode.mp3":
                        (stage / name).write_bytes(data[name])
                write_json(stage / "entry.json", entry)
                stage.rename(target)
        saved = read_object(target / "entry.json")
        if saved != entry:
            raise ValueError("Existing content-addressed preparation changed")
        _validate(root, entry)
        write_json(
            target.parent / "latest.json", {"identity": token, "entry_sha256": identity(entry)}
        )
        return target
