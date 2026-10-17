"""A renderer failure becomes a plain sentence; retrying redoes only the video."""

import argparse
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import patch

from field_notes_audio import audio
from field_notes_audio.production import renderer_process as rp
from field_notes_audio.production import runner
from field_notes_audio.production.renderer_process import RenderFailed
from field_notes_audio.storage import write_json
from field_notes_studio.readiness_models import split_details

COMMAND = ["node", "/very/long/path/video/render.mjs", "props.json"]
TIMEOUT = (
    "Error: Timeout (120000ms) exceeded rendering the component at frame 1553\n"
    'increase the timeout using "timeoutInMilliseconds"'
)


class FakeProcess:
    """Stands in for Popen: no real subprocess is started."""

    def __init__(self, stderr="", code=1, hang=False):
        self.stderr = io.StringIO(stderr)
        self.code, self.hang, self.killed = code, hang, False

    def wait(self, timeout=None):
        if self.hang and not self.killed:
            raise TimeoutExpired(COMMAND, timeout)
        return self.code

    def kill(self):
        self.killed = True


def spawn(**kwargs):
    return patch.object(rp.subprocess, "Popen", return_value=FakeProcess(**kwargs))


class RenderFailureTests(unittest.TestCase):
    def fail(self, stderr, code=1, **kwargs):
        with spawn(stderr=stderr, code=code, **kwargs), patch("sys.stderr"):
            with self.assertRaises(RenderFailed) as caught:
                rp.run_renderer(COMMAND, Path("."))
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

    def test_hour_long_hang_strips_ansi_and_text_stderr_and_missing_node_is_plain(self):
        sentence, details = self.fail("\x1b[31mpartial\x1b[0m  \n", hang=True)
        self.assertIn("over an hour", sentence)
        self.assertEqual(details, "partial")
        sentence, details = self.fail("", hang=True)
        self.assertIn("over an hour", sentence)
        self.assertTrue(details)
        with patch.object(rp.subprocess, "Popen", side_effect=FileNotFoundError("node")):
            with self.assertRaisesRegex(RenderFailed, "Node is missing"):
                rp.run_renderer(COMMAND, Path("."))

    def test_stderr_is_bounded_and_echoed_live(self):
        noise = "".join(f"line {n}\n" for n in range(5000))
        with spawn(stderr=noise), patch("sys.stderr", new=io.StringIO()) as shown:
            with self.assertRaises(RenderFailed) as caught:
                rp.run_renderer(COMMAND, Path("."))
        self.assertLessEqual(len(str(caught.exception)), 2200)
        self.assertIn("line 4999", str(caught.exception))
        self.assertNotIn("line 10\n", str(caught.exception))
        self.assertIn("line 0\n", shown.getvalue())

    def test_remotion_validation_and_missing_input_are_not_called_busy(self):
        for text in (
            'Error: "timeoutInMilliseconds" must be a number larger than 7000',
            "Error: ENOENT: no such file or directory, open '/tmp/x/props.json'",
        ):
            sentence, _ = self.fail(text)
            self.assertIn("stopped unexpectedly", sentence)
            self.assertNotIn("busy", sentence)
        self.assertIn("30 seconds", self.fail("Timeout (30000ms) exceeded rendering at frame 1")[0])
        self.assertIn("tool is missing", self.fail("Error: spawn ENOENT: npx not found")[0])

    def test_unparseable_load_falls_back_to_the_configured_workers(self):
        with patch.object(rp.os, "getloadavg", side_effect=OSError):
            self.assertEqual(rp.renderer_concurrency(3), 3)

    def test_busy_machine_gets_fewer_frame_workers_but_at_least_one(self):
        with patch.object(rp.os, "sched_getaffinity", return_value=set(range(8))):
            with patch.object(rp.os, "getloadavg", return_value=(9.0, 0, 0)):
                self.assertEqual(rp.renderer_concurrency(4), 1)
            with patch.object(rp.os, "getloadavg", return_value=(5.5, 0, 0)):
                self.assertEqual(rp.renderer_concurrency(4), 2)
            with patch.object(rp.os, "getloadavg", return_value=(0.5, 0, 0)):
                self.assertEqual(rp.renderer_concurrency(4), 4)

    def test_renderer_script_passes_a_configurable_frame_timeout_everywhere(self):
        source = (audio.ROOT / "video/render.mjs").read_text()
        self.assertIn("MG_RENDER_FRAME_TIMEOUT_MS", source)
        self.assertGreaterEqual(source.count("timeoutInMilliseconds"), 5)  # constant + 4 calls

    def test_bad_timeout_values_fall_back_with_a_warning(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node unavailable")
        source = (audio.ROOT / "video/render.mjs").read_text()
        start = source.index("const configuredTimeout")
        end = source.index("const started")
        script = source[start:end] + "console.log(timeoutInMilliseconds);"
        for value, expected, warned in (
            ("5000", "120000", True),
            ("1.5", "120000", True),
            ("3000000000", "120000", True),
            ("1e400", "120000", True),
            ("abc", "120000", True),
            ("7000", "7000", False),
            ("2147483647", "2147483647", False),
        ):
            done = subprocess.run(
                [node, "--input-type=module", "-e", script],
                env={**os.environ, "MG_RENDER_FRAME_TIMEOUT_MS": value},
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(done.stdout.strip(), expected, value)
            self.assertEqual("must be a whole number" in done.stderr, warned, value)


class IdentityTests(unittest.TestCase):
    """The cache identity depends on bytes-affecting settings, never on load or worker count."""

    def identity(self, concurrency, load):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "video/node_modules/@remotion/renderer").mkdir(parents=True)
            (root / "video/render.mjs").write_text("// fixture")
            (root / "docs/assets").mkdir(parents=True)
            (root / "docs/assets/moth-mark.svg").write_text("<svg/>")
            (root / "docs/assets/podcast-cover.png").write_bytes(b"png")
            edition = root / "artifacts/production/fixture/edition"
            edition.mkdir(parents=True)
            (edition / "master.wav").write_bytes(b"wav")
            (edition / "cues.json").write_text("{}")
            write_json(
                edition / "production.json",
                {"fingerprint": "f", "timeline_duration_seconds": 4, "files": {}},
            )
            settings = {
                "video": {"width": 1920, "height": 1080, "fps": 30, "concurrency": concurrency}
            }
            args = argparse.Namespace(preview_seconds=None, browser_executable=None)
            seen = []
            real = runner.fingerprint

            def record(value):
                seen.append(real(value))
                return seen[-1]

            with (
                patch.object(runner, "fingerprint", record),
                patch.object(rp.os, "getloadavg", return_value=(load, 0, 0)),
                patch.object(runner, "cache_valid", return_value=False),
                patch(
                    "field_notes_audio.production.video.render_video",
                    side_effect=RenderFailed("stop here"),
                ) as render,
                self.assertRaises(RenderFailed),
            ):
                runner.produce_video({"id": "fixture"}, root, edition, settings, args)
            return seen[0], render.call_args

    def test_identity_is_equal_across_load_and_concurrency(self):
        first, _ = self.identity(4, 0.0)
        self.assertEqual(first, self.identity(4, 9.0)[0])
        self.assertEqual(first, self.identity(1, 0.0)[0])
        self.assertEqual(first, self.identity(8, 20.0)[0])


if __name__ == "__main__":
    unittest.main()
