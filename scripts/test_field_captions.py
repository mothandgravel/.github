"""Offline caption/recovery tests with synthetic audio and documented V2 response shapes."""
import argparse
import base64
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import field_captions as captions
from field_audio import digest


def operation(uri, done=True):
    result = {"name": "projects/12345/locations/us/operations/test-job", "done": done}
    if done:
        result["response"] = {"results": {uri: {"inlineResult": {
            "transcript": {"results": [{"alternatives": [{
                "transcript": "Hello world. Another question.", "words": [
                    {"word": "Hello", "startOffset": "0s", "endOffset": "0.4s", "speakerLabel": "1"},
                    {"word": "world.", "startOffset": "0.4s", "endOffset": "0.9s", "speakerLabel": "1"},
                    {"word": "Another", "startOffset": "1.1s", "endOffset": "1.4s", "speakerLabel": "2"},
                    {"word": "question.", "startOffset": "1.4s", "endOffset": "1.9s", "speakerLabel": "2"}]}]}]},
            "srtCaptions": "1\n00:00:00,000 --> 00:00:01,000\nHello world.\n\n2\n00:00:01,100 --> 00:00:02,000\nAnother question.\n",
            "vttCaptions": "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello world.\n\n00:00:01.100 --> 00:00:02.000\nAnother question.\n"}}}}
    return result


