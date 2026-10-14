"""FFmpeg finishing with measured narration and two-pass loudness normalization."""

from __future__ import annotations

import json
import math
import subprocess
import wave
from pathlib import Path

from field_notes_audio.captions import probe_audio
from field_notes_audio.production.sound import RATE, write_motif


def ffmpeg(arguments: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-y", *arguments],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError("FFmpeg production failed: " + result.stderr[-2000:])
    return result


def loudness(path: Path, settings: dict) -> dict:
    target = f"I={settings['target_lufs']}:TP={settings['true_peak_db']}:LRA=11"
    result = ffmpeg(
        ["-i", str(path), "-af", f"loudnorm={target}:print_format=json", "-f", "null", "-"]
    )
    # FFmpeg can print its final progress/size line after the JSON report.
    # Decode one object, without treating those log lines as JSON data.
    offset = result.stderr.rfind("{")
    if offset < 0:
        raise ValueError("FFmpeg did not return a loudness measurement report")
    report, _ = json.JSONDecoder().raw_decode(result.stderr[offset:])
    for key in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"):
        if not math.isfinite(float(report[key])):
            raise ValueError("Cannot normalize silent or invalid audio")
    return report


def music_clip(path: Path, seconds: float, settings: dict, closing: bool) -> None:
    if settings["music_mode"] == "motif":
        write_motif(path, seconds, closing)
    else:
        # Loop short user-selected material and give both edges a gentle envelope.
        ffmpeg(
            [
                "-stream_loop",
                "-1",
                "-i",
                settings["music_file"],
                "-t",
                str(seconds),
                "-af",
                f"afade=t=in:d=0.08,afade=t=out:st={max(0, seconds - 1.5)}:d={min(1.5, seconds)}",
                "-ar",
                str(RATE),
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                str(path),
            ]
        )


def finish_audio(source: Path, directory: Path, settings: dict) -> dict:
    voice = directory / "voice.wav"
    ffmpeg(
        [
            "-v",
            "error",
            "-i",
            str(source),
            "-af",
            f"atempo={settings['speed']}",
            "-ar",
            str(RATE),
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(voice),
        ]
    )
    with wave.open(str(voice), "rb") as handle:
        voice_duration = handle.getnframes() / handle.getframerate()
    intro = settings["intro_seconds"]
    outro = settings["outro_seconds"]
    total = intro + voice_duration + outro
    if total > 1200:
        raise ValueError("Finished editions must remain within the 20-minute collection limit")
    inputs = ["-i", str(voice)]
    delay = round(intro * 1000)
    filters = [f"[0:a]adelay={delay}:all=1,apad,atrim=duration={total}[voice]"]
    branches = []
    if settings["music_mode"] != "none":
        for name, seconds, start, closing in (
            ("intro", intro + settings["music_overlap_seconds"], 0, False),
            ("outro", outro, intro + voice_duration, True),
        ):
            if seconds <= 0:
                continue
            file = directory / f"{name}.wav"
            music_clip(file, seconds, settings, closing)
            index = len(inputs) // 2
            inputs.extend(["-i", str(file)])
            filters.append(
                f"[{index}:a]volume={settings['music_gain_db']}dB,"
                f"adelay={round(start * 1000)}:all=1,apad,atrim=duration={total}[{name}]"
            )
            branches.append(f"[{name}]")
    if branches:
        filters.extend(
            [
                "[voice]asplit=2[main][side]",
                f"{''.join(branches)}amix=inputs={len(branches)}:normalize=0[music]",
                "[music][side]sidechaincompress=threshold=0.025:ratio=8:attack=15:release=350[ducked]",
                "[main][ducked]amix=inputs=2:normalize=0[out]",
            ]
        )
    else:
        filters.append("[voice]anull[out]")
    mix = directory / "mix.wav"
    ffmpeg(
        [
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-t",
            str(total),
            "-c:a",
            "pcm_s16le",
            str(mix),
        ]
    )
    measured = loudness(mix, settings)
    target = f"I={settings['target_lufs']}:TP={settings['true_peak_db']}:LRA=11"
    normalize = (
        f"loudnorm={target}:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true:print_format=json"
    )
    master = directory / "master.wav"
    ffmpeg(
        [
            "-i",
            str(mix),
            "-af",
            normalize,
            "-ar",
            str(RATE),
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(master),
        ]
    )
    output = directory / "episode.mp3"
    ffmpeg(
        [
            "-v",
            "error",
            "-i",
            str(master),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            "-ar",
            str(RATE),
            str(output),
        ]
    )
    final_measurement = loudness(output, settings)
    if abs(float(final_measurement["input_i"]) - settings["target_lufs"]) > 1:
        raise ValueError("Finished loudness differs by more than 1 LU from the production target")
    if float(final_measurement["input_tp"]) > -0.5:
        raise ValueError("Encoded audio has insufficient true-peak headroom")
    with wave.open(str(master), "rb") as handle:
        master_duration = handle.getnframes() / handle.getframerate()
    encoded_duration = probe_audio(output)
    if abs(master_duration - total) > 0.05 or abs(encoded_duration - total) > 0.15:
        raise ValueError(
            f"Finished audio lost its intended duration: timeline={total:.3f}s, "
            f"master={master_duration:.3f}s, MP3={encoded_duration:.3f}s"
        )
    for name in ("voice.wav", "mix.wav", "intro.wav", "outro.wav"):
        (directory / name).unlink(missing_ok=True)
    return {
        "voice_duration_seconds": voice_duration,
        "timeline_duration_seconds": total,
        "master_duration_seconds": master_duration,
        "duration_seconds": encoded_duration,
        "loudness": final_measurement,
    }
