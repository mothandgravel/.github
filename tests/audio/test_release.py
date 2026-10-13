"""Offline collection/release checks with real synthetic MP3s and mocked recognition."""

import argparse
import io
import json
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from field_notes_audio import audio as audio
from field_notes_audio import captions as captions
from field_notes_audio import release as release
from field_notes_audio import site as build_audio
from tests.audio.test_captions import operation

SOURCE_ROOT = audio.ROOT


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools unavailable")
class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        path = Path(cls.fixture.name) / "audio.mp3"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=330:duration=4",
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "libmp3lame",
                str(path),
            ],
            check=True,
        )
        cls.audio_bytes = path.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(SOURCE_ROOT / "audio", self.root / "audio")
        (self.root / "docs/assets/audio").mkdir(parents=True)
        (self.root / "docs/notes").mkdir(parents=True)
        for name in ("notes.json", "podcast-cover.png"):
            shutil.copy(SOURCE_ROOT / "docs/assets" / name, self.root / "docs/assets" / name)
        (self.root / "docs/assets/audio/episodes.json").write_text("[]\n")
        for source in (SOURCE_ROOT / "docs/notes").glob("*.html"):
            shutil.copy(source, self.root / "docs/notes" / source.name)
        self.patch = patch.object(audio, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.episodes = json.loads((self.root / "audio/episodes.json").read_text())

    def completed(self):
        completed = []
        for episode in self.episodes:
            plan = audio.make_plan(episode["id"], "gemini-2.5-pro-tts", "global", self.root)
            recording = self.root / "artifacts/audio" / episode["id"] / plan["fingerprint"][:16]
            directory = recording / "captions/fixture"
            directory.mkdir(parents=True)
            (recording / "episode.mp3").write_bytes(self.audio_bytes)
            (recording / "transcript.txt").write_text(plan["script"] + "\n")
            audio_hash = audio.digest(self.audio_bytes)
            audio.write_json(
                recording / "episode.json",
                {
                    "id": episode["id"],
                    "audio_sha256": audio_hash,
                    "script_sha256": plan["script_sha256"],
                    "source_sha256": episode["source_sha256"],
                },
            )
            uri = "gs://private-working-bucket/" + audio_hash + ".mp3"
            caption_plan = dict(
                audio_sha256=audio_hash,
                audio_uri=uri,
                duration_seconds=4.1,
                title=episode["title"],
                model="chirp_3",
                location="us",
                language="en-US",
            )
            with redirect_stdout(io.StringIO()):
                captions.export_result(
                    directory,
                    operation(uri),
                    caption_plan,
                    plan["script"],
                    [s["alias"] for s in episode["speakers"]],
                )
            completed.append((episode, directory))
        return completed

    def prepare(self):
        completed = self.completed()
        with redirect_stdout(io.StringIO()):
            entries = release.prepare_publication(completed)
        return entries, completed

    def test_all_notes_get_real_listen_labels_and_feed_enclosures(self):
        before = {
            n["id"]: audio.source_article(self.root, n) for n in audio.catalog(self.root).values()
        }
        entries, _ = self.prepare()
        self.assertEqual(len(entries), len(self.episodes))
        for note in audio.catalog(self.root).values():
            page = (self.root / "docs/notes" / note["slug"]).read_text()
            self.assertIn("Listen to this note · 1 min", page)
            self.assertIn("AI-narrated", page)
            self.assertIn("Hello world.", page)  # Recognized speech, not the input script.
            self.assertIn('value="1.15" selected', page)
            self.assertEqual(audio.source_article(self.root, note), before[note["id"]])
        rss = ET.parse(self.root / "docs/notes/podcast.xml")
        items = rss.findall("./channel/item")
        self.assertEqual(len(items), len(self.episodes))
        self.assertEqual(len({item.findtext("guid") for item in items}), len(self.episodes))
        by_title = {e["title"]: e for e in entries}
        for item in items:
            e = by_title[item.findtext("title")]
            self.assertEqual(int(item.find("enclosure").get("length")), len(self.audio_bytes))
            self.assertEqual(item.find("enclosure").get("type"), "audio/mpeg")
            self.assertEqual(
                item.find("enclosure").get("url"), build_audio.DOMAIN + "/" + e["audio"]
            )
            self.assertEqual(len(item.findall(f"{{{build_audio.NS['podcast']}}}transcript")), 2)
        build_audio.build(check=True, root=self.root)
        archive = (self.root / "docs/notes/index.html").read_text()
        self.assertIn("Listen through the archive", archive)
        self.assertIn("Subscribe to the podcast", archive)
        self.assertEqual(archive.count("data-queue-index="), len(self.episodes))
        self.assertTrue(all(e["review_status"] == "pending" for e in entries))

    def test_missing_recording_prevents_partial_collection_publication(self):
        completed = self.completed()[1:]
        with (
            self.assertRaisesRegex(ValueError, "Every published note"),
            redirect_stdout(io.StringIO()),
        ):
            release.prepare_publication(completed)
        self.assertEqual(
            json.loads((self.root / "docs/assets/audio/episodes.json").read_text()), []
        )
        self.assertFalse(list((self.root / "docs/assets/audio").glob("*.mp3")))

    def test_caption_and_recording_provenance_must_match(self):
        completed = self.completed()
        (completed[0][1].parent.parent / "episode.mp3").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "provenance disagree"):
            release.prepare_publication(completed)
        self.assertEqual(
            json.loads((self.root / "docs/assets/audio/episodes.json").read_text()), []
        )

    def test_changed_caption_file_blocks_publication(self):
        completed = self.completed()
        (completed[0][1] / "captions.vtt").write_text("Different subtitles")
        with self.assertRaisesRegex(ValueError, "caption file changed"):
            release.prepare_publication(completed)

    def test_changed_source_is_never_published_against_old_audio(self):
        completed = self.completed()
        path = self.root / "docs/notes/001-curiosity-with-calluses.html"
        path.write_text(
            path.read_text().replace("Resistance tells you", "A changed source tells you")
        )
        with self.assertRaisesRegex(ValueError, "source note changed"):
            release.prepare_publication(completed)

    def test_public_media_tampering_and_invented_duration_fail_site_checks(self):
        entries, _ = self.prepare()
        path = build_audio.media_path(self.root, entries[0]["audio"])
        path.write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError, "Published MP3 changed"):
            build_audio.load_entries(self.root)
        path.write_bytes(self.audio_bytes)
        entries[0]["duration_seconds"] = 240
        audio.write_json(self.root / "docs/assets/audio/episodes.json", entries)
        with self.assertRaisesRegex(ValueError, "actual recording"):
            build_audio.load_entries(self.root)

    def test_repeated_preparation_keeps_guids_publication_dates_and_assets(self):
        entries, completed = self.prepare()
        first = (self.root / "docs/notes/podcast.xml").read_bytes()
        with redirect_stdout(io.StringIO()):
            repeated = release.prepare_publication(completed)
        self.assertEqual(entries, repeated)
        self.assertEqual(first, (self.root / "docs/notes/podcast.xml").read_bytes())
        self.assertNotIn("settings.json", json.dumps(release.release_state()))
        self.assertNotIn("operation.json", json.dumps(release.release_state()))

    def test_empty_manifest_does_not_advertise_nonexistent_audio(self):
        build_audio.build(root=self.root)
        page = (self.root / "docs/notes/index.html").read_text()
        self.assertNotIn("Listen through the archive", page)
        self.assertNotIn("Subscribe to the podcast", page)
        self.assertEqual(
            ET.parse(self.root / "docs/notes/podcast.xml").findall("./channel/item"), []
        )

    def test_paths_cannot_escape_public_media_directory(self):
        for path in [
            "../private-file.txt",
            "https://other.example/audio.mp3",
            "assets/audio/../settings.json",
        ]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                build_audio.media_path(self.root, path)

    def test_note_002_includes_every_prose_block_and_measurement_section(self):
        note = audio.catalog(self.root)["002"]
        body = audio.source_article(self.root, note)
        self.assertIn("The atmosphere isn't precious", body)
        self.assertIn("15.25", body)
        self.assertIn("Brass is a signal", body)
        script = (self.root / "audio/scripts/note-002.txt").read_text()
        self.assertIn("What remains to be proven", script)
        self.assertIn("15.25", script)
        self.assertNotIn("DESIGN DECISIONS", script)  # Sidebar decoration.

    def test_sync_adds_new_published_notes_without_replacing_existing_scripts(self):
        notes_path = self.root / "docs/assets/notes.json"
        notes = json.loads(notes_path.read_text())
        new_id = f"{max(int(n['id']) for n in notes) + 1:03d}"
        notes.append(
            {
                "id": new_id,
                "slug": new_id + "-new-study.html",
                "title": "A new study.",
                "summary": "A study.",
            }
        )
        audio.write_json(notes_path, notes)
        (self.root / "docs/notes" / (new_id + "-new-study.html")).write_text(
            '<article class="note-prose"><h2>A new question.</h2><p>Keep every word and its limits.</p></article>'
        )
        original = (self.root / "audio/scripts/note-001.txt").read_bytes()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(release.sync_catalog(), ["note-" + new_id])
            self.assertEqual(release.sync_catalog(), [])
        self.assertIn(
            "Keep every word and its limits.",
            (self.root / "audio/scripts" / ("note-" + new_id + ".txt")).read_text(),
        )
        self.assertEqual((self.root / "audio/scripts/note-001.txt").read_bytes(), original)
        audio.load_episode("note-" + new_id, self.root)

    def test_script_candidate_keeps_study_limits_and_omits_context_sidebar(self):
        note = audio.catalog(self.root)["008"]
        path = self.root / "docs/notes" / note["slug"]
        path.write_text(
            '<article class="note-prose"><p>A possible repair.</p>'
            '<aside class="note-aside"><p>DECORATIVE CONTEXT</p></aside>'
            '<aside class="native-study-status"><h2>Study scope</h2>'
            "<p>No native session or player study was run.</p></aside>"
            "<p>The observation remains to be done.</p></article>"
        )
        _, script = release.script_candidate(self.root, note)
        self.assertIn("No native session or player study was run.", script)
        self.assertIn("The observation remains to be done.", script)
        self.assertNotIn("DECORATIVE CONTEXT", script)

    def test_sync_does_not_accept_changed_source_for_an_existing_recording(self):
        note = audio.catalog(self.root)["001"]
        path = self.root / "docs/notes" / note["slug"]
        path.write_text(
            path.read_text().replace(
                '<article class="note-prose">',
                '<article class="note-prose"><p>A revised published claim.</p>',
                1,
            )
        )
        original = (self.root / "audio/scripts/note-001.txt").read_bytes()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(release.sync_catalog(), [])
        self.assertEqual((self.root / "audio/scripts/note-001.txt").read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "Note 001 changed"):
            audio.load_episode("note-001", self.root)

    def test_batch_pending_job_preserves_progress_and_does_not_publish(self):
        args = argparse.Namespace(
            command="make-all",
            project="audio-pilot-project",
            bucket="private-bucket",
            model="gemini-2.5-pro-tts",
            endpoint="global",
            location="us",
            auth="gcloud",
            wait=0,
            retry_uncertain=False,
            restart_failed=False,
            publish=False,
            dry_run=False,
        )
        with (
            patch.object(release.workflow, "ensure_setup"),
            patch.object(
                release.workflow,
                "make",
                side_effect=[None] + [self.root] * (len(self.episodes) - 1),
            ) as make,
            patch.object(release, "prepare_publication") as prepare,
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaisesRegex(RuntimeError, "collection is incomplete"):
                release.make_all(args)
            self.assertEqual(make.call_count, len(self.episodes))
            prepare.assert_not_called()

    def test_publication_blocks_unrelated_changes_and_never_pushes_main(self):
        self.prepare()
        installed = shutil.which
        with patch.object(release, "dirty_paths", return_value=["README.md"]):
            with self.assertRaisesRegex(ValueError, "existing changes"):
                release.assert_clean_or_prepared()
        with (
            patch.object(release, "dirty_paths", return_value=[]),
            patch.object(release, "publication_remote", return_value=("origin", "main")),
            patch.object(release, "git", return_value="") as git,
            patch.object(
                release.shutil,
                "which",
                side_effect=lambda name: None if name == "gh" else installed(name),
            ),
            redirect_stdout(io.StringIO()),
        ):
            release.publish()
        pushes = [call.args[0] for call in git.call_args_list if call.args[0][0] == "push"]
        self.assertEqual(len(pushes), 1)
        self.assertIn("HEAD:refs/heads/studio/field-notes-listening-", pushes[0][-1])
        self.assertNotEqual(pushes[0][-1], "HEAD:refs/heads/main")

    def test_git_status_preserves_leading_status_columns(self):
        result = SimpleNamespace(
            returncode=0,
            stdout=" M docs/notes/index.html\0?? docs/assets/audio/new.mp3\0",
            stderr="",
        )
        with patch.object(release.subprocess, "run", return_value=result):
            self.assertEqual(
                release.dirty_paths(), ["docs/notes/index.html", "docs/assets/audio/new.mp3"]
            )

    def test_new_note_batch_can_resume_after_sync_without_publishing_old_collection(self):
        path = self.root / "docs/assets/notes.json"
        notes = json.loads(path.read_text())
        new_id = f"{max(int(n['id']) for n in notes) + 1:03d}"
        notes.append(
            {
                "id": new_id,
                "slug": new_id + "-new-study.html",
                "title": "A new study.",
                "summary": "A study.",
            }
        )
        audio.write_json(path, notes)
        (self.root / "docs/notes" / (new_id + "-new-study.html")).write_text(
            '<article class="note-prose"><p>The next study preserves its questions.</p></article>'
        )
        args = argparse.Namespace(
            command="make-all",
            project="audio-pilot-project",
            bucket="private-bucket",
            model="gemini-2.5-pro-tts",
            endpoint="global",
            location="us",
            auth="gcloud",
            wait=0,
            retry_uncertain=False,
            restart_failed=False,
            publish=True,
            dry_run=False,
        )
        with (
            patch.object(release, "publication_remote", return_value=("origin", "studio/audio")),
            patch.object(release, "dirty_paths", return_value=[]),
            patch.object(release.workflow, "ensure_setup"),
            patch.object(release.workflow, "make", return_value=None),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaisesRegex(RuntimeError, "collection is incomplete"):
                release.make_all(args)
        self.assertEqual(release.release_state()["phase"], "generating")
        with patch.object(
            release,
            "dirty_paths",
            return_value=["audio/episodes.json", "audio/scripts/note-" + new_id + ".txt"],
        ):
            release.assert_clean_or_prepared()
            with self.assertRaisesRegex(ValueError, "No prepared release"):
                release.publish()

    def test_caption_formatting_is_readable_without_rewriting_native_subtitles(self):
        self.assertEqual(build_audio.caption_text("Moth &amp; <b>Gravel</b>"), "Moth & Gravel")
        self.assertEqual(build_audio.caption_text("<v Speaker 1>Hello world.</v>"), "Hello world.")

    def test_live_verifier_checks_real_feed_enclosures_and_byte_ranges(self):
        entries, _ = self.prepare()
        feed = (self.root / "docs/notes/podcast.xml").read_bytes()
        from email.message import Message

        class Response:
            def __init__(self, data=b"", status=200, size=None, ranged=False):
                self.data, self.status = data, status
                self.headers = Message()
                if size is not None:
                    self.headers["Content-Length"] = str(size)
                    self.headers["Content-Type"] = "audio/mpeg"
                if ranged:
                    self.headers["Content-Range"] = f"bytes 0-0/{size}"

            def read(self, count):
                return self.data[:count]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def fetch(value, timeout):
            if isinstance(value, str):
                return Response(feed)
            if value.has_header("Range"):
                return Response(self.audio_bytes[:1], 206, len(self.audio_bytes), True)
            return Response(size=len(self.audio_bytes))

        with (
            patch.object(release.request, "urlopen", side_effect=fetch) as network,
            redirect_stdout(io.StringIO()),
        ):
            release.verify_live()
        ranges = [
            call.args[0]
            for call in network.call_args_list
            if not isinstance(call.args[0], str) and call.args[0].has_header("Range")
        ]
        self.assertEqual(len(ranges), len(entries))

        def no_ranges(value, timeout):
            if not isinstance(value, str) and value.has_header("Range"):
                return Response(self.audio_bytes[:1], 200, len(self.audio_bytes))
            return fetch(value, timeout)

        with (
            patch.object(release.request, "urlopen", side_effect=no_ranges),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaisesRegex(ValueError, "byte-range"):
                release.verify_live()


def browser_fixture(destination):
    """Real HTML, synthetic media. Kept under ignored artifacts, never published."""
    destination = Path(destination).resolve()
    if not destination.is_relative_to((SOURCE_ROOT / "artifacts").resolve()):
        raise ValueError("Browser fixtures must stay under artifacts/")
    ReleaseTests.setUpClass()
    case = ReleaseTests()
    try:
        case.setUp()
        shutil.copytree(SOURCE_ROOT / "docs", case.root / "docs", dirs_exist_ok=True)
        release.sync_catalog()
        case.episodes = json.loads((case.root / "audio/episodes.json").read_text())
        case.prepare()
        shutil.copytree(case.root / "docs", destination, dirs_exist_ok=True)
        print(f"Synthetic listening fixture: {destination}")
    finally:
        case.doCleanups()
        ReleaseTests.tearDownClass()


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 3 and sys.argv[1] == "--browser-fixture":
        browser_fixture(sys.argv[2])
    else:
        unittest.main()
