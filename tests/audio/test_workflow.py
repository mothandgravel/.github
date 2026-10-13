"""Offline checks for setup, saved defaults and interruption-safe episode workflows."""

import argparse
import io
import os
import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from field_notes_audio import audio, cli
from field_notes_audio import captions as captions
from field_notes_audio import workflow as workflow
from tests.audio.test_audio import wav_bytes
from tests.audio.test_captions import operation


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.root_patch = patch.object(audio, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def args(self, **overrides):
        values = dict(
            command="make",
            episode="workbench-001",
            project="audio-pilot-project",
            bucket=None,
            endpoint=None,
            location=None,
            model=None,
            auth=None,
            wait=0,
            no_open=True,
            retry_uncertain=False,
            restart_failed=False,
        )
        return argparse.Namespace(**(values | overrides))

    def save(self, **changes):
        settings = dict(
            project="audio-pilot-project",
            bucket="audio-pilot-project-field-notes-audio",
            endpoint="global",
            location="us",
            auth="gcloud",
            model="gemini-2.5-pro-tts",
            caption_model="chirp_3",
        )
        settings.update(changes)
        audio.write_json(workflow.settings_path(), settings)
        return settings

    def private_bucket(self):
        return {
            "projectNumber": "12345",
            "location": "US",
            "iamConfiguration": {
                "publicAccessPrevention": "enforced",
                "uniformBucketLevelAccess": {"enabled": True},
            },
        }

    def test_explicit_then_environment_then_saved_project_without_repeating_flags(self):
        self.save()
        self.assertEqual(
            workflow.resolve_defaults(self.args(project=None), False).project, "audio-pilot-project"
        )
        with patch.dict(os.environ, {"FIELD_AUDIO_PROJECT": "another-project"}):
            args = workflow.resolve_defaults(self.args(project=None), False)
            self.assertEqual(args.project, "another-project")
            self.assertEqual(args.bucket, "another-project-field-notes-audio")
            self.assertEqual(
                workflow.resolve_defaults(self.args(project="explicit-project"), False).project,
                "explicit-project",
            )
        with patch.object(
            workflow,
            "gcloud",
            side_effect=AssertionError("Offline must not discover Cloud defaults"),
        ):
            workflow.resolve_defaults(self.args(project=None), False)

    def test_discovers_gcloud_project_and_defaults_to_working_global_endpoint(self):
        with (
            patch.object(workflow.shutil, "which", return_value="installed"),
            patch.object(workflow, "gcloud", return_value="audio-pilot-project") as cli,
        ):
            args = workflow.resolve_defaults(self.args(project=None))
        cli.assert_called_once_with(["config", "get-value", "project"])
        self.assertEqual(args.endpoint, "global")
        self.assertEqual(args.location, "us")

    def test_setup_creates_private_bucket_and_saves_no_credentials(self):
        args = workflow.resolve_defaults(self.args(command="setup"))
        with (
            patch.object(workflow.shutil, "which", return_value="installed"),
            patch.object(audio, "access_token", return_value="secret-in-memory"),
            patch.object(workflow, "gcloud", side_effect=["True", "12345", ""]),
            patch.object(
                captions,
                "cloud_json",
                side_effect=[captions.CloudError({"http_status": 404}), self.private_bucket()],
            ) as cloud,
            redirect_stdout(io.StringIO()),
        ):
            workflow.setup(args)
        body = cloud.call_args.args[3]
        self.assertEqual(body["iamConfiguration"]["publicAccessPrevention"], "enforced")
        self.assertTrue(body["iamConfiguration"]["uniformBucketLevelAccess"]["enabled"])
        self.assertEqual(workflow.read_settings()["prepared"], workflow.resource_key(args))
        self.assertNotIn("secret-in-memory", workflow.settings_path().read_text())
        with patch.object(workflow, "setup") as setup:
            workflow.ensure_setup(args)
            setup.assert_not_called()

    def test_existing_bucket_with_wrong_owner_or_privacy_is_not_modified(self):
        for info in [
            self.private_bucket() | {"projectNumber": "98765"},
            self.private_bucket() | {"iamConfiguration": {"publicAccessPrevention": "inherited"}},
        ]:
            args = workflow.resolve_defaults(self.args(command="setup"))
            with (
                self.subTest(info=info),
                patch.object(workflow.shutil, "which", return_value="installed"),
                patch.object(audio, "access_token", return_value="secret"),
                patch.object(workflow, "gcloud", side_effect=["True", "12345", ""]),
                patch.object(captions, "cloud_json", return_value=info) as cloud,
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(ValueError):
                    workflow.setup(args)
                self.assertEqual(cloud.call_count, 1)
                self.assertFalse(workflow.settings_path().exists())

    def test_eu_setup_checks_bucket_location_and_uses_separate_bucket_name(self):
        self.save()
        args = workflow.resolve_defaults(self.args(command="setup", location="eu"))
        self.assertTrue(args.bucket.endswith("-eu"))
        with (
            patch.object(workflow.shutil, "which", return_value="installed"),
            patch.object(audio, "access_token", return_value="secret"),
            patch.object(workflow, "gcloud", side_effect=["True", "12345", ""]),
            patch.object(captions, "cloud_json", return_value=self.private_bucket()),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaisesRegex(ValueError, "EU transcription"):
                workflow.setup(args)

    def test_unsupported_saved_caption_model_stops_before_cloud_or_synthesis(self):
        self.save(caption_model="unsupported")
        args = workflow.resolve_defaults(self.args())
        with (
            patch.object(workflow, "ensure_setup") as setup,
            patch.object(audio, "generate") as generate,
        ):
            with self.assertRaisesRegex(ValueError, "Saved caption model"):
                workflow.make(args)
            setup.assert_not_called()
            generate.assert_not_called()

    def test_disabled_billing_stops_before_api_or_bucket_changes(self):
        args = workflow.resolve_defaults(self.args(command="setup"))
        with (
            patch.object(workflow.shutil, "which", return_value="installed"),
            patch.object(audio, "access_token", return_value="secret"),
            patch.object(workflow, "gcloud", return_value="False") as cli,
            patch.object(captions, "cloud_json") as cloud,
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaisesRegex(ValueError, "Billing is disabled"):
                workflow.setup(args)
        self.assertEqual(cli.call_count, 1)
        cloud.assert_not_called()

    def test_latest_recording_lookup_and_automatic_speaker_detection(self):
        for index, date in enumerate(["2026-01-01", "2026-02-01"]):
            directory = self.root / "artifacts/audio/workbench-001" / str(index)
            directory.mkdir(parents=True)
            (directory / "episode.mp3").write_bytes(str(index).encode())
            audio.write_json(
                directory / "episode.json",
                dict(
                    id="workbench-001",
                    generated_at=date,
                    audio_sha256=audio.digest(str(index).encode()),
                    language="en-GB",
                    speakers=[{}, {}],
                ),
            )
        args = self.args(command="captions", audio="workbench-001", model="chirp_3")
        workflow.prepare_captions(args)
        self.assertEqual(args.audio.parent.name, "1")
        self.assertTrue(args.diarize)
        self.assertEqual(args.language, "en-GB")
        args.audio.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "latest saved MP3 changed"):
            workflow.find_audio("workbench-001")

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools unavailable"
    )
    def test_make_resumes_without_resynthesis_resubmission_or_reencoding(self):
        args = workflow.resolve_defaults(self.args())
        self.save(prepared=workflow.resource_key(args))

        def submit(url, project, auth, payload=None):
            uri = payload["files"][0]["uri"]
            self.assertIn("diarizationConfig", payload["config"]["features"])
            return operation(uri, done=False)

        with (
            patch.object(workflow.shutil, "which", return_value="installed"),
            patch.object(audio, "access_token", return_value="secret"),
            patch.object(audio, "synthesize", return_value=wav_bytes(4)) as synth,
            patch.object(captions, "ensure_upload", return_value="1") as upload,
            patch.object(captions, "cloud_json", side_effect=submit) as cloud,
            redirect_stdout(io.StringIO()),
        ):
            workflow.make(args)
            self.assertEqual(cloud.call_count, 1)
            initial_chunks = synth.call_count
            self.assertGreater(initial_chunks, 0)
            path = workflow.find_audio("workbench-001")
            audio_before = path.read_bytes()
            metadata_before = path.with_name("episode.json").read_bytes()
            uri = f"gs://{args.bucket}/field-notes-input/{audio.digest(audio_before)}.mp3"
            cloud.side_effect = None
            cloud.return_value = operation(uri)
            workflow.make(args)
            self.assertEqual(cloud.call_count, 2)  # POST once, then GET saved operation
            self.assertEqual(len(cloud.call_args.args), 3)
            workflow.make(args)
            self.assertEqual(cloud.call_count, 2)
            self.assertEqual(synth.call_count, initial_chunks)
            self.assertEqual(upload.call_count, 1)
            self.assertEqual(path.read_bytes(), audio_before)
            self.assertEqual(path.with_name("episode.json").read_bytes(), metadata_before)
            with zipfile.ZipFile(path.parent.parent / "episode.zip") as archive:
                self.assertEqual(archive.read("audio.mp3"), audio_before)
                self.assertEqual(
                    set(archive.namelist()),
                    {
                        "listen.html",
                        "audio.mp3",
                        "captions.srt",
                        "captions.vtt",
                        "transcript.txt",
                        "words.json",
                        "cues.json",
                        "comparison.json",
                        "captions.json",
                        "episode.json",
                        "input-script.txt",
                    },
                )
                self.assertNotIn(b"secret", archive.read("episode.json"))

    def test_polling_retries_transient_reads_but_never_permission_rejections(self):
        with (
            patch.object(
                captions,
                "cloud_json",
                side_effect=[captions.CloudError({"http_status": 502}), {"done": True}],
            ) as cloud,
            patch.object(captions.time, "sleep"),
            redirect_stdout(io.StringIO()),
        ):
            self.assertTrue(captions.poll_operation("url", "project", "gcloud")["done"])
            self.assertTrue(all(len(call.args) == 3 for call in cloud.call_args_list))
        with patch.object(
            captions, "cloud_json", side_effect=captions.CloudError({"http_status": 403})
        ) as cloud:
            with self.assertRaises(captions.CloudError):
                captions.poll_operation("url", "project", "gcloud")
            self.assertEqual(cloud.call_count, 1)

    def test_offline_plan_needs_neither_project_nor_gcloud(self):
        with (
            patch.object(workflow, "gcloud", side_effect=AssertionError("No Cloud calls")),
            patch.object(audio, "access_token", side_effect=AssertionError("No authentication")),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(cli.main(["plan", "note-001"]), 0)


if __name__ == "__main__":
    unittest.main()
