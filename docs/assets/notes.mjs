import { queryNotes, PAGE_SIZE } from './notes-model.mjs';

const form = document.querySelector('#archive-controls');
if (form) {
  try {
    const response = await fetch(new URL('./notes.json', import.meta.url));
    if (!response.ok) throw new Error('Catalog unavailable');
    const notes = (await response.json()).map(n => ({ ...n, topics: n.topics || [] }));
    const results = document.querySelector('#archive-results');
    const status = document.querySelector('#archive-status');
    const pager = document.querySelector('#archive-pagination');
    const previous = document.querySelector('#archive-previous');
    const next = document.querySelector('#archive-next');
    const topic = form.elements.topic;
    const search = form.elements.q;
    const sort = form.elements.sort;
    const reset = document.querySelector('#archive-reset');
    const topics = [...new Set(notes.flatMap(n => n.topics))].sort();
    for (const value of topics) topic.add(new Option(value, value));
    let state;
    const element = (tag, text, cls) => {
      const node = document.createElement(tag);
      if (text) node.textContent = text;
      if (cls) node.className = cls;
      return node;
    };
    function readURL() {
      const params = new URLSearchParams(location.search);
      const candidate = params.get('topic') || '';
      state = { q: params.get('q') || '', topic: topics.includes(candidate) ? candidate : '',
        sort: ['newest', 'oldest', 'title'].includes(params.get('sort')) ? params.get('sort') : 'newest',
        page: params.get('page') || 1 };
      search.value = state.q; topic.value = state.topic; sort.value = state.sort;
    }
    function render() {
      const view = queryNotes(notes, state);
      state.page = view.page;
      const fragment = document.createDocumentFragment();
      for (const n of view.entries) {
        const article = element('article', '', 'archive-entry notes-index-entry');
        article.dataset.noteId = n.id;
        const meta = element('div', `${n.id} / ${n.type.toUpperCase()}`, 'editorial-meta mono');
        const body = element('div');
        const heading = element('h3');
        const link = element('a', n.title);
        link.href = './' + n.slug;
        const arrow = element('span', ' ↗'); arrow.setAttribute('aria-hidden', 'true');
        link.append(arrow); heading.append(link);
        body.append(heading, element('p', n.summary), element('p', n.topics.join(' · '), 'archive-topics mono'));
        article.append(meta, body); fragment.append(article);
      }
      if (!view.total) fragment.append(element('p', 'No notes match. Try another word or clear the filters.', 'archive-empty'));
      results.replaceChildren(fragment);
      const start = view.total ? (view.page - 1) * PAGE_SIZE + 1 : 0;
      status.textContent = `${view.total} ${view.total === 1 ? 'note' : 'notes'}${view.total ? ` · Showing ${start}–${Math.min(start + PAGE_SIZE - 1, view.total)}` : ''}`;
      previous.disabled = view.page <= 1; next.disabled = view.page >= view.pages;
      document.querySelector('#archive-page').textContent = `Page ${view.page} of ${view.pages}`;
      pager.hidden = view.pages <= 1;
      reset.hidden = !(state.q || state.topic || state.sort !== 'newest');
    }
    function commit(focus = false) {
      render();
      const url = new URL(location.href);
      for (const key of ['q', 'topic', 'sort', 'page']) url.searchParams.delete(key);
      if (state.q) url.searchParams.set('q', state.q);
      if (state.topic) url.searchParams.set('topic', state.topic);
      if (state.sort !== 'newest') url.searchParams.set('sort', state.sort);
      if (state.page > 1) url.searchParams.set('page', state.page);
      url.hash = 'archive';
      try { history.pushState(null, '', url); } catch (_) { /* filtering still works */ }
      if (focus) document.querySelector('#archive-title').focus({ preventScroll: false });
    }
    form.addEventListener('submit', event => {
      event.preventDefault();
      state = { q: search.value.trim(), topic: topic.value, sort: sort.value, page: 1 };
      commit();
    });
    reset.addEventListener('click', () => {
      state = { q: '', topic: '', sort: 'newest', page: 1 };
      search.value = ''; topic.value = ''; sort.value = 'newest'; commit(); search.focus();
    });
    previous.addEventListener('click', () => { state.page -= 1; commit(true); });
    next.addEventListener('click', () => { state.page += 1; commit(true); });
    window.addEventListener('popstate', () => { readURL(); render(); });
    readURL(); render();
    document.querySelector('#archive-fallback').remove();
    results.hidden = false; status.hidden = false; form.hidden = false;
  } catch (_) {
    // A failed module/catalog request leaves the complete static archive readable.
  }
}
