"""Real Tk preparation controls, read-only scripts and stale-selection protection."""

import os
import unittest

from field_notes_studio.preparation_models import PreparationItem, PreparationSnapshot


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class PreparationWindowTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk

        from field_notes_studio.presentation import theme
        from field_notes_studio.presentation.preparation import PreparationWindow

        self.root = tk.Tk()
        theme.apply(self.root)
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.view = PreparationWindow(self.root)
        self.view.connect(lambda: None, self.view.clear, lambda: None, self.view.close)
        self.items = [
            PreparationItem(
                "104", "Window", "104-window.html", "studio-essay", "Inspect script", "Inspect first."
            ),
            PreparationItem("105", "Newer", "105-newer.html", "", "Needs script", "No script yet."),
        ]
        self.view.show_catalog(self.items)
        self.root.update()

    def select(self, identifier):
        self.view.tree.selection_set(identifier)
        self.root.update()

    def snapshot(self, note="104"):
        return PreparationSnapshot(
            note, "studio-essay", "Window", "Exact script.", "Offline plan.", "a" * 64
        )

    def test_new_notes_without_media_or_script_are_visible(self):
        self.assertEqual(self.view.tree.get_children(), ("104", "105"))
        self.select("105")
        self.assertTrue(self.view.inspect_button.instate(["disabled"]))
        self.assertIn("No script yet", self.view.plan.get("1.0", "end"))

    def test_script_is_read_only_and_old_results_cannot_overwrite_another_note(self):
        self.select("104")
        self.view.show_snapshot(self.snapshot())
        self.assertEqual(self.view.script.cget("state"), "disabled")
        self.select("105")
        self.view.show_snapshot(self.snapshot())
        self.assertIsNone(self.view.snapshot)
        self.assertEqual(self.view.script.get("1.0", "end").strip(), "")

    def test_busy_disables_duplicate_inspections_and_refresh(self):
        self.select("104")
        self.assertFalse(self.view.inspect_button.instate(["disabled"]))
        self.view.busy(True)
        self.assertTrue(self.view.refresh_button.instate(["disabled"]))
        self.assertTrue(self.view.inspect_button.instate(["disabled"]))
        self.view.busy(False)
        self.assertFalse(self.view.inspect_button.instate(["disabled"]))

    def test_failed_read_clears_the_previous_script_and_plan_identity(self):
        self.select("104")
        self.view.show_snapshot(self.snapshot())
        self.view.clear("Preparation needs attention: source changed")
        self.assertIsNone(self.view.snapshot)
        self.assertEqual(self.view.script.get("1.0", "end").strip(), "")
        self.assertIn("source changed", self.view.message.cget("text"))

    def test_refresh_preserves_selection_not_inspection(self):
        self.select("104")
        self.view.show_snapshot(self.snapshot())
        self.view.show_catalog(self.items)
        self.root.update()
        self.assertEqual(self.view.selected(), "104")
        self.assertIsNone(self.view.snapshot)

    def test_refresh_removes_disappeared_notes(self):
        self.select("104")
        self.view.show_catalog(self.items[1:])
        self.root.update()
        self.assertEqual(self.view.selected(), "")
        self.assertTrue(self.view.inspect_button.instate(["disabled"]))

    def test_empty_catalog_explains_scope_without_a_dead_action(self):
        self.view.show_catalog([])
        self.assertIn("0 written notes", self.view.message.cget("text"))
        self.assertTrue(self.view.inspect_button.instate(["disabled"]))

    def test_controls_fit_the_smallest_supported_window(self):
        # A transient window requires a mapped owner to obtain real dimensions.
        self.root.deiconify()
        self.view.window.geometry("760x580")
        self.root.update()
        for widget in (
            self.view.tree,
            self.view.refresh_button,
            self.view.inspect_button,
            self.view.message,
        ):
            self.assertGreater(widget.winfo_width(), 10)
            self.assertLessEqual(
                widget.winfo_rootx() + widget.winfo_width(),
                self.view.window.winfo_rootx() + self.view.window.winfo_width(),
            )
