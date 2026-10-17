// One undo: a rules sketch of SkyStack Builder's stamp tools.
// Authored from the source study in Field Note 008 (pinned commit 33f5c03). No game code,
// art or assets. A proposal is checked whole; a placement becomes one batch; Undo removes
// that batch only when every block it placed is still on top, and otherwise keeps it.

const W = 8, H = 6, LIMIT = 3, START_BLOCKS = 14;
// Water around an irregular island, and two cells where something already stands.
const WATER = new Set([0, 1, 6, 7, 8, 15, 40, 46, 47, 39]);
const STANDING = new Set([19, 36]);

const STAMPS = {
  single: { label: "Single block", turns: false },
  platform: { label: "2 × 2 platform", turns: false },
  line: { label: "Three-cell line", turns: true },
  run: { label: "Three-cell run (“Stairs”)", turns: true },
};
const DIRS = [["east", 1, 0], ["south", 0, 1], ["west", -1, 0], ["north", 0, -1]];

const footprint = (stamp, dir, x, y) => {
  const [, dx, dy] = DIRS[dir];
  if (stamp === "single") return [[x, y]];
  if (stamp === "platform") return [[x, y], [x + 1, y], [x, y + 1], [x + 1, y + 1]];
  if (stamp === "line") return [[x - dx, y - dy], [x, y], [x + dx, y + dy]];
  return [[x, y], [x + dx, y + dy], [x + 2 * dx, y + 2 * dy]];
};

