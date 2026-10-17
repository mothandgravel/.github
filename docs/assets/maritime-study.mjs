// Silent study films never autoplay. Posters arrive as a film approaches, so they do not compete with the
// opening; one film plays at a time, and a film pauses once it leaves the screen.
const films = [...document.querySelectorAll('video[data-pause-offscreen]')];
const showPoster = film => { if (film.dataset.poster && !film.getAttribute('poster')) film.setAttribute('poster', film.dataset.poster); };
for (const film of films) {
  film.addEventListener('play', () => {
    for (const other of films) if (other !== film && !other.paused) other.pause();
  });
}
if ('IntersectionObserver' in window) {
  const approach = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) { showPoster(entry.target); approach.unobserve(entry.target); }
  }, { rootMargin: '600px 0px' });
  const leave = new IntersectionObserver(entries => {
    for (const entry of entries) if (!entry.isIntersecting && !entry.target.paused) entry.target.pause();
  }, { threshold: 0.2 });
  for (const film of films) { approach.observe(film); leave.observe(film); }
} else {
  films.forEach(showPoster);
}
