"""The shelf's Next column is a cached verified check, invalidated by any input change."""

import tempfile
import unittest
from pathlib import Path

from field_notes_studio import readiness_cache
from field_notes_studio.readiness_models import Readiness
from field_notes_studio.repository import Repository


class StudioStub:
    def __init__(self, root):
        self.root = root
        self.repository = Repository(root / "artifacts/studio/studio.sqlite3")
        self.checks = 0
        self.action = "review"
        self.recipe = {"speed": 1.15, "music_file": None}

        class Pipeline:
            def source(self, episode):
                return {"id": episode, "title": "Window"}

        self.pipeline = Pipeline()

    def settings(self, episode):
        return dict(self.recipe)

    def readiness(self, episode, settings):
        self.checks += 1
        return Readiness(episode, self.action, "Ready for one full review", "Watch and approve.")


class ReadinessCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.studio = StudioStub(self.root)
        self.edition = self.root / "artifacts/production/ep/edition-1"
        self.edition.mkdir(parents=True)
        (self.edition / "episode.mp3").write_bytes(b"audio")

    def next(self, check=True):
        return readiness_cache.verified_next(self.studio, ["ep"], check=check)["ep"]

    def test_verified_once_then_served_from_cache(self):
        label, verified, value = self.next()
        self.assertEqual((label, verified, self.studio.checks), ("Review", True, 1))
        self.assertEqual(value.title, "Ready for one full review")
        self.assertEqual(self.next()[:2], ("Review", True))
        self.assertEqual(self.studio.checks, 1)
        # Survives a restart: the cache is in the studio journal.
        self.studio.repository = Repository(self.root / "artifacts/studio/studio.sqlite3")
        self.assertEqual(self.next(check=False)[:2], ("Review", True))
        self.assertEqual(self.studio.checks, 1)

    def test_file_change_invalidates(self):
        self.next()
        (self.edition / "review.json").write_text("{}")
        self.assertEqual(self.next(check=False)[:2], ("Check", False))
        self.studio.action = "export"
        self.assertEqual(self.next()[:2], ("Release", True))
        self.assertEqual(self.studio.checks, 2)

    def test_upload_folder_change_invalidates_the_package_state(self):
        self.studio.action = "package"
        self.next()
        uploads = self.root / "artifacts/uploads/ep"
        uploads.mkdir(parents=True)
        (uploads / "title.txt").write_text("New title\n")
        self.assertEqual(self.next(check=False)[:2], ("Check", False))

    def test_recipe_change_invalidates(self):
        self.next()
        self.studio.recipe["speed"] = 1.0
        self.assertEqual(self.next(check=False)[:2], ("Check", False))
        self.next()
        self.assertEqual(self.studio.checks, 2)

    def test_job_and_release_record_changes_invalidate(self):
        self.studio.action = "package"
        self.next()
        identifier = self.studio.repository.submit("ep", "export", {})
        self.assertEqual(self.next(check=False)[:2], ("Check", False))
        self.studio.repository.claim()
        self.studio.repository.finish(identifier, "succeeded", result="x")
        self.next()
        self.studio.repository.publication("ep", "https://example.com/v", "2026-10-17")
        self.assertEqual(self.next(check=False)[:2], ("Check", False))
        self.assertEqual(self.next()[:2], ("Done", True))

    def test_an_active_job_result_is_never_cached(self):
        self.studio.action = "job"
        self.assertEqual(self.next()[:2], ("Working", True))
        self.assertIsNone(self.studio.repository.cached_readiness("ep"))

    def test_a_change_during_the_check_is_not_cached(self):
        original = self.studio.readiness

        def changing(episode, settings):
            (self.edition / "late.json").write_text("{}")
            return original(episode, settings)

        self.studio.readiness = changing
        self.next()
        self.assertIsNone(self.studio.repository.cached_readiness("ep"))


if __name__ == "__main__":
    unittest.main()
