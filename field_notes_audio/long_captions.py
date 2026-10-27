"""Caption a recording longer than one caption job by splitting it locally.

Each part is an ordinary caption job: ``captions.run`` uploads it, reserves the
paid attempt through the spend guard, and keeps its own receipt, so the same
uncertain, failed and resume rules hold per part. Parts are cut at a pause near
the limit when ``silencedetect`` finds one; otherwise at a fixed time with a
short overlap, whose duplicated words are dropped at the overlap midpoint.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from field_notes_audio import captions
from field_notes_audio.locks import run_lock
from field_notes_audio.progress import raise_if_stopped, report
from field_notes_audio.storage import digest_file, read_object, write_json

PART_SECONDS = 19 * 60
SEARCH_SECONDS = 90.0
OVERLAP_SECONDS = 5.0
SILENCE = {"noise": "-35dB", "min_seconds": 0.3}
SPLIT_VERSION = 1
ENCODE = ("-c:a", "libmp3lame", "-q:a", "2")


def silences(path: Path) -> list[tuple[float, float]]:
    """Pauses in the recording as (start, end) seconds, measured locally."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={SILENCE['noise']}:d={SILENCE['min_seconds']}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode:
        raise ValueError("Silence detection could not read the recording")
    found, start = [], None
    for line in result.stderr.splitlines():
        if match := re.search(r"silence_start: (-?[\d.]+)", line):
            start = max(0.0, float(match[1]))
        elif (match := re.search(r"silence_end: ([\d.]+)", line)) and start is not None:
            found.append((start, float(match[1])))
            start = None
    return found


def split_parts(duration: float, pauses: list[tuple[float, float]]) -> list[dict]:
    """Part ranges of at most ``PART_SECONDS``; a pause cut has no overlap."""
    parts, start = [], 0.0
    while duration - start > PART_SECONDS:
        limit = start + PART_SECONDS
        cuts = [
            round((max(a, limit - SEARCH_SECONDS) + min(b, limit)) / 2, 1)
            for a, b in pauses
            if min(b, limit) - max(a, limit - SEARCH_SECONDS) > 0
        ]
        if cuts:
            end, overlap = round(max(cuts), 3), 0.0
        else:
            end, overlap = round(limit, 3), OVERLAP_SECONDS
        parts.append({"start": round(start, 3), "end": end, "cut": "silence" if cuts else "fixed"})
        start = end - overlap
    parts.append({"start": round(start, 3), "end": round(duration, 3), "cut": "end"})
    for index, part in enumerate(parts, 1):
        part["index"] = index
    return parts


def boundaries(parts: list[dict]) -> list[float | None]:
    """Where overlapping neighbours hand over: the overlap midpoint, else None."""
    return [
        (a["end"] + b["start"]) / 2 if b["start"] < a["end"] else None
        for a, b in zip(parts, parts[1:], strict=False)
    ]


def encode_part(source: Path, part: dict, target: Path) -> None:
    temporary = target.with_suffix(".tmp.mp3")
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{part['start']:.3f}",
            "-t",
            f"{part['end'] - part['start']:.3f}",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-map_metadata",
            "-1",
            *ENCODE,
            "-fflags",
            "+bitexact",
            "-flags:a",
            "+bitexact",
            str(temporary),
        ],
        check=True,
        capture_output=True,
        timeout=600,
    )
    temporary.replace(target)


def prepare_parts(source: Path, audio_sha256: str, duration: float, directory: Path) -> list[dict]:
    """Split once and reuse: ``split.json`` fingerprints every part's audio."""
    if not shutil.which("ffmpeg"):
        raise ValueError("Captioning a long recording requires ffmpeg")
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "split.json"
    identity = {
        "version": SPLIT_VERSION,
        "audio_sha256": audio_sha256,
        "part_seconds": PART_SECONDS,
        "search_seconds": SEARCH_SECONDS,
        "overlap_seconds": OVERLAP_SECONDS,
        "silence": SILENCE,
        "encode": list(ENCODE),
    }
    manifest = read_object(manifest_path) if manifest_path.exists() else {}
    if manifest.get("identity") != identity:
        manifest = {"identity": identity, "parts": split_parts(duration, silences(source))}
    for part in manifest["parts"]:
        path = directory / f"part-{part['index']:02d}.mp3"
        if path.exists() and digest_file(path) == part.get("sha256"):
            continue
        encode_part(source, part, path)
        measured = digest_file(path)
        if part.get("sha256") not in {None, measured}:
            raise ValueError(
                f"Part {part['index']} re-encoded differently from its saved fingerprint, "
                "so its saved captions cannot be reused. Restore the part file or remove "
                f"{manifest_path} to split again; new parts are new paid caption jobs."
            )
        part["sha256"] = measured
    write_json(manifest_path, manifest)
    return manifest["parts"]


