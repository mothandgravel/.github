export const PAGE_SIZE = 20;
export function specimenFor(note, specimens) {
  if (!note.specimen?.href) return null;
  const target = new URL(note.specimen.href, 'https://mothandgravel.com/notes/');
  if (target.origin !== 'https://mothandgravel.com') return null;
  return specimens.find(item => {
    const family = new URL(item.href, target.origin);
    return family.pathname !== '/' ? target.pathname.startsWith(family.pathname) :
      target.pathname === '/' && target.hash === family.hash;
  }) || null;
}

export function relationshipFor(note, specimens) {
  if (!note.specimen?.href) return null;
  const specimen = specimenFor(note, specimens);
  const target = new URL(note.specimen.href, 'https://mothandgravel.com/notes/');
  const label = note.specimen.label.replace(/^Return to /, 'Open ');
  if (specimen) return { kind: 'specimen', kicker: `SPECIMEN ${specimen.id}`, label };
  if (target.origin === 'https://mothandgravel.com' && target.pathname.startsWith('/investigations/'))
    return { kind: 'investigation', kicker: 'INVESTIGATION', label };
  return null;
}

export function queryNotes(notes, { q = '', topic = '', sort = 'newest', page = 1 } = {}) {
  const words = q.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const filtered = notes.filter(n => (!topic || (n.topics || []).includes(topic)) && words.every(word =>
    [n.id, n.title, n.summary, n.type, n.project, ...(n.topics || [])].join(' ').toLocaleLowerCase().includes(word)));
  filtered.sort((a, b) => {
    if (sort === 'title') return a.title.localeCompare(b.title);
    const direction = sort === 'oldest' ? 1 : -1;
    return direction * (Number(a.id) - Number(b.id));
  });
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(pages, Math.max(1, Number.isFinite(Number(page)) ? Math.floor(Number(page)) : 1));
  return { total: filtered.length, pages, page: current, entries: filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE) };
}
