"""FFmpeg finishing with measured narration and two-pass loudness normalization."""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
import threading
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


def stream_output(arguments: list[str], write, timeout: int = 600) -> None:
    """Drain encoded bytes into the parent writer with bounded memory and a deadline."""
    with (
        tempfile.TemporaryFile() as errors,
        subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-nostdin", *arguments, "pipe:1"],
            stdout=subprocess.PIPE,
            stderr=errors,
        ) as process,
    ):
        expired = threading.Event()

        def stop():
            expired.set()
            process.kill()

        timer = threading.Timer(timeout, stop)
        timer.start()
        try:
            while chunk := process.stdout.read(1024 * 1024):
                write(chunk)
            process.wait()
        except BaseException:
            process.kill()
            process.wait()
            raise
        finally:
            timer.cancel()
        if expired.is_set():
            raise subprocess.TimeoutExpired("FFmpeg production", timeout)
        if process.returncode:
            errors.seek(0)
            raise RuntimeError(
                "FFmpeg production failed: " + errors.read().decode(errors="replace")[-2000:]
            )


def pcm_output(arguments: list[str], path: Path) -> None:
    # Spool PCM first so the header contains its final frame count from the first
    # write. No output muxer needs to seek back and repair a provisional header.
    with tempfile.TemporaryFile(dir=path.parent) as pcm:
        stream_output([*arguments, "-ar", str(RATE), "-ac", "2", "-f", "s16le"], pcm.write)
        size = pcm.tell()
        if size % 4:
            raise ValueError("FFmpeg returned a partial stereo PCM frame")
        pcm.seek(0)
        with wave.open(str(path), "wb") as output:
            output.setparams((2, 2, RATE, size // 4, "NONE", "not compressed"))
            while chunk := pcm.read(1024 * 1024):
                output.writeframesraw(chunk)


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
        pcm_output(
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
            ],
            path,
        )


def finish_audio(source: Path, directory: Path, settings: dict) -> dict:
    voice = directory / "voice.wav"
    pcm_output(
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
        ],
        voice,
    )
    with wave.open(str(voice), "rb") as handle:
        voice_duration = handle.getnframes() / handle.getframerate()
    source_duration = probe_audio(source)
    if abs(voice_duration - source_duration / settings["speed"]) > 0.25:
        raise ValueError("Decoded narration duration disagrees with the source and requested pace")
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
    pcm_output(
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
        ],
        mix,
    )
    measured = loudness(mix, settings)
    target = f"I={settings['target_lufs']}:TP={settings['true_peak_db']}:LRA=11"
    normalize = (
        f"loudnorm={target}:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true:print_format=json"
    )
    master = directory / "master.wav"
    pcm_output(
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
        ],
        master,
    )
    output = directory / "episode.mp3"
    with output.open("wb") as handle:
        stream_output(
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
                "-write_xing",
                "0",
                "-f",
                "mp3",
            ],
            handle.write,
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
