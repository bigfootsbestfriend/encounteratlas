// Creature pages: show this creature's latest approved reader reports, if it has any.
(() => {
  const sec = document.querySelector('[data-rr]');
  if (!sec || !sec.dataset.api) return;
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const when = (d) => {
    const [y, m, day] = (d || '').split('-').map(Number);
    if (!y) return '';
    return m ? `${MONTHS[m - 1]} ${day ? day + ', ' : ''}${y}` : String(y);
  };
  fetch(`${sec.dataset.api}/api/reports?limit=6&creature=${encodeURIComponent(sec.dataset.rr)}`)
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => {
      if (!d || !d.reports || !d.reports.length) return;
      const list = sec.querySelector('.rr-list');
      const all = sec.querySelector('p:last-child a').getAttribute('href');
      const reportsPage = all.split('?')[0];
      for (const x of d.reports) {
        const a = document.createElement('a');
        a.className = 'ws-card';
        a.href = `${reportsPage}${encodeURIComponent(x.id)}/`;
        const b = document.createElement('b');
        b.textContent = x.place || 'Somewhere';
        const m = document.createElement('span');
        m.className = 'ws-meta';
        m.textContent = (x.date_approx ? 'Around ' : '') + when(x.seen_date) + (x.witnesses > 1 ? ` · ${x.witnesses} witnesses` : '');
        const t = document.createElement('span');
        t.className = 'ws-dek';
        t.textContent = x.snippet;
        const g = document.createElement('span');
        g.className = 'ws-go';
        g.textContent = 'Read the report';
        a.append(b, m, t, g);
        list.append(a);
      }
      list.classList.add('ws-grid');
      sec.hidden = false;
      const link = document.querySelector('[data-rr-link]');
      if (link) { link.hidden = false; link.textContent = `${d.reports.length}${d.next ? '+' : ''} reader report${d.reports.length === 1 && !d.next ? '' : 's'}`; }
      const jump = document.querySelector('.jump');
      if (jump && !jump.querySelector('a[href="#reader"]')) {
        const j = document.createElement('a');
        j.href = '#reader';
        j.textContent = 'Reader reports';
        jump.insertBefore(j, jump.children[1] || null);
      }
    })
    .catch(() => {});
})();
