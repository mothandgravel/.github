"""State integrity and media hashing checks."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from field_notes_audio import storage


class StorageTests(unittest.TestCase):
    def test_failed_atomic_replacement_keeps_saved_outcome_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            storage.write_json(path, {"status": "uncertain"})
            original = path.read_bytes()
            with patch.object(Path, "replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    storage.write_json(path, {"status": "complete"})
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_duplicate_state_fields_and_nonobjects_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            for content in (
                '{"status":"uncertain","status":"complete"}',
                "[]",
                '{"nested":{"outcome":1,"outcome":2}}',
            ):
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        storage.read_object(path)

    def test_large_media_hash_matches_without_whole_file_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recording.mp3"
            data = b"media" * 500000
            path.write_bytes(data)
            with patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")):
                self.assertEqual(storage.digest_file(path), hashlib.sha256(data).hexdigest())
