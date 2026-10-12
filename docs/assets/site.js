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

  function closeMenu() {
    if (!navigation || !menuButton) return;
    navigation.classList.remove("is-open");
    menuButton.setAttribute("aria-expanded", "false");
  }

  menuButton?.addEventListener("click", () => {
    const willOpen = !navigation?.classList.contains("is-open");
    navigation?.classList.toggle("is-open", willOpen);
    menuButton.setAttribute("aria-expanded", String(willOpen));
  });

  navigation?.querySelectorAll("a").forEach(link => link.addEventListener("click", () => {
    if (!navigation.classList.contains("is-open")) return;
    closeMenu();
    // Move keyboard focus to the section selected from the mobile menu.
    const hash = link.getAttribute("href");
    if (!hash?.startsWith("#")) return;
    const target = document.getElementById(hash.slice(1));
    if (target) {
      target.setAttribute("tabindex", "-1");
      target.focus({ preventScroll: true });
    }
  }));

  document.addEventListener("keydown", event => {
    // Escape should never steal focus when the mobile menu is already closed.
    if (event.key === "Escape" && navigation?.classList.contains("is-open")) {
      closeMenu();
      menuButton?.focus();
    }
  });

  document.addEventListener("pointerdown", event => {
    if (navigation?.classList.contains("is-open") &&
        !navigation.contains(event.target) &&
        !menuButton?.contains(event.target)) {
      closeMenu();
    }
  });

  window.matchMedia("(min-width: 901px)").addEventListener("change", event => {
    if (event.matches) closeMenu();
  });

  document.getElementById("year")?.replaceChildren(document.createTextNode(String(new Date().getFullYear())));
})();
