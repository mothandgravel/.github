// The same week, two shapes. Six authored, fictional items from a Decision Docket-style
// recap, drawn as a river and as a circle. Nothing here comes from a real workspace.
// The list is the interface; both drawings follow it.

const ITEMS = [
  { day: 0, hour: 9.3, glyph: "○", kind: "Captured source", title: "A review was requested.", text: "A request for review opened on an example change.", rev: "example-r1", meaning: "Recorded as it was when captured. It says nothing yet about the change." },
  { day: 1, hour: 14.1, glyph: "◇", kind: "Person-authored decision", title: "A choice now has a name.", text: "Someone wrote down the decision to keep capture time beside every source.", rev: "example-d2", meaning: "A person decided this. It is not inferred from a merge." },
  { day: 2, hour: 11.7, glyph: "⌁", kind: "Merged · not verified", title: "The draft crossed into main.", text: "The example change was merged.", rev: "example-r3", meaning: "The source records the merge. Verification needs evidence of its own." },
  { day: 3, hour: 16.5, glyph: "●", kind: "Captured source", title: "A check reported green.", text: "An automated check passed on the merged change.", rev: "example-r4", meaning: "The check describes the steps it ran. It does not establish a release." },
  { day: 4, hour: 10.2, glyph: "○", kind: "Captured source", title: "The wording changed.", text: "A comment revised the label on the status line.", rev: "example-r5", meaning: "Captured on Friday. Anything after that is not in this picture." },
  { day: null, hour: null, glyph: "↳", kind: "Waiting on you", title: "One conversation still needs you.", text: "A review is still requested from you.", rev: "example-r6", meaning: "Current waiting state, outside the week. Reading this recap does not withdraw it." },
];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const SVG = "http://www.w3.org/2000/svg";

export function mount(root) {
  let selected = 2, shape = "river";
  root.innerHTML = `
  <div class="toy toy-week">
    <div class="toy-controls">
      <fieldset class="toy-fieldset toy-fieldset-row"><legend>Shape</legend>
        <label class="toy-choice"><input type="radio" name="shape-${root.id}" value="river" checked> River</label>
        <label class="toy-choice"><input type="radio" name="shape-${root.id}" value="circle"> Circle</label>
      </fieldset>
      <ol class="week-list"></ol>
    </div>
    <div class="toy-stage">
      <figure class="week-figure"><svg class="week-svg" viewBox="0 0 640 360" aria-hidden="true" focusable="false"></svg>
      <figcaption>Fictional items, drawn twice. The list beside the drawing is the same in both shapes.</figcaption></figure>
      <div class="week-detail" aria-live="polite"></div>
    </div>
  </div>`;
  const $ = (s) => root.querySelector(s);
  const svg = $(".week-svg"), list = $(".week-list"), detail = $(".week-detail");

  ITEMS.forEach((it, i) => {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.type = "button"; b.className = "week-item"; b.dataset.i = i;
    const when = document.createElement("span"); when.className = "mono";
    when.textContent = it.day === null ? "NOW" : `${DAYS[it.day].toUpperCase()} ${String(Math.floor(it.hour)).padStart(2, "0")}:${String(Math.round((it.hour % 1) * 60)).padStart(2, "0")}`;
    const t = document.createElement("strong"); t.textContent = it.title;
    b.append(when, t);
    li.append(b); list.append(li);
  });

  const el = (name, attrs, parent = svg) => { const n = document.createElementNS(SVG, name); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); parent.append(n); return n; };

  const position = (it) => {
    if (shape === "river") {
      if (it.day === null) return [598, 180];
      const x = 40 + (it.day + it.hour / 24) * (500 / 7);
      return [x, 180 + Math.sin(x / 58) * 46];
    }
    if (it.day === null) return [320, 180];
    const a = ((it.day + it.hour / 24) / 7) * Math.PI * 2 - Math.PI / 2;
    return [320 + Math.cos(a) * 128, 180 + Math.sin(a) * 128];
  };

  const draw = () => {
    svg.replaceChildren();
    if (shape === "river") {
      let d = "M40 " + (180 + Math.sin(40 / 58) * 46);
      for (let x = 44; x <= 540; x += 4) d += ` L${x} ${(180 + Math.sin(x / 58) * 46).toFixed(1)}`;
      el("path", { d, class: "week-flow" });
      DAYS.forEach((dname, i) => {
        const x = 40 + i * (500 / 7);
        el("line", { x1: x, x2: x, y1: 70, y2: 300, class: "week-tick" });
        el("text", { x: x + 6, y: 64, class: "week-label" }).textContent = dname.toUpperCase();
      });
      el("line", { x1: 560, x2: 560, y1: 70, y2: 300, class: "week-edge" });
      el("text", { x: 572, y: 64, class: "week-label" }).textContent = "NOW";
    } else {
      el("circle", { cx: 320, cy: 180, r: 128, class: "week-flow" });
      DAYS.forEach((dname, i) => {
        const a = (i / 7) * Math.PI * 2 - Math.PI / 2;
        el("line", { x1: 320 + Math.cos(a) * 104, y1: 180 + Math.sin(a) * 104, x2: 320 + Math.cos(a) * 152, y2: 180 + Math.sin(a) * 152, class: "week-tick" });
        const la = a + Math.PI / 7;
        el("text", { x: 320 + Math.cos(la) * 168, y: 184 + Math.sin(la) * 168, class: "week-label", "text-anchor": "middle" }).textContent = dname.toUpperCase();
      });
      el("circle", { cx: 320, cy: 180, r: 34, class: "week-edge" });
    }
    ITEMS.forEach((it, i) => {
      const [x, y] = position(it);
      const g = el("g", { class: "week-dot" + (i === selected ? " is-selected" : "") + (it.day === null ? " is-waiting" : ""), "data-i": i });
      el("circle", { cx: x, cy: y, r: i === selected ? 17 : 12 }, g);
      el("text", { x, y: y + 5, "text-anchor": "middle" }, g).textContent = it.glyph;
    });
  };

  const show = (i) => {
    selected = i;
    const it = ITEMS[i];
    list.querySelectorAll(".week-item").forEach((b, j) => b.setAttribute("aria-pressed", String(j === i)));
    detail.replaceChildren();
    const k = document.createElement("p"); k.className = "mono week-kind"; k.textContent = it.kind.toUpperCase();
    const h = document.createElement("h4"); h.textContent = it.title;
    const p = document.createElement("p"); p.textContent = it.text;
    const m = document.createElement("p"); m.className = "week-meaning"; m.textContent = it.meaning;
    const r = document.createElement("p"); r.className = "mono week-rev"; r.textContent = `CAPTURED REVISION / ${it.rev} (SYNTHETIC)`;
    detail.append(k, h, p, m, r);
    draw();
  };

  list.addEventListener("click", (e) => { const b = e.target.closest(".week-item"); if (b) show(Number(b.dataset.i)); });
  svg.addEventListener("click", (e) => { const g = e.target.closest(".week-dot"); if (g) show(Number(g.dataset.i)); });
  root.querySelectorAll(`input[name="shape-${root.id}"]`).forEach((r) => r.addEventListener("change", () => { shape = r.value; draw(); }));
  show(selected);
}
