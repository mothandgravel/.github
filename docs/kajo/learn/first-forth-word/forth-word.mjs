const exercise = document.querySelector('[data-forth-double]');
const inputGroup = exercise.querySelector('[data-forth-input]');
const controls = exercise.querySelector('[data-forth-controls]');
const stack = exercise.querySelector('[data-forth-stack]');
const status = exercise.querySelector('[data-forth-status]');
const back = exercise.querySelector('[data-forth-back]');
const step = exercise.querySelector('[data-forth-step]');
const reset = exercise.querySelector('[data-forth-reset]');
const stackAnnouncement = document.createElement('span');
stackAnnouncement.className = 'visually-hidden';

let frame = 0;
const finalFrame = 2;

function render() {
  const number = Number(inputGroup.querySelector('input:checked').value);
  const frames = [
    { values: [number], note: 'Number pushed. Next is DUP.' },
    { values: [number, number], note: 'DUP copied the top value. Next is +.' },
    { values: [number + number], note: '+ replaced the two values with their sum. Done.' },
  ];
  const { values, note } = frames[frame];
  stack.textContent = `[${values.join(' ')}]`;
  stackAnnouncement.textContent = ` Data stack ${stack.textContent}.`;
  status.replaceChildren(note, stackAnnouncement);
  back.setAttribute('aria-disabled', String(frame === 0));
  step.setAttribute('aria-disabled', String(frame === finalFrame));
  reset.setAttribute('aria-disabled', String(frame === 0));
}

function goTo(nextFrame) {
  if (nextFrame < 0 || nextFrame > finalFrame || frame === nextFrame) return;
  frame = nextFrame;
  render();
}

inputGroup.addEventListener('change', () => {
  frame = 0;
  render();
});
back.addEventListener('click', () => goTo(frame - 1));
step.addEventListener('click', () => goTo(frame + 1));
reset.addEventListener('click', () => goTo(0));

render();
inputGroup.hidden = false;
controls.hidden = false;
