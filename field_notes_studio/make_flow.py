"""Make episode coordination: work list, pre-flight, run timeline and website update.

UI intent only. Reads run on the controller's background executor and come back
through its main-thread mailbox; the website update streams from its own thread,
because it can run for minutes. Every decision with a cost stays in the service:
this module never builds a request, a consent or a command line itself.
"""

from __future__ import annotations

import threading

from field_notes_studio.processes import notify, open_url
from field_notes_studio.readiness_models import readable

BILLING_CONSOLE = "https://console.cloud.google.com/billing"


class MakeFlow:
    def __init__(self, controller, app):
        self.controller = controller
        self.app = app
        self.studio = controller.studio
        self.preflight = None
        self.run_id = None
        self.run_loading = False
        self.work_loading = False
        self.groups = {}
        self.notify = False
        self.website_thread = None

    # Work list -----------------------------------------------------------------------

    def refresh_work(self, *, check=True):
        """A quick pass from the cache first, then verify whatever changed."""
        if self.work_loading:
            return
        self.work_loading = True

        def quick(work):
            self.app.home.load(work)
            self._notice(work)
            if check:
                self.controller.task(
                    lambda: self.studio.work_list(check=True), self._verified, self._failed
                )
            else:
                self.work_loading = False

        self.controller.task(lambda: self.studio.work_list(check=False), quick, self._failed)

    def _verified(self, work):
        self.work_loading = False
        self.app.home.load(work)
        self._notice(work)

    def _failed(self, message):
        self.work_loading = False
        sentence, technical = readable(message)
        self.app.status(
            "The work list could not be read. Menu → Episodes and stages still works."
            if technical
            else sentence
        )

    def _notice(self, work):
        """A desktop notification when a run newly needs the person (optional)."""
        groups = {item.identifier: item.group for item in work.items if item.run}
        if self.notify:
            for identifier, group in groups.items():
                if group == "needs-you" and self.groups.get(identifier) == "working":
                    item = next(i for i in work.items if i.identifier == identifier)
                    notify("Moth & Gravel studio", f"{item.title}: {item.state}")
        self.groups = groups

    def open_item(self, item):
        if item.run:
            self.show_run(item.run)
        elif item.next == "Make":
            self.open_preflight(note=item.note)
        else:
            self.app.show_episode(item.identifier)

    def choose(self):
        """Make episode from a note…: pick a note, then see the summary."""
        from field_notes_studio.presentation.make_episode import NoteChooser

        def loaded(work):
            items = [
                i
                for i in work.items
                if i.next == "Make" or (not i.run and i.next in {"Produce"} and not i.note)
            ]
            NoteChooser(self.app.root, items, self.open_item_for_make)

        self.controller.task(lambda: self.studio.work_list(check=False), loaded)

    def open_item_for_make(self, item):
        if item.note:
            self.open_preflight(note=item.note)
        else:
            self.open_preflight(episode=item.identifier)

    # Pre-flight ----------------------------------------------------------------------

    def open_preflight(self, *, note="", episode=""):
        from field_notes_studio.presentation.make_episode import PreflightDialog

        if self.preflight is not None and self.preflight.window.winfo_exists():
            self.preflight.window.destroy()
        dialog = self.preflight = PreflightDialog(
            self.app.root,
            {
                "confirm": self.confirm,
                "expert": lambda: self.expert(note, episode),
                "settings": lambda: self.settings(episode),
                "waiting": self.waiting_text,
                "closed": lambda: None,
            },
        )
        self.controller.task(
            lambda: self.studio.make_plan(note=note, episode=episode),
            dialog.show,
            dialog.failed,
        )

    def waiting_text(self, plan):
        keys = [s.key for s in plan.steps if s.kind in {"paid", "local"}]
        try:
            history = [self.studio.repository.durations(key) for key in keys]
        except Exception:
            history = []
        if not history or not all(history):
            return "No timing history on this computer yet; you can close Studio meanwhile."
        low = sum(min(values) for values in history) / 60
        high = sum(max(values) for values in history) / 60
        span = (
            f"about {round(high)}" if round(low) == round(high) else f"{round(low)}–{round(high)}"
        )
        return f"{span} minutes of waiting on this computer before; you can close Studio meanwhile."

    def confirm(self, plan, allowed):
        dialog = self.preflight

        def started(run_id):
            if dialog is not None and dialog.window.winfo_exists():
                dialog.window.destroy()
            self.app.status("Make episode started. Nothing is published; you review first.")
            self.show_run(run_id)
            self.refresh_work(check=False)

        def failed(message):
            if dialog is None or not dialog.window.winfo_exists():
                return
            # Re-inspect: the summary must show what a new confirm would cover.
            dialog.loading(message + " Checking again…")
            self.controller.task(
                lambda: self.studio.make_plan(note=plan.note, episode=plan.episode),
                dialog.show,
                dialog.failed,
            )

        self.controller.task(lambda: self.studio.make_episode(plan, allowed), started, failed)

    def expert(self, note, episode):
        if self.preflight is not None and self.preflight.window.winfo_exists():
            self.preflight.window.destroy()
        if note:
            self.app.open_preparation(note=note)
        elif episode:
            self.app.show_episode(episode)

    def settings(self, episode):
        if self.preflight is not None and self.preflight.window.winfo_exists():
            self.preflight.window.destroy()
        if episode:
            self.app.show_episode(episode)
            self.controller.episode_controls.open_recipes()
        else:
            self.app.status("Show settings apply once the note is narrated; defaults are used.")

    # Run timeline ----------------------------------------------------------------------

    def show_run(self, run_id):
        self.run_id = run_id
        self.app.show_view("run")
        self.reload_run()

    def reload_run(self):
        if self.run_id is None or self.run_loading:
            return
        self.run_loading = True
        run_id = self.run_id

        def read():
            view = self.studio.runs().view(run_id)
            title = view.episode
            for episode in self.studio.catalog():
                if episode.identifier == view.episode:
                    title = f"{view.episode} · {episode.title}"
            run = self.studio.repository.run(run_id)
            name = (run.get("consent") or {}).get("title") or title.split(" · ", 1)[-1]
            if run.get("note"):
                title = f"Field Note {run['note']} · {name}"
            attempts, diagnostics = (), ""
            if view.phase == "paused":
                spend = self.studio.spend_state(view.episode)
                attempts = spend.attempts
                diagnostics = "\n".join(
                    [view.headline, view.detail, spend.limits, spend.sentence()]
                    + [f"{a.when} · {a.part} · {a.detail} · {a.estimate}" for a in attempts]
                    + [f"run {run_id} · job {view.job}"]
                )
            return view, title, attempts, diagnostics

        def shown(value):
            self.run_loading = False
            if run_id == self.run_id:
                self.app.run_panel.show(*value)

        def failed(_message):
            self.run_loading = False

        self.controller.task(read, shown, failed)

    def stop(self, view):
        self.controller.task(
            lambda: self.studio.stop_after_step(view.identifier), lambda _: self.reload_run()
        )
        self.app.status("Studio stops after the current step; saved work is kept.")

    def next(self, view):
        if view.phase == "stopped":
            self.controller.task(
                lambda: self.studio.continue_run(view.identifier), lambda _: self.reload_run()
            )
        elif view.phase == "review":
            self.app.show_episode(view.episode, stage=1)
        else:
            self.app.show_episode(view.episode, stage=2)

    def recover(self, view):
        """Try once more…: the expert recovery with its own duplicate-charge consent."""
        run = self.studio.repository.run(view.identifier)
        self.app.open_preparation(note=run.get("note", ""))

    def billing(self):
        open_url(BILLING_CONSOLE)

    def set_notify(self, value):
        self.notify = bool(value)
        self.controller.task(lambda: self.studio.remember(notify=self.notify), lambda _: None)

    # Website update --------------------------------------------------------------------

    def open_website(self, episode):
        from field_notes_studio.presentation.website import WebsiteDialog

        if getattr(self, "website", None) is None or not self.website.window.winfo_exists():
            self.website = WebsiteDialog(self.app.root, {"run": self.run_website})
        self.website.open(self.app.root)
        self.controller.task(lambda: self.studio.website_plan(episode), self.website.show)

    def run_website(self, plan):
        mailbox = self.controller.mailbox
        dialog = self.website

        def work():
            def emit(line):
                mailbox.put((dialog.line, line, None, None))

            try:
                result = self.studio.website_update(plan, confirmed=True, emit=emit)
            except Exception as exc:  # noqa: BLE001 - shown to the person, nothing hidden
                from field_notes_studio.website import WebsiteResult

                result = WebsiteResult(False, f"The website update stopped: {exc}")
            mailbox.put((dialog.finished, result, None, None))

        self.website_thread = threading.Thread(target=work, name="studio-website", daemon=True)
        self.website_thread.start()
