"""Protect edited controls from stale background plans; never touch Tk off-thread."""

import threading
import unittest
from types import SimpleNamespace

from field_notes_studio.controller import Controller


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class ControllerTests(unittest.TestCase):
    def test_changed_controls_cannot_queue_an_old_plan(self):
        calls = []
        workspace = SimpleNamespace(
            speed=Value("1.15"),
            outro=Value("5"),
            action=Value("audio"),
            show_plan=lambda *args, **kwargs: calls.append(args),
        )
        view = SimpleNamespace(workspace=workspace, status=lambda text: calls.append(text))
        studio = SimpleNamespace(plan=lambda *_: ({"settings": {}}, "Old plan"))
        controller = Controller(studio, view)
        self.addCleanup(controller.close)
        controller.selected = "note-001"
        pending = []
        controller.task = lambda operation, callback: pending.append((operation, callback))
        controller.inspect()
        controller.changed()
        operation, callback = pending.pop()
        callback(operation())
        self.assertIsNone(controller.ready)
        controller.submit()
        self.assertFalse(pending)

    def test_background_completion_only_reaches_view_when_main_thread_pumps(self):
        caller = threading.get_ident()
        calls = []
        view = SimpleNamespace(status=lambda _: None)
        controller = Controller(None, view)
        self.addCleanup(controller.close)
        controller.task(lambda: 42, lambda value: calls.append((threading.get_ident(), value)))
        controller.executor.shutdown(wait=True)
        self.assertEqual(calls, [])
        controller.pump()
        self.assertEqual(calls, [(caller, 42)])
