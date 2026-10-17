"""A renderer failure becomes a plain sentence; retrying redoes only the video."""

import argparse
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

from field_notes_audio import audio
from field_notes_audio.production import runner, video
from field_notes_audio.production.video import RenderFailed
from field_notes_audio.storage import read_object, write_json
from field_notes_studio.readiness_models import split_details

COMMAND = ["node", "/very/long/path/video/render.mjs", "props.json"]
TIMEOUT = (
    "Error: Timeout (30000ms) exceeded rendering the component at frame 1553\n"
    'increase the timeout using "timeoutInMilliseconds"'
)


def failing(stderr, code=1):
    return patch.object(
        video.subprocess, "run", return_value=CompletedProcess(COMMAND, code, "", stderr)
    )


class RenderFailureTests(unittest.TestCase):
    def fail(self, stderr, code=1):
        with failing(stderr, code), patch("sys.stderr"):
            with self.assertRaises(RenderFailed) as caught:
                video.run_renderer(COMMAND, Path("."))
        return split_details(str(caught.exception))

    def test_timeout_names_the_cause_the_saved_work_and_the_retry(self):
        sentence, details = self.fail(TIMEOUT)
        self.assertIn("a frame took longer than 2 minutes", sentence)
        self.assertIn("busy", sentence)
        self.assertIn("Your audio and captions are saved", sentence)
        self.assertIn("Make it again", sentence)
        self.assertIn("frame 1553", details)

    def test_memory_missing_tool_and_unknown_failures_are_classified(self):
        self.assertIn(
            "ran out of memory", self.fail("FATAL ERROR: JavaScript heap out of memory")[0]
        )
        self.assertIn("ran out of memory", self.fail("", -9)[0])
        self.assertIn(
            "tool is missing", self.fail("Error: Cannot find module '@remotion/renderer'")[0]
        )
        sentence, details = self.fail("something odd")
        self.assertIn("stopped unexpectedly", sentence)
        self.assertEqual(details, "something odd")

    def test_message_never_shows_the_python_error_repr_or_paths(self):
        sentence, _ = self.fail(TIMEOUT)
        for raw in ("CalledProcessError", "non-zero exit status", "/very/long/path", "node"):
            self.assertNotIn(raw, sentence)

    def test_silent_failure_still_has_details(self):
        self.assertIn("printed nothing", self.fail("")[1])

    def test_hour_long_hang_and_missing_node_are_plain(self):
        with patch.object(video.subprocess, "run", side_effect=TimeoutExpired(COMMAND, 3600)):
            with self.assertRaisesRegex(RenderFailed, "over an hour"):
                video.run_renderer(COMMAND, Path("."))
        with patch.object(video.subprocess, "run", side_effect=FileNotFoundError("node")):
            with self.assertRaisesRegex(RenderFailed, "Node is missing"):
                video.run_renderer(COMMAND, Path("."))

    def test_busy_machine_gets_fewer_frame_workers_but_at_least_one(self):
        with patch.object(video.os, "cpu_count", return_value=8):
            with patch.object(video.os, "getloadavg", return_value=(9.0, 0, 0)):
                self.assertEqual(video.renderer_concurrency(4), 1)
            with patch.object(video.os, "getloadavg", return_value=(5.5, 0, 0)):
                self.assertEqual(video.renderer_concurrency(4), 2)
            with patch.object(video.os, "getloadavg", return_value=(0.5, 0, 0)):
                self.assertEqual(video.renderer_concurrency(4), 4)

    def test_renderer_script_passes_a_configurable_frame_timeout_everywhere(self):
        source = (audio.ROOT / "video/render.mjs").read_text()
        self.assertIn("MG_RENDER_FRAME_TIMEOUT_MS", source)
        self.assertGreaterEqual(source.count("timeoutInMilliseconds"), 5)  # constant + 4 calls


class RetryTests(unittest.TestCase):
    def test_retry_after_a_render_failure_redoes_only_the_video(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            config = root / "settings.json"
            write_json(config, audio_defaults())
            edition = root / "artifacts/production/fixture/fingerprint"
            edition.mkdir(parents=True)
            write_json(
                edition / "production.json", {"files": {"master.wav": "m", "cues.json": "c"}}
            )
            rendered = edition / "video/abc"
            rendered.mkdir(parents=True)
            args = argparse.Namespace(
                episode="fixture",
                config=config,
                output_dir=None,
                audio_only=False,
                preview_seconds=None,
                browser_executable=None,
            )
            with (
                patch.object(runner.site, "load_entries", return_value=[{"id": "fixture"}]),
                patch.object(runner, "preflight"),
                patch.object(runner, "produce_audio", return_value=edition) as saved_audio,
                patch.object(
                    runner,
                    "produce_video",
                    side_effect=[RenderFailed("The video renderer stopped."), rendered],
                ) as render,
            ):
                with self.assertRaises(RenderFailed):
                    runner.produce(args, root)
                directory = root / "artifacts/production/fixture"
                self.assertIsNone(read_object(directory / "latest.json")["video"])
                runner.produce(args, root)
            # Audio is a verified cache hit in production (no narration or caption request exists
            # in this path); the retry never leaves the produce pipeline and only the video reruns.
            self.assertEqual(saved_audio.call_count, 2)
            self.assertEqual(render.call_count, 2)
            self.assertEqual(
                read_object(directory / "latest.json")["video"], "fingerprint/video/abc"
            )


def audio_defaults():
    import json

    return json.loads((audio.ROOT / "audio/production/settings.json").read_text())


if __name__ == "__main__":
    unittest.main()
