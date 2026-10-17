"""Plain-language mappings, the shelf's Next filter, release limits and appearance choice."""

import unittest
from unittest.mock import patch

from field_notes_studio import appearance
from field_notes_studio.presentation.publication import measure
from field_notes_studio.presentation.queue import stage_sentence
from field_notes_studio.presentation.readiness import checklist, journey
from field_notes_studio.presentation.shelf import matches
from field_notes_studio.readiness_models import Readiness


def snapshot(action, *stages):
    return Readiness("note-013", action, "Title", "Detail", stages)


class PlainLanguageTests(unittest.TestCase):
    def test_raw_stage_ids_become_sentences(self):
        self.assertEqual(stage_sentence("narration-2-of-3"), "Narrating part 2 of 3")
        self.assertEqual(stage_sentence("narration-2-of-3-complete"), "Part 2 of 3 saved")
        self.assertEqual(stage_sentence("video"), "Making the video")
        self.assertEqual(stage_sentence("audio-complete"), "Audio and captions saved")
        self.assertEqual(stage_sentence("queued"), "Waiting for its turn")
        self.assertEqual(stage_sentence(""), "")

    def test_stepper_and_checklist_restate_only_checked_evidence(self):
        review = snapshot(
            "review",
            "Recording: verified",
            "Full episode: verified",
            "Review: needed",
            "Package: not yet",
        )
        self.assertEqual(
            [(step.label, step.state, step.kind) for step in journey(review)],
            [
                ("Prepare", "Saved", "done"),
                ("Produce", "Made", "done"),
                ("Review", "Needs you", "now"),
                ("Release", "Not started", "todo"),
            ],
        )
        self.assertEqual(
            [kind for _, _, kind in checklist(review)], ["ok", "ok", "now", "todo", "todo"]
        )
        # Nothing checked yet: nothing is shown as done except the narration's existence.
        self.assertTrue(all(kind == "todo" for _, _, kind in checklist(None)))
        changed = snapshot(
            "produce",
            "Recording: verified",
            "Full episode: saved; draft differs",
            "Review: approved",
        )
        self.assertEqual(journey(changed)[1].state, "Settings changed")
        self.assertEqual(journey(changed)[2].kind, "done")

    def test_release_is_recorded_only_from_a_saved_record(self):
        ready = snapshot(
            "package",
            "Recording: verified",
            "Full episode: verified",
            "Review: approved",
            "Package: current and verified",
        )
        self.assertEqual(journey(ready)[3].state, "Ready to upload")
        self.assertEqual(journey(ready, published=True)[3].state, "Recorded")


class ShelfAndReleaseTests(unittest.TestCase):
    def test_needs_me_filter(self):
        for step in ("Prepare", "Produce", "Review", "Release", "Recover", "Resume"):
            self.assertTrue(matches(step, "Needs me"))
        for step in ("Working", "Done", "In feed", "Needs script"):
            self.assertFalse(matches(step, "Needs me"))
        self.assertTrue(matches("In feed", "Done"))
        self.assertTrue(matches("Working", "Working"))

    def test_copy_limits_use_the_engine_units(self):
        self.assertEqual(measure("Title", "x" * 57), "57 / 100")
        self.assertEqual(measure("Description", "é"), "3 / 5,000 bytes")
        # Multiword tags count their quotes, and tags their separators.
        self.assertEqual(measure("Tags", "field notes, audio"), "19 / 500")
        self.assertEqual(measure("Hashtags", "#One #Two"), "2 / 3 tags")


class AppearanceTests(unittest.TestCase):
    def test_choice_wins_over_the_system_setting(self):
        self.assertEqual(appearance.resolve("light", True), "light")
        self.assertEqual(appearance.resolve("night", False), "night")
        self.assertEqual(appearance.resolve("system", True), "night")
        self.assertEqual(appearance.resolve("system", None), "light")

    def test_portal_answer_is_parsed_and_unknown_stays_unknown(self):
        with patch.object(appearance, "_run", return_value="(<<uint32 1>>,)\n"):
            self.assertTrue(appearance._portal())
        with patch.object(appearance, "_run", return_value="(<<uint32 2>>,)\n"):
            self.assertFalse(appearance._portal())
        with patch.object(appearance, "_run", return_value="(<<uint32 0>>,)\n"):
            self.assertIsNone(appearance._portal())
        with patch.object(appearance, "_run", return_value=None):
            self.assertIsNone(appearance._portal())

    def test_gnome_scheme_then_theme_name(self):
        answers = {"color-scheme": "'prefer-dark'\n", "gtk-theme": "'Adwaita'\n"}
        with patch.object(appearance, "_run", side_effect=lambda command: answers[command[-1]]):
            self.assertTrue(appearance._gsettings())
        answers = {"color-scheme": "'default'\n", "gtk-theme": "'Yaru-dark'\n"}
        with patch.object(appearance, "_run", side_effect=lambda command: answers[command[-1]]):
            self.assertTrue(appearance._gsettings())


if __name__ == "__main__":
    unittest.main()
