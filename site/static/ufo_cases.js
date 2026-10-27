// Famous UFO cases. Hub (/ufo/cases/): decade, shape and verdict chips filter the cards instantly (every case is in the
// HTML, this only hides). Case pages: a copy-link button on the case file header and a "What do you think it was?" poll
// whose pick is saved in this browser only.
(function () {
  const ga = (name, p) => { if (window.gtag) try { window.gtag('event', name, { page_type: 'ufo', ...p }); } catch (x) { /* no analytics */ } };
  const mk = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text != null) el.textContent = text; return el; };

  // ---- Hub filters ----
  const filters = document.querySelector('.uc-filters');
  if (filters) {
    filters.hidden = false;
    const chips = [...filters.querySelectorAll('.uc-chip')];
    const cards = [...document.querySelectorAll('.ce-card[data-slug]')];
    const groups = [...document.querySelectorAll('.ce-dec')];
    const status = document.querySelector('.ce-status');
    const clear = filters.querySelector('.uc-clear');
    const st = { dec: '', k: '', s: '' };
    const apply = () => {
      let shown = 0;
      const slugs = [];
      cards.forEach((c) => {
        const ok = (!st.dec || c.dataset.dec === st.dec) && (!st.k || c.dataset.k.split(' ').includes(st.k)) && (!st.s || c.dataset.s === st.s);
        c.hidden = !ok;
        if (ok) { shown++; slugs.push(c.dataset.slug); }
      });
      groups.forEach((g) => { g.hidden = !g.querySelector('.ce-card:not([hidden])'); });
      chips.forEach((b) => b.setAttribute('aria-pressed', String(st[b.dataset.g] === b.dataset.f)));
      const any = st.dec || st.k || st.s;
      clear.hidden = !any;
      if (status) status.textContent = !any ? '' : shown ? `Showing ${shown} case${shown === 1 ? '' : 's'}.` : 'No cases match all of those. Try clearing one.';
      document.dispatchEvent(new CustomEvent('ce:filter', { detail: { slugs: any ? slugs : null } }));
    };
    chips.forEach((b) => b.addEventListener('click', () => {
      st[b.dataset.g] = st[b.dataset.g] === b.dataset.f ? '' : b.dataset.f;
      apply();
      ga('ufo_case_filter', { group: b.dataset.g, value: b.dataset.f || 'all' });
    }));
    clear.addEventListener('click', () => { st.dec = st.k = st.s = ''; apply(); });
  }

  // ---- Case file: copy link ----
  const copy = document.querySelector('.uc-copy');
  if (copy) {
    copy.hidden = false;
    copy.addEventListener('click', async () => {
      const url = location.origin + location.pathname;
      try { await navigator.clipboard.writeText(url); copy.textContent = 'Link copied'; }
      catch (x) { copy.textContent = 'Copy failed, sorry'; }
      ga('ufo_case_copy_link', {});
      setTimeout(() => { copy.textContent = 'Copy link to this case'; }, 2200);
    });
  }

  // ---- Poll ----
  const poll = document.querySelector('.uc-poll');
  if (!poll) return;
  poll.hidden = false;
  const slug = poll.dataset.slug, lean = poll.dataset.lean, status = poll.dataset.status;
  const KEY = 'ea-ufo-poll-' + slug;
  const LAB = { made: 'aircraft, a rocket or a balloon', natural: 'something natural', hoax: 'a hoax', unknown: 'truly unknown' };
  const opts = [...poll.querySelectorAll('.uc-opt')];
  const res = poll.querySelector('.uc-res');
  const facts = document.querySelector('.ce-facts small');
  const note = facts ? facts.textContent.trim() : '';
  const pill = document.querySelector('.ce-facts .ce-pill');
  let pick = '';
  try { pick = localStorage.getItem(KEY) || ''; } catch (x) { pick = ''; }

  function verdict() {
    if (!lean) return { t: "Honestly? Nobody agrees on this one, so your guess is as good as anyone's.", m: '' };
    if (pick === lean) return { t: pick === 'unknown' ? "Same as us. Nobody's explained this one yet." : `Same call as us: ${LAB[lean]}.`, m: 'agree' };
    if (pick === 'unknown') return { t: `Fair. We lean toward ${LAB[lean]}, but not everyone's convinced.`, m: 'near' };
    if (lean === 'unknown') return { t: "We'd file this under unknown. Nothing's been proven either way.", m: 'differ' };
    return { t: `We see it differently. We lean toward ${LAB[lean]}.`, m: 'differ' };
  }

  function paint() {
    opts.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.o === pick)));
    res.replaceChildren();
    poll.dataset.m = '';
    if (!pick) return;
    const v = verdict();
    poll.dataset.m = v.m;
    const you = mk('p', 'uc-you');
    you.append('Your pick: ', mk('b', '', LAB[pick]));
    const take = mk('div', 'uc-take');
    const head = mk('p', 'uc-take-h', 'Our take');
    if (pill) { const p = pill.cloneNode(true); head.append(' ', p); }
    take.append(head, mk('p', 'uc-line', v.t));
    if (note) take.append(mk('p', 'uc-note', note));
    res.append(you, take);
  }
  opts.forEach((b) => b.addEventListener('click', () => {
    pick = pick === b.dataset.o ? '' : b.dataset.o;
    try { pick ? localStorage.setItem(KEY, pick) : localStorage.removeItem(KEY); } catch (x) { /* private mode */ }
    paint();
    if (pick) ga('ufo_case_poll', { case_slug: slug, pick, lean: lean || 'open', status });
  }));
  paint();
})();
