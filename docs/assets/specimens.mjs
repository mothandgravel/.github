// Optional handling light for the specimen plates. The records stay native HTML.
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const fine = matchMedia('(hover: hover) and (pointer: fine)');
const quietEntry = Boolean(location.hash) || performance.getEntriesByType('navigation')[0]?.type !== 'navigate';
const plates = [...document.querySelectorAll('.specimen-plane')].map((plane, index) => {
  const figure = plane.closest('.work-specimen');
  const card = plane.closest('.work-card');
  let visible = false;
  let frame = 0;
  let position;
  let arrived = false;
  const settle = () => {
    plane.removeAttribute('data-arriving');
    plane.style.removeProperty('--plate-delay');
  };
  const arrive = ratio => {
    if (arrived || ratio < .35) return;
    arrived = true;
    plane.setAttribute('data-arrival-seen', '');
    if (quietEntry || document.hidden || reduced.matches || card.contains(document.activeElement)) return;
    plane.style.setProperty('--plate-delay', `${index * 45}ms`);
    plane.setAttribute('data-arriving', '');
  };
  plane.addEventListener('animationend', settle);
  plane.addEventListener('animationcancel', settle);
  const reset = () => {
    cancelAnimationFrame(frame);
    frame = 0;
    position = undefined;
    plane.style.removeProperty('--plate-x');
    plane.style.removeProperty('--plate-y');
    plane.removeAttribute('data-handled');
  };
  const allowed = () => visible && !document.hidden && !reduced.matches && fine.matches;
  const move = event => {
    if (!allowed() || event.pointerType !== 'mouse' || card.contains(document.activeElement)) return;
    settle();
    const box = figure.getBoundingClientRect();
    position = [Math.max(-1, Math.min(1, (event.clientX - box.left) / box.width * 2 - 1)),
      Math.max(-1, Math.min(1, (event.clientY - box.top) / box.height * 2 - 1))];
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      if (!allowed() || !position) return reset();
      plane.style.setProperty('--plate-x', `${(-position[1] * 3).toFixed(2)}deg`);
      plane.style.setProperty('--plate-y', `${(position[0] * 3).toFixed(2)}deg`);
      plane.setAttribute('data-handled', '');
    });
  };
  figure.addEventListener('pointermove', move);
  figure.addEventListener('pointerleave', reset);
  figure.addEventListener('pointercancel', () => { settle(); reset(); });
  card.addEventListener('focusin', () => { arrived = true; settle(); reset(); });
  plane.setAttribute('data-depth-ready', '');
  return { figure, reset, settle, visibility(value, ratio) {
    visible = value;
    if (!value) { reset(); settle(); }
    else arrive(ratio);
  } };
});
const resetAll = () => plates.forEach(plate => { plate.reset(); plate.settle(); });
reduced.addEventListener('change', resetAll);
fine.addEventListener('change', resetAll);
document.addEventListener('visibilitychange', resetAll);
window.addEventListener('pagehide', resetAll);
window.addEventListener('blur', resetAll);
window.addEventListener('resize', resetAll);
document.addEventListener('keydown', () => plates.forEach(plate => plate.settle()));
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) plates.find(plate => plate.figure === entry.target)?.visibility(entry.isIntersecting, entry.intersectionRatio);
  }, {threshold:[0,.35]});
  plates.forEach(plate => observer.observe(plate.figure));
}
