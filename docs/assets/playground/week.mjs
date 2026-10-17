// The same week, two shapes. Six authored, fictional items in the manner of a Decision
// Docket recap, drawn as a river and as a ring. Nothing here comes from a real workspace.
// The list is the interface; both drawings are decorative and follow it.
//
// The river is a band, not a line: its width swells with each day's activity, it sits in
// soft banks, three flow lines drift along it, and at the right edge it opens into a mouth
// where what waits on you now sits. A crisp edge line gives the water its contrast, so the
// fill can stay soft. Flow stops for reduced motion (CSS).

const ITEMS = [
  { day: 0, hour: 9.3, mark: "source", kind: "Captured source", title: "A review was requested.", text: "A request for review opened on an example change.", rev: "example-r1", meaning: "Recorded as it was when captured. It says nothing yet about the change." },
  { day: 1, hour: 14.1, mark: "decision", kind: "Person-authored decision", title: "A choice now has a name.", text: "Someone wrote down the decision to keep capture time beside every source.", rev: "example-d2", meaning: "A person decided this. It is not inferred from a merge." },
  { day: 2, hour: 11.7, mark: "merged", kind: "Merged · not verified", title: "The draft crossed into main.", text: "The example change was merged.", rev: "example-r3", meaning: "The source records the merge. Verification needs evidence of its own." },
  { day: 3, hour: 16.5, mark: "check", kind: "Captured source", title: "A check reported green.", text: "An automated check passed on the merged change.", rev: "example-r4", meaning: "The check describes the steps it ran. It does not establish a release." },
  { day: 4, hour: 10.2, mark: "source", kind: "Captured source", title: "The wording changed.", text: "A comment revised the label on the status line.", rev: "example-r5", meaning: "Captured on Friday. Anything after that is not in this picture." },
  { day: null, hour: null, mark: "waiting", kind: "Waiting on you", title: "One conversation still needs you.", text: "A review is still requested from you.", rev: "example-r6", meaning: "Current waiting state, outside the week. Reading this recap does not withdraw it." },
];
// Authored activity per day (changes landed or revised), which sets the river's width.
const ACTIVITY = [2, 3, 6, 4, 3, 0, 1];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const NS = "http://www.w3.org/2000/svg";
const VW = 640, VH = 270, MID = 132, X0 = 28, COL = 76, MIN_W = 16, MAX_W = 74;
const widths = ACTIVITY.map((a) => MIN_W + (MAX_W - MIN_W) * Math.sqrt(a / Math.max(...ACTIVITY)));
let uid = 0;

const curve = (pts, y) => pts.map(([x, w], i) => {
  if (!i) return `${x.toFixed(1)} ${y(w).toFixed(1)}`;
  const [px, pw] = pts[i - 1], cx = ((px + x) / 2).toFixed(1);
  return `C ${cx} ${y(pw).toFixed(1)} ${cx} ${y(w).toFixed(1)} ${x.toFixed(1)} ${y(w).toFixed(1)}`;
}).join(" ");
const band = (pts, s = 1) => `M ${curve(pts, (w) => MID - (w * s) / 2)} L ${curve([...pts].reverse(), (w) => MID + (w * s) / 2)} Z`;
const flowLine = (pts, o) => `M ${curve(pts, (w) => MID + w * o)}`;
const RIVER = [[X0, widths[0]], ...widths.map((w, i) => [X0 + (i + 0.5) * COL, w]), [X0 + 7 * COL, widths[6]], [VW - 4, 150]];

// The ring: the same widths around a circle, eased between day centres.
const CX = 320, CY = 135, R = 92;
const ringWidth = (t) => {
  const p = ((t % 7) + 7) % 7 - 0.5, i = Math.floor(p), f = p - i;
  const a = widths[(i + 7) % 7], b = widths[(i + 8) % 7], e = (1 - Math.cos(Math.PI * f)) / 2;
  return (a + (b - a) * e) * 0.62;
};
const ringPoint = (t, r) => { const a = (t / 7) * Math.PI * 2 - Math.PI / 2; return [CX + Math.cos(a) * r, CY + Math.sin(a) * r]; };
const ringPath = (s = 1) => {
  const outer = [], inner = [];
  for (let k = 0; k <= 140; k++) { const t = (k / 140) * 7, w = ringWidth(t) * s; outer.push(ringPoint(t, R + w / 2)); inner.push(ringPoint(t, R - w / 2)); }
  const line = (ps) => ps.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  return `${line(outer)} Z ${line(inner.reverse())} Z`;
};
const ringFlow = (o) => { const ps = []; for (let k = 0; k <= 140; k++) { const t = (k / 140) * 7; ps.push(ringPoint(t, R + ringWidth(t) * o)); } return ps.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" "); };