def _trim(text: str, drop_first: int, drop_last: int) -> str:
    spans = [m.span() for m in re.finditer(r"\S+", text)]
    if drop_first + drop_last >= len(spans):
        return ""
    start = spans[drop_first][0] if drop_first else 0
    end = spans[len(spans) - 1 - drop_last][1] if drop_last else len(text)
    return text[start:end].strip()


def join(parts: list[dict], results: list[dict], duration: float) -> dict:
    """Shift each part's recognition by its offset and join it as one recognition."""
    handover = boundaries(parts)
    many_speakers = len(parts) > 1

    def speaker(index, label):
        return f"{index}.{label}" if label is not None and many_speakers else label

    words, cues, passages, issues, adjustments, omissions = [], [], [], [], [], []
    statuses = set()
    for position, (part, result) in enumerate(zip(parts, results, strict=True)):
        index, offset = part["index"], part["start"]
        lower = handover[position - 1] if position else None
        upper = handover[position] if position < len(handover) else None

        def inside(start, lower=lower, upper=upper):
            return (lower is None or start >= lower) and (upper is None or start < upper)

        statuses.add(result["word_timing_status"])
        shifted = [
            {
                **w,
                "start": round(w["start"] + offset, 3),
                "end": round(w["end"] + offset, 3),
                "speaker": speaker(index, w["speaker"]),
            }
            for w in result["words"]
        ]
        kept = [w for w in shifted if inside(w["start"])]
        words.extend(kept)
        text = result["transcript"]
        if (lower is not None or upper is not None) and result["word_timing_status"] != "complete":
            # Without every word's time the duplicated overlap text cannot be located.
            issues.append(
                {
                    "part": index,
                    "reason": "overlap text kept twice: incomplete word timing in this part",
                }
            )
        elif lower is not None or upper is not None:
            text = _trim(
                text,
                sum(lower is not None and w["start"] < lower for w in shifted),
                sum(upper is not None and w["start"] >= upper for w in shifted),
            )
        if text:
            passages.append(text)
        for cue in result["cues"]:
            start = round(cue["start"] + offset, 3)
            if inside(start):
                cues.append(
                    {
                        **cue,
                        "start": start,
                        "end": round(cue["end"] + offset, 3),
                        "speakers": [speaker(index, s) for s in cue["speakers"]],
                    }
                )
        issues.extend(
            {"part": index, "offset_seconds": offset, **i} for i in result["word_timing_issues"]
        )
        adjustments.extend(
            {
                **entry,
                "part": index,
                "original_end": round(entry["original_end"] + offset, 3),
                "end": round(entry["end"] + offset, 3),
            }
            for entry in result["caption_timing_adjustments"]
        )
        omissions.extend(
            {
                **entry,
                "part": index,
                "start": round(entry["start"] + offset, 3),
                "end": round(entry["end"] + offset, 3),
            }
            for entry in result["caption_timing_omissions"]
        )
    for position, cue in enumerate(cues[:-1]):
        following = cues[position + 1]
        if cue["end"] > following["start"]:
            adjustments.append(
                {
                    "cue_index": position,
                    "original_end": cue["end"],
                    "end": following["start"],
                    "reason": "overlaps the next part's caption",
                }
            )
            cue["end"] = following["start"]
    if not cues:
        raise ValueError("No caption cues occur within the finished recording")
    srt, vtt = captions.render_captions(cues), captions.render_captions(cues, vtt=True)
    # Same validation as a single job's output: ordered, non-overlapping, inside the recording.
    captions.parse_captions(srt, duration)
    captions.parse_captions(vtt, duration, vtt=True)
    status = (
        "unavailable"
        if not words
        else "partial"
        if issues or statuses != {"complete"}
        else "complete"
    )
    return {
        "transcript": "\n\n".join(passages),
        "words": words,
        "cues": cues,
        "srt": srt,
        "vtt": vtt,
        "word_timing_status": status,
        "word_timing_issues": issues,
        "caption_timing_adjustments": adjustments,
        "caption_timing_omissions": omissions,
    }


