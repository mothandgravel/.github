"""Named local recipe versioning, visible overrides and explicit per-episode application."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from field_notes_audio.storage import read_object, write_json
from field_notes_studio.pipeline import Pipeline
from field_notes_studio.recipes import KEY, Recipes, differences
from field_notes_studio.repository import Repository
from tests.studio import test_ui

ROOT = Path(__file__).resolve().parents[2]


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repository = Repository(self.root / "artifacts/studio/studio.sqlite3")
        self.pipeline = Pipeline(self.root)
        self.recipes = Recipes(self.repository, self.pipeline)
        self.settings = read_object(ROOT / "audio/production/settings.json")
        write_json(self.root / "audio/production/settings.json", self.settings)

    def test_empty_library_does_not_change_show_defaults_or_create_a_job(self):
        data, identity = self.recipes.load()
        self.assertEqual(data["recipes"], {})
        self.assertEqual(identity, "")
        self.assertEqual(self.repository.jobs(), [])

    def test_named_recipe_survives_reopening_and_does_not_mutate_input(self):
        saved, identity = self.recipes.save("Field Notes", self.settings, "")
        self.settings["speed"] = 1.5
        again = Recipes(self.repository, self.pipeline).select(saved["id"], identity)
        self.assertEqual(again["settings"]["speed"], 1.15)
        self.assertEqual(self.repository.jobs(), [])
        self.assertEqual(self.repository.publications(), {})

    def test_stale_window_save_and_apply_fail_closed(self):
        saved, identity = self.recipes.save("Default show", self.settings, "")
        self.recipes.save("Other", self.settings, identity)
        with self.assertRaisesRegex(ValueError, "another window"):
            self.recipes.save("Default show", self.settings, identity, saved["id"])
        with self.assertRaisesRegex(ValueError, "Show settings changed"):
            self.recipes.select(saved["id"], identity)

    def test_same_name_requires_explicit_update_case_insensitively(self):
        saved, identity = self.recipes.save("Default", self.settings, "")
        with self.assertRaisesRegex(ValueError, "with that name exist"):
            self.recipes.save("default", self.settings, identity)
        changed = {**self.settings, "speed": 1.25}
        updated, new_identity = self.recipes.save("Default", changed, identity, saved["id"])
        self.assertNotEqual(identity, new_identity)
        self.assertEqual(updated["settings"]["speed"], 1.25)
        self.assertEqual(len(self.recipes.load()[0]["recipes"]), 1)

    def test_unfinished_invalid_and_unknown_recipe_values_are_rejected(self):
        for change in ({"speed": ""}, {"speed": float("nan")}, {"speed": True}, {"unknown": 2}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.recipes.save("Bad", {**self.settings, **change}, "")
        self.assertEqual(self.recipes.load()[0]["recipes"], {})

    def test_invalid_names_do_not_create_journal_entries(self):
        for name in (None, "", "  ", "a\nb", "a" * 61):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.recipes.save(name, self.settings, "")

    def test_missing_custom_music_is_rejected_at_apply_not_while_listing_other_recipes(self):
        music = self.root / "music.wav"
        music.write_bytes(b"a local path whose media is checked by production")
        custom = {
            **self.settings,
            "music_mode": "file",
            "music_file": str(music),
            "music_credit": "Licensed",
        }
        saved, identity = self.recipes.save("Custom", custom, "")
        music.unlink()
        self.assertIn(saved["id"], self.recipes.load()[0]["recipes"])
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.recipes.select(saved["id"], identity)

    def test_video_and_audio_overrides_are_visible_not_mutated_by_comparison(self):
        before = copy.deepcopy(self.settings)
        current = copy.deepcopy(before)
        current["speed"] = 1.25
        current["video"]["fps"] = 30
        result = differences(before, current)
        self.assertIn("Pace ×: 1.15 → 1.25", result)
        self.assertIn("Frame rate: 24 → 30", result)
        self.assertEqual(self.settings, before)

    def test_corrupt_recipe_library_is_not_silently_replaced(self):
        self.repository.checkpoint({KEY: {"version": True, "recipes": {}}})
        with self.assertRaisesRegex(ValueError, "Saved show settings are damaged"):
            self.recipes.load()
        self.assertIs(self.repository.state(KEY)["version"], True)

    def test_malformed_non_object_library_is_preserved_not_reset(self):
        for value in ([], {}, None, "broken"):
            with self.subTest(value=value):
                self.repository.checkpoint({KEY: value})
                with self.assertRaises(ValueError):
                    self.recipes.load()
                self.assertEqual(self.repository.state(KEY), value)

    def test_captured_job_and_episode_drafts_do_not_follow_later_recipe_changes(self):
        saved, identity = self.recipes.save("Show", self.settings, "")
        self.repository.checkpoint({"draft:note-013": {"show_recipe": saved}})
        identifier = self.repository.submit("note-013", "video", {"settings": saved["settings"]})
        self.recipes.save("Show", {**self.settings, "speed": 1.5}, identity, saved["id"])
        self.assertEqual(
            json.loads(self.repository.get(identifier).request)["settings"]["speed"], 1.15
        )
        self.assertEqual(
            self.repository.state("draft:note-013")["show_recipe"]["settings"]["speed"], 1.15
        )


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class RecipeUiTests(unittest.TestCase):
    def setUp(self):
        self.h = test_ui.UITests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.c = self.h.app.controller
        self.w = self.h.app.workspace
        self.controls = self.c.episode_controls
        self.book = Recipes(self.c.studio.repository, self.c.studio.pipeline)
        self.h.wait(lambda: not self.controls.busy)

    def test_save_apply_override_and_undo_preserve_publication_draft(self):
        self.controls.open_recipes()
        self.controls.save_recipe("Standard", None)
        self.w.speed.set("1.25")
        self.assertIn("Pace", self.w.recipe_info.cget("text"))
        self.controls.reload_recipes()
        self.controls.window.choice.set("Standard")
        self.controls.apply_recipe()
        self.assertEqual(float(self.w.speed.get()), 1.15)
        self.w.publication.url.set("https://youtu.be/real-destination")
        self.controls.undo_recipe()
        self.assertEqual(float(self.w.speed.get()), 1.25)
        self.assertEqual(self.w.publication.url.get(), "https://youtu.be/real-destination")
        self.assertEqual(self.c.studio.repository.jobs(), [])

    def test_apply_copies_complete_recipe_then_full_job_uses_it(self):
        recipe = self.w.effective_recipe()
        recipe["video"]["fps"] = 30
        self.book.save("30 fps", recipe, "")
        self.controls.open_recipes()
        self.controls.window.choice.set("30 fps")
        self.controls.apply_recipe()
        self.w.full_episode.invoke()
        self.h.wait(lambda: not self.c.production.busy)
        job = self.c.studio.repository.jobs()[0]
        self.assertEqual(json.loads(job.request)["settings"]["video"]["fps"], 30)

    def test_invalid_save_and_stale_apply_leave_draft_and_jobs_unchanged(self):
        self.controls.open_recipes()
        self.w.speed.set("unfinished")
        self.controls.save_recipe("Nope", None)
        self.assertEqual(self.book.load()[0]["recipes"], {})
        self.assertEqual(self.w.speed.get(), "unfinished")
        self.assertEqual(self.c.studio.repository.jobs(), [])

    def test_saved_recipe_and_overrides_survive_draft_restore(self):
        self.controls.open_recipes()
        self.controls.save_recipe("My show", None)
        self.w.outro.set("8")
        self.c.checkpoint()
        self.c.select("note-001", reload=True)
        self.h.wait(lambda: not self.c.loading)
        self.assertEqual(self.w.show_recipe["name"], "My show")
        self.assertEqual(float(self.w.outro.get()), 8)
        self.assertIn("Outro", self.w.recipe_info.cget("text"))

    def test_recipe_window_selection_change_cannot_apply_to_other_episode(self):
        self.controls.open_recipes()
        self.controls.save_recipe("My show", None)
        original = self.w.effective_recipe()
        self.controls.window.episode = "other-episode"
        self.controls.apply_recipe()
        self.assertEqual(self.w.effective_recipe(), original)
        self.assertEqual(self.c.studio.repository.jobs(), [])

    def test_batch_uses_each_episodes_captured_recipe_not_current_selection(self):
        recipe = self.w.effective_recipe()
        recipe["video"]["fps"] = 30
        self.c.studio.repository.checkpoint(
            {
                "draft:note-002": {
                    "production_base": recipe,
                    "recipe": {"speed": "1.25", "outro": "8"},
                }
            }
        )
        plans, _ = self.c.studio.batch_plan(["note-001", "note-002"], "video")
        self.assertEqual(plans[0][2]["settings"]["speed"], 1.15)
        self.assertEqual(plans[1][2]["settings"]["speed"], 1.25)
        self.assertEqual(plans[1][2]["settings"]["video"]["fps"], 30)

    def test_open_recipe_window_shows_later_library_changes_without_auto_apply(self):
        self.controls.open_recipes()
        self.controls.save_recipe("Field Notes", None)
        reference = self.w.show_recipe
        _, identity = self.book.load()
        self.book.save(
            "Field Notes", {**reference["settings"], "speed": 1.5}, identity, reference["id"]
        )
        self.controls.reload_recipes()
        self.assertIn(
            "These saved show settings changed", self.controls.window.message.cget("text")
        )
        self.assertEqual(float(self.w.speed.get()), 1.15)
        self.assertEqual(self.w.show_recipe["settings"]["speed"], 1.15)

    def test_recipe_controls_fit_native_minimum_and_expose_all_overrides(self):
        self.controls.open_recipes()
        self.controls.save_recipe("Field Notes", None)
        self.w.speed.set("1.25")
        self.w.outro.set("8")
        window = self.controls.window
        window.window.geometry("680x420+0+0")
        self.h.root.update()
        self.assertIn("Pace ×: 1.15 → 1.25", window.diff.get("1.0", "end"))
        self.assertIn("Outro (seconds): 5.0 → 8.0", window.diff.get("1.0", "end"))
        for widget in (
            window.select,
            window.apply,
            window.diff,
            window.save_new,
            window.update,
            window.undo,
        ):
            self.assertTrue(widget.winfo_viewable())
            self.assertLessEqual(
                widget.winfo_rootx() + widget.winfo_width(),
                window.window.winfo_rootx() + window.window.winfo_width(),
            )
            self.assertLessEqual(
                widget.winfo_rooty() + widget.winfo_height(),
                window.window.winfo_rooty() + window.window.winfo_height(),
            )
        self.assertGreater(window.diff.winfo_height(), 100)
