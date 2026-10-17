"""UI coordinator: bounded background reads return through a main-thread mailbox."""

from __future__ import annotations

import copy
import json
import queue
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from field_notes_studio.episode_controls import EpisodeControls
from field_notes_studio.job_progress import progress_for
from field_notes_studio.models import DraftConflict
from field_notes_studio.processes import launch_worker
from field_notes_studio.production_flow import ProductionFlow
from field_notes_studio.readiness_models import split_details


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
        self.preparation_jobs = None
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
        self.production = ProductionFlow(self)
        self.episode_controls = EpisodeControls(self)

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
        if getattr(self.view, "root", None):
            self.task(self.studio.preferences, self.preferences_loaded, lambda _: None)

    def preferences_loaded(self, preferences):
        self.view.workspace.review.remember(preferences.get("reviewer", ""))

    def refresh_shelf_hints(self):
        if not hasattr(self.view.shelf, "load_hints"):
            return

        def hints():
            # A hint that cannot be read is only a missing hint; the card still checks.
            try:
                return self.studio.shelf_hints()
            except Exception:
                return {}

        self.task(hints, self.view.shelf.load_hints)

    def refresh_notes(self):
        notes = getattr(self.view, "notes", None)
        if notes is None or not hasattr(self.view.shelf, "load_notes"):
            return

        def catalog():
            # Written notes are a convenience row source; a checkout without the
            # site catalog still shows its narrated episodes.
            try:
                return notes().catalog()
            except Exception:
                return []

        self.task(catalog, self.view.shelf.load_notes)

    def loaded(self, episodes):
        self.episodes = {episode.identifier: episode for episode in episodes}
        self.view.shelf.load(episodes)
        self.view.workspace.batch.load(episodes)
        self.refresh_shelf_hints()
        self.refresh_notes()
        home = getattr(self.view, "view_name", "episodes") == "home"
        self.view.status(
            "Work list ready. Open a row, or choose Make episode from a note…"
            if home
            else ""
            if getattr(self.view, "view_name", "episodes") == "run"
            else "Episodes loaded."
            if getattr(self.view, "view_name", "episodes") != "episodes"
            else "Episodes loaded. Choose one on the left; its card shows the next step."
            if episodes
            else "No narrated notes yet. Choose Make episode from a note… to start."
        )
        if not episodes and self.selected is None and hasattr(self.view.workspace, "show_empty"):
            self.view.workspace.show_empty(
                "No narrated notes yet",
                "Narrate a written note first. Studio then makes its audio, captions and "
                "video, and you review it once.",
                "Make episode from a note…",
                getattr(self.view, "make_episode", self.view.open_preparation),
            )
            self.view.readiness.empty(
                "",
                "Nothing to check yet",
                "A narrated note appears here with its next step.",
                "Make episode from a note…",
                getattr(self.view, "make_episode", self.view.open_preparation),
            )
        if episodes and self.selected is None:
            session = self.studio.repository.state("session")
            self.restore_session = session
            identifier = session.get("episode", episodes[0].identifier)
            if identifier not in self.episodes:
                identifier = episodes[0].identifier
            self.view.shelf.reveal(identifier)
            self.select(identifier)

    def select(
        self, identifier, review_scope=None, *, reload=False, after_load=None, on_error=None
    ):
        self.selected_note = None
        if identifier == self.selected and not reload:
            if review_scope is not None:
                self.show_review(review_scope)
            if after_load is not None:
                after_load()
            return
        try:
            if not reload:
                self.checkpoint()
        except Exception as exc:
            self.view.status(f"Keep this draft open: checkpoint failed: {exc}")
            if on_error is not None:
                on_error(str(exc))
            return
        self.loading = True
        if hasattr(self.view.workspace, "episode_available"):
            self.view.workspace.episode_available(False)
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
                        self.view.shelf.query.set(session.get("search", ""))
                        for episode, choice in self.view.workspace.batch.choices.items():
                            choice.set(episode in session.get("batch", []))
                        geometry = session.get("geometry", "")
                        if geometry:
                            self.view.root.geometry(geometry)
                self.loading = False
                if hasattr(self.view.workspace, "episode_available"):
                    self.view.workspace.episode_available(True)
                self.changed()
                if review_scope is None:
                    if hasattr(self.view.workspace.review, "scope"):
                        self.view.workspace.review.scope.set("Full video and audio")
                    self.refresh_review()
                else:
                    self.show_review(review_scope)
                self.refresh_release()
                if getattr(self.view, "root", None):
                    self.load_metadata()
                self.episode_controls.invalidate(refresh=True)
                if after_load is not None:
                    after_load()
            elif on_error is not None:
                on_error("Selection changed while loading the episode. No production was queued.")

        def failed(_message):
            if on_error is not None:
                on_error(_message)
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

    def select_note(self, item):
        """A written note that is not narrated yet: show its one next step, nothing else."""
        if self.loading:
            return
        if self.selected is None and getattr(self, "selected_note", None) == item:
            return  # Re-selected by a shelf refresh; nothing changed.
        try:
            self.checkpoint()
        except Exception as exc:
            self.view.status(f"Keep this draft open: checkpoint failed: {exc}")
            return
        self.selected = None
        self.selected_note = item
        for name in (
            "generation",
            "selection_generation",
            "review_generation",
            "release_generation",
            "package_generation",
        ):
            setattr(self, name, getattr(self, name) + 1)
        self.episode_controls.epoch += 1
        self.ready = None
        workspace = self.view.workspace
        workspace.draft_conflict(False)
        state = item.state if item.state != "Check script" else "Not narrated yet"
        workspace.show_empty(
            "Not narrated yet" if item.state != "Needs script" else "No narration script yet",
            item.detail
            or "Narrate this note first. You see the plan and its cost before anything is sent.",
            "Prepare this note…" if item.state != "Needs script" else None,
            lambda: self.view.open_preparation(note=item.note),
            heading=item.title,
        )
        workspace.subtitle.configure(text=f"Field Note {item.note} · written note · {state}")
        self.view.readiness.empty(
            f"FIELD NOTE {item.note}",
            "Not narrated yet",
            "Narration and captions come first. Studio shows the plan and any cost before "
            "it sends anything.",
            "Prepare this note…" if item.state != "Needs script" else None,
            (lambda: self.view.open_preparation(note=item.note))
            if item.state != "Needs script"
            else None,
        )

    def changed(self):
        self.episode_controls.invalidate()
        self.generation += 1
        self.ready = None
        self.view.workspace.show_plan("Check your changes before queueing a version.")
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
            self.view.status("Choose a narrated episode and wait for its settings to load.")
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
        self.view.workspace.show_plan("Checking the note and the saved versions…")

        def planned(value):
            if generation != self.generation:
                return
            request, summary = value
            self.view.workspace.preflight_status(
                "Ready. Checks on this computer passed; nothing is published.",
                action,
            )
            self.ready = (identifier, action, request)
            self.view.workspace.show_plan(summary, ready=True)
            self.view.status("Plan checked. Queue it when you are ready.")

        recipe = (
            copy.deepcopy(self.view.workspace.production_base)
            if hasattr(self.view.workspace, "production_base")
            else None
        )

        def failed(message):
            if generation == self.generation and identifier == self.selected:
                self.episode_controls.failed(message)
                self.view.workspace.preflight_status("Blocked: " + message, action)
                self.view.workspace.show_plan("Checks stopped this plan:\n\n" + message)

        self.task(
            lambda: self.studio.checked_plan(identifier, action, speed, outro, sound, recipe),
            planned,
            failed,
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
        if self.production.busy:
            self.view.status(
                "The full episode is being checked or queued. No second job was started."
            )
            return
        if self.ready is None:
            self.view.status("Check the plan first.")
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
            job = self.view.jobs.jobs.get(identifier)
            if job and job.action == "prepare" and job.status != "waiting":
                self.view.open_preparation(note=json.loads(job.request)["note"])
                return
            self.task(
                lambda: self.studio.retry(identifier),
                lambda _: self.view.status(
                    "Retry queued with the original settings. A changed note will block it."
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
            self.view.status(f"Release record saved for {identifier}.")
            self.refresh_shelf_hints()

        def saved(_):
            self.task(self.studio.catalog, refreshed)

        self.task(lambda: self.studio.publication(identifier, url, published), saved)

    def refresh_release(self):
        self.episode_controls.invalidate(refresh=True)
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

        def cost(text):
            if generation == self.release_generation and identifier == self.selected:
                publication.show_cost(text)

        self.task(lambda: self.studio.cost_line(identifier), cost, lambda _message: None)

    def prepare_package(self):
        """Release's Make upload folder: the same checked, local export as the card."""
        if not self.selected or self.loading or self.episode_controls.busy:
            return
        self.episode_controls.export()

    def refresh_package(self):
        if not self.selected or self.loading:
            return
        identifier = self.selected
        self.package_generation += 1
        generation = self.package_generation
        files = self.view.workspace.publication.files
        files.clear("Checking the upload folder and the latest full version…", loading=True)

        def loaded(snapshot):
            if generation == self.package_generation and identifier == self.selected:
                files.load(snapshot)
                if snapshot.details is not None:
                    self.view.workspace.publication.load_details(snapshot.details)

        def failed(message):
            if generation == self.package_generation and identifier == self.selected:
                files.clear("Upload folder unavailable: " + message)

        self.task(lambda: self.studio.package_snapshot(identifier), loaded, failed)

    def package_action_failed(self, generation, snapshot, message):
        files = self.view.workspace.publication.files
        if generation == self.package_generation and files.snapshot == snapshot:
            files.ready()
            files.error(message)

    def copy_package_path(self, name):
        files = self.view.workspace.publication.files
        snapshot = files.snapshot
        generation = self.package_generation
        if not snapshot or name not in files.copy_buttons:
            return
        files.working(name)

        def copied(path):
            if generation == self.package_generation and files.snapshot == snapshot:
                files.copied(name, path)
                self.view.status("Upload path copied. Paste it into the browser's file picker.")

        self.task(
            lambda: self.studio.package_upload_path(snapshot, name),
            copied,
            lambda message: self.package_action_failed(generation, snapshot, message),
        )

    def release_review(self):
        if self.selected and not self.loading:
            self.show_review(True)

    def open_publisher(self):
        self.task(
            self.studio.open_publisher,
            lambda _: self.view.status(
                "YouTube Studio opened. Upload the files, then record the published link and date."
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

    def open_prepared(self, episode):
        generation = self.generation

        def loaded(episodes):
            if generation != self.generation:
                return
            self.refresh_prepared_shelf(episodes)
            if episode not in self.episodes:
                self.view.status("The narration is not ready yet. Follow its job first.")
                return
            self.select(episode)
            if self.selected == episode:
                self.view.shelf.reveal(episode)
                self.view.workspace.tabs.select(0)
                self.view.status(
                    "Narration ready. Produce episode makes audio, captions, full video and "
                    "thumbnail together. You review it once; nothing is published."
                )
                if getattr(self.view, "preparation", None):
                    self.view.preparation.close()

        self.task(self.studio.catalog, loaded)

    def review_job(self):
        identifier = self.view.jobs.selection()
        if not identifier:
            return
        selected_job = getattr(self.view.jobs, "jobs", {}).get(identifier)
        if selected_job and selected_job.status == "succeeded" and selected_job.action == "prepare":
            self.production.start(selected_job.episode)
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
                self.view.status("This job's episode is no longer on the shelf.")
                return
            self.view.shelf.reveal(job.episode)
            self.select(job.episode, review_scope=job.action == "video")
            self.view.status("Reviewing the latest saved version; it may be newer than this job.")

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
            self.view.status("Tick both checks and enter your name before approving.")
            return
        identifier, reviewer = self.selected, review.reviewer.get().strip()
        generation = self.review_generation
        review.busy = True
        review.update_controls()

        def saved(_):
            self.view.status(f"Approval recorded for {identifier}.")
            review.remember(reviewer)
            self.task(lambda: self.studio.remember(reviewer=reviewer), lambda _: None)
            self.refresh_shelf_hints()
            if identifier == self.selected:
                self.episode_controls.invalidate(refresh=True)
            if generation == self.review_generation:
                self.refresh_review()

        def failed(message):
            if generation == self.review_generation:
                review.clear(message + " Check the version again before reviewing.")

        self.task(lambda: self.studio.approve(identifier, snapshot, reviewer), saved, failed)

    def job_detail(self):
        identifier = self.view.jobs.selection()
        if not identifier:
            return

        def shown(value):
            if self.view.jobs.selection() != identifier:
                return
            job, events, spend = value
            last = events[-1]["message"] if events else "Waiting for the background producer."
            result = job.result
            if result:
                try:
                    result = "Saved: " + str(Path(result).relative_to(self.studio.root))
                except ValueError:
                    pass
            guidance = {
                "queued": "Waiting for the background producer; jobs run one at a time.",
                "running": "Working; closing Studio keeps the job running.",
                "failed": "Retry with the same settings, or check a fresh plan if the note changed.",
                "interrupted": "Outcome unknown. Look at the saved result, or retry; checked saved parts are reused.",
                "cancelled": "Stopped at a safe point. Retry reuses the stages already checked and saved.",
                "succeeded": "Open the saved result. Review the full episode before making the upload folder.",
                "waiting": "Captions are still being made. Resume asks about the same caption request.",
            }.get(job.status, "")
            if job.action == "prepare":
                guidance = {
                    "failed": "Narration stopped. Check recovery shows the attempts; keep the saved parts.",
                    "interrupted": "Outcome unknown. Check recovery before another request.",
                    "succeeded": "Narration ready. Produce episode makes audio, captions, full video and thumbnail in one job. Review follows; nothing is published.",
                    "waiting": "Use Resume to check the same caption operation. No new narration is generated.",
                }.get(job.status, guidance)
            if job.identifier in getattr(self.view.jobs, "resolved", set()):
                guidance = "Historical attempt: a later attempt completed. No recovery is needed for this earlier failure; keep its history."
            meaningful = [
                event["stage"]
                for event in events
                if event["stage"] not in {"failed", "interrupted", "cancelled", "succeeded"}
            ]
            at = (
                meaningful[-1]
                if job.stage in {"failed", "interrupted", "cancelled"} and meaningful
                else job.stage
            )
            if job.status == "running" and (
                re.fullmatch(r"narration-\d+-of-\d+", at)
                or at in {"audio", "video", "captions", "export"}
            ):
                started = next((e["time"] for e in reversed(events) if e["stage"] == at), None)
                try:
                    elapsed = max(
                        0,
                        int(
                            (
                                datetime.now(timezone.utc) - datetime.fromisoformat(started)
                            ).total_seconds()
                        ),
                    )
                except (TypeError, ValueError, OverflowError):
                    elapsed = None
                waiting = (
                    f" · {elapsed // 60}:{elapsed % 60:02d} elapsed locally"
                    if elapsed is not None
                    else ""
                )
                if job.action == "prepare":
                    activity = (
                        "Waiting for caption response"
                        if at == "captions"
                        else "Waiting for narration response"
                    )
                    guidance = activity + waiting + "; provider progress unavailable."
                else:
                    activity = {
                        "audio": "Finishing audio and captions",
                        "video": "Rendering video",
                        "export": "Checking and exporting files",
                    }.get(at, "Working")
                    guidance = activity + waiting + "; completion estimate unavailable."
            if job.cancel_requested and job.status in {"queued", "running"}:
                guidance = "Stop requested; the current stage finishes its writes before stopping."
            milestones = progress_for(
                job, events, historical=job.identifier in getattr(self.view.jobs, "resolved", set())
            )
            if hasattr(self.view.jobs, "progress"):
                self.view.jobs.progress.show(milestones)
            context = f"{job.episode} · {milestones.title}"
            if job.action != "prepare":
                settings = json.loads(job.request).get("settings", {})
                recipe = (
                    "Saved full version"
                    if job.action == "export"
                    else f"{settings.get('speed', '—')}× pace · {settings.get('outro_seconds', '—')}s outro"
                )
                context += " · " + recipe
            if job.status == "succeeded":
                guidance = milestones.next_step
                review = self.view.workspace.review.snapshot
                if (
                    job.action == "video"
                    and job.episode == self.selected
                    and review
                    and review.identity
                    and review.approved
                    and review.full_video
                    and review.video
                    and job.result
                    and Path(review.video).parent == Path(job.result)
                ):
                    guidance = "This full episode is already approved. Next: make its upload folder. This job published nothing."
            reason, hidden = split_details(job.error or result or last)
            if hidden:
                reason += " Full renderer output is in Job history."
            if job.status in {"failed", "interrupted", "cancelled"} and not re.fullmatch(
                r"narration-\d+-of-\d+", at
            ):
                # Keep the exact diagnostic stage beside the milestones, unless the
                # milestone title already names it ("Narration 2/3").
                reason = f"{at}: {reason}"
            reason = shorten(reason, 200 if spend else 260)
            if spend and job.status in {"failed", "interrupted", "cancelled"}:
                # Always visible beside a paid failure, even when the reason is truncated.
                reason = spend + "\n" + reason
            self.view.jobs.detail.configure(text=f"{context} · {guidance}\n{reason}")

        def read():
            job = self.studio.repository.get(identifier)
            spend = ""
            if job.action == "prepare" and job.status in {"failed", "interrupted", "cancelled"}:
                summary = getattr(self.studio, "spend_summary", None)
                spend = summary(job.episode) if summary else ""
            return job, self.studio.repository.events(identifier), spend

        self.task(read, shown)

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

    def refresh_prepared_shelf(self, episodes):
        # Updating the catalog must not reload the selected episode's unfinished controls.
        selected = self.selected
        choices = self.view.workspace.batch.selection()
        self.loaded(episodes)
        for identifier, choice in self.view.workspace.batch.choices.items():
            choice.set(identifier in choices)
        if selected in self.episodes:
            self.view.status(
                "Shelf refreshed. Your edits stay open; new narrations still need producing and review."
            )

    def poll(self):
        if self.closed or self.polling:
            return
        self.polling = True

        def loaded(jobs):
            self.polling = False
            self.view.jobs.render(jobs)
            prepared = tuple(
                (job.identifier, job.status) for job in jobs if job.action == "prepare"
            )
            if prepared != self.preparation_jobs:
                self.preparation_jobs = prepared
                if any(status == "succeeded" for _, status in prepared):
                    self.task(self.studio.catalog, self.refresh_prepared_shelf)
            self.job_detail()
            self.episode_controls.jobs_changed(jobs)
            statuses = tuple((job.identifier, job.status) for job in jobs)
            if statuses != getattr(self, "shelf_jobs", None):
                self.shelf_jobs = statuses
                self.refresh_shelf_hints()
            signature = tuple(
                (job.identifier, job.status) for job in jobs if job.episode == self.selected
            )
            if signature != self.review_jobs:
                previous = self.review_jobs
                self.review_jobs = signature
                if previous is not None:
                    old = dict(previous)
                    if any(
                        job.episode == self.selected
                        and job.action == "video"
                        and job.status == "succeeded"
                        and old.get(job.identifier) != "succeeded"
                        for job in jobs
                    ):
                        self.view.workspace.review.scope.set("Full video and audio")
                        self.view.status(
                            f"{self.selected}: full episode ready. Review it once, with its "
                            "subtitles, then make the upload folder."
                        )
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


def shorten(text: str, limit: int) -> str:
    """Cut at a sentence end where possible, never mid-label; History keeps the rest."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    end = head.rfind(". ")
    head = head[: end + 1] if end >= limit // 3 else head.rsplit(" ", 1)[0] + "…"
    return head + " Full details in History."
