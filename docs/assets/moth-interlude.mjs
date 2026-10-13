import { DURATION, sampleScene } from './moth-choreography.mjs';

const room = document.querySelector('#moth-interlude');
const stage = room?.querySelector('.moth-stage');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const seenKey = 'moth-and-gravel-interlude-seen';
let seen = false;
try { seen = sessionStorage.getItem(seenKey) === 'yes'; } catch { /* One visit still works. */ }
const remember = () => {
  seen = true;
  try { sessionStorage.setItem(seenKey,'yes'); } catch { /* One visit still works. */ }
};

if (stage && 'IntersectionObserver' in window) initialise().catch(() => {
  // The resting mark and real question link remain complete without enhancement.
  room.querySelectorAll('.moth-controls button').forEach(button => { button.hidden = true; });
});

async function initialise() {
  let startupController;
  const earlyInterrupt = () => { remember();startupController?.abort(); };
  const earlyKey = event => { if(event.key==='Escape')earlyInterrupt(); };
  const earlyVisibility = () => { if(document.hidden)earlyInterrupt(); };
  window.addEventListener('blur',earlyInterrupt);
  window.addEventListener('pagehide',earlyInterrupt);
  document.addEventListener('keydown',earlyKey);
  document.addEventListener('visibilitychange',earlyVisibility);
  reduced.addEventListener('change',earlyInterrupt);
  try {
  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = new URL('./moth-interlude.css', import.meta.url).href;
  const styled = new Promise((resolve, reject) => {
    css.onload = resolve;
    css.onerror = () => reject(new Error('Interlude stylesheet unavailable'));
  });
  document.head.append(css);
  const [response] = await Promise.all([fetch(new URL('./moth-rig.svg', import.meta.url)), styled]);
  if (!response.ok) throw new Error('Interlude rig unavailable');
  const parsed = new DOMParser().parseFromString(await response.text(), 'image/svg+xml');
  if (parsed.querySelector('parsererror')) throw new Error('Interlude rig invalid');
  const svg = document.importNode(parsed.documentElement, true);
  const traveller = document.createElement('div');
  traveller.className = 'moth-traveller';
  traveller.setAttribute('aria-hidden', 'true');
  traveller.hidden = true;
  traveller.append(svg);
  const shadow = document.createElement('div');
  shadow.className = 'moth-shadow';
  shadow.setAttribute('aria-hidden', 'true');
  shadow.hidden = true;
  stage.append(shadow, traveller);
  const wings = [['softFore','wing-soft-fore',486,460],['softHind','wing-soft-hind',486,505],
    ['stoneFore','wing-stone-fore',522,460],['stoneHind','wing-stone-hind',524,505]]
    .map(([key,id,x,y]) => ({key,node:svg.querySelector(`#${id}`),x,y}));
  const body = svg.querySelector('#moth-body');
  const antennae = svg.querySelector('#moth-antennae');
  if (wings.some(wing => !wing.node) || !body || !antennae) throw new Error('Interlude rig incomplete');
  let renderer;
  room.dataset.mothRenderer = 'svg';
  const play = room.querySelector('[data-moth-play]');
  const pause = room.querySelector('[data-moth-pause]');
  const finish = room.querySelector('[data-moth-finish]');
  const status = room.querySelector('[data-moth-status]');
  let frame = 0, started = 0, elapsed = 0, layout, visible = false, observed = false, fits = true, pendingPlay = false, state = 'idle';
  const still = () => reduced.matches || document.hidden;
  const setState = value => {
    state = value;
    room.dataset.mothState = value;
    pause.textContent = value === 'paused' ? 'Resume' : 'Pause';
    pause.disabled = !['playing','paused'].includes(value);
    finish.disabled = !['playing','paused'].includes(value);
    play.disabled = reduced.matches || !observed || !fits || value === 'playing' || value === 'paused';
  };
  const end = (message = '', restoreFocus = false) => {
    const focusedControl = [pause,finish].includes(document.activeElement);
    cancelAnimationFrame(frame); frame = 0;
    traveller.hidden = true; shadow.hidden = true;
    room.removeAttribute('data-moth-phase');
    stage.style.removeProperty('--moth-light');
    elapsed = 0;
    setState('idle');
    status.textContent = message;
    if (restoreFocus || focusedControl) {
      const target = play.disabled ? room.querySelector('.moth-question a') : play;
      target.focus({ preventScroll:true });
    }
  };
  const rectIn = (node, box) => {
    const b = node.getBoundingClientRect();
    return {left:b.left-box.left,top:b.top-box.top,right:b.right-box.left,bottom:b.bottom-box.top};
  };
  function measure() {
    const box = stage.getBoundingClientRect();
    const source = room.querySelector('.moth-source img').getBoundingClientRect();
    const perch = room.querySelector('.moth-perch').getBoundingClientRect();
    const size = Math.min(68, box.width * .18);
    return {width:box.width,height:box.height,
      source:{x:source.left-box.left + source.width*.495,y:source.top-box.top + source.height*.52,size:source.width*.75},
      perch:{x:perch.left-box.left + perch.width*.5,y:perch.top-box.top-size*(renderer?.contactOffset??197/750),size},
      question:rectIn(room.querySelector('.moth-question'),box)};
  }
  function safeGeometry(candidate) {
    // Check the whole visible envelope, including turns, before releasing it.
    const q = candidate.question;
    for (let t = 0; t <= DURATION; t += 16) {
      const p = sampleScene(t,candidate), w = candidate.source.size*p.scale, h = w*430/750;
      const angle = p.heading*Math.PI/180;
      const rx = (Math.abs(Math.cos(angle))*w + Math.abs(Math.sin(angle))*h)/2 + 4;
      const ry = (Math.abs(Math.sin(angle))*w + Math.abs(Math.cos(angle))*h)/2 + 4;
      if (p.x-rx < 8 || p.x+rx > candidate.width-8 || p.y-ry < 8 || p.y+ry > candidate.height-8) return false;
      if (p.x+rx > q.left-8 && p.x-rx < q.right+8 && p.y+ry > q.top-8 && p.y-ry < q.bottom+8) return false;
    }
    return true;
  }
  const paint = time => {
    const p = sampleScene(time,layout);
    room.dataset.mothPhase = p.phase;
    traveller.style.transform = `translate3d(${p.x}px,${p.y}px,0) translate(-50%,-50%) rotate(${p.heading}deg) scale(${p.scale})`;
    traveller.style.opacity = p.opacity;
    for (const wing of wings) {
      const {compression:a,shear:b} = p[wing.key];
      wing.node.setAttribute('transform',`matrix(${a} ${b} 0 1 ${wing.x*(1-a)} ${-b*wing.x})`);
      const travelling = ['lift','travel','inspect','depart'].includes(p.phase);
      const far = travelling && wing.key.startsWith('stone') ? .94 : 1;
      wing.node.style.opacity = (.83 + .17*a) * far;
    }
    body.setAttribute('transform',`rotate(${p.bodyPitch} 500 470)`);
    antennae.setAttribute('transform',`rotate(${p.antennaAngle} 500 389)`);
    if (renderer && !renderer.render(p,time,Math.max(102,layout.source.size))) {
      renderer.dispose();renderer = undefined;svg.removeAttribute('hidden');room.dataset.mothRenderer = 'svg';
      interrupt();return false;
    }
    shadow.style.transform = `translate3d(${p.x+6}px,${p.y+layout.source.size*p.scale*.25+10}px,0) translate(-50%,-50%) scaleX(${p.shadow.scale})`;
    shadow.style.opacity = p.shadow.opacity;
    stage.style.setProperty('--moth-light', p.phase === 'settle' ? '.15' : '.06');
    return true;
  };
  const tick = now => {
    frame = 0;
    if (state !== 'playing') return;
    if (still() || !visible) return end();
    elapsed = Math.min(DURATION, now-started);
    if (!paint(elapsed)) return;
    if (elapsed >= DURATION) return end('A question worth following.');
    frame = requestAnimationFrame(tick);
  };
  const begin = (manual = false) => {
    if (still() || state !== 'idle') return;
    if (!visible) {
      if (manual) { pendingPlay = true;stage.scrollIntoView({block:'center',behavior:'smooth'}); }
      return;
    }
    pendingPlay = false;
    layout = measure();
    fits = safeGeometry(layout);
    if (!fits) { setState('idle');status.textContent = 'Still, in this view.';return; }
    remember();
    traveller.style.width = `${layout.source.size}px`;
    traveller.style.height = `${layout.source.size*430/750}px`;
    shadow.style.width = `${layout.source.size}px`;
    traveller.hidden = false; shadow.hidden = false;
    elapsed = 0; started = performance.now();
    setState('playing'); status.textContent = '';
    play.textContent = 'Watch again';
    if (paint(0)) frame = requestAnimationFrame(tick);
  };
  play.addEventListener('click',()=>begin(true));
  pause.addEventListener('click',() => {
    if (state === 'playing') {
      cancelAnimationFrame(frame);frame = 0;setState('paused');
      status.textContent = 'Paused.';
    } else if (state === 'paused' && !still() && visible) {
      started = performance.now()-elapsed;setState('playing');status.textContent = '';
      frame = requestAnimationFrame(tick);
    }
  });
  finish.addEventListener('click',()=>end('Still again.',true));
  document.addEventListener('keydown',event => {
    if (['PageUp','PageDown','Home','End','ArrowUp','ArrowDown',' '].includes(event.key)) pendingPlay = false;
    if (event.key === 'Escape') {
      if (!observed) suppressAutomatic();
      pendingPlay = false;
      if (state !== 'idle') end('', room.contains(document.activeElement));
    }
  });
  const interrupt = () => { pendingPlay = false;if (state !== 'idle') end(); };
  const suppressAutomatic = () => { remember();startupController?.abort();interrupt(); };
  const cancelPending = () => { pendingPlay = false; };
  window.addEventListener('wheel',cancelPending,{passive:true});
  window.addEventListener('touchmove',cancelPending,{passive:true});
  document.addEventListener('pointerdown',event=>{
    if (!room.contains(event.target)) cancelPending();
  },{capture:true});
  document.addEventListener('focusin',event=>{
    if (!room.contains(event.target)) cancelPending();
  });
  const remeasure = () => {
    interrupt();
    if (visible) {
      fits = safeGeometry(measure());setState('idle');
      status.textContent = reduced.matches ? 'Still, by preference.' : fits ? '' : 'Still, in this view.';
    }
  };
  document.addEventListener('visibilitychange',()=>{if(document.hidden)suppressAutomatic();else interrupt();});
  window.addEventListener('pagehide',suppressAutomatic);
  window.addEventListener('blur',suppressAutomatic);
  window.addEventListener('resize',remeasure);
  reduced.addEventListener('change',()=>{
    suppressAutomatic();setState('idle');status.textContent = reduced.matches ? 'Still, by preference.' : '';
  });
  // The source rig remains a complete flight fallback. A failed or lost GPU
  // never strands the question or replaces native controls with an error flow.
  if (!reduced.matches) {
    const controller = new AbortController();startupController = controller;
    let rejectAbort;
    const aborted = new Promise((_,reject)=>{rejectAbort=reject;});
    const onAbort = () => rejectAbort(new DOMException('Interlude setup cancelled','AbortError'));
    controller.signal.addEventListener('abort',onAbort,{once:true});
    const deadline = setTimeout(()=>controller.abort(),1800);
    try {
      const setup = async () => {
        const { createMothRenderer } = await import('./moth-webgl.mjs');
        if(controller.signal.aborted)throw new DOMException('Interlude setup cancelled','AbortError');
        return createMothRenderer(traveller,()=>{
          renderer = undefined;svg.removeAttribute('hidden');room.dataset.mothRenderer = 'svg';interrupt();
        },controller.signal);
      };
      renderer = await Promise.race([setup(),aborted]);
      svg.setAttribute('hidden','');room.dataset.mothRenderer = 'webgl';
    } catch { /* Keep the source-derived SVG performance. */ }
    finally {clearTimeout(deadline);controller.signal.removeEventListener('abort',onAbort);startupController = undefined;}
  }
  const observer = new IntersectionObserver(entries=>{
    const entry = entries[0];
    observed = true;
    if (!entry.isIntersecting) pendingPlay = false;
    visible = entry.isIntersecting && entry.intersectionRatio >= .7;
    if (!visible && state !== 'idle') interrupt();
    else fits = safeGeometry(measure());
    setState(state);
    if (!fits && !reduced.matches) status.textContent = 'Still, in this view.';
    if (visible && pendingPlay && !still()) begin();
    else if (visible && !seen) {
      remember();
      if (!still() && fits && document.hasFocus()) begin();
    }
  },{threshold:[0,.7,1]});
  if ('ResizeObserver' in window) new ResizeObserver(remeasure).observe(stage);
  room.querySelectorAll('.moth-controls button').forEach(button=>{button.hidden = false;});
  setState('idle');
  room.dataset.mothReady = 'true';
  if (reduced.matches) status.textContent = 'Still, by preference.';
  observer.observe(stage);
  } finally {
    window.removeEventListener('blur',earlyInterrupt);
    window.removeEventListener('pagehide',earlyInterrupt);
    document.removeEventListener('keydown',earlyKey);
    document.removeEventListener('visibilitychange',earlyVisibility);
    reduced.removeEventListener('change',earlyInterrupt);
  }
}
