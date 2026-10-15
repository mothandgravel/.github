"""UI coordinator: bounded background reads return through a main-thread mailbox."""

from __future__ import annotations

import json
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
        self.review_generation = 0
        self.review_jobs = None
        self.release_generation = 0
        self.selection_generation = 0

    def task(self, operation, callback, on_error=None):
        future = self.executor.submit(operation)

        def done(completed):
            try:
                value, error = completed.result(), None
            except Exception as exc:
                value, error = None, str(exc)
            self.mailbox.put((callback, value, error, on_error))

        future.add_done_callback(done)

    def start(self):
        self.task(lambda: launch_worker(self.studio.root), lambda _: None)
        self.task(self.studio.catalog, self.loaded)

    def loaded(self, episodes):
        self.episodes = {episode.identifier: episode for episode in episodes}
        self.view.shelf.load(episodes)
        self.view.status(
            "Choose an episode → inspect changes → queue production → review saved media."
            if episodes
            else "No prepared episodes found. This checkout needs the original media and captions."
        )
        if episodes and self.selected is None:
            self.view.shelf.tree.selection_set(episodes[0].identifier)
            self.select(episodes[0].identifier)

    def select(self, identifier, review_scope=None):
        if identifier == self.selected:
            if review_scope is not None:
                self.show_review(review_scope)
            return
        self.selected = identifier
        self.selection_generation += 1
        selection = self.selection_generation
        self.release_generation += 1
        self.review_generation += 1
        self.review_jobs = None
        self.view.workspace.review.clear()
        self.changed()
        self.loading = True
        self.view.workspace.publication.loading_episode()

        def loaded(settings):
            if selection == self.selection_generation:
                self.view.workspace.load(self.episodes[identifier], settings)
                self.loading = False
                self.changed()
                if review_scope is None:
                    self.refresh_review()
                else:
                    self.show_review(review_scope)
                self.refresh_release()

        def failed(_message):
            if selection == self.selection_generation:
                self.loading = False

        self.task(lambda: self.studio.settings(identifier), loaded, failed)

    def changed(self):
        self.generation += 1
        self.ready = None
        self.view.workspace.show_plan("Inspect your changes before queueing an edition.")

    def inspect(self):
        if not self.selected or self.loading:
            self.view.status("Choose an episode and wait for its settings to load.")
            return
        action = self.view.workspace.action.get()
        speed = outro = None
        if action != "export":
            try:
                speed = float(self.view.workspace.speed.get())
                outro = float(self.view.workspace.outro.get())
            except ValueError:
                self.view.status("Pace and outro must be numbers.")
                return
        generation = self.generation
        identifier = self.selected
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
        if not self.selected or self.loading:
            return
        identifier = self.selected
        url, published = self.view.workspace.url.get(), self.view.workspace.date.get()

        def refreshed(episodes):
            self.episodes = {episode.identifier: episode for episode in episodes}
            self.view.shelf.load(episodes)
            episode = self.episodes.get(identifier)
            if episode is not None:
                self.view.workspace.publication.record_saved(episode, url, published)
            self.view.status(f"Publication record saved for {identifier}.")

        def saved(_):
            self.task(self.studio.catalog, refreshed)

        self.task(lambda: self.studio.publication(identifier, url, published), saved)

    def refresh_release(self):
        if not self.selected or self.loading:
            return
        identifier = self.selected
        self.release_generation += 1
        generation = self.release_generation
        publication = self.view.workspace.publication
        publication.clear()

        def loaded(details):
            if generation == self.release_generation and identifier == self.selected:
                publication.load_details(details)

        def failed(message):
            if generation == self.release_generation and identifier == self.selected:
                publication.clear("Upload copy unavailable: " + message, loading=False)

        self.task(lambda: self.studio.release_details(identifier), loaded, failed)

    def prepare_package(self):
        if not self.selected or self.loading:
            return
        self.view.workspace.action.set("export")
        self.view.workspace.show_plan_tab()
        self.inspect()

    def release_review(self):
        if self.selected and not self.loading:
            self.show_review(True)

    def open_publisher(self):
        self.task(
            self.studio.open_publisher,
            lambda _: self.view.status(
                "YouTube Studio opened. Upload the saved package, then record its published link/date."
            ),
        )

    def open_output(self, kind):
        identifier = self.selected
        if identifier:
            self.task(lambda: self.studio.open_output(identifier, kind), lambda _: None)

    def open_job_output(self):
        identifier = self.view.jobs.selection()
        if identifier:
            self.task(lambda: self.studio.open_job_output(identifier), lambda _: None)

    def show_review(self, full_video):
        review = self.view.workspace.review
        review.scope.set("Full video and audio" if full_video else "Audio and captions")
        self.view.workspace.show_review()
        self.refresh_review()

    def review_job(self):
        identifier = self.view.jobs.selection()
        if not identifier:
            return
        generation = self.generation

        def loaded(job):
            if self.view.jobs.selection() != identifier or generation != self.generation:
                return
            if job.status != "succeeded" or job.action not in {"audio", "video"}:
                self.view.status(
                    "Choose a completed audio or full-video job to review its episode."
                )
                return
            if job.episode not in self.episodes:
                self.view.status("This job's episode is no longer in the prepared episode shelf.")
                return
            self.view.shelf.reveal(job.episode)
            self.select(job.episode, review_scope=job.action == "video")
            self.view.status("Reviewing the latest saved edition; it may be newer than this job.")

        self.task(lambda: self.studio.repository.get(identifier), loaded)

    def refresh_review(self):
        if not self.selected or self.loading:
            return
        identifier = self.selected
        self.review_generation += 1
        generation = self.review_generation
        review = self.view.workspace.review
        full_video = review.full_video()
        review.clear(loading=True)

        def loaded(snapshot):
            if generation != self.review_generation or identifier != self.selected:
                return
            review.load(snapshot)
            self.view.workspace.subtitle.configure(
                text=f"{identifier} · AI-narrated · " + snapshot.summary.splitlines()[0]
            )

        def failed(message):
            if generation == self.review_generation:
                review.clear(f"Review unavailable: {message}")

        self.task(lambda: self.studio.review_snapshot(identifier, full_video), loaded, failed)

    def open_review(self, kind):
        snapshot = self.view.workspace.review.snapshot
        if snapshot and snapshot.identity:
            self.task(lambda: self.studio.open_review(snapshot, kind), lambda _: None)

    def approve(self):
        if not self.selected or self.loading:
            return
        review = self.view.workspace.review
        snapshot = review.snapshot
        if (
            review.busy
            or not snapshot
            or not snapshot.identity
            or not review.audio_checked.get()
            or not review.captions_checked.get()
            or (snapshot.full_video and not review.video_checked.get())
            or not review.reviewer.get().strip()
        ):
            self.view.status("Check the saved media and enter your name before approving.")
            return
        identifier, reviewer = self.selected, review.reviewer.get().strip()
        generation = self.review_generation
        review.busy = True
        review.update_controls()

        def saved(_):
            self.view.status(f"Review recorded for {identifier}.")
            if generation == self.review_generation:
                self.refresh_review()

        def failed(message):
            if generation == self.review_generation:
                review.clear(message + " Refresh the edition before reviewing again.")

        self.task(lambda: self.studio.approve(identifier, snapshot, reviewer), saved, failed)

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
            settings = json.loads(job.request).get("settings", {})
            recipe = (
                "Saved edition · recipe controls do not affect export"
                if job.action == "export"
                else f"{settings.get('speed', '—')}× pace · {settings.get('outro_seconds', '—')}s outro"
            )
            guidance = {
                "queued": "Waiting for the worker; jobs run one at a time.",
                "running": "Stage in progress; closing the window keeps production running.",
                "failed": "Retry the captured recipe, or inspect a fresh plan after source changes.",
                "interrupted": "Outcome unknown. Inspect saved output or retry with validated caches.",
                "cancelled": "Stopped at a safe boundary. Retry reuses validated completed stages.",
                "succeeded": "Open the saved output. Audio and full video can be reviewed before export.",
            }.get(job.status, "")
            if job.cancel_requested and job.status in {"queued", "running"}:
                guidance = "Stop requested; the current stage finishes its writes before stopping."
            self.view.jobs.detail.configure(
                text=f"{recipe} · {guidance}\n{job.error or result or last}"
            )

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
            signature = tuple(
                (job.identifier, job.status) for job in jobs if job.episode == self.selected
            )
            if signature != self.review_jobs:
                previous = self.review_jobs
                self.review_jobs = signature
                if previous is not None:
                    self.refresh_review()
                    self.refresh_release()

        def failed(_message):
            self.polling = False

        self.task(self.studio.repository.jobs, loaded, failed)

    def pump(self):
        if self.closed:
            return
        for _ in range(100):
            try:
                callback, value, error, on_error = self.mailbox.get_nowait()
            except queue.Empty:
                break
            if error:
                self.view.status(error)
                if on_error:
                    on_error(error)
            else:
                callback(value)

    def close(self):
        self.closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
