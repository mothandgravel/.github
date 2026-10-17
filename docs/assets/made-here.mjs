// Made here, on the homepage: everything made under the one studio, with one plain status each.
// The homepage imports this after its load event, so its first paint carries none of these bytes,
// and the list is in place (inside a box the homepage already reserves) before anyone scrolls to it.
// Its styles are set on the elements themselves: adding a stylesheet after load restyles the whole
// page, and the moth interlude's timing is sensitive to that. Without scripts, the section links to
// the same list on the standing-investigations page; check_site.py keeps the two lists in step.
export const MADE_HERE = [
  ['Decision Docket', 'pr', 'In production for our own work'],
  ['Cyber Grid', 'pl', 'Playable, link coming'],
  ['Raivari', '', 'Prototype'],
  ['Ajo', '', 'Prototype'],
  ['SkyStack Builder', '', 'Prototype'],
  ['Geaidnu', '', 'Prototype'],
  ['LiveConnect', 'sd', 'Study, parked'],
  ['Kitronik buggy', 'sd', 'Study'],
  ['raivari-rpc', 'sd', 'Study'],
  ['flutter-test-rs', '', 'Prototype'],
  ['paja', 'in', 'Internal tool'],
  ['Field Notes studio', 'pr', 'In production for our own work'],
];

// Shape, not only colour, separates the statuses: filled circle, filled square, dashed circle, square.
const MARK = {
  pr: 'background:currentColor;border-radius:50%', pl: 'background:currentColor;border-radius:1px',
  sd: 'border-style:dashed;border-radius:50%', in: 'border-radius:1px', '': 'border-radius:50%',
};
const narrow = matchMedia('(max-width:660px)');
const roll = document.querySelector('[data-made-here]');
if (roll && !roll.querySelector('ul')) {
  const list = document.createElement('ul');
  list.style.cssText = 'margin:6px 0 22px;padding:0;list-style:none;columns:3 260px;column-gap:36px';
  const rows = MADE_HERE.map(([name, kind, status]) => {
    const item = document.createElement('li');
    const label = document.createElement('span');
    const mark = document.createElement('span');
    mark.setAttribute('aria-hidden', 'true');
    mark.style.cssText = `width:8px;height:8px;border:1px solid;flex:none;${MARK[kind]}`;
    label.style.cssText = 'display:flex;align-items:center;gap:8px;font:600 11px/1.4 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:'
      + (kind === 'pr' ? 'var(--gold-bright)' : kind === 'pl' ? 'var(--ink)' : 'var(--secondary)');
    label.append(mark, status);
    item.append(name + ' ', label);
    list.append(item);
    return item;
  });
  const lay = () => rows.forEach((item) => {
    item.style.cssText = 'break-inside:avoid;gap:' + (narrow.matches ? '4px;display:grid' : '12px;display:flex;justify-content:space-between')
      + ';padding:10px 0;border-bottom:1px solid var(--line-soft);font-weight:600';
  });
  lay();
  narrow.addEventListener('change', lay);
  const fallback = roll.querySelector('[data-made-here-link]');
  roll.insertBefore(list, fallback);
  fallback.replaceChildren('Three of them, in your hands. ', Object.assign(document.createElement('a'), {
    className: 'line-link', href: './workbench/playground/', textContent: 'Open the playground ↗' }));
}
