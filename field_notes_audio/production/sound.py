"""A small deterministic plucked/metallic motif rendered directly to PCM."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RATE = 48000


def write_motif(path: Path, duration: float, closing: bool = False) -> None:
    """Original synthesis recipe, no downloaded music or generative service."""
    notes = [(0.08, 220.0, 0.28), (0.55, 329.63, 0.19), (1.18, 293.66, 0.15)]
    if closing:
        notes = [(0.08, 293.66, 0.18), (0.65, 329.63, 0.14), (1.3, 220.0, 0.25)]
    count = round(duration * RATE)
    with wave.open(str(path), "wb") as output:
        output.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
        for offset in range(0, count, 4096):
            buffer = bytearray()
            for index in range(offset, min(count, offset + 4096)):
                t = index / RATE
                fade = min(1, t / 0.04, max(0, (duration - t) / min(1.5, duration)))
                channels = []
                for channel in (0, 1):
                    value = 0.0
                    for onset, frequency, gain in notes:
                        elapsed = t - onset
                        if elapsed >= 0:
                            envelope = (1 - math.exp(-elapsed * 100)) * math.exp(-elapsed * 1.65)
                            phase = 2 * math.pi * frequency * elapsed
                            tone = math.sin(phase) + 0.22 * math.sin(phase * 2.01 + channel * 0.12)
                            value += gain * envelope * tone
                    channels.append(round(max(-1, min(1, value * fade)) * 32767))
                buffer.extend(struct.pack("<hh", *channels))
            output.writeframesraw(buffer)
