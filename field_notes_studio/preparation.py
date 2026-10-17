"""Read-only adapter for written notes and the existing offline narration planner.

No authentication, resource setup, synthesis, caption submission or site writes.
Preparation is deliberately independent of the recorded-episode production adapter.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from field_notes_studio.preparation_models import PreparationItem, PreparationSnapshot


class Preparation:
    def __init__(self, root: Path, planner=None):
        self.root = root.resolve()
        self._planner = planner

    def _path(self, relative: str) -> Path:
        path = self.root / relative
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Preparation files must remain inside this checkout")
        return path

    def _json(self, relative: str, kind, *, optional=False):
        path = self._path(relative)
        if optional and not path.exists():
            return kind()
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, kind):
            raise ValueError(f"{relative} must contain a JSON {kind.__name__}")
        return value

    @staticmethod
    def _unique(items: list, label: str) -> dict:
        result = {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise ValueError(f"Invalid {label} entry")
            identifier = item["id"]
            if identifier in result:
                raise ValueError(f"Duplicate {label} identifier: {identifier}")
            result[identifier] = item
        return result

    def _catalogs(self):
        notes = self._unique(self._json("docs/assets/notes.json", list), "note")
        episodes = self._unique(self._json("audio/episodes.json", list), "episode")
        recordings = self._unique(
            self._json("docs/assets/audio/episodes.json", list, optional=True), "recording"
        )
        return notes, episodes, recordings

    def _script(self, episode: dict) -> Path:
        relative = episode.get("script")
        if not isinstance(relative, str):
            raise ValueError("Episode has no script path")
        path = self._path("audio/" + relative)
        if not path.resolve().is_relative_to(self._path("audio/scripts").resolve()):
            raise ValueError("Script must live under audio/scripts/")
        return path

    def _item(self, note: dict, episodes: dict, recordings: dict) -> PreparationItem:
        identifier, slug = note["id"], note.get("slug", "")
        if (
            not re.fullmatch(r"\d{3,}", identifier)
            or not isinstance(slug, str)
            or not re.fullmatch(r"\d{3,}-[a-z0-9-]+\.html", slug)
            or slug.split("-", 1)[0] != identifier
            or not isinstance(note.get("title"), str)
        ):
            raise ValueError(f"Invalid written-note identity: {identifier}")
        # Join the explicit publication relationship, never the latest number or
        # an aggregate episode's source list. A workbench may cite many notes.
        matches = [
            entry
            for entry in episodes.values()
            if isinstance(entry.get("publication"), dict)
            and entry["publication"].get("kind") == "note"
            and entry["publication"].get("note_id") == identifier
        ]
        state, detail, episode = (
            "Needs script",
            "No dedicated episode is registered for this note.",
            "",
        )
        if len(matches) > 1:
            state, detail = (
                "Needs repair",
                "More than one episode claims this note; resolve the catalog conflict.",
            )
        elif matches:
            entry = matches[0]
            episode = entry["id"]
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", episode):
                raise ValueError("Invalid episode identifier")
            try:
                path = self._script(entry)
                if not path.is_file() or not path.stat().st_size:
                    detail = (
                        "The registered script is missing or empty. Restore it before checking."
                    )
                else:
                    state = "Check script"
                    detail = "Script saved; check its sources and narration request before anything is sent."
                    if episode in recordings:
                        state = "On production shelf"
                        detail = "Narration listed in this checkout's catalog; media and external publication are not verified here."
                    else:
                        detail += " No narrated note is listed on the shelf; unregistered local jobs may still exist."
            except (OSError, ValueError) as exc:
                state, detail = "Needs repair", str(exc)
        if not self._path("docs/notes/" + slug).is_file():
            state, detail = "Needs repair", "The written article is missing from this checkout."
        return PreparationItem(identifier, note["title"], slug, episode, state, detail)

    def catalog(self) -> list[PreparationItem]:
        notes, episodes, recordings = self._catalogs()
        return [self._item(note, episodes, recordings) for note in notes.values()]

    def _identity(self, item: PreparationItem, episode: dict) -> str:
        paths = {
            "docs/assets/notes.json",
            "audio/episodes.json",
            "docs/assets/audio/episodes.json",
            "artifacts/audio/settings.json",
            "docs/notes/" + item.slug,
        }
        # Aggregate sources must participate too, even though note discovery uses
        # only the primary publication relationship.
        notes = self._unique(self._json("docs/assets/notes.json", list), "note")
        for identifier in episode.get("notes", []):
            if identifier not in notes:
                raise ValueError(f"Source note {identifier} is absent from the written catalog")
            source = self._item(notes[identifier], {}, {})
            paths.add("docs/notes/" + source.slug)
        script = self._script(episode)
        paths.add(str(script.relative_to(self.root)))
        digest = hashlib.sha256()
        for relative in sorted(paths):
            path = self._path(relative)
            digest.update(relative.encode("utf-8") + b"\0")
            if path.exists():
                digest.update(b"present\0" + hashlib.sha256(path.read_bytes()).digest())
            else:
                digest.update(b"missing\0")
        return digest.hexdigest()

    def inspect(self, note_id: str) -> PreparationSnapshot:
        notes, episodes, recordings = self._catalogs()
        if note_id not in notes:
            raise ValueError("The written note changed or disappeared. Refresh preparation.")
        item = self._item(notes[note_id], episodes, recordings)
        if not item.episode or item.state in {"Needs script", "Needs repair"}:
            raise ValueError(item.detail)
        episode = episodes[item.episode]
        before = self._identity(item, episode)
        saved = self._json("artifacts/audio/settings.json", dict, optional=True)
        model = saved.get("model", "gemini-2.5-pro-tts")
        endpoint = saved.get("endpoint", "global")
        if self._planner is None:
            from field_notes_audio import audio

            if model not in audio.MODELS or endpoint not in audio.ENDPOINTS:
                raise ValueError("Invalid model or endpoint in saved narration settings")
            plan = audio.make_plan(item.episode, model, endpoint, self.root)
        else:
            plan = self._planner(item.episode, model, endpoint, self.root)
        after = self._identity(item, episode)
        current_notes, current_episodes, _ = self._catalogs()
        if (
            before != after
            or current_notes.get(note_id) != notes[note_id]
            or current_episodes.get(item.episode) != episode
        ):
            raise ValueError(
                "Sources or settings changed during the check. Refresh and check again."
            )
        summary = (
            f"{item.episode} · {item.title}\n"
            "Source fingerprints and script checked by the narration engine.\n"
            f"{plan['word_count']} words · approximately {plan['estimated_minutes']} minutes "
            f"at the {plan['target_wpm']} wpm planning pace.\n"
            f"{len(plan['requests'])} bounded narration requests · {model} · {endpoint}.\n\n"
            f"{item.detail}\n\n"
            "Before production: explicitly authorize narration, obtain and check captions, "
            "then add the narrated note to the shelf. Existing saved parts "
            "and remote caption jobs have not been checked in this pass.\n"
            "This check does not cover credentials, billing, Cloud resources or tool readiness. "
            "It does not generate audio, submit captions, approve media or publish anything.\n"
            "Cloud execution from this preparation panel is not enabled yet. "
            "No service request was made."
        )
        return PreparationSnapshot(
            note_id, item.episode, item.title, plan["script"], summary, before
        )
