"""CLI compatibility and cache identity across the package move."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from field_notes_audio import audio


class EntryPointTests(unittest.TestCase):
    def test_legacy_launcher_from_another_directory_keeps_the_same_plan(self):
        root = Path(__file__).resolve().parents[2]
        expected = audio.make_plan("note-001", "gemini-2.5-pro-tts", "global")
        arguments = [
            "plan",
            "note-001",
            "--model",
            "gemini-2.5-pro-tts",
            "--endpoint",
            "global",
            "--json",
        ]
        module = subprocess.run(
            [sys.executable, "-m", "field_notes_audio", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        with tempfile.TemporaryDirectory() as directory:
            legacy = subprocess.run(
                [sys.executable, str(root / "scripts/field_audio.py"), *arguments],
                cwd=directory,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        self.assertEqual(json.loads(module.stdout), expected)
        self.assertEqual(json.loads(legacy.stdout), expected)

    def test_generation_command_name_stays_compatible(self):
        result = subprocess.run(
            [sys.executable, "-m", "field_notes_audio", "generate", "--help"],
            cwd=audio.ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        self.assertIn("--retry-uncertain", result.stdout)
