"""UI coordinator: bounded background reads return through a main-thread mailbox."""

from __future__ import annotations

import json
import queue
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from field_notes_studio.models import DraftConflict
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
        self.package_generation = 0
        self.draft_timer = None
        self.restore_session = None
        self.batch_ready = None
        self.batch_generation = 0
        self.health_busy = False
        self.window_id = uuid.uuid4().hex
        self.draft_identity = ""
        self.draft_value = None

    def draft_changed(self):
        if self.loading or self.closed or not getattr(self.view, "root", None):
            return
        if self.draft_timer is not None:
            self.view.root.after_cancel(self.draft_timer)
        self.draft_timer = self.view.root.after(400, self.autosave)

    def checkpoint(self):
        if not getattr(self.view, "root", None) or not self.selected:
            return
        workspace = self.view.workspace
        values = {
            "session": {
                "episode": self.selected,
                "tab": workspace.tabs.index(workspace.tabs.select()),
                "release_tab": workspace.publication.tabs.index(
                    workspace.publication.tabs.select()
                ),
                "search": self.view.shelf.query.get(),
                "geometry": self.view.root.geometry(),
                "batch": workspace.batch.selection(),
            },
        }
        key = "draft:" + self.selected
        draft = workspace.draft() if not self.loading else None
        expected = {}
        if draft is not None and draft != self.draft_value:
            values[key] = draft
            expected[key] = self.draft_identity
        try:
            identities = self.studio.repository.checkpoint(values, expected=expected)
        except DraftConflict:
            self.studio.repository.recover_draft(self.selected, self.window_id, draft)
            workspace.draft_conflict(True)
            raise
        if key in identities:
            self.draft_identity = identities[key]
            self.draft_value = draft

    def resolve_draft(self, keep):
        if not self.selected or self.loading:
            return
        try:
            if keep:
                saved, identity = self.studio.repository.state_snapshot("draft:" + self.selected)
                self.studio.repository.recover_draft(
                    self.selected, self.window_id + "-other", saved
                )
                self.draft_identity = identity
                self.draft_value = None
                self.checkpoint()
                self.view.workspace.draft_conflict(False)
                self.view.status(
                    "This window's draft saved. Both versions remain in draft-recovery."
                )
            else:
                self.studio.repository.recover_draft(
                    self.selected, self.window_id, self.view.workspace.draft()
                )
                self.select(self.selected, reload=True)
        except Exception as exc:
            self.view.status(str(exc))

    def open_draft_recovery(self):
        self.task(self.studio.open_draft_recovery, lambda _: None)

    def autosave(self):
        self.draft_timer = None
        try:
            self.checkpoint()
        except Exception as exc:
            self.view.status(f"Draft could not be saved: {exc}. Keep Studio open and retry.")

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
        self.view.workspace.batch.load(episodes)
        self.view.status(
            "Choose an episode → inspect changes → queue production → review saved media."
            if episodes
            else "No prepared episodes found. This checkout needs the original media and captions."
        )
        if episodes and self.selected is None:
            session = self.studio.repository.state("session")
            self.restore_session = session
            identifier = session.get("episode", episodes[0].identifier)
            if identifier not in self.episodes:
                identifier = episodes[0].identifier
            self.view.shelf.reveal(identifier)
            self.select(identifier)

    def select(self, identifier, review_scope=None, *, reload=False):
        if identifier == self.selected and not reload:
            if review_scope is not None:
                self.show_review(review_scope)
            return
        try:
            if not reload:
                self.checkpoint()
        except Exception as exc:
            self.view.status(f"Keep this draft open: checkpoint failed: {exc}")
            return
        self.loading = True
        self.selected = identifier
        self.package_generation += 1
        self.selection_generation += 1
        selection = self.selection_generation
        self.release_generation += 1
        self.review_generation += 1
        self.review_jobs = None
        self.view.workspace.review.clear()
        self.changed()
        self.loading = True
        self.view.workspace.publication.loading_episode()
        if getattr(self.view, "root", None):
            self.view.workspace.draft_conflict(False)
            self.view.workspace.publication.drafts.pop(identifier, None)

        def loaded(settings):
            if selection == self.selection_generation:
                self.view.workspace.load(self.episodes[identifier], settings)
                if getattr(self.view, "root", None):
                    draft, self.draft_identity = self.studio.repository.state_snapshot(
                        "draft:" + identifier
                    )
                    self.view.workspace.restore(draft)
                    self.draft_value = self.view.workspace.draft()
                    session, self.restore_session = self.restore_session, None
                    if session:
                        self.view.workspace.tabs.select(
                            min(session.get("tab", 0), len(self.view.workspace.tabs.tabs()) - 1)
                        )
                        self.view.workspace.publication.tabs.select(
                            min(
                                session.get("release_tab", 0),
                                len(self.view.workspace.publication.tabs.tabs()) - 1,
                            )
                        )
                        self.view.shelf.query.set(session.get("search", ""))
                        for episode, choice in self.view.workspace.batch.choices.items():
                            choice.set(episode in session.get("batch", []))
                        geometry = session.get("geometry", "")
                        if geometry:
                            self.view.root.geometry(geometry)
                self.loading = False
                self.changed()
                if review_scope is None:
                    self.refresh_review()
                else:
                    self.show_review(review_scope)
                self.refresh_release()
                if getattr(self.view, "root", None):
                    self.load_metadata()

        def failed(_message):
            if selection == self.selection_generation:
                self.loading = False
                # Old controls do not belong to the failed selection. In particular,
                # closing must not checkpoint them under the new episode's identity.
                self.selected = None
                if getattr(self.view, "root", None):
                    self.view.shelf.tree.selection_remove(identifier)
                    self.view.workspace.title.configure(text="Episode settings unavailable")
                    self.view.workspace.subtitle.configure(
                        text="Choose the episode again to retry loading its settings."
                    )

        self.task(lambda: self.studio.settings(identifier), loaded, failed)

    def changed(self):
        self.generation += 1
        self.ready = None
        self.view.workspace.show_plan("Inspect your changes before queueing an edition.")
        self.draft_changed()
        if hasattr(self.view.workspace, "batch"):
            self.batch_changed()

    def batch_changed(self):
        self.batch_generation += 1
        self.batch_ready = None
        self.view.workspace.batch.show("Inspect the selected episodes before queueing.")
        self.draft_changed()

    def health(self):
        if self.health_busy:
            return
        self.health_busy = True
        self.view.workspace.show_health("Checking worker, media tools and production settings…")

        def loaded(message):
            self.health_busy = False
            self.view.workspace.show_health(message)

        self.task(self.studio.health, loaded, loaded)

    def restart_worker(self):
        def restarted(message):
            self.view.status(message)
            self.health()

        self.task(self.studio.restart_worker, restarted)

    def inspect_batch(self):
        if self.loading:
            return
        try:
            self.checkpoint()
        except Exception as exc:
            self.view.status(f"Batch blocked: draft save failed: {exc}")
            return
        self.batch_changed()
        generation = self.batch_generation
        identifiers = self.view.workspace.batch.selection()
        action = self.view.workspace.action.get()
        self.view.workspace.batch.show("Inspecting every selected episode…")

        def loaded(result):
            if generation == self.batch_generation:
                self.batch_ready, summary = result
                self.view.workspace.batch.show(summary, ready=True)

        def failed(message):
            if generation == self.batch_generation:
                self.view.workspace.batch.show("Nothing queued. " + message)

        self.task(lambda: self.studio.batch_plan(identifiers, action), loaded, failed)

    def submit_batch(self):
        if self.batch_ready is None:
            return
        plans = self.batch_ready
        self.batch_changed()
        self.task(
            lambda: self.studio.submit_batch(plans),
            lambda jobs: self.view.status(
                f"Queued {len(jobs)} episodes with their inspected recipes."
            ),
        )

    def inspect(self):
        if not self.selected or self.loading:
            self.view.status("Choose an episode and wait for its settings to load.")
            return
        action = self.view.workspace.action.get()
        sound = None
        speed = outro = None
        if action != "export":
            try:
                speed = float(self.view.workspace.speed.get())
                outro = float(self.view.workspace.outro.get())
                if hasattr(self.view.workspace, "sound"):
                    sound = self.view.workspace.sound.sound()
            except ValueError:
                self.view.status("Pace, outro and sound levels must be valid numbers.")
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

        self.task(
            lambda: self.studio.plan(identifier, action, speed, outro, sound)
            if sound is not None
            else self.studio.plan(identifier, action, speed, outro),
            planned,
        )

    def load_metadata(self, discard=False):
        if not self.selected or self.loading:
            return
        identifier, selection = self.selected, self.selection_generation
        publication = self.view.workspace.publication
        editor = publication.editor
        editor.save.configure(state="disabled")
        if discard:
            publication.metadata_draft = {}
            editor.loaded = False

        def loaded(snapshot):
            if identifier == self.selected and selection == self.selection_generation:
                editor.load(publication.metadata_draft or snapshot)
                publication.metadata_draft = {}
                self.draft_changed()

        self.task(lambda: self.studio.metadata_editor(identifier), loaded)

    def save_metadata(self):
        if not self.selected or self.loading:
            return
        identifier, selection = self.selected, self.selection_generation
        editor = self.view.workspace.publication.editor
        if not editor.loaded or str(editor.save["state"]) == "disabled":
            return
        snapshot = editor.snapshot()
        editor.save.configure(state="disabled")

        def saved(result):
            if identifier == self.selected and selection == self.selection_generation:
                # Preserve text typed while the write was in flight, with its new file identity.
                editor.baseline = result["baseline"]
                editor.save.configure(state="normal")
                editor.save.complete("Saved")
                self.draft_changed()
                self.refresh_release()
            self.view.status(
                "Publishing settings saved. Export again to update an existing upload package."
            )

        def failed(_):
            if identifier == self.selected and selection == self.selection_generation:
                editor.save.configure(state="normal")

        self.task(lambda: self.studio.save_metadata(identifier, snapshot), saved, failed)

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
                self.draft_changed()
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
        self.package_generation += 1
        publication.files.clear()
        if publication.files_visible():
            self.refresh_package()

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

    def refresh_package(self):
        if not self.selected or self.loading:
            return
        identifier = self.selected
        self.package_generation += 1
        generation = self.package_generation
        files = self.view.workspace.publication.files
        files.clear("Checking the saved package and latest full edition…", loading=True)

        def loaded(snapshot):
            if generation == self.package_generation and identifier == self.selected:
                files.load(snapshot)
                if snapshot.details is not None:
                    self.view.workspace.publication.load_details(snapshot.details)

        def failed(message):
            if generation == self.package_generation and identifier == self.selected:
                files.clear("Package unavailable: " + message)

        self.task(lambda: self.studio.package_snapshot(identifier), loaded, failed)

    def open_package_file(self):
        files = self.view.workspace.publication.files
        snapshot, name = files.snapshot, files.selection()
        if snapshot and name:
            generation = self.package_generation
            files.working("open")

            def opened(_):
                if (
                    generation == self.package_generation
                    and files.snapshot == snapshot
                    and files.selection() == name
                ):
                    files.selected()

            self.task(
                lambda: self.studio.open_package_file(snapshot, name),
                opened,
                lambda message: self.package_action_failed(generation, snapshot, name, message),
            )

    def package_action_failed(self, generation, snapshot, name, message):
        files = self.view.workspace.publication.files
        if (
            generation == self.package_generation
            and files.snapshot == snapshot
            and files.selection() == name
        ):
            files.selected()
            files.error(message)

    def copy_package_path(self):
        files = self.view.workspace.publication.files
        snapshot, name = files.snapshot, files.selection()
        generation = self.package_generation
        if not snapshot or not name:
            return
        files.working("copy")

        def copied(path):
            if (
                generation == self.package_generation
                and files.snapshot == snapshot
                and files.selection() == name
            ):
                files.copied(path)
                self.view.status("Upload path copied. Paste it into the browser's file picker.")

        self.task(
            lambda: self.studio.package_upload_path(snapshot, name),
            copied,
            lambda message: self.package_action_failed(generation, snapshot, name, message),
        )

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
        self.checkpoint()
        if self.draft_timer is not None:
            self.view.root.after_cancel(self.draft_timer)
        self.closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
