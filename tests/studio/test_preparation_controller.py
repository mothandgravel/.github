"""Background reads may finish late, but must never update a different selection."""

import threading
import time
import unittest
from types import SimpleNamespace

from field_notes_studio.preparation_controller import PreparationController


class View:
    def __init__(self):
        self.note = "104"
        self.messages = []
        self.catalog = None
        self.snapshots = []
        self.destroyed = False
        self.loading = False
        self.scheduled = {}
        self.counter = 0
        self.thread = threading.get_ident()

    def connect(self, *callbacks):
        self.callbacks = callbacks

    def selected(self):
        return self.note

    def clear(self, text=""):
        self.messages.append(text)
        self.snapshots.clear()

    def busy(self, value):
        self.loading = value

    def show_catalog(self, value):
        assert threading.get_ident() == self.thread
        self.catalog = value

    def show_snapshot(self, value):
        assert threading.get_ident() == self.thread
        self.snapshots.append(value)

    def schedule(self, delay, callback):
        self.counter += 1
        self.scheduled[self.counter] = callback
        return self.counter

    def unschedule(self, handle):
        self.scheduled.pop(handle, None)

    def close(self):
        self.destroyed = True


class PreparationControllerTests(unittest.TestCase):
    def controller(self, inspect):
        view = View()
        controller = PreparationController(
            SimpleNamespace(catalog=lambda: ["104", "105"], inspect=inspect), view
        )
        self.addCleanup(controller.close)
        self.drain(controller)
        return controller, view

    def drain(self, controller):
        deadline = time.monotonic() + 2
        while controller.busy and time.monotonic() < deadline:
            time.sleep(0.005)
            controller.pump()
        self.assertFalse(controller.busy)

    def test_results_are_delivered_on_the_owning_thread(self):
        controller, view = self.controller(lambda note: (note, threading.get_ident()))
        self.assertEqual(view.catalog, ["104", "105"])
        controller.inspect()
        self.drain(controller)
        self.assertEqual(view.snapshots[0][0], "104")
        self.assertNotEqual(view.snapshots[0][1], view.thread)

    def test_switching_selection_discards_a_late_result(self):
        entered, finish = threading.Event(), threading.Event()
        self.addCleanup(finish.set)

        def inspect(note):
            entered.set()
            finish.wait(2)
            return note

        controller, view = self.controller(inspect)
        controller.inspect()
        self.assertTrue(entered.wait(1))
        view.note = "105"
        controller.select()
        finish.set()
        self.drain(controller)
        self.assertEqual(view.snapshots, [])
        self.assertFalse(view.loading)

    def test_duplicate_inspections_and_refreshes_are_not_queued(self):
        entered, finish = threading.Event(), threading.Event()
        self.addCleanup(finish.set)
        calls = []

        def inspect(note):
            calls.append(note)
            entered.set()
            finish.wait(2)
            return note

        controller, _ = self.controller(inspect)
        controller.inspect()
        self.assertTrue(entered.wait(1))
        for _ in range(10):
            controller.inspect()
            controller.refresh()
        finish.set()
        self.drain(controller)
        self.assertEqual(calls, ["104"])

    def test_close_does_not_allow_a_late_read_to_touch_the_destroyed_view(self):
        entered, finish, completed = threading.Event(), threading.Event(), threading.Event()
        self.addCleanup(finish.set)

        def inspect(note):
            entered.set()
            finish.wait(2)
            completed.set()
            return note

        controller, view = self.controller(inspect)
        controller.inspect()
        self.assertTrue(entered.wait(1))
        controller.close()
        finish.set()
        self.assertTrue(completed.wait(1))
        controller.pump()
        self.assertTrue(view.destroyed)
        self.assertEqual(view.snapshots, [])
        controller.close()

    def test_failed_inspection_clears_previous_evidence(self):
        def fail(_):
            raise ValueError("Source changed")

        controller, view = self.controller(fail)
        view.snapshots.append("old evidence")
        controller.inspect()
        self.drain(controller)
        self.assertEqual(view.snapshots, [])
        self.assertIn("Source changed", view.messages[-1])

    def test_queue_acknowledgement_survives_switching_notes_without_redirecting_selection(self):
        entered, finish = threading.Event(), threading.Event()
        self.addCleanup(finish.set)
        controller, view = self.controller(lambda note: note)
        view.snapshot = SimpleNamespace(note="104", episode="studio-essay")
        view.authorized = SimpleNamespace(get=lambda: True)
        acknowledgements = []
        view.queued = lambda *value: acknowledgements.append(value)

        def submit(snapshot, authorized):
            self.assertTrue(authorized)
            self.assertEqual(snapshot.note, "104")
            entered.set()
            finish.wait(2)
            return "saved-job"

        controller.service.submit = submit
        controller.submit()
        self.assertTrue(entered.wait(1))
        view.note = "105"
        controller.select()
        finish.set()
        self.drain(controller)
        self.assertEqual(acknowledgements, [("studio-essay", "saved-job")])
        self.assertEqual(view.note, "105")
