"""Audit reproductions for release trust boundaries and cross-command recovery."""

import copy
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from field_notes_audio import audio, release, site
from field_notes_audio.production import packages, promotion
from field_notes_audio.storage import digest_file, read_object, write_json
from tests.audio import test_production_release as fixtures


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.PublishingTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        fixtures.PublishingTests.tearDownClass()

    def setUp(self):
        self.case = fixtures.PublishingTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_upload_self_consistent_modified_hashes_cannot_override_authoritative_copy(self):
        c = self.case
        packages.export(c.args, c.root)
        path = c.upload / "title.txt"
        path.write_text("Wrong title\n")
        saved = read_object(c.upload / "upload.json")
        saved["files"]["title.txt"] = digest_file(path)
        write_json(c.upload / "upload.json", saved)
        packages.export(c.args, c.root)
        self.assertEqual(path.read_text().strip(), c.entry["title"])

    def test_cached_upload_cannot_claim_a_different_review_state(self):
        c = self.case
        packages.export(c.args, c.root)
        saved = read_object(c.upload / "upload.json")
        saved["review_status"] = "approved"
        saved["default_playback_rate"] = 1.15
        write_json(c.upload / "upload.json", saved)
        packages.export(c.args, c.root)
        fixed = read_object(c.upload / "upload.json")
        self.assertEqual(fixed["review_status"], "pending")
        self.assertEqual(fixed["default_playback_rate"], 1)

    def test_unexpected_files_and_symlinks_survive_export_preflight_rejection(self):
        c = self.case
        packages.export(c.args, c.root)
        extra = c.upload / "keep-me.txt"
        extra.write_text("user work")
        config = read_object(c.config)
        config["episodes"]["note-001"]["title"] = "Changed title"
        write_json(c.config, config)
        with self.assertRaisesRegex(ValueError, "unexpected"):
            packages.export(c.args, c.root)
        self.assertEqual(extra.read_text(), "user work")
        extra.unlink()
        title = c.upload / "title.txt"
        title.unlink()
        title.symlink_to(c.finished / "description.txt")
        with self.assertRaisesRegex(ValueError, "unexpected"):
            packages.export(c.args, c.root)
        self.assertTrue(title.is_symlink())

    def test_malformed_inventory_fails_before_changing_any_package(self):
        c = self.case
        packages.export(c.args, c.root)
        before = (c.upload / "title.txt").read_bytes()
        config = read_object(c.config)
        config["episodes"]["note-001"]["title"] = "New title"
        write_json(c.config, config)
        write_json(c.upload.parent / "index.json", {"schema_version": 1, "episodes": [None]})
        with self.assertRaisesRegex(ValueError, "inventory"):
            packages.export(c.args, c.root)
        self.assertEqual(before, (c.upload / "title.txt").read_bytes())

    def test_shortened_mp3_is_rejected_when_its_hash_is_updated(self):
        c = self.case
        short = c.finished / "short.mp3"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(c.finished / "episode.mp3"),
                "-t",
                "1",
                "-c",
                "copy",
                str(short),
            ],
            check=True,
        )
        short.replace(c.finished / "episode.mp3")
        state = read_object(c.finished / "production.json")
        state["files"]["episode.mp3"] = digest_file(c.finished / "episode.mp3")
        write_json(c.finished / "production.json", state)
        with self.assertRaisesRegex(ValueError, "MP3 duration"):
            packages.export(c.args, c.root)

    def test_corrupt_unused_video_does_not_block_reviewed_audio_promotion(self):
        c = self.case
        c.approve()
        (c.video / "episode.mp4").unlink()
        promotion.promote(c.args, c.root)
        self.assertEqual(site.load_entries(c.root)[0]["review_status"], "approved")
        c.args.audio_only = True
        packages.review(c.args, c.root)
        with self.assertRaises(ValueError):
            packages.export(c.args, c.root)

    def test_original_repreparation_retains_finished_assets_and_release_classification(self):
        c = self.case
        c.approve()
        promotion.promote(c.args, c.root)
        completed = [
            (episode, c.root / directory.relative_to(c.seed)) for episode, directory in c.completed
        ]
        with patch.object(audio, "ROOT", c.root):
            release.prepare_publication(completed)
        entry = site.load_entries(c.root)[0]
        journal = read_object(c.root / "artifacts/audio/release.json")
        self.assertEqual(journal["edition"], "finished")
        for field in ("audio", "srt", "vtt", "transcript", "cues"):
            self.assertEqual(
                journal["files"]["docs/" + entry[field]],
                digest_file(site.media_path(c.root, entry[field])),
            )

    def test_changed_source_captions_require_new_finished_review(self):
        c = self.case
        c.approve()
        promotion.promote(c.args, c.root)
        completed = [
            (episode, c.root / directory.relative_to(c.seed)) for episode, directory in c.completed
        ]
        directory = completed[0][1]
        metadata = read_object(directory / "captions.json")
        for name in ("captions.srt", "captions.vtt", "transcript.txt", "cues.json"):
            path = directory / name
            path.write_text(path.read_text().replace("Hello world.", "Corrected words."))
            metadata["files"][name] = digest_file(path)
        write_json(directory / "captions.json", metadata)
        with patch.object(audio, "ROOT", c.root):
            release.prepare_publication(completed)
        entry = site.load_entries(c.root)[0]
        self.assertNotIn("production", entry)
        self.assertEqual(entry["review_status"], "pending")

    def test_utf8_description_byte_limit_and_show_title_validation(self):
        c = self.case
        base = read_object(c.config)
        for change in ("description", "show"):
            value = copy.deepcopy(base)
            if change == "description":
                value["episodes"]["note-001"]["description"] = "界" * 2000
            else:
                value["show"]["title"] = "<Invalid show>"
            write_json(c.config, value)
            with self.assertRaises(ValueError):
                packages.export(c.args, c.root)
            self.assertFalse(c.upload.exists())

    def test_abrupt_promotion_exit_recovers_all_public_files_before_next_command(self):
        c = self.case
        c.approve()
        before = {
            p.relative_to(c.root): p.read_bytes()
            for p in (c.root / "docs").rglob("*")
            if p.is_file()
        }
        code = """import argparse, os, sys
from pathlib import Path
from field_notes_audio.production import promotion
from field_notes_audio.transactions import FileTransaction
root = Path(sys.argv[1])
install = FileTransaction._install
def crash(self, target, source):
 install(self, target, source)
 if target == root / 'docs/assets/audio/episodes.json': os._exit(19)
FileTransaction._install = crash
promotion.promote(argparse.Namespace(episode='note-001', output_dir=None), root)
"""
        result = subprocess.run([sys.executable, "-c", code, str(c.root)], check=False)
        self.assertEqual(result.returncode, 19)
        with release.collection_lock(c.root):
            pass
        after = {
            p.relative_to(c.root): p.read_bytes()
            for p in (c.root / "docs").rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)
        site.build(check=True, root=c.root)

    def test_bad_state_shapes_fail_with_actionable_validation_error(self):
        c = self.case
        state = read_object(c.finished / "production.json")
        state["settings"]["music_mode"] = []
        write_json(c.finished / "production.json", state)
        with self.assertRaisesRegex(ValueError, "settings"):
            packages.export(c.args, c.root)

    def test_public_finished_audio_requires_a_valid_review_timestamp(self):
        c = self.case
        c.approve()
        promotion.promote(c.args, c.root)
        manifest = c.root / "docs/assets/audio/episodes.json"
        entries = json.loads(manifest.read_text())
        entries[0]["production"]["review"]["reviewed_at"] = "not a date"
        manifest.write_text(json.dumps(entries))
        with self.assertRaisesRegex(ValueError, "review timestamp"):
            site.load_entries(c.root)

    def test_video_frame_rate_must_match_its_render_metadata(self):
        c = self.case
        rendered = read_object(c.video / "render.json")
        import math

        rendered["fps"] = 24
        rendered["frames"] = math.ceil(
            read_object(c.finished / "production.json")["timeline_duration_seconds"] * 24
        )
        write_json(c.video / "render.json", rendered)
        state = read_object(c.video / "production.json")
        state["files"]["render.json"] = digest_file(c.video / "render.json")
        write_json(c.video / "production.json", state)
        with self.assertRaisesRegex(ValueError, "complete"):
            packages.export(c.args, c.root)
