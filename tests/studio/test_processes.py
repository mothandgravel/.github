"""Native and WSL file-picker paths must point at the existing media, never copy it."""

import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from field_notes_studio.processes import upload_path


class UploadPathTests(unittest.TestCase):
    def test_native_picker_receives_the_original_path(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("platform.release", return_value="linux"),
            patch("subprocess.run") as run,
        ):
            self.assertEqual(upload_path(Path("/tmp/episode.mp4")), "/tmp/episode.mp4")
            run.assert_not_called()

    def test_wsl_converts_to_a_windows_picker_path_and_handles_spaces(self):
        expected = r"\\wsl.localhost\Ubuntu\home\user\My show\episode.mp4"
        path = Path("/home/user/My show/episode.mp4")
        with (
            patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
            patch("subprocess.run", return_value=SimpleNamespace(stdout=expected + "\n")) as run,
        ):
            self.assertEqual(upload_path(path), expected)
            run.assert_called_once_with(
                ["wslpath", "-w", str(path)], capture_output=True, text=True, check=True, timeout=5
            )

    def test_wsl_kernel_is_detected_even_without_the_distribution_variable(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("platform.release", return_value="6.6.87-microsoft-standard-WSL2"),
            patch("subprocess.run", return_value=SimpleNamespace(stdout="C:\\episode.mp4\n")),
        ):
            self.assertEqual(upload_path(Path("/mnt/c/episode.mp4")), "C:\\episode.mp4")

    def test_translation_failures_do_not_copy_a_misleading_linux_path(self):
        with patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True):
            for error in (FileNotFoundError(), subprocess.TimeoutExpired("wslpath", 5)):
                with (
                    self.subTest(error=error),
                    patch("subprocess.run", side_effect=error),
                    self.assertRaisesRegex(ValueError, "Windows upload path"),
                ):
                    upload_path(Path("/tmp/episode.mp4"))
            with (
                patch("subprocess.run", return_value=SimpleNamespace(stdout="\n")),
                self.assertRaisesRegex(ValueError, "empty upload path"),
            ):
                upload_path(Path("/tmp/episode.mp4"))
