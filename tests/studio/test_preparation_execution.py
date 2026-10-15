"""Real local media with mocked Cloud boundaries; no paid or human-review evidence."""

import argparse
import io
import json
import math
import shutil
import struct
import tempfile
import unittest
import wave
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

from field_notes_audio import audio, captions, site, workflow
from field_notes_audio.production import sources
from field_notes_audio.storage import read_object, write_json
from field_notes_studio.pipeline import Pipeline
from field_notes_studio.preparation_jobs import PreparationJobs
from field_notes_studio.preparation_service import PreparationService
from field_notes_studio.repository import Repository
from field_notes_studio.service import Studio
from field_notes_studio.worker import execute
from tests.audio.test_captions import operation

ROOT = Path(__file__).resolve().parents[2]


class PreparationExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            handle.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            handle.writeframes(
                b"".join(struct.pack("<h", int(4000 * math.sin(i * 0.06))) for i in range(96000))
            )
        cls.wav = buffer.getvalue()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        note = {
            "id": "104",
            "title": "Window",
            "slug": "104-window.html",
            "summary": "Offline fixture.",
        }
        article = '<article class="note-prose"><p>Hello world. Another question.</p></article>'
        self.text("docs/notes/104-window.html", article)
        self.text("audio/scripts/window.txt", "Hello world. Another question.\n")
        write_json(self.root / "docs/assets/notes.json", [note])
        write_json(self.root / "docs/assets/audio/episodes.json", [])
        self.episode = {
            "id": "studio-essay",
            "title": "Window",
            "script": "scripts/window.txt",
            "notes": ["104"],
            "language": "en-US",
            "speakers": [{"alias": "Narrator", "voice": "Charon"}],
            "prompt": "Read exactly.",
            "target_wpm": 140,
            "source_sha256": {"104": audio.digest(audio.source_article(self.root, note).encode())},
            "publication": {"kind": "note", "note_id": "104"},
        }
        write_json(self.root / "audio/episodes.json", [self.episode])
        self.config = {
            "project": "fixture-project",
            "bucket": "fixture-private-bucket",
            "model": "gemini-2.5-pro-tts",
            "endpoint": "global",
            "auth": "gcloud",
            "caption_model": "chirp_3",
            "location": "us",
        }
        self.settings = self.root / "artifacts/audio/settings.json"
        write_json(
            self.settings,
            {
                **self.config,
                "prepared": {
                    "version": workflow.SETUP_VERSION,
                    "project": self.config["project"],
                    "bucket": self.config["bucket"],
                    "location": "us",
                },
            },
        )
        for filename in ("settings.json", "publishing.json"):
            target = self.root / "audio/production" / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "audio/production" / filename, target)
        self.adapter = PreparationJobs(self.root)
        self.snapshot = self.adapter.inspect("104")
        self.request = json.loads(self.snapshot.request_json)
        self.repository = Repository(self.root / "artifacts/studio/studio.sqlite3")
        self.pipeline = Pipeline(self.root)
        self.events = []

    def text(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def original_files(self):
        return {
            str(p.relative_to(self.root)): p.read_bytes()
            for parent in ("docs", "audio")
            for p in (self.root / parent).rglob("*")
            if p.is_file()
        }

    @contextmanager
    def cloud(self, *, pending=False):
        which = shutil.which
        args_fn = PreparationJobs._caption_args

        def quick_args(*args):
            result = args_fn(*args)
            result.wait = 0
            return result

        def submit(url, project, auth, payload):
            self.assertIn(":batchRecognize", url)
            return operation(payload["files"][0]["uri"], done=not pending)

        with ExitStack() as stack:
            stack.enter_context(
                patch("socket.create_connection", side_effect=AssertionError("Unexpected network"))
            )
            stack.enter_context(
                patch(
                    "shutil.which",
                    side_effect=lambda name: "/fixture/gcloud" if name == "gcloud" else which(name),
                )
            )
            stack.enter_context(
                patch.object(PreparationJobs, "_caption_args", staticmethod(quick_args))
            )
            auth = stack.enter_context(
                patch.object(audio, "access_token", return_value="fixture-token")
            )
            synth = stack.enter_context(patch.object(audio, "synthesize", return_value=self.wav))
            upload = stack.enter_context(patch.object(captions, "ensure_upload", return_value="1"))
            submitted = stack.enter_context(
                patch.object(captions, "cloud_json", side_effect=submit)
            )
            polled = stack.enter_context(patch.object(captions, "poll_operation"))
            yield auth, synth, upload, submitted, polled

    def run_adapter(self):
        return Path(self.adapter.run(self.request, lambda *e: self.events.append(e), lambda: False))

    def prepare(self):
        with self.cloud():
            return self.run_adapter()

    def test_explicit_authorization_is_required_and_inspection_never_calls_cloud(self):
        service = PreparationService(self.root)
        with (
            patch("field_notes_studio.preparation_service.launch_worker") as launch,
            self.cloud() as calls,
        ):
            service.inspect("104")
            for value in (False, None, 1, "yes"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    service.submit(self.snapshot, value)
            self.assertEqual(service.repository.jobs(), [])
            launch.assert_not_called()
            for call in calls:
                call.assert_not_called()
            identifier = service.submit(self.snapshot, True)
            self.assertEqual(service.repository.get(identifier).action, "prepare")
            with self.assertRaisesRegex(ValueError, "queued or running"):
                service.submit(self.snapshot, True)

    def test_private_adoption_does_not_publish_or_approve_and_can_feed_real_production(self):
        before = self.original_files()
        target = self.prepare()
        self.assertTrue(target.is_relative_to(self.root / "artifacts/studio/prepared"))
        self.assertEqual(before, self.original_files())
        self.assertEqual(site.load_entries(self.root), [])
        entry = sources.load_entries(self.root)[0]
        self.assertEqual(entry["review_status"], "pending")
        self.assertNotIn("published_at", entry)
        episode = self.pipeline.catalog()[0]
        self.assertEqual(
            (episode.publication_url, episode.podcast_url, episode.publication_date), ("", "", "")
        )
        self.assertEqual(self.repository.publications(), {})
        request = self.pipeline.request("studio-essay", "audio", 1.15, 1)
        identifier = self.repository.submit("studio-essay", "audio", request)
        execute(self.repository, self.pipeline, self.repository.claim())
        job = self.repository.get(identifier)
        self.assertEqual(job.status, "succeeded", job.error)
        review = self.pipeline.review_snapshot("studio-essay")
        self.assertTrue(review.identity)
        self.assertEqual(before, self.original_files())

    def test_verified_mp3_is_reused_without_wav_chunks_auth_upload_or_resubmission(self):
        target = self.prepare()
        recording = self.adapter._recording(self.request["plan"])
        for path in recording.glob("chunk-*"):
            path.unlink()
        with self.cloud() as calls:
            self.assertEqual(self.run_adapter(), target)
            for call in calls:
                call.assert_not_called()
        self.assertIn("no synthesis is needed", self.adapter.inspect("104").summary)

    def test_waiting_captions_resume_same_job_without_resynthesis_or_resubmission(self):
        identifier = self.repository.submit("studio-essay", "prepare", self.request)
        with self.cloud(pending=True) as calls:
            execute(self.repository, self.pipeline, self.repository.claim())
            job = self.repository.get(identifier)
            self.assertEqual(job.status, "waiting", job.error)
            self.assertFalse(job.result)
            calls[1].assert_called_once()
            calls[3].assert_called_once()
            self.assertEqual(sources.load_entries(self.root), [])
            with self.assertRaises(ValueError):
                self.repository.submit("studio-essay", "prepare", self.request)
            caps = next(self.adapter._recording(self.request["plan"]).glob("captions/*/plan.json"))
            calls[4].return_value = operation(read_object(caps)["audio_uri"])
            with patch("field_notes_studio.service.launch_worker"):
                resumed = Studio(self.root).retry(identifier)
            self.assertEqual(resumed, identifier)
            execute(self.repository, self.pipeline, self.repository.claim())
            self.assertEqual(self.repository.get(identifier).status, "succeeded")
            calls[1].assert_called_once()
            calls[3].assert_called_once()
            calls[4].assert_called_once()
            self.assertEqual(len(self.repository.jobs()), 1)

    def test_changed_script_after_queueing_blocks_before_authentication(self):
        identifier = self.repository.submit("studio-essay", "prepare", self.request)
        self.text("audio/scripts/window.txt", "A different script.")
        with self.cloud() as calls:
            execute(self.repository, self.pipeline, self.repository.claim())
            self.assertEqual(self.repository.get(identifier).status, "failed")
            for call in calls:
                call.assert_not_called()

    def test_stop_after_narration_preserves_mp3_and_never_submits_captions(self):
        identifier = self.repository.submit("studio-essay", "prepare", self.request)
        original = self.repository.event

        def cancel_after(job, stage, message):
            original(job, stage, message)
            if stage == "narration-complete":
                self.repository.cancel(job)

        with (
            patch.object(self.repository, "event", side_effect=cancel_after),
            self.cloud() as calls,
        ):
            execute(self.repository, self.pipeline, self.repository.claim())
            self.assertEqual(self.repository.get(identifier).status, "cancelled")
            self.assertTrue(
                (self.adapter._recording(self.request["plan"]) / "episode.mp3").exists()
            )
            calls[3].assert_not_called()

    def test_uncertain_narration_never_replays_automatically(self):
        directory = self.adapter._recording(self.request["plan"])
        write_json(directory / "chunk-001.json", {"status": "uncertain"})
        self.assertFalse(self.adapter.inspect("104").request_json)
        with self.cloud() as calls, self.assertRaisesRegex(ValueError, "uncertain"):
            self.run_adapter()
        calls[1].assert_not_called()

    def test_uncertain_caption_submission_is_not_repeated_on_retry(self):
        with self.cloud() as calls:
            calls[3].side_effect = TimeoutError("No acknowledgement")
            with self.assertRaisesRegex(RuntimeError, "operation ID"):
                self.run_adapter()
            calls[3].assert_called_once()
            self.assertFalse(self.adapter.inspect("104").request_json)
            with self.assertRaisesRegex(ValueError, "acknowledgement"):
                self.run_adapter()
            calls[3].assert_called_once()
            calls[1].assert_called_once()

    def test_mutated_captured_plan_and_configuration_are_rejected(self):
        for field in ("plan", "configuration"):
            request = json.loads(self.snapshot.request_json)
            request[field]["unexpected"] = "value"
            with self.subTest(field=field), self.cloud() as calls, self.assertRaises(ValueError):
                self.adapter.run(request, lambda *_: None, lambda: False)
            for call in calls:
                call.assert_not_called()

    def test_setup_is_not_automatically_performed_or_secrets_copied(self):
        saved = read_object(self.settings)
        saved["credential"] = "never-capture-this"
        write_json(self.settings, saved)
        snapshot = self.adapter.inspect("104")
        self.assertNotIn("never-capture-this", snapshot.request_json)
        self.settings.unlink()
        with patch.object(workflow, "setup", side_effect=AssertionError("Setup")):
            snapshot = self.adapter.inspect("104")
        self.assertTrue(snapshot.script)
        self.assertFalse(snapshot.request_json)
        self.assertIn("Cloud setup is missing", snapshot.summary)

    def test_saved_mp3_corruption_is_not_hidden_by_resynthesis(self):
        self.prepare()
        self.adapter._recording(self.request["plan"]).joinpath("episode.mp3").write_bytes(
            b"changed"
        )
        with self.cloud() as calls, self.assertRaisesRegex(ValueError, "Saved narration"):
            self.run_adapter()
        calls[1].assert_not_called()

    def test_private_asset_corruption_blocks_production_source_loading(self):
        target = self.prepare()
        (target / "captions.vtt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "vtt changed"):
            sources.load_entries(self.root)

    def test_private_recording_cannot_be_passed_off_as_a_public_catalog_entry(self):
        self.prepare()
        entry = sources.load_entries(self.root)[0]
        shutil.copyfile(
            ROOT / "docs/assets/podcast-cover.png", self.root / "docs/assets/podcast-cover.png"
        )
        with self.assertRaisesRegex(ValueError, "Published audio assets"):
            site.load_entries(self.root, [entry])

    def test_caption_rewrite_or_disagreement_blocks_adoption(self):
        self.prepare()
        plan = self.request["plan"]
        directory = next(self.adapter._recording(plan).glob("captions/*/captions.json")).parent
        (directory / "captions.srt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "Caption output changed"):
            sources.adopt(self.root, plan, directory)

    def test_cache_symlink_escape_is_rejected_before_any_request(self):
        directory = self.adapter._recording(self.request["plan"])
        directory.mkdir(parents=True)
        (directory / "chunk-001.json").symlink_to(self.settings)
        with self.cloud() as calls, self.assertRaisesRegex(ValueError, "symbolic links"):
            self.run_adapter()
        for call in calls:
            call.assert_not_called()

    def test_private_media_path_escapes_are_rejected(self):
        for value in (
            "studio-prepared/../../private.txt",
            "studio-prepared/essay/not-a-hash/episode.mp3",
        ):
            with self.subTest(path=value), self.assertRaises(ValueError):
                sources.media_path(self.root, value)

    def test_waiting_job_survives_recovery_and_does_not_poll_itself(self):
        identifier = self.repository.submit("studio-essay", "prepare", self.request)
        self.repository.claim()
        self.repository.pause(identifier, "Awaiting saved caption operation")
        reopened = Repository(self.repository.path)
        reopened.recover()
        self.assertEqual(reopened.get(identifier).status, "waiting")
        self.assertIsNone(reopened.claim())
        self.assertIsNone(reopened.latest_recipe("studio-essay"))

    def test_preparation_changes_do_not_become_a_production_recipe(self):
        self.repository.submit("studio-essay", "prepare", self.request)
        self.assertIsNone(self.repository.latest_recipe("studio-essay"))

    def test_queue_capacity_does_not_lose_waiting_caption_work(self):
        identifier = self.repository.submit("studio-essay", "prepare", self.request)
        self.repository.claim()
        self.repository.pause(identifier, "Waiting")
        for i in range(32):
            self.repository.submit(f"fixture-{i}", "audio", {})
        with self.assertRaisesRegex(ValueError, "queue is full"):
            self.repository.resume_preparation(identifier)
        self.assertEqual(self.repository.get(identifier).status, "waiting")

    def test_lost_caption_receipt_cannot_turn_resume_into_a_new_submission(self):
        identifier = self.repository.submit("studio-essay", "prepare", self.request)
        with self.cloud(pending=True) as calls:
            execute(self.repository, self.pipeline, self.repository.claim())
            self.assertEqual(self.repository.get(identifier).status, "waiting")
            saved_request = json.loads(self.repository.get(identifier).request)
            self.assertTrue(saved_request["resume"]["operation"])
            state = next(
                self.adapter._recording(self.request["plan"]).glob("captions/*/state.json")
            )
            state.unlink()
            self.repository.resume_preparation(identifier)
            execute(self.repository, self.pipeline, self.repository.claim())
            job = self.repository.get(identifier)
            self.assertEqual(job.status, "failed")
            self.assertIn("will not create a new submission", job.error)
            calls[1].assert_called_once()
            calls[3].assert_called_once()
            calls[4].assert_not_called()

    def test_lost_saved_narration_cannot_turn_resume_into_resynthesis(self):
        identifier = self.repository.submit("studio-essay", "prepare", self.request)
        with self.cloud(pending=True) as calls:
            execute(self.repository, self.pipeline, self.repository.claim())
            self.assertEqual(self.repository.get(identifier).status, "waiting")
            directory = self.adapter._recording(self.request["plan"])
            (directory / "episode.mp3").unlink()
            (directory / "episode.json").unlink()
            self.repository.resume_preparation(identifier)
            execute(self.repository, self.pipeline, self.repository.claim())
            job = self.repository.get(identifier)
            self.assertEqual(job.status, "failed")
            self.assertIn("no resynthesis", job.error)
            calls[1].assert_called_once()
            calls[3].assert_called_once()

    def test_source_change_after_narration_blocks_the_next_remote_stage(self):
        def emit(stage, message):
            if stage == "narration-complete":
                self.text("audio/scripts/window.txt", "A changed script.")

        with (
            self.cloud() as calls,
            self.assertRaisesRegex(ValueError, "Sources or settings changed"),
        ):
            self.adapter.run(self.request, emit, lambda: False)
        calls[1].assert_called_once()
        calls[3].assert_not_called()

    def test_private_pointer_symlink_is_rejected(self):
        target = self.prepare()
        pointer = target.parent / "latest.json"
        pointer.unlink()
        pointer.symlink_to(self.settings)
        with self.assertRaisesRegex(ValueError, "symbolic links"):
            sources.load_entries(self.root)

    def test_missing_tools_fail_before_a_billable_request(self):
        with (
            self.cloud() as calls,
            patch("shutil.which", return_value=None),
            self.assertRaisesRegex(ValueError, "tools are missing"),
        ):
            self.run_adapter()
        calls[1].assert_not_called()
        calls[3].assert_not_called()

    def test_public_promotion_does_not_silently_include_a_private_recording(self):
        from field_notes_audio.production import promotion

        self.prepare()
        before = self.original_files()
        for identifier in ("all", "studio-essay"):
            with (
                self.subTest(episode=identifier),
                self.assertRaisesRegex(ValueError, "No prepared episode"),
            ):
                promotion.promote(
                    argparse.Namespace(episode=identifier, output_dir=None), self.root
                )
        self.assertEqual(self.original_files(), before)
