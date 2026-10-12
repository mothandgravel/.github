(() => {
  "use strict";

  const root = document.documentElement;
  const themeButton = document.getElementById("light-switch");
  const themeLabel = themeButton?.querySelector(".switch-label");
  const menuButton = document.getElementById("menu-toggle");
  const navigation = document.getElementById("primary-nav");
  const storageKey = "moth-and-gravel-theme";

  function setTheme(theme) {
    const isAfterlight = theme === "afterlight";
    root.dataset.theme = isAfterlight ? "afterlight" : "night";
    themeButton?.setAttribute("aria-pressed", String(isAfterlight));
    themeButton?.setAttribute("aria-label", isAfterlight ? "Switch to night color theme" : "Switch to afterlight color theme");
    if (themeLabel) themeLabel.textContent = isAfterlight ? "Nightfall" : "Afterlight";
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

  navigation?.querySelectorAll("a").forEach(link => link.addEventListener("click", closeMenu));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      closeMenu();
      menuButton?.focus();
    }
  });

  document.getElementById("year")?.replaceChildren(document.createTextNode(String(new Date().getFullYear())));
})();
