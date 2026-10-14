"""UI coordinator: bounded background reads return through a main-thread mailbox."""

from __future__ import annotations

import queue
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from field_notes_studio.processes import launch_worker


class Controller:
    def __init__(self, studio, view):
        self.studio = studio
        self.view = view
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="studio-read")
        self.mailbox = queue.Queue()
        self.episodes = {}
        self.selected = None
        self.generation = 0
        self.ready = None
        self.polling = False
        self.closed = False
        self.loading = False

    def task(self, operation, callback):
        future = self.executor.submit(operation)

        def done(completed):
            try:
                value, error = completed.result(), None
            except Exception as exc:
                value, error = None, str(exc)
            self.mailbox.put((callback, value, error))

        future.add_done_callback(done)

    def start(self):
        self.task(lambda: launch_worker(self.studio.root), lambda _: None)
        self.task(self.studio.catalog, self.loaded)

    def loaded(self, episodes):
        self.episodes = {episode.identifier: episode for episode in episodes}
        self.view.shelf.load(episodes)
        self.view.status("Ready. Choose an episode and inspect its changes.")
        if episodes and self.selected is None:
            self.view.shelf.tree.selection_set(episodes[0].identifier)
            self.select(episodes[0].identifier)

    def select(self, identifier):
        if identifier == self.selected:
            return
        self.selected = identifier
        self.changed()
        self.loading = True

        def loaded(settings):
            if self.selected == identifier:
                self.view.workspace.load(self.episodes[identifier], settings)
                self.loading = False
                self.changed()

        self.task(lambda: self.studio.settings(identifier), loaded)

    def changed(self):
        self.generation += 1
        self.ready = None
        self.view.workspace.show_plan("Inspect your changes before queueing an edition.")

    def inspect(self):
        if not self.selected or self.loading:
            self.view.status("Choose an episode and wait for its settings to load.")
            return
        try:
            speed = float(self.view.workspace.speed.get())
            outro = float(self.view.workspace.outro.get())
        except ValueError:
            self.view.status("Pace and outro must be numbers.")
            return
        generation = self.generation
        identifier = self.selected
        action = self.view.workspace.action.get()
        self.view.workspace.show_plan("Checking source and local editions…")

        def planned(value):
            if generation != self.generation:
                return
            request, summary = value
            self.ready = (identifier, action, request)
            self.view.workspace.show_plan(summary, ready=True)
            self.view.status("Plan inspected. Queue this edition when ready.")

        self.task(lambda: self.studio.plan(identifier, action, speed, outro), planned)

    def submit(self):
        if self.ready is None:
            self.view.status("Inspect the current changes first.")
            return
        identifier, action, request = self.ready
        self.changed()
        self.task(
            lambda: self.studio.submit(identifier, action, request),
            lambda job: self.view.status(f"Queued {action} for {identifier} · {job[:8]}"),
        )

    def stop(self):
        identifier = self.view.jobs.selection()
        if identifier:
            self.task(
                lambda: self.studio.repository.cancel(identifier),
                lambda _: self.view.status("Stop requested. The current stage will finish safely."),
            )

    def retry(self):
        identifier = self.view.jobs.selection()
        if identifier:
            self.task(
                lambda: self.studio.retry(identifier),
                lambda _: self.view.status(
                    "Retry queued with the original recipe. Source changes will block it."
                ),
            )

    def publication(self):
        if not self.selected:
            return
        identifier = self.selected
        url, published = self.view.workspace.url.get(), self.view.workspace.date.get()

        def saved(_):
            self.view.status("Publication record saved.")
            self.task(self.studio.catalog, self.loaded)

        self.task(lambda: self.studio.publication(identifier, url, published), saved)

    def open_output(self, kind):
        identifier = self.selected
        if identifier:
            self.task(lambda: self.studio.open_output(identifier, kind), lambda _: None)

    def job_detail(self):
        identifier = self.view.jobs.selection()
        if not identifier:
            return

        def shown(value):
            if self.view.jobs.selection() != identifier:
                return
            job, events = value
            last = events[-1]["message"] if events else "Waiting for the worker."
            result = job.result
            if result:
                try:
                    result = "Saved: " + str(Path(result).relative_to(self.studio.root))
                except ValueError:
                    pass
            self.view.jobs.detail.configure(text=job.error or result or last)

        self.task(
            lambda: (
                self.studio.repository.get(identifier),
                self.studio.repository.events(identifier),
            ),
            shown,
        )

    def history(self):
        identifier = self.view.jobs.selection()
        if identifier:
            self.task(
                lambda: (
                    self.studio.repository.get(identifier),
                    self.studio.repository.events(identifier),
                ),
                lambda value: self.view.jobs.show_history(*value),
            )

    def poll(self):
        if self.closed or self.polling:
            return
        self.polling = True

        def loaded(jobs):
            self.polling = False
            self.view.jobs.render(jobs)
            self.job_detail()

        self.task(self.studio.repository.jobs, loaded)

    def pump(self):
        if self.closed:
            return
        for _ in range(100):
            try:
                callback, value, error = self.mailbox.get_nowait()
            except queue.Empty:
                break
            if error:
                self.polling = False
                self.loading = False
                self.view.status(error)
            else:
                callback(value)

    def close(self):
        self.closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
