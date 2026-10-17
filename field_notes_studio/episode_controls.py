"""UI coordination for checked readiness and deliberate recipe application."""

from __future__ import annotations

import copy

from field_notes_studio.readiness_models import Readiness, readable
from field_notes_studio.recipes import Recipes, differences


class EpisodeControls:
    def __init__(self, controller):
        self.c = controller
        self.epoch = 0
        self.busy = False
        self.again = False
        self.window = None
        self.undo_value = None
        self.signature = None
        self.open_package_after_check = False

    @property
    def enabled(self):
        return hasattr(self.c.view, "readiness")

    def invalidate(self, *, refresh=False):
        if not self.enabled or self.c.closed:
            return
        self.epoch += 1
        self.c.view.readiness.invalidate(enabled=bool(self.c.selected and not self.c.loading))
        self.c.view.workspace.preflight_status("Not checked for the current recipe.", "both")
        self.open_package_after_check = False
        self.update_overrides()
        if refresh:
            self.refresh()

    def update_overrides(self):
        w = self.c.view.workspace
        if not hasattr(w, "recipe_info"):
            return
        reference = w.show_recipe
        if self.window and self.window.alive():
            self.window.valid_selection = self.window.episode == self.c.selected
        if self.window and self.window.alive() and not self.window.valid_selection:
            self.window.message.configure(
                text="Episode selection changed. Reload recipes to work on the newly selected episode."
            )
            for button in (self.window.apply, self.window.save_new, self.window.update):
                button.configure(state="disabled")
        try:
            current = w.effective_recipe()
            if self.window and self.window.alive() and self.window.valid_selection:
                self.window.current = current
                self.window.show_difference()
            delta = differences(reference.get("settings", w.production_base), current)
            text = ("Recipe snapshot: " + reference["name"]) if reference else "Configured defaults"
            text += f" · {len(delta)} episode override(s)" if delta else " · no episode overrides"
            if delta:
                text += (
                    "\n"
                    + "; ".join(delta[:2])
                    + (" · more in Show recipes" if len(delta) > 2 else "")
                )
        except (TypeError, KeyError, ValueError):
            text = "Unfinished recipe values · finish editing before checking or saving."
            if self.window and self.window.alive() and self.window.valid_selection:
                self.window.message.configure(text=text)
        w.recipe_info.configure(text=text)

    def refresh(self):
        c = self.c
        if not self.enabled or c.closed or not c.selected or c.loading:
            return
        if self.busy:
            self.again = True
            return
        try:
            settings = c.view.workspace.effective_recipe()
        except (TypeError, KeyError, ValueError) as exc:
            self.failed(str(exc))
            return
        episode, epoch = c.selected, self.epoch
        self.busy = True
        c.view.readiness.working()

        def finish(snapshot=None, error=None):
            self.busy = False
            if not c.closed and episode == c.selected and epoch == self.epoch:
                if error:
                    self.failed(error)
                else:
                    c.view.readiness.show(snapshot)
                    c.view.workspace.preflight_status(
                        snapshot.detail,
                        "export" if snapshot.action in {"export", "package"} else "video",
                    )
                    if snapshot.action in {"export", "package", "review"}:
                        c.view.workspace.preflight_status(
                            "Saved full edition verified. No production needed for the checked recipe."
                        )
                    if self.open_package_after_check and snapshot.action == "package":
                        c.view.workspace.tabs.select(c.view.workspace.publication)
                        c.view.workspace.publication.tabs.select(c.view.workspace.publication.files)
                        c.refresh_package()
                    self.open_package_after_check = False
            if self.again and not c.closed:
                self.again = False
                self.refresh()

        c.task(
            lambda: c.studio.readiness(episode, settings),
            lambda value: finish(value),
            lambda message: finish(error=message),
        )

    def failed(self, message):
        if self.enabled and not self.c.closed:
            sentence, detail = readable(message)
            self.c.view.readiness.show(
                Readiness(
                    self.c.selected or "",
                    "repair",
                    "Check the blockers",
                    sentence,
                    technical=detail,
                )
            )
            self.c.view.workspace.preflight_status("Blocked: " + sentence)

    def jobs_changed(self, jobs):
        if not self.enabled:
            return
        signature = (
            self.c.selected,
            tuple((j.identifier, j.status) for j in jobs if j.episode == self.c.selected),
        )
        if signature != self.signature:
            self.signature = signature
            self.invalidate(refresh=True)

    def act(self):
        c = self.c
        if c.closed or c.loading or self.busy or not self.enabled:
            return
        snapshot = c.view.readiness.snapshot
        if snapshot is None or snapshot.episode != c.selected:
            self.refresh()
        elif snapshot.action == "check":
            self.refresh()
        elif snapshot.action == "produce":
            c.production.start()
        elif snapshot.action == "review":
            c.show_review(True)
        elif snapshot.action == "export":
            self.export()
        elif snapshot.action == "package":
            self.open_package_after_check = True
            self.refresh()
        elif snapshot.action == "job":
            if c.view.jobs.tree.exists(snapshot.job):
                c.view.jobs.tree.selection_set(snapshot.job)
                c.view.jobs.tree.see(snapshot.job)
                c.job_detail()
            self.refresh()
        elif snapshot.action == "health":
            c.view.workspace.tabs.select(c.view.workspace.health.master)
            c.view.workspace.show_health(
                "Preflight blocker:\n\n"
                + snapshot.detail
                + "\n\nCheck health for installed tools. No installation or repair is automatic."
                + ("\n\nTechnical detail: " + snapshot.technical if snapshot.technical else "")
            )
        else:
            c.view.workspace.show_plan_tab()
            c.view.workspace.show_plan(
                snapshot.detail
                + ("\n\nTechnical detail: " + snapshot.technical if snapshot.technical else "")
            )
            c.view.workspace.preflight_status("Blocked: " + snapshot.detail)

    def export(self):
        c = self.c
        episode, generation = c.selected, c.generation
        self.busy = True
        c.view.readiness.working()
        c.view.workspace.preflight_status(
            "Checking full review, export files and saved publishing copy…", "export"
        )

        def failed(message):
            self.busy = False
            if not c.closed and episode == c.selected and generation == c.generation:
                self.failed(message)
                c.view.workspace.preflight_status("Blocked: " + message, "export")
            else:
                self.invalidate(refresh=True)

        def planned(value):
            if c.closed or episode != c.selected or generation != c.generation:
                failed("Selection or recipe changed. Check readiness again; nothing was queued.")
                return
            request, _ = value

            def queued(identifier):
                self.busy = False
                c.view.status(
                    f"{episode}: upload package queued · {identifier[:8]}. No rendering or publication."
                )
                self.invalidate(refresh=True)

            c.task(lambda: c.studio.submit(episode, "export", request), queued, failed)

        c.task(lambda: c.studio.checked_plan(episode, "export", None, None), planned, failed)

    def open_recipes(self):
        c = self.c
        if not c.selected or c.loading:
            return
        from field_notes_studio.presentation.recipes import RecipeWindow

        if self.window and self.window.alive():
            self.window.window.lift()
        else:
            self.window = RecipeWindow(
                c.view.root,
                self.apply_recipe,
                self.save_recipe,
                self.reload_recipes,
                self.undo_recipe,
            )
            self.window.difference = lambda base, current: (
                "Differences from selected recipe:\n\n"
                + ("\n".join(differences(base, current)) or "No differences.")
                if base
                else "Save the current settings as a named recipe, or choose a saved recipe."
            )
        self.reload_recipes()

    def reload_recipes(self):
        c = self.c
        if not self.window or not self.window.alive() or not c.selected:
            return
        try:
            current = c.view.workspace.effective_recipe()
            book = Recipes(c.studio.repository, c.studio.pipeline)
            data, identity = book.load()
            self.window.episode = c.selected
            self.window.valid_selection = True
            self.window.save_new.configure(state="normal")
            self.window.load(data, identity, current, c.view.workspace.show_recipe)
        except (OSError, ValueError, KeyError) as exc:
            self.window.message.configure(text=str(exc))

    def apply_recipe(self):
        c, window = self.c, self.window
        if (
            c.loading
            or not c.selected
            or not window
            or not window.alive()
            or window.episode != c.selected
        ):
            return
        try:
            item = window.items.get(window.choice.get())
            if not item:
                return
            reference = Recipes(c.studio.repository, c.studio.pipeline).select(
                item[0], window.identity
            )
            c.checkpoint()
            w = c.view.workspace
            self.undo_value = (
                c.selected,
                {
                    key: copy.deepcopy(value)
                    for key, value in w.draft().items()
                    if key in {"production_base", "show_recipe", "recipe", "sound"}
                },
            )
            w.production_base = copy.deepcopy(reference["settings"])
            w.show_recipe = reference
            w.speed.set(str(reference["settings"]["speed"]))
            w.outro.set(str(reference["settings"]["outro_seconds"]))
            w.sound.fill(reference["settings"])
            c.changed()
            c.checkpoint()
            window.undo.configure(state="normal")
            self.reload_recipes()
            window.message.configure(
                text="Applied to this episode draft only. Use Undo apply to recover the previous draft. No job queued."
            )
        except (OSError, ValueError, KeyError) as exc:
            window.message.configure(text=str(exc))

    def undo_recipe(self):
        c = self.c
        if not self.undo_value or self.undo_value[0] != c.selected or c.loading:
            self.window.message.configure(
                text="Undo belongs to the episode where the recipe was applied."
            )
            return
        try:
            retained = c.view.workspace.draft()
            retained.update(self.undo_value[1])
            c.view.workspace.restore(retained)
            c.changed()
            c.checkpoint()
            self.undo_value = None
            self.window.undo.configure(state="disabled")
            self.reload_recipes()
        except (OSError, ValueError, KeyError) as exc:
            self.window.message.configure(text="Draft needs attention: " + str(exc))

    def save_recipe(self, name, identifier):
        c, window = self.c, self.window
        if (
            c.loading
            or not c.selected
            or not window
            or not window.alive()
            or window.episode != c.selected
        ):
            return
        try:
            settings = c.view.workspace.effective_recipe()
            reference, _ = Recipes(c.studio.repository, c.studio.pipeline).save(
                name, settings, window.identity, identifier
            )
            # Binding the current draft to its saved recipe does not change media.
            c.view.workspace.show_recipe = reference
            c.changed()
            c.checkpoint()
            window.choice.set(name.strip())
            self.reload_recipes()
            window.message.configure(
                text="Show recipe saved locally. Other episode drafts and queued work are unchanged."
            )
        except (OSError, ValueError, KeyError) as exc:
            window.message.configure(text=str(exc))
