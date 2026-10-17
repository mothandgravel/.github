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
from field_notes_audio.production import editions, mix, runner
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

    def test_caption_precision_failure_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "millisecond precision"):
            retime([{"start": 1, "end": 1.0001, "text": "Too short"}], 1.5, 0, 3)

    def test_latest_keeps_full_video_when_audio_or_preview_is_requested(self):
        edition = self.root / "audio-fingerprint"
        edition.mkdir()
        write_json(
            edition / "production.json", {"files": {"master.wav": "master", "cues.json": "cues"}}
        )
        full = edition / "video/full"
        preview = edition / "video/preview"
        runner.update_latest(self.root, edition, full)
        runner.update_latest(self.root, edition)
        runner.update_latest(self.root, edition, preview, 6)
        latest = read_object(self.root / "latest.json")
        self.assertEqual(latest["video"], "audio-fingerprint/video/full")
        self.assertEqual(latest["preview"], "audio-fingerprint/video/preview")
        self.assertEqual(latest["preview_seconds"], 6)
        # Rebuilt sound under the same input identity must not retain stale video links.
        write_json(
            edition / "production.json", {"files": {"master.wav": "changed", "cues.json": "cues"}}
        )
        runner.update_latest(self.root, edition)
        self.assertIsNone(read_object(self.root / "latest.json")["video"])

    def test_missing_node_is_detected_before_finishing_any_audio(self):
        args = argparse.Namespace(
            episode="fixture",
            config=self.config,
            output_dir=None,
            audio_only=False,
            preview_seconds=None,
            browser_executable=None,
        )
        with (
            patch.object(runner.site, "load_entries", return_value=[{"id": "fixture"}]),
            patch.object(
                runner.shutil,
                "which",
                side_effect=lambda name: None if name == "node" else "/bin/tool",
            ),
            patch.object(runner, "produce_audio") as finish,
        ):
            with self.assertRaisesRegex(ValueError, "Node 22"):
                runner.produce(args, self.root)
            finish.assert_not_called()
        self.assertFalse((self.root / "artifacts").exists())

    def test_video_failure_leaves_finished_audio_discoverable(self):
        directory = self.root / "artifacts/production/fixture"
        edition = directory / "fingerprint"
        edition.mkdir(parents=True)
        write_json(
            edition / "production.json", {"files": {"master.wav": "master", "cues.json": "cues"}}
        )
        args = argparse.Namespace(
            episode="fixture",
            config=self.config,
            output_dir=None,
            audio_only=False,
            preview_seconds=None,
            browser_executable=None,
        )
        with (
            patch.object(runner.site, "load_entries", return_value=[{"id": "fixture"}]),
            patch.object(runner, "preflight"),
            patch.object(runner, "produce_audio", return_value=edition),
            patch.object(runner, "produce_video", side_effect=RuntimeError("Render interrupted")),
        ):
            with self.assertRaisesRegex(RuntimeError, "Render interrupted"):
                runner.produce(args, self.root)
        latest = read_object(directory / "latest.json")
        self.assertEqual(latest["audio"], "fingerprint")
        self.assertIsNone(latest["video"])

    def test_replacement_rolls_back_on_interrupt_and_keeps_existing_video(self):
        destination, stage = self.root / "destination", self.root / "stage"
        for path in (destination, stage):
            path.mkdir()
            for name in editions.AUDIO_FILES:
                (path / name).write_text("old" if path == destination else "new")
        (destination / "video").mkdir()
        (destination / "video/finished.mp4").write_text("valuable render")
        rename = Path.rename

        def interrupted(path, target):
            if path == stage:
                raise KeyboardInterrupt
            return rename(path, target)

        with patch.object(Path, "rename", interrupted), self.assertRaises(KeyboardInterrupt):
            runner.commit_stage(
                stage, destination, {"fingerprint": "identity"}, editions.AUDIO_FILES
            )
        self.assertEqual((destination / "episode.mp3").read_text(), "old")
        self.assertEqual((destination / "video/finished.mp4").read_text(), "valuable render")
        runner.commit_stage(stage, destination, {"fingerprint": "identity"}, editions.AUDIO_FILES)
        self.assertEqual((destination / "episode.mp3").read_text(), "new")
        self.assertEqual((destination / "video/finished.mp4").read_text(), "valuable render")

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

    def test_retry_after_a_render_failure_reuses_cached_audio_and_calls_nothing_paid(self):
        from field_notes_audio.production.renderer_process import RenderFailed

        config = self.root / "settings.json"
        write_json(config, DEFAULTS)
        args = argparse.Namespace(
            episode="fixture",
            config=config,
            output_dir=self.root / "artifacts/production",
            audio_only=False,
            preview_seconds=None,
            browser_executable=None,
        )
        directory = args.output_dir / "fixture"
        rendered = []

        def render(entry, root, edition, settings, args):
            if not rendered:
                rendered.append(edition)
                raise RenderFailed("The video renderer stopped.")
            self.assertEqual(edition, rendered[0])
            video = edition / "video/abc"
            video.mkdir(parents=True)
            for name in ("episode.mp4", "thumbnail.png"):
                (video / name).write_bytes(b"x")
            return video

        def paid(*_args, **_kwargs):
            raise AssertionError("A video retry must not narrate or caption")

        with (
            patch.object(runner, "load_entries", return_value=[self.entry]),
            patch.object(runner.site, "source_entry", side_effect=lambda entry: entry),
            patch.object(runner, "preflight"),
            patch.object(runner, "produce_video", side_effect=render),
        ):
            with self.assertRaises(RenderFailed):
                runner.produce(args, self.root)
            first = read_object(directory / "latest.json")
            self.assertIsNone(first["video"])
            with (
                patch.object(editions, "finish_audio", side_effect=paid),
                patch.object(audio, "synthesize", side_effect=paid),
                patch.object(audio, "generate", side_effect=paid),
                patch.object(captions, "run", side_effect=paid),
            ):
                runner.produce(args, self.root)
        second = read_object(directory / "latest.json")
        self.assertEqual(second["audio"], first["audio"])
        self.assertEqual(second["video"], f"{first['audio']}/video/abc")

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
            editions, "finish_audio", side_effect=AssertionError("Audio should be reused")
        ):
            self.assertEqual(
                runner.produce_audio(self.entry, self.root, self.output, self.settings), destination
            )
        (destination / "episode.mp3").write_bytes(b"damaged")
        (destination / "video").mkdir()
        (destination / "video/previous.mp4").write_bytes(b"an existing render")
        with patch.object(editions, "finish_audio", wraps=finish_audio) as finish:
            self.assertEqual(
                runner.produce_audio(self.entry, self.root, self.output, self.settings), destination
            )
            finish.assert_called_once()
        self.assertTrue(runner.cache_valid(destination, state["fingerprint"], editions.AUDIO_FILES))
        self.assertEqual((destination / "video/previous.mp4").read_bytes(), b"an existing render")

    def test_source_link_change_invalidates_the_description_cache(self):
        runner.produce_audio(self.entry, self.root, self.output, self.settings)
        self.entry["slug"] = "new-written-edition.html"
        with patch.object(editions, "finish_audio", side_effect=RuntimeError("new identity")):
            with self.assertRaisesRegex(RuntimeError, "new identity"):
                runner.produce_audio(self.entry, self.root, self.output, self.settings)

    def test_caption_failure_saves_exact_measurements_without_committing_bad_media(self):
        with patch.object(editions, "retime", side_effect=ValueError("Bad timing")):
            with self.assertRaisesRegex(ValueError, "diagnostic saved"):
                runner.produce_audio(self.entry, self.root, self.output, self.settings)
        files = list((self.output / "failures").glob("*.json"))
        self.assertEqual(len(files), 1)
        state = read_object(files[0])
        self.assertEqual(state["error"], "Bad timing")
        self.assertGreater(state["measurements"]["master_duration_seconds"], 0)
        self.assertFalse(list(self.output.glob("*/episode.mp3")))

    def test_silent_bookends_and_zero_lengths_are_supported(self):
        self.settings.update(music_mode="none", intro_seconds=0, outro_seconds=0)
        destination = runner.produce_audio(self.entry, self.root, self.output, self.settings)
        state = read_object(destination / "production.json")
        self.assertAlmostEqual(state["timeline_duration_seconds"], state["voice_duration_seconds"])

    def test_audio_failure_does_not_commit_a_partial_edition(self):
        with patch.object(editions, "finish_audio", side_effect=RuntimeError("Interrupted")):
            with self.assertRaises(RuntimeError):
                runner.produce_audio(self.entry, self.root, self.output, self.settings)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_custom_music_is_mixed_and_credited_from_a_real_file(self):
        self.settings.update(
            music_mode="file",
            music_file=str(self.root / self.entry["audio"].replace("assets/", "docs/assets/", 1)),
            music_credit="Fixture tone / original test material",
        )
        destination = runner.produce_audio(self.entry, self.root, self.output, self.settings)
        self.assertIn(
            "Fixture tone / original test material", (destination / "description.txt").read_text()
        )
        state = read_object(destination / "production.json")
        self.assertAlmostEqual(
            state["master_duration_seconds"], state["timeline_duration_seconds"], delta=0.05
        )

    def test_successful_encoder_with_truncated_output_is_rejected(self):
        self.settings.update(music_mode="none", intro_seconds=0, outro_seconds=0)
        original = mix.stream_output

        def truncate(arguments, write, timeout=600):
            if "mp3" in arguments:
                return original(arguments, lambda chunk: write(chunk[: len(chunk) // 2]), timeout)
            return original(arguments, write, timeout)

        with patch.object(mix, "stream_output", side_effect=truncate):
            with self.assertRaisesRegex(ValueError, "intended duration"):
                runner.produce_audio(self.entry, self.root, self.output, self.settings)
        self.assertFalse(list(self.output.glob("*/production.json")))


if __name__ == "__main__":
    unittest.main()
