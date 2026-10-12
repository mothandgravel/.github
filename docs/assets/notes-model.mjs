export const PAGE_SIZE = 20;
export function queryNotes(notes, { q = '', topic = '', sort = 'newest', page = 1 } = {}) {
  const words = q.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const filtered = notes.filter(n => (!topic || (n.topics || []).includes(topic)) && words.every(word =>
    [n.id, n.title, n.summary, n.type, n.project, ...(n.topics || [])].join(' ').toLocaleLowerCase().includes(word)));
  filtered.sort((a, b) => {
    if (sort === 'title') return a.title.localeCompare(b.title);
    const direction = sort === 'oldest' ? 1 : -1;
    return direction * (a.date.localeCompare(b.date) || Number(a.id) - Number(b.id));
  });
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(pages, Math.max(1, Number.isFinite(Number(page)) ? Math.floor(Number(page)) : 1));
  return { total: filtered.length, pages, page: current, entries: filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE) };
}
