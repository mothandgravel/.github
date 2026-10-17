// Loads a playground toy only when its bench comes near the viewport. Used on the
// playground and the question pages; never on the homepage.
const benches = document.querySelectorAll('[data-toy]');
const load = (el) => {
  if (el.dataset.loaded) return;
  el.dataset.loaded = 'loading';
  import(new URL(`./playground/${el.dataset.toy}.mjs`, import.meta.url).href)
    .then((toy) => { toy.mount(el); el.dataset.loaded = 'ready'; })
    .catch(() => { el.dataset.loaded = ''; });
};
if (!('IntersectionObserver' in window)) benches.forEach(load);
else {
  const watch = new IntersectionObserver((entries) => {
    for (const entry of entries) if (entry.isIntersecting) { watch.unobserve(entry.target); load(entry.target); }
  }, { rootMargin: '240px 0px' });
  benches.forEach((bench) => watch.observe(bench));
}
