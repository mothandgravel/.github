"""Derived-edition boundaries, retiming and real FFmpeg/cache behavior."""

import argparse
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_audio import audio, captions, cli
from field_notes_audio.production import runner
from field_notes_audio.production.config import load_settings
from field_notes_audio.production.mix import finish_audio
from field_notes_audio.production.timeline import caption_pages, retime
from field_notes_audio.production.video import visual_assets
from field_notes_audio.storage import digest_file, read_object, write_json

DEFAULTS = json.loads((audio.ROOT / "audio/production/settings.json").read_text())


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = self.root / "settings.json"
        write_json(self.config, DEFAULTS)

    def test_settings_merge_partial_video_override_and_resolve_music_from_shared_file(self):
        (self.root / "episodes").mkdir()
        music = self.root / "music.wav"
        music.write_bytes(b"fixture")
        write_json(
            self.root / "episodes/note-001.json",
            {
                "speed": 1,
                "music_mode": "file",
                "music_file": "music.wav",
                "music_credit": "Fixture / test license",
                "video": {"concurrency": 1},
            },
        )
        settings = load_settings(self.config, "note-001")
        self.assertEqual(settings["speed"], 1)
        self.assertEqual(settings["music_file"], str(music))
        self.assertEqual(settings["video"]["width"], 1920)
        self.assertEqual(settings["video"]["concurrency"], 1)

    def test_invalid_recipe_fails_before_processing(self):
        for field, value in (
            ("speed", True),
            ("speed", float("nan")),
            ("speed", 2),
            ("intro_seconds", -1),
            ("schema_version", True),
            ("music_mode", []),
            ("music_file", "unexpected.wav"),
            ("video", None),
            ("video", {**DEFAULTS["video"], "width": 1000}),
        ):
            with self.subTest(field=field, value=value):
                config = copy.deepcopy(DEFAULTS)
                config[field] = value
                write_json(self.config, config)
                with self.assertRaises(ValueError):
                    load_settings(self.config, "note-001")

    def test_unknown_override_and_invalid_video_object_are_rejected(self):
        (self.root / "episodes").mkdir()
        for override in ({"unknown": 1}, {"video": None}):
            write_json(self.root / "episodes/note-001.json", override)
            with self.assertRaises(ValueError):
                load_settings(self.config, "note-001")

    def test_subtitles_follow_baked_speed_and_intro_without_mutating_source(self):
        cues = [
            {"start": 1.15, "end": 2.3, "text": "One."},
            {"start": 3.45, "end": 5.0, "text": "Two."},
        ]
        original = copy.deepcopy(cues)
        shifted = retime(cues, 1.15, 4, 4)
        self.assertEqual((shifted[0]["start"], shifted[0]["end"]), (5, 6))
        self.assertEqual(shifted[1]["end"], 8)
        self.assertEqual(cues, original)
        for vtt in (False, True):
            self.assertEqual(
                captions.parse_captions(captions.render_captions(shifted, vtt), 9, vtt), shifted
            )
        with self.assertRaises(ValueError):
            retime([{"start": 10, "end": 11, "text": "Outside"}], 1, 0, 4)

    def test_caption_pages_preserve_words_and_cue_bounds(self):
        text = "A small question deserves room to remain readable. " * 12
        pages = caption_pages([{"start": 4, "end": 20, "text": text}])
        self.assertEqual(" ".join(p["text"] for p in pages), text.strip())
        self.assertEqual(pages[0]["start"], 4)
        self.assertEqual(pages[-1]["end"], 20)
        self.assertTrue(all(len(p["text"]) <= 128 for p in pages))
        self.assertTrue(all(a["end"] == b["start"] for a, b in zip(pages, pages[1:], strict=False)))

    def test_produce_never_resolves_cloud_authentication(self):
        with (
            patch.object(cli.workflow, "resolve_defaults") as cloud,
            patch.object(runner, "produce") as produce,
        ):
            self.assertEqual(cli.main(["produce", "note-001", "--audio-only"]), 0)
            cloud.assert_not_called()
            produce.assert_called_once()

    def test_published_source_cannot_be_used_as_output(self):
        args = argparse.Namespace(
            episode="note-001",
            config=None,
            output_dir=self.root / "docs/assets/audio",
            audio_only=True,
            preview_seconds=None,
        )
        with self.assertRaisesRegex(ValueError, "separate from source"):
            runner.produce(args, self.root)

    def test_preview_is_explicitly_bounded(self):
        for preview in (0, float("nan"), 61):
            args = argparse.Namespace(preview_seconds=preview, audio_only=False)
            with self.assertRaises(ValueError):
                runner.produce(args, self.root)

    def test_artwork_selection_ignores_remote_and_outside_paths(self):
        article = self.root / "docs/notes/note.html"
        article.parent.mkdir(parents=True)
        asset = self.root / "docs/assets/notes/local.svg"
        asset.parent.mkdir(parents=True)
        asset.write_text("<svg/>")
        article.write_text(
            '<img src="https://example.test/a.svg"><img src="../../private.svg"><img src="../assets/notes/local.svg">'
        )
        self.assertEqual(visual_assets(self.root, {"slug": "note.html"})["artwork.svg"], asset)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools unavailable")
class FinishedAudioTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        assets = self.root / "docs/assets/audio"
        assets.mkdir(parents=True)
        source = assets / "fixture.mp3"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=4",
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "96k",
                str(source),
            ],
            check=True,
        )
        (assets / "fixture.json").write_text(
            json.dumps([{"start": 0.3, "end": 3.4, "text": "A source caption."}])
        )
        (assets / "fixture.txt").write_text("A source caption.\n")
        self.entry = {
            "id": "fixture",
            "title": "A fixture.",
            "description": "A test recording.",
            "slug": None,
            "audio": "assets/audio/fixture.mp3",
            "cues": "assets/audio/fixture.json",
            "transcript": "assets/audio/fixture.txt",
            "audio_sha256": digest_file(source),
            "script_sha256": "fixture",
            "source_sha256": {},
            "files_sha256": {
                "cues": digest_file(assets / "fixture.json"),
                "transcript": digest_file(assets / "fixture.txt"),
            },
            "review_status": "pending",
        }
        self.output = self.root / "artifacts/fixture"
        self.output.mkdir(parents=True)
        self.settings = copy.deepcopy(DEFAULTS)
        self.settings.update(intro_seconds=0.5, outro_seconds=0.5, music_overlap_seconds=0.2)

    def test_real_finishing_retimes_exports_reuses_audio_on_video_change_and_repairs_corrupt_cache(
        self,
    ):
        source_hash = self.entry["audio_sha256"]
        destination = runner.produce_audio(self.entry, self.root, self.output, self.settings)
        state = read_object(destination / "production.json")
        self.assertAlmostEqual(float(state["loudness"]["input_i"]), -16, delta=1)
        self.assertLessEqual(float(state["loudness"]["input_tp"]), -0.5)
        cues = captions.parse_captions(
            (destination / "captions.srt").read_text(), state["duration_seconds"]
        )
        self.assertAlmostEqual(cues[0]["start"], 0.5 + 0.3 / 1.15, delta=0.001)
        self.assertEqual(digest_file(self.root / "docs/assets/audio/fixture.mp3"), source_hash)
        self.settings["video"]["width"] = 1280
        self.settings["video"]["height"] = 720
        with patch.object(
            runner, "finish_audio", side_effect=AssertionError("Audio should be reused")
        ):
            self.assertEqual(
                runner.produce_audio(self.entry, self.root, self.output, self.settings), destination
            )
        (destination / "episode.mp3").write_bytes(b"damaged")
        with patch.object(runner, "finish_audio", wraps=finish_audio) as finish:
            self.assertEqual(
                runner.produce_audio(self.entry, self.root, self.output, self.settings), destination
            )
            finish.assert_called_once()
        self.assertTrue(runner.cache_valid(destination, state["fingerprint"], runner.AUDIO_FILES))

    def test_silent_bookends_and_zero_lengths_are_supported(self):
        self.settings.update(music_mode="none", intro_seconds=0, outro_seconds=0)
        destination = runner.produce_audio(self.entry, self.root, self.output, self.settings)
        state = read_object(destination / "production.json")
        self.assertAlmostEqual(state["timeline_duration_seconds"], state["voice_duration_seconds"])

    def test_audio_failure_does_not_commit_a_partial_edition(self):
        with patch.object(runner, "finish_audio", side_effect=RuntimeError("Interrupted")):
            with self.assertRaises(RuntimeError):
                runner.produce_audio(self.entry, self.root, self.output, self.settings)
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
