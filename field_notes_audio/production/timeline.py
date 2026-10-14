"""Retiming and readable caption pages for the derived listening edition."""

from __future__ import annotations

from field_notes_audio.site import caption_text


def retime(cues: list[dict], speed: float, intro: float, voice_duration: float) -> list[dict]:
    result = []
    for index, cue in enumerate(cues):
        start = cue["start"] / speed
        end = min(cue["end"] / speed, voice_duration)
        if start >= end:
            raise ValueError("A source caption falls outside the decoded narration")
        rounded_start, rounded_end = round(intro + start, 3), round(intro + end, 3)
        if rounded_start >= rounded_end:
            raise ValueError(f"Caption {index + 1} is shorter than subtitle millisecond precision")
        result.append({**cue, "start": rounded_start, "end": rounded_end})
    return result


def caption_pages(cues: list[dict], limit: int = 128) -> list[dict]:
    """Split long cues; intra-cue page boundaries are proportional, not word alignment."""
    result = []
    for cue in cues:
        words = caption_text(cue["text"]).split()
        chunks, chunk = [], []
        for word in words:
            if chunk and len(" ".join([*chunk, word])) > limit:
                chunks.append(chunk)
                chunk = []
            chunk.append(word)
        if chunk:
            chunks.append(chunk)
        consumed = 0
        for chunk in chunks:
            start = cue["start"] + (cue["end"] - cue["start"]) * consumed / len(words)
            consumed += len(chunk)
            end = cue["start"] + (cue["end"] - cue["start"]) * consumed / len(words)
            result.append({"start": start, "end": end, "text": " ".join(chunk)})
    return result
