// Silent study films never autoplay. One plays at a time, and a film pauses once it leaves the screen.
const films = [...document.querySelectorAll('video[data-pause-offscreen]')];
for (const film of films) {
  film.addEventListener('play', () => {
    for (const other of films) if (other !== film && !other.paused) other.pause();
  });
}
if ('IntersectionObserver' in window && films.length) {
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) if (!entry.isIntersecting && !entry.target.paused) entry.target.pause();
  }, { threshold: 0.2 });
  for (const film of films) observer.observe(film);
}
