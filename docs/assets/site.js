(() => {
  "use strict";

  const root = document.documentElement;
  const themeButton = document.getElementById("light-switch");
  const menuButton = document.getElementById("menu-toggle");
  const navigation = document.getElementById("primary-nav");
  const storageKey = "moth-and-gravel-theme";

  // A per-device choice in the studio's own names: Night, Afterlight, or follow the system.
  // Choices use the same values as data-theme, so every Night and Afterlight style applies.
  const names = { night: "Night", afterlight: "Afterlight" };
  const prefersLight = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;
  const themeLabel = themeButton?.querySelector("[data-theme-label]");

  // One polite voice for small confirmations: the page's own status region when it has
  // one, otherwise a visually hidden region created on first use.
  let voice = null;
  function say(message) {
    if (!voice) {
      voice = document.querySelector('[role="status"]');
      if (!voice) {
        voice = document.createElement("p");
        voice.className = "visually-hidden";
        voice.setAttribute("role", "status");
        document.body.append(voice);
      }
    }
    voice.textContent = "";
    setTimeout(() => { voice.textContent = message; }, 40);
  }

  function themeName(choice, resolved) {
    return choice === "system" ? "System · " + names[resolved] : names[resolved];
  }

  function applyTheme(choice) {
    const resolved = choice === "system" ? (prefersLight?.matches ? "afterlight" : "night") : choice;
    root.dataset.themeChoice = choice;
    root.dataset.theme = resolved;
    if (themeLabel) themeLabel.textContent = themeName(choice, resolved);
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", resolved === "afterlight" ? "#f1eee6" : "#17191b");
  }

  applyTheme(["night", "afterlight"].includes(root.dataset.themeChoice) ? root.dataset.themeChoice : "system");

  // Each press changes what you see first: from System to the other named theme, then the
  // remaining one, then back to System.
  themeButton?.addEventListener("click", () => {
    const current = root.dataset.themeChoice;
    const shown = root.dataset.theme;
    const choice = current === "system" ? (shown === "night" ? "afterlight" : "night")
      : (prefersLight?.matches ? "afterlight" : "night") === current ? "system"
      : current === "night" ? "afterlight" : "night";
    applyTheme(choice);
    try { localStorage.setItem(storageKey, choice); } catch (_) {}
    say("Theme: " + themeName(choice, root.dataset.theme));
  });
  prefersLight?.addEventListener?.("change", () => {
    if (root.dataset.themeChoice === "system") applyTheme("system");
  });

  // The address is always a plain mailto link; copying is an extra for people without a mail app.
  const address = "hello@mothandgravel.com";
  function enableCopy(button) {
    button.hidden = false;
    const label = button.firstChild;
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(address);
        label.textContent = "Copied";
        say("Email address copied: " + address);
        setTimeout(() => { label.textContent = "Copy"; }, 2400);
      } catch (_) {
        const link = button.parentElement?.querySelector('a[href^="mailto:"]');
        if (link) {
          const range = document.createRange();
          range.selectNodeContents(link);
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
        }
        say("Copying is unavailable here. The address is " + address + ".");
      }
    });
  }
  document.querySelectorAll("[data-copy-email]").forEach(enableCopy);

  root.classList.add("has-site-controls");

  // The authored disclosure works without scripts. Enhancement only manages focus
  // and dismisses this nonmodal index when the visitor leaves it.
  const disclosure = menuButton?.closest("details");
  let keyboardOpening = false;
  if (disclosure) {
    menuButton.setAttribute("aria-expanded", String(disclosure.open));
    menuButton.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") keyboardOpening = true;
    });
    menuButton.addEventListener("pointerdown", () => { keyboardOpening = false; });
    disclosure.addEventListener("toggle", () => {
      const open = disclosure.open;
      navigation.classList.toggle("is-open", open);
      menuButton.setAttribute("aria-expanded", String(open));
      if (open && keyboardOpening) navigation.querySelector("a")?.focus({preventScroll:true});
      keyboardOpening = false;
    });
  }

  function closeMenu(restoreFocus = false) {
    if (!navigation || !menuButton) return;
    if (disclosure) disclosure.open = false;
    navigation.classList.remove("is-open");
    menuButton.setAttribute("aria-expanded", "false");
    if (restoreFocus) menuButton.focus({preventScroll:true});
  }

  navigation?.querySelectorAll("a").forEach(link => link.addEventListener("click", () => {
    if (!disclosure?.open) return;
    closeMenu();
    // Move keyboard focus to the selected room, with native anchor scrolling.
    const destination = new URL(link.href);
    if (destination.pathname !== location.pathname || !destination.hash) return;
    const target = document.getElementById(destination.hash.slice(1));
    if (target) {
      target.setAttribute("tabindex", "-1");
      target.focus({ preventScroll: true });
    }
  }));

  document.addEventListener("keydown", event => {
    // This is a nonmodal index: the page remains usable, and leaving it closes it.
    if (event.key === "Escape" && disclosure?.open) {
      closeMenu(true);
    }
  });

  document.addEventListener("pointerdown", event => {
    if (disclosure?.open &&
        !navigation.contains(event.target) &&
        !menuButton?.contains(event.target)) {
      closeMenu(navigation.contains(document.activeElement));
    }
  });

  navigation?.addEventListener("focusout", event => {
    if (event.relatedTarget && !navigation.contains(event.relatedTarget) && event.relatedTarget !== menuButton) closeMenu();
  });
  navigation?.addEventListener("keydown", event => {
    if (event.key === "Tab" && event.shiftKey && document.activeElement === navigation.querySelector("a")) {
      event.preventDefault();
      closeMenu(true);
    }
  });
  let menuWidth = window.innerWidth;
  window.addEventListener("resize", () => {
    const changed = menuWidth !== window.innerWidth;
    menuWidth = window.innerWidth;
    if (changed && disclosure?.open) closeMenu(navigation.contains(document.activeElement));
  });
  window.addEventListener("pagehide", () => {
    if (disclosure?.open) closeMenu(navigation.contains(document.activeElement));
  });
  window.addEventListener("blur", () => {
    if (disclosure?.open) closeMenu(navigation.contains(document.activeElement));
  });

  document.getElementById("year")?.replaceChildren(document.createTextNode(String(new Date().getFullYear())));
})();
