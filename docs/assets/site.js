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

  // Keep the authored routes as the source of the index. Without enhancement,
  // these are still ordinary, visible navigation links on every screen size.
  if (navigation && menuButton) {
    const routes = [...navigation.querySelectorAll("a")];
    // Hints are visual company for each route; the link keeps its plain name.
    const hints = {
      "workbench": "Saved traces. Work in progress.",
      "field notes": "Questions worth following.",
      "the thinking": "Soft wings. Hard ground.",
      "contact": "Email, or shape a brief first.",
      "the studio": "Back to the bench.",
      "bring a question": "Give a question a little shape."
    };
    const heading = document.createElement("div");
    heading.className = "nav-sheet-heading";
    const index = document.createElement("span");
    index.className = "mono";
    index.textContent = "M+G / THE STUDIO INDEX";
    const title = document.createElement("p");
    title.textContent = "A few ways in.";
    heading.append(index, title);
    navigation.prepend(heading);
    routes.forEach((link, i) => {
      const label = link.textContent.trim();
      const number = document.createElement("span");
      number.className = "nav-sheet-index mono";
      number.setAttribute("aria-hidden", "true");
      number.textContent = String(i + 1).padStart(2, "0");
      const name = document.createElement("span");
      name.className = "nav-sheet-label";
      name.textContent = label;
      const hint = document.createElement("span");
      hint.className = "nav-sheet-hint";
      hint.setAttribute("aria-hidden", "true");
      hint.textContent = link.dataset.hint || hints[label.toLowerCase()] || "";
      link.replaceChildren(number, name, hint);
    });
    const foot = document.createElement("div");
    foot.className = "nav-sheet-foot";
    const invitation = document.createElement("a");
    invitation.className = "nav-sheet-invitation";
    // Every shared masthead already points its brand at the studio's home.
    const home = new URL(document.querySelector(".brand").getAttribute("href"), location.href);
    invitation.href = new URL("questions/", home).href;
    invitation.textContent = "Shape a brief first ↗";
    const mail = document.querySelector(".header-mail")?.cloneNode(true);
    if (mail) {
      mail.className = "nav-sheet-mail";
      mail.querySelector("a")?.classList.remove("header-mail-link");
      mail.querySelectorAll("[data-copy-email]").forEach(enableCopy);
    }
    const reach = document.createElement("p");
    reach.className = "mono";
    reach.textContent = "BASED IN FINLAND / QUESTIONS FROM ANYWHERE";
    foot.append(...[invitation, mail, reach].filter(Boolean));
    navigation.append(foot);
    root.classList.add("has-nav-sheet");
  }

  function closeMenu(restoreFocus = false) {
    if (!navigation || !menuButton) return;
    navigation.classList.remove("is-open");
    menuButton.setAttribute("aria-expanded", "false");
    if (restoreFocus) menuButton.focus({preventScroll:true});
  }

  menuButton?.addEventListener("click", () => {
    const willOpen = !navigation?.classList.contains("is-open");
    navigation?.classList.toggle("is-open", willOpen);
    menuButton.setAttribute("aria-expanded", String(willOpen));
    if (willOpen) navigation?.querySelector("a")?.focus({preventScroll:true});
  });

  navigation?.querySelectorAll("a").forEach(link => link.addEventListener("click", () => {
    if (!navigation.classList.contains("is-open")) return;
    closeMenu();
    // Move keyboard focus to the selected room, with native anchor scrolling.
    const hash = link.getAttribute("href");
    if (!hash?.startsWith("#")) return;
    const target = document.getElementById(hash.slice(1));
    if (target) {
      target.setAttribute("tabindex", "-1");
      target.focus({ preventScroll: true });
    }
  }));

  document.addEventListener("keydown", event => {
    // This is a nonmodal index: the page remains usable, and leaving it closes it.
    if (event.key === "Escape" && navigation?.classList.contains("is-open")) {
      closeMenu(true);
    }
  });

  document.addEventListener("pointerdown", event => {
    if (navigation?.classList.contains("is-open") &&
        !navigation.contains(event.target) &&
        !menuButton?.contains(event.target)) {
      closeMenu(navigation.contains(document.activeElement));
    }
  });

  navigation?.addEventListener("focusout", event => {
    if (event.relatedTarget && !navigation.contains(event.relatedTarget) && event.relatedTarget !== menuButton) closeMenu();
  });
  let menuWidth = window.innerWidth;
  window.addEventListener("resize", () => {
    const changed = menuWidth !== window.innerWidth;
    menuWidth = window.innerWidth;
    if (changed && navigation?.classList.contains("is-open")) closeMenu(navigation.contains(document.activeElement));
  });
  window.addEventListener("pagehide", () => {
    if (navigation?.classList.contains("is-open")) closeMenu(navigation.contains(document.activeElement));
  });
  window.addEventListener("blur", () => {
    if (navigation?.classList.contains("is-open")) closeMenu(navigation.contains(document.activeElement));
  });

  document.getElementById("year")?.replaceChildren(document.createTextNode(String(new Date().getFullYear())));
})();