export function mount(root) {
  const id = `week-${++uid}`;
  let selected = 2, shape = "river";
  root.innerHTML = `
  <div class="toy toy-week">
    <div class="toy-controls">
      <fieldset class="toy-fieldset toy-fieldset-row"><legend>Shape</legend>
        <label class="toy-choice"><input type="radio" name="${id}-shape" value="river" checked> River</label>
        <label class="toy-choice"><input type="radio" name="${id}-shape" value="ring"> Ring</label>
      </fieldset>
      <ol class="week-list" aria-label="The week, in order"></ol>
    </div>
    <div class="toy-stage">
      <figure class="week-figure river-visual"><div class="week-scroll" tabindex="0" role="region" aria-label="The drawing of the week. On a narrow screen it scrolls sideways."><svg class="week-svg" viewBox="0 0 ${VW} ${VH}" aria-hidden="true" focusable="false"></svg></div>
      <figcaption>Fictional items, drawn twice. The list is the same in both shapes; the drawing follows it.</figcaption></figure>
      <div class="week-detail" aria-live="polite"></div>
    </div>
  </div>`;
  const svg = root.querySelector(".week-svg"), list = root.querySelector(".week-list"), detail = root.querySelector(".week-detail");

  ITEMS.forEach((it, i) => {
    const li = document.createElement("li"), b = document.createElement("button"), when = document.createElement("span"), t = document.createElement("strong");
    b.type = "button"; b.className = "week-item"; b.dataset.i = i;
    when.className = "mono";
    when.textContent = it.day === null ? "NOW" : `${DAYS[it.day].toUpperCase()} ${String(Math.floor(it.hour)).padStart(2, "0")}:${String(Math.round((it.hour % 1) * 60)).padStart(2, "0")}`;
    t.textContent = it.title;
    b.append(when, t); li.append(b); list.append(li);
  });

  const el = (name, attrs, parent = svg) => { const n = document.createElementNS(NS, name); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); parent.append(n); return n; };
  const text = (x, y, s, attrs = {}) => { el("text", { x, y, class: "week-label", ...attrs }).textContent = s; };

  const place = (it) => {
    if (shape === "river") {
      if (it.day === null) return [VW - 34, MID + 6];
      const t = it.day + it.hour / 24, w = widths[it.day];
      const y = { source: MID - w / 2 - 6, check: MID + w / 2 + 6, decision: MID - w * 0.08, merged: MID + w * 0.14 }[it.mark];
      return [X0 + t * COL, y];
    }
    if (it.day === null) return [CX, CY];
    const t = it.day + it.hour / 24, w = ringWidth(t);
    return ringPoint(t, R + { source: -w / 2 - 6, check: w / 2 + 6, decision: -w * 0.08, merged: w * 0.14 }[it.mark]);
  };

  const markShape = (it, x, y, on) => {
    const g = el("g", { class: `week-mark is-${it.mark}${on ? " is-selected" : ""}`, "data-i": ITEMS.indexOf(it) });
    if (on) el("circle", { cx: x, cy: y, r: 15, class: "week-ring" }, g);
    if (it.mark === "decision") { el("ellipse", { cx: x, cy: y + 2, rx: 9, ry: 6.5, class: "stone-shade" }, g); el("ellipse", { cx: x, cy: y, rx: 9, ry: 6.5, class: "stone" }, g); }
    else if (it.mark === "merged") el("path", { d: `M${x} ${y - 8} L${x + 8} ${y} L${x} ${y + 8} L${x - 8} ${y} Z`, class: "float is-unverified" }, g);
    else if (it.mark === "waiting") { el("path", { d: `M${x} ${y - 10} L${x + 10} ${y} L${x} ${y + 10} L${x - 10} ${y} Z`, class: "float is-now" }, g); }
    else el("circle", { cx: x, cy: y, r: it.mark === "check" ? 6 : 5.5, class: `float${it.mark === "check" ? " is-check" : ""}` }, g);
  };

  const draw = () => {
    svg.replaceChildren();
    const defs = el("defs", {});
    const grad = el("linearGradient", shape === "river" ? { id: `${id}-w`, x1: 0, x2: 0, y1: 0, y2: 1 } : { id: `${id}-w`, x1: 0, x2: 1, y1: 0, y2: 1 }, defs);
    [["0", "edge"], ["0.5", "core"], ["1", "edge"]].forEach(([o, c]) => el("stop", { offset: o, class: `river-stop-${c}` }, grad));
    const it = ITEMS[selected];
    if (shape === "river") {
      DAYS.forEach((d, i) => text(X0 + (i + 0.5) * COL, 26, d.toUpperCase(), { "text-anchor": "middle" }));
      text(VW - 34, 26, "NOW", { "text-anchor": "middle" });
      el("path", { d: band(RIVER, 1.45), class: "river-bank" });
      el("path", { d: band(RIVER), fill: `url(#${id}-w)` });
      if (it.day !== null) {
        const clip = el("clipPath", { id: `${id}-lit` }, defs);
        el("rect", { x: X0 + it.day * COL, y: 0, width: COL, height: VH }, clip);
        el("path", { d: band(RIVER, 1.1), class: "river-lit", "clip-path": `url(#${id}-lit)` });
      }
      [-0.22, 0.04, 0.26].forEach((o) => el("path", { d: flowLine(RIVER, o), class: "river-flow" }));
      el("path", { d: band(RIVER), class: "river-edge" });
      if (it.day !== null) el("rect", { x: X0 + it.day * COL + 1, y: 36, width: COL - 2, height: VH - 46, rx: 4, class: "river-frame" });
    } else {
      DAYS.forEach((d, i) => { const [x, y] = ringPoint(i + 0.5, R + 62); text(x, y + 4, d.toUpperCase(), { "text-anchor": "middle" }); });
      el("path", { d: ringPath(1.5), class: "river-bank", "fill-rule": "evenodd" });
      el("path", { d: ringPath(), fill: `url(#${id}-w)`, "fill-rule": "evenodd" });
      if (it.day !== null) {
        const clip = el("clipPath", { id: `${id}-lit` }, defs);
        const [ax, ay] = ringPoint(it.day, 200), [bx, by] = ringPoint(it.day + 1, 200);
        el("path", { d: `M${CX} ${CY} L${ax} ${ay} A200 200 0 0 1 ${bx} ${by} Z` }, clip);
        el("path", { d: ringPath(1.1), class: "river-lit", "fill-rule": "evenodd", "clip-path": `url(#${id}-lit)` });
      }
      [-0.22, 0.04, 0.26].forEach((o) => el("path", { d: ringFlow(o), class: "river-flow" }));
      el("path", { d: ringPath(), class: "river-edge", "fill-rule": "evenodd" });
      el("circle", { cx: CX, cy: CY, r: 26, class: "river-mouth" });
      text(CX, CY + 44, "NOW", { "text-anchor": "middle" });
    }
    ITEMS.forEach((m, i) => { const [x, y] = place(m); markShape(m, x, y, i === selected); });
  };

  const show = (i) => {
    selected = i;
    const it = ITEMS[i];
    list.querySelectorAll(".week-item").forEach((b, j) => b.setAttribute("aria-pressed", String(j === i)));
    const k = document.createElement("p"), h = document.createElement("h3"), p = document.createElement("p"), m = document.createElement("p"), r = document.createElement("p");
    k.className = "mono week-kind"; k.textContent = it.kind.toUpperCase();
    h.textContent = it.title; p.textContent = it.text;
    m.className = "week-meaning"; m.textContent = it.meaning;
    r.className = "mono week-rev"; r.textContent = `CAPTURED REVISION / ${it.rev} (SYNTHETIC)`;
    detail.replaceChildren(k, h, p, m, r);
    draw();
  };

  list.addEventListener("click", (e) => { const b = e.target.closest(".week-item"); if (b) show(Number(b.dataset.i)); });
  svg.addEventListener("click", (e) => { const g = e.target.closest(".week-mark"); if (g) show(Number(g.dataset.i)); });
  root.querySelectorAll(`input[name="${id}-shape"]`).forEach((r) => r.addEventListener("change", () => { shape = r.value; draw(); }));
  show(selected);
}