class CaptionFormatTests(unittest.TestCase):
    def test_exported_timings_and_detected_ids_follow_the_recording(self):
        uri = "gs://bucket/source.mp3"
        recognized = captions.extract_recognition(operation(uri), uri, 4)
        self.assertEqual(recognized["words"][0]["start"], 0)
        self.assertEqual(recognized["cues"][0]["speakers"], ["1"])
        self.assertEqual(recognized["cues"][1]["speakers"], ["2"])
        self.assertNotIn("Explore", json.dumps(recognized))

    def test_wrong_input_uri_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "submitted audio URI"):
            captions.extract_recognition(operation("gs://bucket/old.mp3"), "gs://bucket/new.mp3", 4)

    def test_caption_timing_outside_audio_and_overlaps_are_rejected(self):
        for text in ["1\n00:00:00,000 --> 00:00:06,000\nToo long.",
                     "1\n00:00:00,000 --> 00:00:02,000\nOne.\n\n2\n00:00:01,000 --> 00:00:03,000\nTwo."]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                captions.parse_captions(text, 4)

    def test_srt_and_vtt_disagreement_is_rejected(self):
        uri = "gs://bucket/source.mp3"
        payload = operation(uri)
        payload["response"]["results"][uri]["inlineResult"]["vttCaptions"] = \
            payload["response"]["results"][uri]["inlineResult"]["vttCaptions"].replace("00:00:01.100", "00:00:01.300")
        with self.assertRaisesRegex(ValueError, "timings differ"):
            captions.extract_recognition(payload, uri, 4)

    def test_malformed_word_offset_is_rejected(self):
        uri = "gs://bucket/source.mp3"
        payload = operation(uri)
        payload["response"]["results"][uri]["inlineResult"]["transcript"]["results"][0]["alternatives"][0]["words"][0]["endOffset"] = "NaNs"
        with self.assertRaises(ValueError):
            captions.extract_recognition(payload, uri, 4)

    def test_script_comparison_keeps_a_missing_negation_visible(self):
        comparison = captions.compare_script("Explore: It cannot establish safety.", "It can establish safety.", ["Explore"])
        self.assertEqual(comparison["review_status"], "pending")
        self.assertEqual(comparison["differences"][0]["script"], "cannot")
        self.assertEqual(comparison["differences"][0]["recognized"], "can")
        self.assertEqual(captions.compare_script("Moth & Gravel", "Moth and Gravel", [])["differences"], [])

    def test_operation_name_cannot_redirect_authenticated_requests(self):
        for name in ["https://other.example", "projects/other-project/locations/us/operations/job",
                     "projects/12345/locations/eu/operations/job", "projects/12345/locations/us/operations/../other"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                captions.operation_url(name, "us", "pilot-project")

    def test_preview_escapes_transcription_text_and_title(self):
        attack = '</script><script>alert("bad")</script>'
        page = captions.listening_preview(attack, [{"start": 0, "end": 1, "text": attack, "speakers": []}])
        self.assertNotIn(attack, page)
        self.assertIn("\\u003c/script>", page)
        self.assertIn("&lt;/script&gt;", page)

    def test_input_upload_is_create_only_and_reuses_matching_content(self):
        content = b"synthetic-mp3"
        metadata = {"size": str(len(content)), "md5Hash": base64.b64encode(hashlib.md5(content).digest()).decode(), "generation": "1"}
        private = {"iamConfiguration": {"publicAccessPrevention": "enforced"}}
        with patch.object(captions, "cloud_json", side_effect=[private, captions.CloudError({"http_status": 404}), metadata]) as cloud:
            self.assertEqual(captions.ensure_upload(content, "bucket", "input.mp3", "pilot-project", "gcloud"), "1")
            self.assertIn("ifGenerationMatch=0", cloud.call_args[0][0])
        with patch.object(captions, "cloud_json", side_effect=[private, metadata]) as cloud:
            captions.ensure_upload(content, "bucket", "input.mp3", "pilot-project", "gcloud")
            self.assertEqual(cloud.call_count, 2)
        with patch.object(captions, "cloud_json", return_value={"iamConfiguration": {"publicAccessPrevention": "inherited"}}):
            with self.assertRaisesRegex(ValueError, "public access prevention"):
                captions.ensure_upload(content, "bucket", "input.mp3", "pilot-project", "gcloud")

    def test_different_storage_content_is_not_overwritten(self):
        private = {"iamConfiguration": {"publicAccessPrevention": "enforced"}}
        with patch.object(captions, "cloud_json", side_effect=[private, {"size": "4", "md5Hash": "wrong"}]) as cloud:
            with self.assertRaisesRegex(ValueError, "nothing was overwritten"):
                captions.ensure_upload(b"four", "bucket", "input.mp3", "pilot-project", "gcloud")
            self.assertEqual(cloud.call_count, 2)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools unavailable")
class CaptionRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_directory = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.fixture_directory.name) / "audio.mp3"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "sine=frequency=300:duration=4", "-ar", "24000", "-ac", "1", "-b:a", "96k",
                        str(cls.fixture)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.audio = self.root / "episode.mp3"
        self.audio.write_bytes(self.fixture.read_bytes())
        self.script = "Explore: Hello world.\nQuestion: Another question.\n"
        (self.root / "transcript.txt").write_text(self.script)
        (self.root / "episode.json").write_text(json.dumps({"title": "Caption pilot",
            "audio_sha256": digest(self.audio.read_bytes()), "script_sha256": digest(self.script.strip().encode()),
            "speakers": [{"alias": "Explore"}, {"alias": "Question"}]}))
        self.uri = "gs://pilot-bucket/field-notes-input/" + digest(self.audio.read_bytes()) + ".mp3"

    def args(self, **changes):
        values = dict(audio=self.audio, project="pilot-project", bucket="pilot-bucket", location="us",
                      model="chirp_3", language="en-US", diarize=True, auth="gcloud", script=None,
                      dry_run=False, wait=0, retry_uncertain=False, restart_failed=False)
        values.update(changes)
        return argparse.Namespace(**values)

    def test_completed_job_exports_and_reuses_without_google_requests(self):
        with patch.object(captions.shutil, "which", return_value="installed"), \
             patch.object(captions, "ensure_upload", return_value="1") as upload, \
             patch.object(captions, "cloud_json", return_value=operation(self.uri)) as cloud, \
             redirect_stdout(io.StringIO()):
            captions.run(self.args())
            captions.run(self.args())
            self.assertEqual(cloud.call_count, 1)
            self.assertEqual(upload.call_count, 1)
        output = next((self.root / "captions").iterdir())
        self.assertEqual((self.root / "transcript.txt").read_text(), self.script)
        self.assertEqual((output / "transcript.txt").read_text().strip(), "Hello world. Another question.")
        self.assertEqual(json.loads((output / "comparison.json").read_text())["differences"], [])
        self.assertEqual(json.loads((output / "captions.json").read_text())["audio_sha256"], digest(self.audio.read_bytes()))
        self.assertEqual((output / "audio.mp3").read_bytes(), self.audio.read_bytes())
        self.assertTrue((output / "listen.html").exists())

    def test_pending_job_resumes_polling_instead_of_resubmitting(self):
        with patch.object(captions.shutil, "which", return_value="installed"), \
             patch.object(captions, "ensure_upload", return_value="1") as upload, \
             patch.object(captions, "cloud_json", side_effect=[operation(self.uri, False), operation(self.uri)]) as cloud, \
             redirect_stdout(io.StringIO()):
            captions.run(self.args())
            captions.run(self.args())
            self.assertEqual(upload.call_count, 1)
            self.assertEqual(len(cloud.call_args_list[0].args), 4)  # submission with request body
            self.assertEqual(len(cloud.call_args_list[1].args), 3)  # poll only

    def test_lost_submission_acknowledgement_requires_explicit_retry(self):
        with patch.object(captions.shutil, "which", return_value="installed"), \
             patch.object(captions, "ensure_upload", return_value="1"), \
             patch.object(captions, "cloud_json", side_effect=TimeoutError) as cloud, \
             redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "No valid transcription operation"):
                captions.run(self.args())
            with self.assertRaisesRegex(ValueError, "no saved acknowledgement"):
                captions.run(self.args())
            self.assertEqual(cloud.call_count, 1)

    def test_file_failure_is_not_misreported_as_completed_captions(self):
        failed = operation(self.uri)
        failed["response"]["results"][self.uri] = {"error": {"code": 7, "message": "Input access denied"}}
        with patch.object(captions.shutil, "which", return_value="installed"), \
             patch.object(captions, "ensure_upload", return_value="1"), \
             patch.object(captions, "cloud_json", return_value=failed), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "transcription job failed"):
                captions.run(self.args())
        output = next((self.root / "captions").iterdir())
        self.assertEqual(json.loads((output / "state.json").read_text())["status"], "failed")
        self.assertFalse((output / "captions.srt").exists())

    def test_failed_job_restart_can_resume_with_the_same_command(self):
        failed = operation(self.uri)
        failed["response"]["results"][self.uri] = {"error": {"code": 7, "message": "Input access denied"}}
        with patch.object(captions.shutil, "which", return_value="installed"), \
             patch.object(captions, "ensure_upload", return_value="1"), \
             patch.object(captions, "cloud_json", side_effect=[failed, operation(self.uri, False), operation(self.uri)]) as cloud, \
             redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                captions.run(self.args())
            captions.run(self.args(restart_failed=True))
            captions.run(self.args(restart_failed=True))
            self.assertEqual(len(cloud.call_args_list[-1].args), 3)  # resume, not another submission
        output = next((self.root / "captions").iterdir())
        self.assertTrue((output / "failed-operation.json").exists())
        self.assertTrue((output / "captions.srt").exists())

    def test_rejected_submission_can_retry_after_permissions_are_repaired(self):
        with patch.object(captions.shutil, "which", return_value="installed"), \
             patch.object(captions, "ensure_upload", return_value="1"), \
             patch.object(captions, "cloud_json", side_effect=[captions.CloudError({"http_status": 403}), operation(self.uri)]), \
             redirect_stdout(io.StringIO()):
            with self.assertRaises(captions.CloudError):
                captions.run(self.args())
            captions.run(self.args())
        output = next((self.root / "captions").iterdir())
        self.assertTrue((output / "captions.srt").exists())

    def test_simultaneous_caption_commands_cannot_both_enter_the_run(self):
        with captions.run_lock(self.root):
            with self.assertRaisesRegex(ValueError, "Another caption command"):
                with captions.run_lock(self.root):
                    self.fail("The competing command acquired the lock")

    def test_dry_run_and_changed_audio_never_authenticate(self):
        with patch.object(captions, "cloud_json") as cloud, patch.object(captions, "ensure_upload") as upload, \
             redirect_stdout(io.StringIO()):
            captions.run(self.args(dry_run=True))
            self.assertFalse((self.root / "captions").exists())
            self.audio.write_bytes(self.audio.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "differs from its episode metadata"):
                captions.run(self.args())
            cloud.assert_not_called()
            upload.assert_not_called()

    def test_changed_script_is_not_silently_used_for_comparison(self):
        (self.root / "transcript.txt").write_text("A different narration.")
        with self.assertRaisesRegex(ValueError, "input script differs"):
            captions.run(self.args(dry_run=True))


if __name__ == "__main__":
    unittest.main()
