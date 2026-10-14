"""FFmpeg measurement output contains JSON mixed with ordinary progress logs."""

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_audio.production.mix import loudness


class LoudnessReportTests(unittest.TestCase):
    def test_progress_after_report_does_not_raise_extra_data(self):
        report = {
            "input_i": "-20",
            "input_tp": "-4",
            "input_lra": "3",
            "input_thresh": "-30",
            "target_offset": "0.1",
        }
        logs = (
            "[Parsed_loudnorm_0] \n"
            + json.dumps(report, indent=2)
            + "\n[out#0/null] audio:123KiB\nsize=N/A time=00:03:00\n"
        )
        with patch(
            "field_notes_audio.production.mix.ffmpeg",
            return_value=subprocess.CompletedProcess([], 0, "", logs),
        ):
            self.assertEqual(
                loudness(Path("recording.wav"), {"target_lufs": -16, "true_peak_db": -1.5}), report
            )

    def test_missing_report_is_a_clear_error(self):
        with patch(
            "field_notes_audio.production.mix.ffmpeg",
            return_value=subprocess.CompletedProcess([], 0, "", "normal log without JSON"),
        ):
            with self.assertRaisesRegex(ValueError, "measurement report"):
                loudness(Path("recording.wav"), {"target_lufs": -16, "true_peak_db": -1.5})
