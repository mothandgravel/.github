"""One explicit full-episode intent; inspect then enqueue one existing video job."""

from __future__ import annotations


class ProductionFlow:
    def __init__(self, controller):
        self.controller = controller
        self.busy = False

    def _busy(self, value):
        self.busy = value
        view = self.controller.view
        view.workspace.production_working(value)
        view.jobs.production_working(value)

    def _failed(self, message):
        self._busy(False)
        self.controller.view.status(f"Episode was not queued: {message}")
        self.controller.view.workspace.preflight_status("Blocked: " + message)

    def start(self, episode=None):
        c = self.controller
        if self.busy or c.closed:
            return
        episode = episode or c.selected
        if not episode:
            c.view.status("Choose a prepared recording first. No production was queued.")
            return
        if c.loading:
            c.view.status("Episode settings are still loading. Wait before starting production.")
            return
        try:
            c.checkpoint()
        except Exception as exc:
            self._failed(str(exc))
            return
        self._busy(True)
        generation = c.generation
        c.view.status(
            f"{episode}: checking the full episode — audio, captions, video and thumbnail…"
        )
        if episode == c.selected:
            self._plan(episode)
            return

        def loaded(episodes):
            if generation != c.generation:
                self._failed(
                    "Selection or settings changed during loading. Click Produce episode again."
                )
                return
            c.episodes = {item.identifier: item for item in episodes}
            choices = c.view.workspace.batch.selection()
            c.view.shelf.load(episodes)
            c.view.workspace.batch.load(episodes)
            for identifier, choice in c.view.workspace.batch.choices.items():
                choice.set(identifier in choices)
            if episode not in c.episodes:
                self._failed("The prepared recording is unavailable. Inspect its preparation job.")
                return
            # Load that episode's draft before capturing its recipe; never use the
            # controls belonging to the previously selected episode.
            c.select(
                episode,
                after_load=lambda: self._plan(episode),
                on_error=self._failed,
            )
            if c.selected == episode:
                c.view.shelf.reveal(episode)

        c.task(c.studio.catalog, loaded, self._failed)

    def _plan(self, episode):
        c = self.controller
        if c.selected != episode or c.loading:
            self._failed(
                "Selection changed before its settings loaded. Click Produce episode again."
            )
            return
        c.view.workspace.action.set("video")
        c.view.workspace.show_plan_tab()
        if getattr(c.view, "preparation", None):
            c.view.preparation.close()
        try:
            c.checkpoint()
            speed = float(c.view.workspace.speed.get())
            outro = float(c.view.workspace.outro.get())
            sound = c.view.workspace.sound.sound()
        except Exception as exc:
            self._failed(f"Check pace, outro and sound settings: {exc}")
            return
        generation = c.generation
        c.view.workspace.show_plan(
            "Checking your saved narration and current recipe. One job will finish audio, "
            "retime captions, render the full video and create its thumbnail.\n\n"
            "No new narration, automatic approval or publication."
        )

        def planned(value):
            if c.selected != episode or generation != c.generation:
                self._failed(
                    "Selection or settings changed during inspection. Click Produce episode again."
                )
                return
            request, summary = value
            c.view.workspace.preflight_status(
                "Full episode checks passed. Queueing audio + video together."
            )
            c.ready = None
            c.view.workspace.show_plan(summary + "\n\nQueueing the full episode…")

            def queued(identifier):
                self._busy(False)
                message = f"{episode}: full episode queued · {identifier[:8]}. Audio + captions → full video + thumbnail."
                c.view.status(message)
                if c.selected == episode and generation == c.generation:
                    c.view.workspace.show_plan(message + "\n\n" + summary)

                def shown(jobs):
                    c.view.jobs.render(jobs)
                    if c.selected == episode and c.view.jobs.tree.exists(identifier):
                        c.view.jobs.tree.selection_set(identifier)
                        c.view.jobs.tree.see(identifier)
                        c.job_detail()

                c.task(c.studio.repository.jobs, shown)

            c.task(lambda: c.studio.submit(episode, "video", request), queued, self._failed)

        recipe = c.view.workspace.effective_recipe()
        c.view.workspace.preflight_status("Checking source, recipe and installed video tools…")
        c.task(
            lambda: c.studio.checked_plan(episode, "video", speed, outro, sound, recipe),
            planned,
            self._failed,
        )
