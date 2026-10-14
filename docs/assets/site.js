(() => {
  "use strict";

  const root = document.documentElement;
  const themeButton = document.getElementById("light-switch");
  const menuButton = document.getElementById("menu-toggle");
  const navigation = document.getElementById("primary-nav");
  const storageKey = "moth-and-gravel-theme";

  function setTheme(theme) {
    const isAfterlight = theme === "afterlight";
    root.dataset.theme = isAfterlight ? "afterlight" : "night";
    themeButton?.setAttribute("aria-pressed", String(isAfterlight));
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", isAfterlight ? "#f1eee6" : "#17191b");
  }

  try {
    const saved = localStorage.getItem(storageKey);
    if (saved === "afterlight") setTheme(saved);
  } catch (_) {
    // The site works without persistent storage.
  }

  themeButton?.addEventListener("click", () => {
    const theme = root.dataset.theme === "afterlight" ? "night" : "afterlight";
    setTheme(theme);
    try { localStorage.setItem(storageKey, theme); } catch (_) {}
  });
  root.classList.add("has-site-controls");

  // Keep the authored routes as the source of the index. Without enhancement,
  // these are still ordinary, visible navigation links on every screen size.
  if (navigation && menuButton) {
    const routes = [...navigation.querySelectorAll("a")];
    const hints = {
      "Workbench": "Saved traces. Work in progress.",
      "Field notes": "Questions worth following.",
      "The thinking": "Soft wings. Hard ground.",
      "Contact": "Leave a loose end."
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
      hint.textContent = hints[label] || "Follow the work.";
      link.replaceChildren(number, name, hint);
    });
    const foot = document.createElement("div");
    foot.className = "nav-sheet-foot";
    const invitation = document.createElement("a");
    invitation.className = "nav-sheet-invitation";
    // Every shared masthead already points its brand at the studio's home.
    const home = new URL(document.querySelector(".brand").getAttribute("href"), location.href);
    invitation.href = new URL("questions/", home).href;
    invitation.textContent = "Give a question a little shape ↗";
    const reach = document.createElement("p");
    reach.className = "mono";
    reach.textContent = "BASED IN FINLAND / QUESTIONS FROM ANYWHERE";
    foot.append(invitation, reach);
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
