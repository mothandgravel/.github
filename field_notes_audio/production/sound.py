"""A small deterministic plucked/metallic motif rendered directly to PCM."""

from __future__ import annotations

import math
import struct
import threading
import wave
from functools import lru_cache
from pathlib import Path

RATE = 48000
_MOTIF_LOCK = threading.Lock()


def write_motif(path: Path, duration: float, closing: bool = False) -> None:
    """Original synthesis recipe, no downloaded music or generative service."""
    # Batch workers share at most eight immutable clips (under 28 MiB). Serialize
    # cache misses so two workers never synthesize the same bookend concurrently.
    with _MOTIF_LOCK:
        pcm = _motif_pcm(duration, closing)
    with wave.open(str(path), "wb") as output:
        output.setparams((2, 2, RATE, len(pcm) // 4, "NONE", "not compressed"))
        output.writeframesraw(pcm)


@lru_cache(maxsize=8)
def _motif_pcm(duration: float, closing: bool) -> bytes:
    if not math.isfinite(duration) or not 0 < duration <= 18:
        raise ValueError("Motif duration must be positive and at most 18 seconds")
    notes = [(0.08, 220.0, 0.28), (0.55, 329.63, 0.19), (1.18, 293.66, 0.15)]
    if closing:
        notes = [(0.08, 293.66, 0.18), (0.65, 329.63, 0.14), (1.3, 220.0, 0.25)]
    count = round(duration * RATE)
    buffer = bytearray(count * 4)
    for index in range(count):
        t = index / RATE
        fade = min(1, t / 0.04, max(0, (duration - t) / min(1.5, duration)))
        left = right = 0.0
        for onset, frequency, gain in notes:
            elapsed = t - onset
            if elapsed >= 0:
                envelope = (1 - math.exp(-elapsed * 100)) * math.exp(-elapsed * 1.65)
                phase = 2 * math.pi * frequency * elapsed
                base = math.sin(phase)
                left += gain * envelope * (base + 0.22 * math.sin(phase * 2.01))
                right += gain * envelope * (base + 0.22 * math.sin(phase * 2.01 + 0.12))
        struct.pack_into(
            "<hh",
            buffer,
            index * 4,
            round(max(-1, min(1, left * fade)) * 32767),
            round(max(-1, min(1, right * fade)) * 32767),
        )
    return bytes(buffer)