def run(
    args: argparse.Namespace,
    directory: Path,
    plan: dict,
    metadata: dict,
    script: str,
    expected_operation: str | list[str] | None = None,
) -> Path | None:
    """Caption every part. ``expected_operation`` (Studio Resume) lists the saved part
    operations to poll; Resume then reuses completed parts and never submits a part."""
    duration, audio_hash = plan["duration_seconds"], plan["audio_sha256"]
    episode = metadata.get("id") or "recording-" + audio_hash[:12]
    source = args.audio.resolve(strict=True)
    resume = None
    if expected_operation is not None:
        if (
            not isinstance(expected_operation, list)
            or not expected_operation
            or not all(isinstance(o, str) for o in expected_operation)
        ):
            raise ValueError(
                "The saved caption receipt is for one job, but this recording is captioned in "
                "parts. Resume will not create a new submission."
            )
        if not (directory / "parts" / "split.json").exists():
            raise ValueError(
                "The saved caption parts disappeared. Resume will not create a new submission."
            )
        resume = set(expected_operation)
    report(
        f"Caption existing recording: {duration / 60:.2f} minutes; longer than one caption "
        f"job, so it is split locally into parts of at most {PART_SECONDS // 60} minutes."
    )
    if args.dry_run:
        parts = split_parts(duration, silences(source))
        report(json.dumps({**plan, "parts": parts}, ensure_ascii=False, indent=2))
        report("Dry run only; nothing uploaded or submitted.")
        return None
    raise_if_stopped(args)
    directory.mkdir(parents=True, exist_ok=True)
    with run_lock(directory):
        parts = prepare_parts(source, audio_hash, duration, directory / "parts")
        report(
            f"{len(parts)} parts: "
            + ", ".join(f"{p['start']:.1f}–{p['end']:.1f} s ({p['cut']})" for p in parts),
            flush=True,
        )
        finished, pending = [], []
        states = {s["index"]: s for s in part_states(args, directory)["parts"]}
        if resume is not None and not resume <= {s["operation"] for s in states.values()}:
            raise ValueError(
                "The saved caption receipt changed or disappeared. Resume will not create a "
                "new submission."
            )
        for part in parts:
            raise_if_stopped(args)
            expected = None
            if resume is not None and states[part["index"]]["status"] != "complete":
                expected = states[part["index"]]["operation"]
                if expected not in resume:
                    raise ValueError(
                        f"Part {part['index']} has no saved operation in this Resume receipt. "
                        "Resume will not create a new submission."
                    )
            report(f"Part {part['index']} of {len(parts)}", flush=True)
            part_args = argparse.Namespace(
                **{
                    **vars(args),
                    "audio": directory / "parts" / f"part-{part['index']:02d}.mp3",
                    "script": None,
                }
            )
            # One ordinary caption job per part: its own receipt and spend-guard attempt.
            completed = captions.run(part_args, expected_operation=expected, episode=episode)
            if completed is None:
                pending.append(part["index"])
            finished.append(completed)
        if pending:
            report(
                f"Parts still transcribing: {', '.join(map(str, pending))}. Repeat the same "
                "command to resume; completed and submitted parts are not resubmitted."
            )
            return None
        results, receipts = [], []
        for part, part_directory in zip(parts, finished, strict=True):
            part_plan = read_object(part_directory / "plan.json")
            operation = read_object(part_directory / "operation.json")
            results.append(
                captions.extract_recognition(
                    operation, part_plan["audio_uri"], part_plan["duration_seconds"]
                )
            )
            receipts.append(
                {
                    "index": part["index"],
                    "start_seconds": part["start"],
                    "end_seconds": part["end"],
                    "cut": part["cut"],
                    "audio_sha256": part["sha256"],
                    "operation": operation["name"],
                }
            )
        recognized = join(parts, results, duration)
        joined_plan = {
            **{k: v for k, v in plan.items() if k not in {"audio_uri", "request"}},
            "parts": receipts,
        }
        write_json(directory / "plan.json", joined_plan)
        if not (directory / "audio.mp3").exists():
            shutil.copyfile(source, directory / "audio.mp3")
        aliases = [s["alias"] for s in metadata.get("speakers", [])]
        captions.write_result(
            directory,
            recognized,
            joined_plan,
            ", ".join(r["operation"] for r in receipts),
            script,
            aliases,
            extra={"parts": receipts},
        )
        # Studio adoption reads this; the part receipts stay in their own folders.
        write_json(
            directory / "state.json",
            {
                "status": "complete",
                "audio_sha256": audio_hash,
                "parts": [r["operation"] for r in receipts],
            },
        )
        return directory


def part_states(args: argparse.Namespace, directory: Path) -> dict:
    """Each part's saved caption state from ``parts/split.json``, and their overall status.

    Overall: any uncertain, failed or rejected part wins, then running, then not submitted;
    complete only when every part is complete.
    """
    manifest = read_object(directory / "parts" / "split.json")
    parts = []
    for part in manifest["parts"]:
        fingerprint = captions.caption_request(args, part["sha256"])[2]
        state_path = directory / "parts" / "captions" / fingerprint[:16] / "state.json"
        state = read_object(state_path) if state_path.exists() else {}
        parts.append(
            {
                "index": part["index"],
                "status": state.get("status", "not submitted"),
                "operation": state.get("operation"),
                "state": state_path,
            }
        )
    order = ("requesting", "uncertain", "failed", "rejected", "running", "not submitted")
    present = {p["status"] for p in parts}
    status = next((s for s in order if s in present), "complete")
    return {"status": status, "parts": parts}


def is_split(directory: Path) -> bool:
    return (directory / "parts" / "split.json").is_file()
