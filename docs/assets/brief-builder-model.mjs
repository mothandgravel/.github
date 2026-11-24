const briefHeading = '# A brief for Moth & Gravel';

function section(title, choices, detail = '') {
  const answer = [...choices.map(text => '- ' + text), detail.trim()].filter(Boolean);
  return answer.length ? '## ' + title + '\n' + answer.join('\n') : '';
}

export function briefSections({ domain, making, friction, difficulty, artifact, ground, constraints }) {
  return [
    section('System', domain, making),
    section('Friction', friction, difficulty),
    section('First artifact', artifact),
    section('Ground rules', ground, constraints),
  ];
}

export function formatBrief(sections) {
  const selected = sections.filter(Boolean);
  return selected.length ? [briefHeading, ...selected].join('\n\n') : '';
}

export function updateBrief(edited, before, after) {
  if (edited === formatBrief(before)) return formatBrief(after);
  let result = edited;
  for (const [i, previous] of before.entries()) {
    const current = after[i];
    if (previous === current) continue;
    const location = previous ? result.lastIndexOf(previous) : -1;
    const line = location === 0 || result[location - 1] === '\n';
    const end = location + previous.length;
    const boundary = end === result.length || result[end] === '\n';
    if (location >= 0 && line && boundary) {
      result = result.slice(0, location) + current + result.slice(end);
    } else if (current) {
      // A manually rewritten section stays intact. Apply the current controls as a new block.
      result += (result ? '\n\n' : '') + current;
    }
  }
  return result;
}

function encodeMail(value) {
  const unicode = new TextDecoder('utf-8', { ignoreBOM: true }).decode(new TextEncoder().encode(value));
  return encodeURIComponent(unicode);
}

export function emailHref(text) {
  const topic = text.split(/\r?\n/).find(line => line.trim() && !line.trimStart().startsWith('#'));
  const subject = 'A brief for Moth & Gravel' + (topic
    ? ': ' + Array.from(topic.replace(/^\s*-\s*/, '').replace(/\s+/g, ' ').trim()).slice(0, 60).join('')
    : '');
  return 'mailto:hello@mothandgravel.com?subject=' + encodeMail(subject) +
    '&body=' + encodeMail(text.replace(/\r?\n/g, '\r\n'));
}