export function mount(root) {
  const stacks = Array.from({ length: W * H }, () => []);
  const history = [];
  let blocks = START_BLOCKS, stamp = "run", dir = 0, focus = 26, preview = null, batchNo = 0;

  root.innerHTML = `
  <div class="toy toy-stamp">
    <div class="toy-controls">
      <fieldset class="toy-fieldset"><legend>Stamp</legend>
        ${Object.entries(STAMPS).map(([k, s]) => `<label class="toy-choice"><input type="radio" name="stamp-${root.id}" value="${k}" ${k === stamp ? "checked" : ""}> ${s.label}</label>`).join("")}
      </fieldset>
      <div class="toy-actions">
        <button type="button" class="toy-button" data-turn>Turn: <span data-dir>east</span></button>
        <button type="button" class="toy-button toy-button-strong" data-undo disabled>Undo the last stamp</button>
        <button type="button" class="toy-button" data-wind disabled>Let the wind take one block</button>
        <button type="button" class="toy-button" data-reset>Start again</button>
      </div>
      <p class="toy-ledger mono"><span>BLOCKS IN HAND / <b data-blocks>${START_BLOCKS}</b></span><span>HISTORY / <b data-history>0</b></span><span>HEIGHT LIMIT / ${LIMIT}</span></p>
    </div>
    <div class="toy-stage">
      <div class="stamp-grid" role="group" aria-label="Island, ${W} columns by ${H} rows. Arrow keys move; Enter places the stamp; R turns it." style="--cols:${W}"></div>
      <p class="toy-readout" data-readout>Point at the island to preview a stamp.</p>
      <p class="toy-status" role="status" aria-live="polite" data-status></p>
    </div>
  </div>`;

  const grid = root.querySelector(".stamp-grid");
  const $ = (s) => root.querySelector(s);
  const cells = [];
  for (let i = 0; i < W * H; i++) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "stamp-cell";
    b.tabIndex = i === focus ? 0 : -1;
    b.dataset.i = i;
    if (WATER.has(i)) b.classList.add("is-water");
    if (STANDING.has(i)) b.classList.add("is-standing");
    grid.append(b);
    cells.push(b);
  }

  const check = (fp) => {
    const reasons = [];
    const inside = fp.filter(([x, y]) => x >= 0 && y >= 0 && x < W && y < H);
    if (inside.length < fp.length || inside.some(([x, y]) => WATER.has(y * W + x))) reasons.push("part of it would leave the island");
    if (inside.some(([x, y]) => STANDING.has(y * W + x))) reasons.push("something already stands in one cell");
    if (inside.some(([x, y]) => stacks[y * W + x].length >= LIMIT)) reasons.push("one cell is at the height limit");
    if (fp.length > blocks) reasons.push(`it needs ${fp.length} blocks and ${blocks} are in hand`);
    return { inside, reasons };
  };

  const describe = (i) => {
    const x = i % W, y = Math.floor(i / W);
    const kind = WATER.has(i) ? "water" : STANDING.has(i) ? "something standing" : `height ${stacks[i].length}`;
    return `Column ${x + 1}, row ${y + 1}, ${kind}`;
  };

  const render = () => {
    const marks = new Map();
    if (preview) for (const [x, y] of preview.inside) marks.set(y * W + x, preview.reasons.length ? "is-refused" : "is-proposed");
    cells.forEach((c, i) => {
      const h = stacks[i].length;
      c.dataset.h = h;
      c.textContent = h ? String(h) : "";
      c.classList.remove("is-proposed", "is-refused", "is-last");
      if (marks.has(i)) c.classList.add(marks.get(i));
      const last = history.at(-1);
      if (last && last.cells.includes(i) && stacks[i].at(-1) === last.id) c.classList.add("is-last");
      c.setAttribute("aria-label", describe(i) + (marks.has(i) ? (marks.get(i) === "is-proposed" ? ", in the proposal" : ", in a refused proposal") : ""));
    });
    $("[data-blocks]").textContent = blocks;
    $("[data-history]").textContent = history.length;
    $("[data-undo]").disabled = history.length === 0;
    $("[data-wind]").disabled = history.length === 0;
    $("[data-dir]").textContent = DIRS[dir][0];
    $("[data-turn]").disabled = !STAMPS[stamp].turns;
  };

  const propose = (i) => {
    const fp = footprint(stamp, dir, i % W, Math.floor(i / W));
    preview = { anchor: i, fp, ...check(fp) };
    $("[data-readout]").textContent = preview.reasons.length
      ? `${STAMPS[stamp].label}: stays a proposal, because ${preview.reasons.join(", and ")}. Nothing is spent.`
      : `${STAMPS[stamp].label}: ${fp.length} ${fp.length === 1 ? "cell" : "cells"}, ${fp.length} ${fp.length === 1 ? "block" : "blocks"}. It fits as one thing.`;
    render();
  };

  const say = (msg) => { $("[data-status]").textContent = ""; setTimeout(() => { $("[data-status]").textContent = msg; }, 30); };

  const place = (i) => {
    propose(i);
    if (preview.reasons.length) { say("Not placed. The whole proposal stays in your hand."); return; }
    const id = ++batchNo;
    const placed = preview.fp.map(([x, y]) => y * W + x);
    placed.forEach((c) => stacks[c].push(id));
    blocks -= placed.length;
    history.push({ id, cells: placed, label: STAMPS[stamp].label });
    propose(i);
    say(`Placed. One ${STAMPS[stamp].label.toLowerCase()}, ${placed.length} ${placed.length === 1 ? "block" : "blocks"}, one entry in history.`);
  };

  const undo = () => {
    const last = history.at(-1);
    if (!last) return;
    const moved = last.cells.filter((c) => stacks[c].at(-1) !== last.id);
    if (moved.length) {
      say(`Undo failed. ${moved.length === 1 ? "One block is" : moved.length + " blocks are"} no longer where the stamp left ${moved.length === 1 ? "it" : "them"}. Nothing was removed, and the history entry stays.`);
      return;
    }
    last.cells.forEach((c) => stacks[c].pop());
    blocks += last.cells.length;
    history.pop();
    preview = null;
    $("[data-readout]").textContent = "Point at the island to preview a stamp.";
    render();
    say(`Undone. The whole ${last.label.toLowerCase()} came back to your hand: ${last.cells.length} ${last.cells.length === 1 ? "block" : "blocks"}.`);
  };

  const wind = () => {
    const last = history.at(-1);
    const target = last?.cells.find((c) => stacks[c].at(-1) === last.id);
    if (target === undefined) { say("The wind found nothing loose on the last stamp."); return; }
    stacks[target].pop();
    render();
    say(`The wind took one block from ${describe(target).toLowerCase()}. It is not in history and not refunded.`);
  };

  grid.addEventListener("pointerover", (e) => { const c = e.target.closest(".stamp-cell"); if (c) propose(Number(c.dataset.i)); });
  grid.addEventListener("pointerleave", () => { preview = null; render(); });
  grid.addEventListener("focusin", (e) => { const c = e.target.closest(".stamp-cell"); if (c) propose(Number(c.dataset.i)); });
  grid.addEventListener("click", (e) => { const c = e.target.closest(".stamp-cell"); if (c) place(Number(c.dataset.i)); });
  grid.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return; // leave browser shortcuts such as Ctrl+R alone
    const moves = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: W, ArrowUp: -W };
    if (e.key in moves) {
      e.preventDefault();
      const n = focus + moves[e.key];
      if (n < 0 || n >= W * H || (Math.abs(moves[e.key]) === 1 && Math.floor(n / W) !== Math.floor(focus / W))) return;
      cells[focus].tabIndex = -1; focus = n; cells[focus].tabIndex = 0; cells[focus].focus();
    } else if (e.key.toLowerCase() === "r" && STAMPS[stamp].turns) { e.preventDefault(); turn(); }
  });
  grid.addEventListener("focusin", (e) => { const c = e.target.closest(".stamp-cell"); if (c) { cells[focus].tabIndex = -1; focus = Number(c.dataset.i); c.tabIndex = 0; } });

  const turn = () => { dir = (dir + 1) % 4; if (preview) propose(preview.anchor); else render(); say(`Facing ${DIRS[dir][0]}.`); };
  root.querySelectorAll(`input[name="stamp-${root.id}"]`).forEach((r) => r.addEventListener("change", () => { stamp = r.value; if (preview) propose(preview.anchor); else render(); }));
  $("[data-turn]").addEventListener("click", turn);
  $("[data-undo]").addEventListener("click", undo);
  $("[data-wind]").addEventListener("click", wind);
  $("[data-reset]").addEventListener("click", () => {
    stacks.forEach((s) => (s.length = 0)); history.length = 0; blocks = START_BLOCKS; preview = null;
    $("[data-readout]").textContent = "Point at the island to preview a stamp."; render(); say("A fresh island. Fourteen blocks in hand.");
  });
  render();
}
