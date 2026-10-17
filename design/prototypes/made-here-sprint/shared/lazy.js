// Loads a playground toy only when its bench comes into view. Nothing here runs on the home page.
(() => {
  const benches = document.querySelectorAll("[data-toy]");
  if (!benches.length) return;
  const base = new URL("./toys/", document.currentScript.src);
  const load = (el) => {
    if (el.dataset.loaded) return;
    el.dataset.loaded = "1";
    import(new URL(el.dataset.toy + ".mjs", base).href)
      .then((m) => m.mount(el))
      .catch(() => { el.dataset.loaded = ""; });
  };
  if (!("IntersectionObserver" in window)) { benches.forEach(load); return; }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { io.unobserve(e.target); load(e.target); }
  }, { rootMargin: "200px 0px" });
  benches.forEach((b) => io.observe(b));
})();
