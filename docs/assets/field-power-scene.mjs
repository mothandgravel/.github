// Code-native axonometric study. Dimensions are visual, not an engineering drawing.
const prism = (x, y, w, d, h, cls = '') => `<g class="fp-object ${cls}"><path class="fp-left" d="M${x-w} ${y}l${w} ${w*.43}v${-h}l${-w} ${-w*.43}Z"/><path class="fp-right" d="M${x} ${y+w*.43}l${d} ${-d*.43}v${-h}l${-d} ${d*.43}Z"/><path class="fp-top" d="M${x-w} ${y-h}l${d} ${-d*.43}l${w} ${w*.43}l${-d} ${d*.43}Z"/></g>`;
const ribs = (x,y,n,h) => Array.from({length:n},(_,i)=>`<path d="M${x+i*8} ${y-i*3.44}v${h}"/>`).join('');
const label = (x,y,id,name) => `<g class="fp-map-label" transform="translate(${x} ${y})"><text class="fp-map-id">${id}</text><text y="20">${name}</text></g>`;
export function sceneMarkup() {
  return `<svg viewBox="0 0 1000 640" role="img" aria-labelledby="fp-scene-title fp-scene-desc">
  <title id="fp-scene-title">A field support site and its power circuit</title><desc id="fp-scene-desc">An illustrative generator, battery, shelter, communications mast, water pump and workshop. Read the live simulated load values and equipment inspector below.</desc>
  <defs><radialGradient id="fp-ground-glow"><stop stop-color="#a89466" stop-opacity=".11"/><stop offset="1" stop-color="#a89466" stop-opacity="0"/></radialGradient><linearGradient id="fp-metal" x2=".6" y2="1"><stop stop-color="#77807d"/><stop offset="1" stop-color="#303a3c"/></linearGradient><pattern id="fp-grid" width="48" height="24" patternUnits="userSpaceOnUse"><path d="M0 12L24 0 48 12 24 24Z" fill="none" stroke="#a9b7b2" stroke-opacity=".055"/></pattern><filter id="fp-glow"><feGaussianBlur stdDeviation="4"/></filter></defs>
  <rect width="1000" height="640" fill="url(#fp-grid)"/><ellipse cx="510" cy="330" rx="470" ry="300" fill="url(#fp-ground-glow)"/>
  <g fill="none" stroke="#677977" stroke-opacity=".19" stroke-width="1"><path d="M-70 366Q80 215 235 232T522 90T1060 185M-50 382Q90 229 247 248T531 108T1070 205M-30 399Q107 246 262 265T541 126T1080 225M-10 415Q123 261 277 282T551 144T1090 245M-30 531Q200 389 335 472T689 500T1090 371M-20 551Q211 409 346 492T700 520T1100 391M-10 571Q222 429 357 512T711 540T1110 411"/></g>
  <g stroke="#738581" stroke-opacity=".35" fill="none"><path d="M80 570h40m-20-20v40M890 92h40m-20-20v40"/><path d="M130 590h100m-100-4v8m50-8v8m50-8v8"/></g><g class="fp-map-small"><text x="130" y="613">ILLUSTRATIVE SITE / NOT TO SCALE</text><text x="828" y="55">N ↑ / FIELD 01</text></g>
  <path d="M145 351L544 174 867 316 466 494Z" fill="#b4b19b" fill-opacity=".035" stroke="#a2a68c" stroke-opacity=".13"/>
  <g class="fp-cables" fill="none" stroke-linejoin="round"><path id="fp-wire-generator" d="M264 326L386 379 478 338"/><path id="fp-wire-battery" d="M443 250L510 279 478 338"/><path id="fp-wire-comms" d="M478 338L711 236 760 258"/><path id="fp-wire-heat" d="M478 338L576 381 667 341"/><path id="fp-wire-water" d="M478 338L337 400 272 428"/><path id="fp-wire-workshop" d="M478 338L482 419 574 459"/></g>
  <ellipse cx="268" cy="329" rx="99" ry="28" fill="#070e11" opacity=".5"/>
  <g id="fp-equipment-generator">${prism(266,323,92,106,10,'fp-plinth')}${prism(260,306,68,90,67,'fp-machine')}
  <path d="M204 260l44 19v37l-44-19Z" fill="#121d21" stroke="#6a7470"/><g stroke="#7a8277" stroke-width="2">${ribs(267,262,9,37)}</g><path d="M287 217v-26l13-6v23" fill="none" stroke="#54615f" stroke-width="7"/><path d="M212 238l37 16" stroke="#a6b1a2" stroke-width="3"/><circle class="fp-lamp" cx="239" cy="277" r="3"/>
  <text x="208" y="290" class="fp-stencil" transform="rotate(23 208 290)">G / 18</text></g>
  <g id="fp-equipment-battery">${prism(444,254,65,80,9,'fp-plinth')}${prism(442,241,44,52,87,'fp-battery')}
  <path d="M448 183l38-16v56l-38 16Z" fill="#101e24" stroke="#71807c"/><g fill="#b9c9b0">${Array.from({length:5},(_,i)=>`<path d="M455 ${181+i*9}l24-10v4l-24 10Z"/>`).join('')}</g><path d="M407 174v53m11-48v53" stroke="#1c2a2e"/><text x="409" y="160" class="fp-stencil" transform="rotate(23 409 160)">BESS</text></g>
  <g id="fp-equipment-heat">${prism(657,345,124,153,9,'fp-plinth')}${prism(651,328,99,127,85,'fp-shelter')}
  <path d="M552 243l127-55 99 43-127 55Z" fill="#6a7775"/><path d="M565 249l126-55m-106 64l126-55m-106 64l126-55m-106 64l126-55" stroke="#97a29a" stroke-opacity=".3"/>
  <path d="M671 284l36-15v56l-36 15Z" fill="#243338" stroke="#76847f"/><path d="M724 263l36-15v22l-36 15Z" class="fp-window"/><path d="M568 264l29 12v21l-29-12Zm42 18l28 12v21l-28-12Z" class="fp-window"/>
  <path d="M682 282l14-6" stroke="#f0d5a1" stroke-width="4" class="fp-lamp"/><path d="M674 332l38 16 13-6-38-17" fill="#7d847b"/>
  <path d="M742 208v-23l10-4v24" stroke="#9aa69a" stroke-width="6"/></g>
  <g id="fp-equipment-comms">${prism(765,260,29,40,11,'fp-plinth')}<path d="M755 238L765 95 779 240M759 181h14m-12-33h9m-8-28h7M756 222l18-41-13-33 9-28" fill="none" stroke="#a3b2aa" stroke-width="2"/><path d="M765 145l-17-9v-33l17 8M767 162l20-9v-33l-20 9" fill="#bbc1ad" stroke="#505e5d"/>
  <path d="M765 115L710 257m55-142l63 140" stroke="#748883" stroke-width=".8"/><circle class="fp-lamp" cx="765" cy="95" r="3"/><path d="M739 111q-12 10 0 22m-6-29q-20 17 0 36" fill="none" stroke="#a4bea9" stroke-opacity=".5"/>
  ${prism(799,266,24,23,27,'fp-machine')}</g>
  <g id="fp-equipment-water">${prism(272,433,48,63,8,'fp-plinth')}<path d="M244 410v-45q32-24 64 0v45q-32 24-64 0Z" fill="url(#fp-metal)" stroke="#71807a"/><ellipse cx="276" cy="365" rx="32" ry="14" fill="#7a8580"/><ellipse cx="276" cy="365" rx="12" ry="5" fill="#455855"/><path d="M309 401h16v17h15" fill="none" stroke="#8c9a8c" stroke-width="5"/></g>
  <g id="fp-equipment-workshop">${prism(580,469,83,108,9,'fp-plinth')}${prism(576,453,68,90,54,'fp-workshop')}
  <g stroke="#7e8c82" stroke-opacity=".4">${ribs(582,426,10,49)}</g><path d="M515 410l49 21v36l-49-21Z" fill="#273337" stroke="#7b8276"/><path d="M517 418l45 20m-45-13l45 20m-45-13l45 20m-45-13l45 20" stroke="#788276" stroke-width="1"/><path d="M526 415l24 10" class="fp-lamp" stroke="#e2c798" stroke-width="3"/>
  ${prism(672,464,17,20,21,'fp-machine')}${prism(697,457,14,18,15,'fp-machine')}</g>
  <g id="fp-equipment-bus">${prism(480,344,21,27,32,'fp-machine')}<path d="M482 329l18-8" stroke="#e0c18c" stroke-width="3"/></g>
  ${label(125,208,'01 / GENERATION','18 kW genset')}${label(373,109,'02 / STORAGE','Battery reserve')}${label(795,176,'03 / ESSENTIAL','Communications')}${label(784,352,'04 / ESSENTIAL','Shelter heat')}${label(152,478,'05 / DEFERRABLE','Water pump')}${label(575,538,'06 / DEFERRABLE','Workshop')}
  </svg>`;
}
export function updateScene(root, s, selected) {
  for (const id of ['generator', 'battery', ...s.loads.map(l => l.id)]) {
    const power = id === 'generator' ? s.generated : id === 'battery' ? s.discharge + s.charge : s.loads.find(l => l.id === id).served;
    root.querySelector(`#fp-wire-${id}`)?.classList.toggle('is-on', power > .01);
    const el = root.querySelector(`#fp-equipment-${id}`);
    el?.classList.toggle('is-off', power <= .01);
    el?.classList.toggle('is-selected', selected === id);
  }
}
