// Can this board be finished? A 5 × 5 reduction of Cyber Grid's route check.
// Ported from the game's move rule (three straight or two diagonal) and its route search:
// cheap shape checks, then a depth-first search with fewest-exits-first ordering, bounded
// by a node budget rather than time. The game treats "not found within budget" and "no
// route" alike, conservatively; this toy keeps them apart, because that is the point.

const N = 5, CELLS = N * N;
const NEXT = Array.from({ length: CELLS }, (_, f) => {
  const fx = f % N, fy = Math.floor(f / N), out = [];
  for (let t = 0; t < CELLS; t++) {
    const dx = Math.abs(fx - (t % N)), dy = Math.abs(fy - Math.floor(t / N));
    if ((dx === 3 && dy === 0) || (dx === 0 && dy === 3) || (dx === 2 && dy === 2)) out.push(t);
  }
  return out;
});

const PRESETS = {
  open: { label: "An open board", blocked: [] },
  three: { label: "Three obstacles", blocked: [2, 13, 21] },
  none: { label: "A board with no route", blocked: [0, 6, 18] },
  corner: { label: "A cut-off corner", blocked: [3, 12, 15] },
};

function shape(blocked) {
  const open = [...Array(CELLS).keys()].filter((i) => !blocked[i]);
  if (!open.length) return "There are no open cells.";
  let dead = 0;
  for (const i of open) {
    const d = NEXT[i].filter((n) => !blocked[n]).length;
    if (d === 0 && open.length > 1) return `Cell ${label(i)} has no legal jump in or out.`;
    if (d === 1) dead++;
  }
  if (dead > 2) return `${dead} cells have only one way in. A route has only two ends.`;
  const seen = new Uint8Array(CELLS), todo = [open[0]];
  seen[open[0]] = 1;
  let reached = 1;
  while (todo.length) for (const n of NEXT[todo.pop()]) if (!blocked[n] && !seen[n]) { seen[n] = 1; reached++; todo.push(n); }
  return reached === open.length ? null : "The open cells fall into separate groups that no jump connects.";
}

function search(blocked, budget) {
  const v = Uint8Array.from(blocked), open = v.reduce((a, b) => a + (b ? 0 : 1), 0), route = [];
  let nodes = 0, out = false;
  const free = (i) => NEXT[i].reduce((d, n) => d + (v[n] ? 0 : 1), 0);
  const viable = (h) => {
    let dead = 0;
    for (let i = 0; i < CELLS; i++) {
      if (v[i]) continue;
      const links = free(i) + (NEXT[h].includes(i) ? 1 : 0);
      if (links === 0 || (links === 1 && ++dead > 1)) return false;
    }
    const seen = new Uint8Array(CELLS), todo = [h];
    let reached = 0;
    while (todo.length) for (const n of NEXT[todo.pop()]) if (!v[n] && !seen[n]) { seen[n] = 1; reached++; todo.push(n); }
    return reached === open - route.length;
  };
  const extend = (h) => {
    if (route.length === open) return true;
    if (++nodes > budget) { out = true; return false; }
    if (!viable(h)) return false;
    for (const n of NEXT[h].filter((n) => !v[n]).sort((a, b) => free(a) - free(b))) {
      v[n] = 1; route.push(n);
      if (extend(n)) return true;
      route.pop(); v[n] = 0;
      if (out) return false;
    }
    return false;
  };
  for (const s of [...Array(CELLS).keys()].filter((i) => !v[i]).sort((a, b) => free(a) - free(b))) {
    v[s] = 1; route.push(s);
    if (extend(s)) return { verdict: "found", route, nodes };
    route.pop(); v[s] = 0;
    if (out) return { verdict: "budget", nodes: budget };
  }
  return { verdict: "exhausted", nodes };
}

const label = (i) => `${"ABCDE"[i % N]}${Math.floor(i / N) + 1}`;

