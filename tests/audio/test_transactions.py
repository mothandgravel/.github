"""Crash/restart recovery, write-ahead history and preservation of later user edits."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from field_notes_audio.storage import read_object, write_json
from field_notes_audio.transactions import FileTransaction


class TransactionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "first.txt"
        self.path.write_text("previous")
        self.journal = self.root / "transaction"

    def transaction(self):
        return FileTransaction(self.root, self.journal, lambda p: p in {"first.txt", "second.txt"})

    def crash(self, body):
        code = (
            """import os, sys
from pathlib import Path
from field_notes_audio.transactions import FileTransaction
root = Path(sys.argv[1])
transaction = FileTransaction(root, root / 'transaction', lambda p: p in {'first.txt', 'second.txt'})
"""
            + body
        )
        result = subprocess.run([sys.executable, "-c", code, str(self.root)], check=False)
        self.assertEqual(result.returncode, 19)

    def test_abrupt_exit_rolls_back_repeated_updates_and_new_files_on_restart(self):
        self.crash("""with transaction as update:
 update.write_text(root / 'first.txt', 'intermediate')
 update.write_text(root / 'first.txt', 'final')
 update.write_text(root / 'second.txt', 'new file')
 os._exit(19)
""")
        self.assertEqual(self.path.read_text(), "final")
        self.transaction().recover()
        self.assertEqual(self.path.read_text(), "previous")
        self.assertFalse((self.root / "second.txt").exists())
        self.assertFalse(self.journal.exists())

    def test_commit_marker_survives_abrupt_exit_without_reverting_complete_outputs(self):
        self.crash("""with transaction as update:
 update.write_text(root / 'first.txt', 'complete')
 update._save('committed')
 os._exit(19)
""")
        self.transaction().recover()
        self.assertEqual(self.path.read_text(), "complete")
        self.assertFalse(self.journal.exists())

    def test_interruption_between_authorization_and_second_write_recovers_history(self):
        self.crash("""original = transaction._install
count = 0
def interrupt(target, source):
 global count
 count += 1
 if count == 2: os._exit(19)
 original(target, source)
transaction._install = interrupt
with transaction as update:
 update.write_text(root / 'first.txt', 'intermediate')
 update.write_text(root / 'first.txt', 'final')
""")
        self.transaction().recover()
        self.assertEqual(self.path.read_text(), "previous")

    def test_recovery_preserves_later_edit_and_does_not_partially_restore_other_files(self):
        self.crash("""with transaction as update:
 update.write_text(root / 'first.txt', 'release')
 update.write_text(root / 'second.txt', 'new release file')
 os._exit(19)
""")
        self.path.write_text("later human edit")
        with self.assertRaisesRegex(ValueError, "later edit"):
            self.transaction().recover()
        self.assertEqual(self.path.read_text(), "later human edit")
        self.assertEqual((self.root / "second.txt").read_text(), "new release file")

    def test_failed_transaction_restores_previous_and_unchanged_writes_preserve_mtime(self):
        before = self.path.stat().st_mtime_ns
        with self.transaction() as update:
            update.write_text(self.path, "previous")
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        with self.assertRaisesRegex(RuntimeError, "failed"), self.transaction() as update:
            update.write_text(self.path, "changed")
            raise RuntimeError("failed")
        self.assertEqual(self.path.read_text(), "previous")

    def test_forged_journal_path_is_rejected_before_restoring_anything(self):
        self.crash("""with transaction as update:
 update.write_text(root / 'first.txt', 'release')
 os._exit(19)
""")
        value = read_object(self.journal / "journal.json")
        value["entries"][0]["path"] = "../outside.txt"
        write_json(self.journal / "journal.json", value)
        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.transaction().recover()
        self.assertEqual(self.path.read_text(), "release")
