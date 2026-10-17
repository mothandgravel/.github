"""Named show recipes in the local journal; explicit apply and optimistic saves.

Applying a recipe copies a version into one episode draft. Library edits never
silently change other drafts, queued jobs, saved media or approvals.
"""

from __future__ import annotations

import copy
import re
import uuid

from field_notes_studio.readiness import recipe

KEY = "show-recipes"
NAMES = {
    "speed": "Pace ×",
    "intro_seconds": "Intro (seconds)",
    "outro_seconds": "Outro (seconds)",
    "music_overlap_seconds": "Music overlap (seconds)",
    "music_gain_db": "Music level (dB)",
    "target_lufs": "Loudness (LUFS)",
    "true_peak_db": "Peak ceiling (dB)",
    "music_mode": "Music mode",
    "music_file": "Custom music file",
    "music_credit": "Music credit and license",
    "video.width": "Video width",
    "video.height": "Video height",
    "video.fps": "Frame rate",
    "video.concurrency": "Video render threads",
}


def flatten(values, prefix=""):
    result = {}
    for key, value in values.items():
        name = prefix + key
        if isinstance(value, dict):
            result.update(flatten(value, name + "."))
        elif name != "schema_version":
            result[name] = value
    return result


def differences(baseline: dict, current: dict) -> tuple[str, ...]:
    before, after = flatten(baseline), flatten(current)
    return tuple(
        f"{NAMES.get(key, key)}: {before.get(key)} → {after.get(key)}"
        for key in sorted(before.keys() | after.keys())
        if before.get(key) != after.get(key)
    )


class Recipes:
    def __init__(self, repository, pipeline):
        self.repository, self.pipeline = repository, pipeline

    def load(self):
        data, identity = self.repository.state_snapshot(KEY)
        if not identity and data == {}:
            data = {"version": 1, "recipes": {}}
        if (
            not isinstance(data, dict)
            or set(data) != {"version", "recipes"}
            or type(data["version"]) is not int
            or data["version"] != 1
            or not isinstance(data["recipes"], dict)
        ):
            raise ValueError("Saved show settings are damaged; keep the journal and check it.")
        if len(data["recipes"]) > 100:
            raise ValueError("Too many saved show settings")
        names = set()
        for identifier, saved in data["recipes"].items():
            if (
                not re.fullmatch(r"[a-f0-9]{32}", identifier)
                or not isinstance(saved, dict)
                or set(saved) != {"name", "settings"}
            ):
                raise ValueError("Damaged saved show settings")
            name = self.name(saved["name"])
            if name.casefold() in names or not isinstance(saved["settings"], dict):
                raise ValueError("Duplicate or damaged saved show settings")
            names.add(name.casefold())
        return data, identity

    @staticmethod
    def name(value):
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > 60
            or len(value.splitlines()) > 1
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
        ):
            raise ValueError("The name must be one plain-text line of 1–60 characters")
        return value.strip()

    def save(self, name, settings, expected, identifier=None):
        name = self.name(name)
        validated = recipe(self.pipeline, settings)
        data, identity = self.load()
        if identity != expected:
            raise ValueError("Show settings changed in another window. Reload before saving.")
        if identifier is not None and identifier not in data["recipes"]:
            raise ValueError("The chosen show settings no longer exist")
        if any(
            other != identifier and item["name"].casefold() == name.casefold()
            for other, item in data["recipes"].items()
        ):
            raise ValueError(
                "Show settings with that name exist. Choose them and update them explicitly."
            )
        if identifier is None and len(data["recipes"]) >= 100:
            raise ValueError("The saved show settings list is full")
        identifier = identifier or uuid.uuid4().hex
        data["recipes"][identifier] = {"name": name, "settings": validated}
        identities = self.repository.checkpoint({KEY: data}, expected={KEY: expected})
        return {"id": identifier, "name": name, "settings": copy.deepcopy(validated)}, identities[
            KEY
        ]

    def select(self, identifier, expected):
        data, identity = self.load()
        if identity != expected or identifier not in data["recipes"]:
            raise ValueError("Show settings changed. Reload and check them before applying.")
        saved = data["recipes"][identifier]
        return {
            "id": identifier,
            "name": saved["name"],
            "settings": recipe(self.pipeline, saved["settings"]),
        }
