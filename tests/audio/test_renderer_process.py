"""Only synthetic Python children; no renderer, media, Cloud or dependencies."""

import io
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_audio.production import renderer_process as rp


class ChunkStream(io.BytesIO):
    def __init__(self, chunks):
        super().__init__()
        self.chunks = iter(chunks)
        self.requested = []

    def read1(self, size):
        self.requested.append(size)
        return next(self.chunks, b"")


class Process:
    def __init__(self, chunks, code=1):
        self.stderr = ChunkStream(chunks)
        self.code = code

    def wait(self, timeout=None):
        return self.code


class RendererProcessTests(unittest.TestCase):
    def test_chunks_decode_split_utf8_and_flush_a_truncated_final_character(self):
        process = Process([b"progress ", b"\xe2", b"\x82", b"\xac", b"\xe2\x82"])
        with (
            patch.object(rp.subprocess, "Popen", return_value=process) as popen,
            patch("sys.stderr", new=io.StringIO()) as echoed,
        ):
            with self.assertRaises(rp.RenderFailed) as failure:
                rp.run_renderer(["synthetic"], Path("."))
        self.assertEqual(echoed.getvalue(), "progress €�")
        self.assertIn("progress €�", str(failure.exception))
        self.assertTrue(process.stderr.closed)
        self.assertTrue(all(size == rp.STDERR_CHUNK_BYTES for size in process.stderr.requested))
        # stdout still inherits the caller's destination; stderr alone is piped.
        self.assertEqual(popen.call_args.kwargs, {"cwd": Path("."), "stderr": subprocess.PIPE})

    def test_text_newlines_remain_normalized_across_chunk_boundaries(self):
        process = Process([b"a\r", b"\nb\r", b"c\r"], code=0)
        with (
            patch.object(rp.subprocess, "Popen", return_value=process),
            patch("sys.stderr", new=io.StringIO()) as echoed,
        ):
            rp.run_renderer(["synthetic"], Path("."))
        self.assertEqual(echoed.getvalue(), "a\nb\nc\n")

    def test_live_output_without_newline_arrives_before_the_child_can_exit(self):
        observed = threading.Event()
        errors = []

        class Echo(io.StringIO):
            def write(self, text):
                result = super().write(text)
                if "progress without newline" in self.getvalue():
                    observed.set()
                return result

        with tempfile.TemporaryDirectory() as directory:
            release = Path(directory) / "release"
            code = (
                "import os,time; from pathlib import Path; "
                "os.write(2,b'progress without newline'); "
                f"release=Path({str(release)!r}); "
                "exec('while not release.exists(): time.sleep(0.01)')"
            )

            def render():
                try:
                    rp.run_renderer([sys.executable, "-c", code], Path(directory), timeout=10)
                except BaseException as exc:
                    errors.append(exc)

            with patch("sys.stderr", new=Echo()):
                thread = threading.Thread(target=render)
                thread.start()
                try:
                    self.assertTrue(observed.wait(3), "stderr waited for newline or child exit")
                    self.assertTrue(thread.is_alive(), "child must still be waiting for release")
                finally:
                    release.touch()
                    thread.join(timeout=12)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])

    def test_retained_context_is_bounded_even_for_one_huge_line(self):
        process = Process([b"x" * rp.STDERR_CHUNK_BYTES] * 300 + [b"last diagnostic"])
        failure = rp._failure
        captured = []

        def capture(returncode, stderr, empty):
            captured.append(stderr)
            return failure(returncode, stderr, empty)

        with (
            patch.object(rp.subprocess, "Popen", return_value=process),
            patch.object(rp, "_failure", side_effect=capture),
            patch("sys.stderr", new=io.StringIO()),
        ):
            with self.assertRaises(rp.RenderFailed) as caught:
                rp.run_renderer(["synthetic"], Path("."))
        self.assertLessEqual(len(captured[0]), rp.STDERR_CHUNK_BYTES * rp.STDERR_TAIL_CHUNKS)
        self.assertTrue(captured[0].endswith("last diagnostic"))
        self.assertLessEqual(len(str(caught.exception).split(rp.DETAILS_MARK)[1]), rp.TAIL_CHARS)

    def test_existing_failure_causes_survive_chunk_boundaries(self):
        cases = [
            (b"Timeout (120000ms) exceeded rendering at frame 2", "2 minutes"),
            (b"FATAL ERROR: JavaScript heap out of memory", "ran out of memory"),
            (b"Error: Cannot find module 'renderer'", "tool is missing"),
            (b"unexpected failure", "stopped unexpectedly"),
        ]
        for stderr, expected in cases:
            with self.subTest(expected=expected):
                process = Process([stderr[index : index + 3] for index in range(0, len(stderr), 3)])
                with (
                    patch.object(rp.subprocess, "Popen", return_value=process),
                    patch("sys.stderr"),
                ):
                    with self.assertRaisesRegex(rp.RenderFailed, expected):
                        rp.run_renderer(["synthetic"], Path("."))

    def test_timeout_kills_reaps_and_closes_stderr_without_a_reader_thread(self):
        children = []
        popen = subprocess.Popen
        readers = {
            thread.ident for thread in threading.enumerate() if thread.name == "renderer-stderr"
        }

        def launch(*args, **kwargs):
            child = popen(*args, **kwargs)
            children.append(child)
            return child

        with tempfile.TemporaryDirectory() as directory:
            code = "import os,time; os.write(2,b'partial progress'); time.sleep(60)"
            with patch.object(rp.subprocess, "Popen", side_effect=launch), patch("sys.stderr"):
                with self.assertRaisesRegex(rp.RenderFailed, "over an hour"):
                    rp.run_renderer([sys.executable, "-c", code], Path(directory), timeout=0.2)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())
        self.assertTrue(children[0].stderr.closed)
        self.assertEqual(
            {thread.ident for thread in threading.enumerate() if thread.name == "renderer-stderr"},
            readers,
        )


if __name__ == "__main__":
    unittest.main()