export function mount(root) {
  const blocked = new Array(CELLS).fill(0);
  let mode = "edit", path = [], shown = null, focus = 12;
  PRESETS.three.blocked.forEach((i) => (blocked[i] = 1));

  root.innerHTML = `
  <div class="toy toy-grid">
    <div class="toy-controls">
      <fieldset class="toy-fieldset"><legend>What your taps do</legend>
        <label class="toy-choice"><input type="radio" name="mode-${root.id}" value="edit" checked> Place or lift obstacles</label>
        <label class="toy-choice"><input type="radio" name="mode-${root.id}" value="play"> Try a route yourself</label>
      </fieldset>
      <label class="toy-select">Start from <select data-preset>${Object.entries(PRESETS).map(([k, p]) => `<option value="${k}" ${k === "three" ? "selected" : ""}>${p.label}</option>`).join("")}</select></label>
      <label class="toy-select">Search budget <select data-budget><option value="25000" selected>25,000 steps (a budget the game uses)</option><option value="40">40 steps</option></select></label>
      <div class="toy-actions"><button type="button" class="toy-button toy-button-strong" data-ask>Ask: can this board be finished?</button></div>
    </div>
    <div class="toy-stage">
      <div class="grid-board" role="group" aria-label="Board, five by five. Arrow keys move between cells." style="--cols:${N}"></div>
      <p class="toy-readout" data-readout>Visit every open cell once. Each jump is three cells straight or two diagonally.</p>
      <div class="grid-verdict" data-verdict hidden><p class="mono" data-verdict-kind></p><p data-verdict-text></p></div>
      <p class="toy-status" role="status" aria-live="polite" data-status></p>
    </div>
  </div>`;

  const $ = (s) => root.querySelector(s);
  const board = $(".grid-board");
  const cells = [...Array(CELLS).keys()].map((i) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "grid-cell"; b.dataset.i = i; b.tabIndex = i === focus ? 0 : -1;
    board.append(b);
    return b;
  });

  const say = (m) => { $("[data-status]").textContent = ""; setTimeout(() => { $("[data-status]").textContent = m; }, 30); };
  const clearVerdict = () => { shown = null; $("[data-verdict]").hidden = true; };

  const render = () => {
    const head = path.at(-1);
    const reachable = mode === "play" && head !== undefined ? new Set(NEXT[head].filter((n) => !blocked[n] && !path.includes(n))) : null;
    cells.forEach((c, i) => {
      const step = shown ? shown.indexOf(i) : path.indexOf(i);
      c.className = "grid-cell" + (blocked[i] ? " is-blocked" : "") + (step >= 0 ? " is-visited" : "") + (i === head && !shown ? " is-head" : "") + (reachable?.has(i) ? " is-reachable" : "");
      c.textContent = blocked[i] ? "" : step >= 0 ? String(step + 1) : "";
      c.setAttribute("aria-label", `${label(i)}, ${blocked[i] ? "obstacle" : step >= 0 ? `step ${step + 1}` : reachable?.has(i) ? "open, a legal next jump" : "open"}`);
    });
  };

  const tap = (i) => {
    if (mode === "edit") {
      blocked[i] ^= 1; path = []; clearVerdict(); render();
      say(`${label(i)} ${blocked[i] ? "is now an obstacle" : "is open again"}.`);
      return;
    }
    clearVerdict();
    if (blocked[i]) return say(`${label(i)} is an obstacle.`);
    if (!path.length) { path = [i]; render(); return say(`Started at ${label(i)}.`); }
    const head = path.at(-1);
    if (path.includes(i)) return say(`${label(i)} is already visited. Choose Start from to begin again.`);
    if (!NEXT[head].includes(i)) return say(`${label(i)} is not a legal jump from ${label(head)}.`);
    path.push(i); render();
    const open = blocked.filter((b) => !b).length;
    const left = NEXT[i].filter((n) => !blocked[n] && !path.includes(n)).length;
    if (path.length === open) say(`Finished. Every one of the ${open} open cells, once.`);
    else if (!left) say(`Stuck at ${label(i)}: ${path.length} of ${open} cells. The board may still be finishable another way.`);
    else say(`Jumped to ${label(i)}. ${path.length} of ${open}.`);
  };

  const ask = () => {
    path = [];
    const reason = shape(blocked);
    const budget = Number($("[data-budget]").value);
    let kind, text;
    if (reason) { kind = "RULED OUT BEFORE SEARCHING"; text = `${reason} No route can exist, so there is nothing to search.`; shown = null; }
    else {
      const r = search(blocked, budget);
      if (r.verdict === "found") { kind = "A ROUTE EXISTS"; text = `Found in ${r.nodes.toLocaleString("en")} search steps. Every jump is numbered on the board, so you can check it yourself.`; shown = r.route; }
      else if (r.verdict === "exhausted") { kind = "NO ROUTE"; text = `The search tried every possibility in ${r.nodes.toLocaleString("en")} steps. This board cannot be finished.`; shown = null; }
      else { kind = "NO ANSWER YET"; text = `The search stopped at its budget of ${budget.toLocaleString("en")} steps. That is not a no. The game would treat this board as not guaranteed, and roll another.`; shown = null; }
    }
    $("[data-verdict]").hidden = false;
    $("[data-verdict]").dataset.kind = kind;
    $("[data-verdict-kind]").textContent = kind;
    $("[data-verdict-text]").textContent = text;
    render();
    say(`${kind.toLowerCase()}. ${text}`);
  };

  board.addEventListener("click", (e) => { const c = e.target.closest(".grid-cell"); if (c) tap(Number(c.dataset.i)); });
  board.addEventListener("focusin", (e) => { const c = e.target.closest(".grid-cell"); if (c) { cells[focus].tabIndex = -1; focus = Number(c.dataset.i); c.tabIndex = 0; } });
  board.addEventListener("keydown", (e) => {
    const m = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: N, ArrowUp: -N }[e.key];
    if (!m) return;
    e.preventDefault();
    const n = focus + m;
    if (n < 0 || n >= CELLS || (Math.abs(m) === 1 && Math.floor(n / N) !== Math.floor(focus / N))) return;
    cells[n].focus();
  });
  root.querySelectorAll(`input[name="mode-${root.id}"]`).forEach((r) => r.addEventListener("change", () => { mode = r.value; path = []; clearVerdict(); render(); say(mode === "play" ? "Tap an open cell to start." : "Tap cells to place or lift obstacles."); }));
  $("[data-preset]").addEventListener("change", (e) => { blocked.fill(0); PRESETS[e.target.value].blocked.forEach((i) => (blocked[i] = 1)); path = []; clearVerdict(); render(); say(`${PRESETS[e.target.value].label}.`); });
  $("[data-budget]").addEventListener("change", clearVerdict);
  $("[data-ask]").addEventListener("click", ask);
  render();
}
