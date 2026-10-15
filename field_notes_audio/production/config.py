"""Strict shared production settings with optional per-episode overrides."""

from __future__ import annotations

import math
from pathlib import Path

from field_notes_audio.storage import read_object


def number(value: object, low: float, high: float, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be a finite number between {low} and {high}")
    return float(value)


def load_settings(path: Path, episode: str) -> dict:
    config = read_object(path)
    if not isinstance(config.get("video"), dict):
        raise ValueError("video must be a settings object")
    override = path.parent / "episodes" / f"{episode}.json"
    if override.exists():
        changes = read_object(override)
        if changes.keys() - config.keys():
            raise ValueError("Unknown per-episode production setting")
        if "video" in changes and not isinstance(changes["video"], dict):
            raise ValueError("Per-episode video must be a settings object")
        config = {**config, **changes, "video": {**config["video"], **changes.get("video", {})}}
    return validate_settings(config, path.parent)


def validate_settings(config: dict, directory: Path) -> dict:
    """Validate a captured recipe using the same contract as file-backed settings."""
    required = {
        "schema_version",
        "speed",
        "intro_seconds",
        "outro_seconds",
        "music_overlap_seconds",
        "music_gain_db",
        "target_lufs",
        "true_peak_db",
        "music_mode",
        "music_file",
        "music_credit",
        "video",
    }
    if (
        config.keys() != required
        or type(config["schema_version"]) is not int
        or config["schema_version"] != 1
    ):
        raise ValueError(
            "Production settings require exactly the documented schema version 1 fields"
        )
    for name, low, high in (
        ("speed", 0.75, 1.5),
        ("intro_seconds", 0, 15),
        ("outro_seconds", 0, 15),
        ("music_overlap_seconds", 0, 3),
        ("music_gain_db", -40, 0),
        ("target_lufs", -24, -14),
        ("true_peak_db", -3, -1),
    ):
        config[name] = number(config[name], low, high, name)
    if not isinstance(config["music_mode"], str) or config["music_mode"] not in {
        "motif",
        "file",
        "none",
    }:
        raise ValueError("music_mode must be motif, file or none")
    if not isinstance(config["music_credit"], str) or len(config["music_credit"]) > 2000:
        raise ValueError("music_credit must be text of at most 2000 characters")
    if config["music_mode"] == "file":
        if not isinstance(config["music_file"], str) or not config["music_credit"].strip():
            raise ValueError(
                "Custom music needs music_file and music_credit (including its license)"
            )
        music = (directory / config["music_file"]).resolve()
        if not music.is_file():
            raise ValueError(f"Custom music file does not exist: {music}")
        config["music_file"] = str(music)
    elif config["music_file"] is not None:
        raise ValueError("music_file is only used with music_mode=file")
    video = config["video"]
    if not isinstance(video, dict) or video.keys() != {"width", "height", "fps", "concurrency"}:
        raise ValueError("video requires width, height, fps and concurrency")
    for key, low, high in (
        ("width", 640, 1920),
        ("height", 360, 1080),
        ("fps", 12, 30),
        ("concurrency", 1, 8),
    ):
        if type(video[key]) is not int or not low <= video[key] <= high:
            raise ValueError(f"video.{key} must be an integer between {low} and {high}")
    if video["width"] * 9 != video["height"] * 16 or video["width"] % 2 or video["height"] % 2:
        raise ValueError("Video dimensions must be even and use the 16:9 aspect ratio")
    return config


def audio_settings(settings: dict) -> dict:
    return {key: value for key, value in settings.items() if key != "video"}
