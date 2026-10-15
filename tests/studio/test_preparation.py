"""Written-note discovery and offline inspection, including moved note numbers."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_studio.preparation import Preparation


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.notes = [
            {"id": "104", "title": "The work outlives the window.", "slug": "104-window.html"},
            {"id": "105", "title": "A newer note.", "slug": "105-newer.html"},
        ]
        self.episodes = [
            {
                "id": "studio-essay",
                "script": "scripts/studio.txt",
                "notes": ["104"],
                "publication": {"kind": "note", "note_id": "104"},
            },
            {
                "id": "workbench-001",
                "script": "scripts/workbench.txt",
                "notes": ["104", "105"],
                "publication": {"kind": "workbench"},
            },
        ]
        self.write("docs/assets/notes.json", self.notes)
        self.write("audio/episodes.json", self.episodes)
        self.write("docs/assets/audio/episodes.json", [])
        self.text("docs/notes/104-window.html", '<article class="note-prose">Window.</article>')
        self.text("docs/notes/105-newer.html", '<article class="note-prose">Newer.</article>')
        self.text("audio/scripts/studio.txt", "The saved narration.\n")
        self.service = Preparation(self.root, self.plan)

    def text(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write(self, relative, value):
        self.text(relative, json.dumps(value))

    def plan(self, identifier, model, endpoint, root):
        self.assertEqual(identifier, "studio-essay")
        self.assertEqual(root, self.root)
        return {
            "script": (root / "audio/scripts/studio.txt").read_text().strip(),
            "word_count": 3,
            "estimated_minutes": 0.02,
            "target_wpm": 140,
            "requests": [{"input": {"text": "The saved narration."}}],
        }

    def test_note_discovery_does_not_depend_on_number_or_episode_id_convention(self):
        items = self.service.catalog()
        self.assertEqual([item.note for item in items], ["104", "105"])
        self.assertEqual(items[0].episode, "studio-essay")
        self.assertEqual(items[0].state, "Inspect script")

    def test_aggregate_episode_does_not_hide_missing_dedicated_script(self):
        item = self.service.catalog()[1]
        self.assertEqual(item.state, "Needs script")
        self.assertEqual(item.episode, "")

    def test_missing_and_empty_scripts_are_visible(self):
        path = self.root / "audio/scripts/studio.txt"
        for state in ("missing", "empty"):
            with self.subTest(state=state):
                if state == "missing":
                    path.unlink()
                else:
                    path.write_text("")
                self.assertEqual(self.service.catalog()[0].state, "Needs script")
                with self.assertRaises(ValueError):
                    self.service.inspect("104")

    def test_catalog_recording_is_not_media_or_publication_approval(self):
        self.write("docs/assets/audio/episodes.json", [{"id": "studio-essay"}])
        item = self.service.catalog()[0]
        self.assertEqual(item.state, "On production shelf")
        self.assertIn("not verified", item.detail)

    def test_missing_recorded_catalog_does_not_hide_written_notes(self):
        (self.root / "docs/assets/audio/episodes.json").unlink()
        self.assertEqual(len(self.service.catalog()), 2)

    def test_duplicate_registration_is_visible_and_not_inspectable(self):
        self.episodes.append({**self.episodes[0], "id": "another-essay"})
        self.write("audio/episodes.json", self.episodes)
        self.assertEqual(self.service.catalog()[0].state, "Needs repair")
        with self.assertRaisesRegex(ValueError, "More than one"):
            self.service.inspect("104")

    def test_duplicate_ids_fail_without_silently_overwriting_an_entry(self):
        for path, entries in (
            ("docs/assets/notes.json", self.notes),
            ("audio/episodes.json", self.episodes),
        ):
            with self.subTest(path=path):
                self.write(path, [*entries, entries[0]])
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    self.service.catalog()
                self.write(path, entries)

    def test_missing_article_blocks_inspection(self):
        (self.root / "docs/notes/104-window.html").unlink()
        self.assertEqual(self.service.catalog()[0].state, "Needs repair")
        with self.assertRaisesRegex(ValueError, "article is missing"):
            self.service.inspect("104")

    def test_article_number_and_identity_must_match(self):
        self.notes[0]["slug"] = "013-window.html"
        self.write("docs/assets/notes.json", self.notes)
        with self.assertRaisesRegex(ValueError, "identity"):
            self.service.catalog()

    def test_script_escape_is_rejected_before_reading(self):
        self.episodes[0]["script"] = "../../outside.txt"
        self.write("audio/episodes.json", self.episodes)
        self.assertEqual(self.service.catalog()[0].state, "Needs repair")

    def test_external_script_symlink_is_rejected(self):
        path = self.root / "audio/scripts/studio.txt"
        path.unlink()
        path.symlink_to(self.root.parent / "outside.txt")
        self.assertEqual(self.service.catalog()[0].state, "Needs repair")

    def test_source_and_settings_changes_during_inspection_are_rejected(self):
        for relative, content in (
            ("docs/notes/104-window.html", "changed article"),
            ("artifacts/audio/settings.json", '{"endpoint":"eu"}'),
            ("audio/scripts/studio.txt", "changed script"),
            ("docs/assets/audio/episodes.json", '[{"id":"studio-essay"}]'),
        ):
            with self.subTest(path=relative):
                path = self.root / relative
                original = path.read_bytes() if path.exists() else None

                def changed(*args, relative=relative, content=content):
                    result = self.plan(*args)
                    self.text(relative, content)
                    return result

                with self.assertRaisesRegex(ValueError, "changed during inspection"):
                    Preparation(self.root, changed).inspect("104")
                if original is None:
                    path.unlink()
                else:
                    path.write_bytes(original)

    def test_existing_engine_rejection_is_not_bypassed(self):
        def stale(*_):
            raise ValueError("Note 104 changed. Review the script before refreshing its fingerprint.")

        with self.assertRaisesRegex(ValueError, "Review the script"):
            Preparation(self.root, stale).inspect("104")

    def test_inspection_has_no_network_process_or_file_write(self):
        before = {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in self.root.rglob("*")
            if p.is_file()
        }
        with patch("socket.socket", side_effect=AssertionError("network")), patch(
            "subprocess.Popen", side_effect=AssertionError("process")
        ):
            snapshot = self.service.inspect("104")
        after = {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in self.root.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual(snapshot.script, "The saved narration.")
        self.assertEqual(len(snapshot.identity), 64)
        self.assertIn("not enabled yet", snapshot.summary)
        self.assertIn("No service request", snapshot.summary)

    def test_disappeared_note_cannot_be_inspected(self):
        with self.assertRaisesRegex(ValueError, "disappeared"):
            self.service.inspect("013")

    def test_malformed_saved_settings_fail_without_secret_echo(self):
        self.write("artifacts/audio/settings.json", ["not-an-object"])
        with self.assertRaisesRegex(ValueError, "JSON dict"):
            self.service.inspect("104")

    def test_real_engine_rejects_stale_source_and_never_authenticates(self):
        from field_notes_audio import audio

        self.episodes[0].update(
            {
                "language": "en-US",
                "speakers": [{"alias": "Narrator", "voice": "Charon"}],
                "prompt": "Read exactly.",
                "source_sha256": {"104": "0" * 64},
                "target_wpm": 140,
            }
        )
        self.write("audio/episodes.json", self.episodes)
        with patch.object(audio, "access_token", side_effect=AssertionError("auth")), patch.object(
            audio, "synthesize", side_effect=AssertionError("synthesis")
        ):
            with self.assertRaisesRegex(ValueError, "Review the script"):
                Preparation(self.root).inspect("104")
            self.episodes[0]["source_sha256"]["104"] = audio.digest(
                audio.source_article(self.root, self.notes[0]).encode("utf-8")
            )
            self.write("audio/episodes.json", self.episodes)
            snapshot = Preparation(self.root).inspect("104")
            self.assertIn("1 bounded narration requests", snapshot.summary)
