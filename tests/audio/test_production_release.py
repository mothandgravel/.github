"""Real-media release packages, review identity, promotion rollback and mixed playback."""

import argparse
import copy
import io
import math
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from field_notes_audio import audio, cli, release, site
from field_notes_audio.production import editions, metadata, packages, promotion, runner
from field_notes_audio.production.config import load_settings
from field_notes_audio.storage import digest_file, read_object, write_json
from tests.audio import test_release as fixtures


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg unavailable")
class PublishingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Prepare one shared synthetic collection; each test receives an isolated copy.
        fixtures.ReleaseTests.setUpClass()
        cls.case = fixtures.ReleaseTests()
        cls.case.setUp()
        cls.seed = cls.case.root
        try:
            with redirect_stdout(io.StringIO()):
                entries, cls.completed = cls.case.prepare()
                cls.entry = entries[0]
                output = cls.seed / "artifacts/production" / cls.entry["id"]
                output.mkdir(parents=True)
                settings = load_settings(
                    cls.seed / "audio/production/settings.json", cls.entry["id"]
                )
                finished = editions.produce_audio(cls.entry, cls.seed, output, settings)
            state = read_object(finished / "production.json")
            identity = editions.fingerprint({"fixture": "full", "audio": state["fingerprint"]})
            video = finished / "video" / identity[:16]
            video.mkdir(parents=True)
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=640x360:r=12",
                    "-i",
                    str(finished / "master.wav"),
                    "-t",
                    str(state["timeline_duration_seconds"]),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-c:a",
                    "aac",
                    str(video / "episode.mp4"),
                ],
                check=True,
            )
            shutil.copyfile(cls.seed / "docs/assets/podcast-cover.png", video / "thumbnail.png")
            write_json(
                video / "render.json",
                {
                    "previewSeconds": None,
                    "frames": math.ceil(state["timeline_duration_seconds"] * 12),
                    "fps": 12,
                    "width": 640,
                    "height": 360,
                },
            )
            write_json(
                video / "production.json",
                {
                    "fingerprint": identity,
                    "preview_seconds": None,
                    "audio_fingerprint": state["fingerprint"],
                    "master_sha256": state["files"]["master.wav"],
                    "cues_sha256": state["files"]["cues.json"],
                    "files": {name: digest_file(video / name) for name in editions.VIDEO_FILES},
                },
            )
            runner.update_latest(output, finished, video)
        finally:
            cls.case.patch.stop()

    @classmethod
    def tearDownClass(cls):
        cls.case.doCleanups()
        fixtures.ReleaseTests.tearDownClass()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(self.seed, self.root, dirs_exist_ok=True)
        self.args = argparse.Namespace(
            episode="note-001",
            output_dir=None,
            upload_dir=None,
            metadata=None,
            approve=False,
            reviewer=None,
        )
        self.output = self.root / "artifacts/production"
        self.directory = self.output / "note-001"
        self.finished = self.directory / read_object(self.directory / "latest.json")["audio"]
        self.video = self.directory / read_object(self.directory / "latest.json")["video"]
        self.upload = self.root / "artifacts/uploads/note-001"
        self.config = self.root / "audio/production/publishing.json"

    def approve(self):
        self.args.approve, self.args.reviewer = True, "Test listener"
        packages.review(self.args, self.root)

    def test_export_contains_every_studio_field_and_portable_media_without_mutating_cache(self):
        before = {p: digest_file(p) for p in self.directory.rglob("*") if p.is_file()}
        packages.export(self.args, self.root)
        self.assertEqual((self.upload / "title.txt").read_text().strip(), self.entry["title"])
        self.assertIn("independent studio", (self.upload / "tags.txt").read_text())
        self.assertIn("#MothAndGravel", (self.upload / "description.txt").read_text())
        self.assertNotIn("pending", (self.upload / "description.txt").read_text())
        self.assertEqual(
            digest_file(self.upload / "episode.mp4"), digest_file(self.video / "episode.mp4")
        )
        self.assertEqual(read_object(self.upload / "upload.json")["review_status"], "pending")
        self.assertTrue(
            packages.upload_valid(
                self.upload, read_object(self.upload / "upload.json")["fingerprint"]
            )
        )
        self.assertEqual(before, {p: digest_file(p) for p in before})
        # A user may rename/edit uploaded files without damaging the canonical cache.
        (self.upload / "episode.mp3").write_bytes(b"edited copy")
        self.assertEqual(
            digest_file(self.finished / "episode.mp3"), before[self.finished / "episode.mp3"]
        )
        packages.export(self.args, self.root)
        self.assertEqual(
            digest_file(self.upload / "episode.mp3"), before[self.finished / "episode.mp3"]
        )

    def test_metadata_changes_and_warm_export_never_copy_or_reencode_large_media(self):
        packages.export(self.args, self.root)
        before = {p: p.stat().st_mtime_ns for p in self.upload.iterdir()}
        with patch.object(editions, "finish_audio", side_effect=AssertionError("No re-encode")):
            packages.export(self.args, self.root)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in self.upload.iterdir()})
        config = read_object(self.config)
        config["episodes"]["note-001"]["title"] = "A clearer upload title"
        config["episodes"]["note-001"]["tags"].append("studio workbench")
        write_json(self.config, config)
        with patch.object(editions, "finish_audio", side_effect=AssertionError("No re-encode")):
            packages.export(self.args, self.root)
        self.assertEqual((self.upload / "title.txt").read_text().strip(), "A clearer upload title")
        self.assertIn("studio workbench", (self.upload / "tags.txt").read_text())
        self.assertEqual(
            {p: stamp for p, stamp in before.items() if p.suffix in {".mp3", ".mp4"}},
            {p: p.stat().st_mtime_ns for p in before if p.suffix in {".mp3", ".mp4"}},
        )

    def test_preview_cannot_masquerade_as_full_video(self):
        latest = read_object(self.directory / "latest.json")
        latest.update(video=None, preview=latest["video"], preview_seconds=6)
        write_json(self.directory / "latest.json", latest)
        with self.assertRaisesRegex(ValueError, "full video"):
            packages.export(self.args, self.root)
        self.assertFalse(self.upload.exists())
        latest["video"] = latest["preview"]
        write_json(self.directory / "latest.json", latest)
        state = read_object(self.video / "production.json")
        state["preview_seconds"] = 6
        write_json(self.video / "production.json", state)
        with self.assertRaisesRegex(ValueError, "preview"):
            packages.export(self.args, self.root)

    def test_stale_video_and_changed_source_are_rejected(self):
        state = read_object(self.video / "production.json")
        state["master_sha256"] = "changed"
        write_json(self.video / "production.json", state)
        with self.assertRaisesRegex(ValueError, "provenance"):
            packages.export(self.args, self.root)
        state["master_sha256"] = read_object(self.finished / "production.json")["files"][
            "master.wav"
        ]
        write_json(self.video / "production.json", state)
        audio_state = read_object(self.finished / "production.json")
        audio_state["source_audio_sha256"] = "different recording"
        write_json(self.finished / "production.json", audio_state)
        with self.assertRaisesRegex(ValueError, "different source"):
            packages.export(self.args, self.root)

    def test_approval_requires_a_reviewer_and_is_bound_to_exact_media(self):
        self.args.approve = True
        with self.assertRaisesRegex(ValueError, "reviewer"):
            packages.review(self.args, self.root)
        self.approve()
        snapshot = packages.snapshot(self.entry, self.output, True)
        self.assertEqual(packages.review_status(snapshot, True), "approved")
        (self.video / "thumbnail.png").write_bytes(
            (self.video / "thumbnail.png").read_bytes() + b"changed"
        )
        with self.assertRaisesRegex(ValueError, "changed"):
            packages.export(self.args, self.root)
        # Even a newly validated replacement requires another review.
        state = read_object(self.video / "production.json")
        state["files"]["thumbnail.png"] = digest_file(self.video / "thumbnail.png")
        write_json(self.video / "production.json", state)
        snapshot = packages.snapshot(self.entry, self.output, True)
        self.assertEqual(packages.review_status(snapshot, True), "pending")
        self.assertEqual(packages.review_status(snapshot), "approved")

    def test_unapproved_promotion_touches_no_public_files(self):
        before = {p: digest_file(p) for p in (self.root / "docs").rglob("*") if p.is_file()}
        with self.assertRaisesRegex(ValueError, "approve"):
            promotion.promote(self.args, self.root)
        self.assertEqual(before, {p: digest_file(p) for p in before})

    def test_promotion_updates_feed_captions_and_rate_preserves_guid_and_source(self):
        self.approve()
        before_feed = ET.parse(self.root / "docs/notes/podcast.xml")
        before_guid = {
            item.findtext("title"): item.findtext("guid")
            for item in before_feed.findall("./channel/item")
        }
        promotion.promote(self.args, self.root)
        entries = site.load_entries(self.root)
        promoted = entries[0]
        self.assertEqual(promoted["production"]["source"], self.entry)
        self.assertEqual(promoted["default_playback_rate"], 1)
        self.assertEqual(promoted["published_at"], self.entry["published_at"])
        self.assertEqual(promoted["audio_sha256"], digest_file(self.finished / "episode.mp3"))
        self.assertNotEqual(promoted["audio"], self.entry["audio"])
        self.assertEqual(
            site.media_path(self.root, promoted["srt"]).read_bytes(),
            (self.finished / "captions.srt").read_bytes(),
        )
        self.assertEqual(
            site.media_path(self.root, self.entry["audio"]).stat().st_size, self.entry["bytes"]
        )
        page = (self.root / "docs/notes" / promoted["slug"]).read_text()
        self.assertIn('value="1" selected', page)
        self.assertIn('data-default-rate="1"', page)
        self.assertIn(
            'value="1.15" selected', (self.root / "docs/notes" / entries[1]["slug"]).read_text()
        )
        feed = ET.parse(self.root / "docs/notes/podcast.xml")
        self.assertEqual(
            before_guid,
            {
                item.findtext("title"): item.findtext("guid")
                for item in feed.findall("./channel/item")
            },
        )
        site.build(check=True, root=self.root)
        # Repeated finishing always reads the original speech and reuses its cache.
        settings = load_settings(self.root / "audio/production/settings.json", "note-001")
        with patch.object(editions, "finish_audio", side_effect=AssertionError("Double finishing")):
            self.assertEqual(
                editions.produce_audio(
                    site.source_entry(promoted), self.root, self.directory, settings
                ),
                self.finished,
            )
        packages.export(self.args, self.root)
        self.assertEqual(read_object(self.upload / "upload.json")["review_status"], "approved")
        before = (self.root / "docs/assets/audio/episodes.json").read_bytes()
        promotion.promote(self.args, self.root)
        self.assertEqual(before, (self.root / "docs/assets/audio/episodes.json").read_bytes())

    def test_promotion_rolls_back_manifest_html_assets_and_previous_release_on_build_failure(self):
        self.approve()
        files = [*self.root.joinpath("docs").rglob("*"), self.root / "artifacts/audio/release.json"]
        before = {p: p.read_bytes() for p in files if p.is_file()}
        original = site.build

        def failed(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("injected publication failure")

        with (
            patch.object(site, "build", side_effect=failed),
            self.assertRaisesRegex(ValueError, "injected"),
        ):
            promotion.promote(self.args, self.root)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual(
            set(p for p in self.root.joinpath("docs").rglob("*") if p.is_file()),
            set(p for p in before if p.is_relative_to(self.root / "docs")),
        )

    def test_original_preparation_does_not_revert_promoted_audio(self):
        self.approve()
        promotion.promote(self.args, self.root)
        expected = site.load_entries(self.root)[0]
        completed = [
            (episode, self.root / directory.relative_to(self.seed))
            for episode, directory in self.completed
        ]
        with patch.object(audio, "ROOT", self.root):
            release.prepare_publication(completed)
        self.assertEqual(site.load_entries(self.root)[0], expected)

    def test_invalid_metadata_fails_before_writing_uploads(self):
        config = read_object(self.config)
        for change in ({"title": "x" * 101}, {"tags": ["tag,other"]}, {"hashtags": ["#bad tag"]}):
            invalid = copy.deepcopy(config)
            invalid["episodes"]["note-001"].update(change)
            write_json(self.config, invalid)
            with self.assertRaises(ValueError):
                packages.export(self.args, self.root)
            self.assertFalse(self.upload.exists())

    def test_future_note_uses_shared_tags_without_inventing_topic_tags(self):
        entry = {**self.entry, "id": "note-012"}
        copy = metadata.load_copy(self.config, entry, "No music.")
        self.assertEqual(copy.tags, tuple(read_object(self.config)["shared_tags"]))
        self.assertEqual(copy.hashtags, ("#MothAndGravel",))

    def test_release_checks_publishing_copy_before_rendering(self):
        config = read_object(self.config)
        config["episodes"]["note-001"]["title"] = "x" * 101
        write_json(self.config, config)
        with patch.object(runner, "produce") as produce, patch.object(packages, "export") as export:
            self.assertEqual(cli.main(["release", "note-001", "--metadata", str(self.config)]), 1)
            produce.assert_not_called()
            export.assert_not_called()

    def test_existing_render_adopts_provenance_without_rerendering(self):
        state = read_object(self.video / "production.json")
        for key in ("audio_fingerprint", "master_sha256", "cues_sha256"):
            state.pop(key)
        write_json(self.video / "production.json", state)
        (self.root / "video/node_modules/@remotion/renderer").mkdir(parents=True)
        shutil.copyfile(
            audio.ROOT / "docs/assets/moth-mark.svg", self.root / "docs/assets/moth-mark.svg"
        )
        before = digest_file(self.video / "episode.mp4")
        from field_notes_audio.production import video

        with (
            patch.object(runner, "fingerprint", return_value=state["fingerprint"]),
            patch.object(video, "render_video") as render,
        ):
            result = runner.produce_video(
                self.entry,
                self.root,
                self.finished,
                load_settings(self.root / "audio/production/settings.json", "note-001"),
                argparse.Namespace(preview_seconds=None),
            )
            render.assert_not_called()
        self.assertEqual(result, self.video)
        self.assertEqual(before, digest_file(self.video / "episode.mp4"))
        packages.snapshot(self.entry, self.output, True)

    def test_shortened_mp4_is_rejected_even_when_its_saved_hash_is_updated(self):
        short = self.video / "short.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(self.video / "episode.mp4"),
                "-t",
                "1",
                "-c",
                "copy",
                str(short),
            ],
            check=True,
        )
        short.replace(self.video / "episode.mp4")
        state = read_object(self.video / "production.json")
        state["files"]["episode.mp4"] = digest_file(self.video / "episode.mp4")
        write_json(self.video / "production.json", state)
        with self.assertRaisesRegex(ValueError, "complete"):
            packages.export(self.args, self.root)

    def test_all_export_validates_every_selected_episode_before_writing(self):
        self.args.episode = "all"
        with self.assertRaisesRegex(ValueError, "no completed"):
            packages.export(self.args, self.root)
        self.assertFalse(self.upload.exists())

    def test_escaped_pointer_and_overlapping_output_are_rejected(self):
        latest = read_object(self.directory / "latest.json")
        latest["audio"] = "../../private"
        write_json(self.directory / "latest.json", latest)
        with self.assertRaisesRegex(ValueError, "pointer"):
            packages.export(self.args, self.root)
        self.args.upload_dir = self.output
        with self.assertRaisesRegex(ValueError, "separate"):
            packages.export(self.args, self.root)

    def test_upload_replacement_recovers_from_interruption(self):
        packages.export(self.args, self.root)
        previous = (self.upload / "title.txt").read_bytes()
        config = read_object(self.config)
        config["episodes"]["note-001"]["title"] = "New copy"
        write_json(self.config, config)
        replace = Path.replace
        triggered = False

        def interrupted(path, target):
            nonlocal triggered
            if target == self.upload / "title.txt" and not triggered:
                triggered = True
                raise KeyboardInterrupt
            return replace(path, target)

        with patch.object(Path, "replace", interrupted), self.assertRaises(KeyboardInterrupt):
            packages.export(self.args, self.root)
        self.assertEqual((self.upload / "title.txt").read_bytes(), previous)

    def test_local_release_commands_never_resolve_cloud_or_allow_preview_release(self):
        for name in ("export", "review", "promote"):
            module = promotion if name == "promote" else packages
            with (
                patch.object(cli.workflow, "resolve_defaults") as cloud,
                patch.object(module, name) as action,
            ):
                self.assertEqual(cli.main([name, "note-001"]), 0)
                cloud.assert_not_called()
                action.assert_called_once()
        with patch.object(runner, "produce") as produce, patch.object(packages, "export") as export:
            self.assertEqual(cli.main(["release", "note-001", "--preview-seconds", "6"]), 1)
            produce.assert_not_called()
            export.assert_not_called()


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 3 and sys.argv[1] == "--browser-fixture":
        destination = Path(sys.argv[2]).resolve()
        if not destination.is_relative_to(audio.ROOT / "artifacts"):
            raise ValueError("Synthetic review fixtures must stay under artifacts")
        PublishingTests.setUpClass()
        case = PublishingTests()
        try:
            case.setUp()
            shutil.copytree(audio.ROOT / "docs", case.root / "docs", dirs_exist_ok=True)
            # Restore synthetic media/manifest after copying authored visual assets.
            shutil.copytree(PublishingTests.seed / "docs", case.root / "docs", dirs_exist_ok=True)
            case.approve()
            promotion.promote(case.args, case.root)
            shutil.copytree(case.root / "docs", destination, dirs_exist_ok=True)
            print(f"Mixed original/finished synthetic listening fixture: {destination}")
        finally:
            case.doCleanups()
            PublishingTests.tearDownClass()
    else:
        unittest.main()
