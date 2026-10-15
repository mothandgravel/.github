"""Bounded background preparation reads; only the Tk thread touches the view."""

from __future__ import annotations

import queue
from concurrent.futures import ThreadPoolExecutor


class PreparationController:
    def __init__(self, service, view):
        self.service, self.view = service, view
        self.closed = False
        self.busy = False
        self.epoch = 0
        self.mailbox = queue.Queue()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="studio-preparation")
        self.handle = None
        view.connect(self.refresh, self.select, self.inspect, self.close)
        if hasattr(view, "connect_execution"):
            view.connect_execution(self.submit)
        self.refresh()
        self.pump()

    def _read(self, operation, callback, *, effect=False):
        if self.closed or self.busy:
            return
        self.busy = True
        self.view.busy(True)
        epoch = self.epoch
        future = self.pool.submit(operation)
        future.add_done_callback(lambda done: self.mailbox.put((epoch, callback, done, effect)))

    def refresh(self):
        if self.closed or self.busy:
            return
        self.epoch += 1
        self.view.clear("Reading written notes and episode registrations…")
        self._read(self.service.catalog, self.view.show_catalog)

    def select(self):
        if self.closed:
            return
        # Selection changes invalidate a pending result without touching the worker.
        self.epoch += 1
        self.view.clear()

    def inspect(self):
        note = self.view.selected()
        if note and not self.closed and not self.busy:
            self.epoch += 1
            self.view.clear("Inspecting the script offline…")
            self._read(lambda: self.service.inspect(note), self.view.show_snapshot)

    def submit(self):
        if self.closed or self.busy:
            return
        snapshot = self.view.snapshot
        authorized = self.view.authorized.get()
        if not snapshot or snapshot.note != self.view.selected() or not authorized:
            return
        self.epoch += 1
        self.view.clear("Queueing the captured preparation request…")
        self._read(
            lambda: self.service.submit(snapshot, authorized),
            lambda identifier: self.view.queued(snapshot.episode, identifier),
            effect=True,
        )

    def pump(self):
        if self.closed:
            return
        while True:
            try:
                epoch, callback, future, effect = self.mailbox.get_nowait()
            except queue.Empty:
                break
            self.busy = False
            self.view.busy(False)
            if epoch != self.epoch and not effect:
                continue
            try:
                callback(future.result())
            except Exception as exc:
                self.view.clear(f"Preparation needs attention: {exc}")
        self.handle = self.view.schedule(50, self.pump)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.epoch += 1
        if self.handle is not None:
            self.view.unschedule(self.handle)
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.view.close()
