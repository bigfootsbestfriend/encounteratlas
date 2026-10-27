// Save / share for any page (2026-10-26). The same sheet design as the podcast player's (podplayer.js), without needing it:
//   window.eaShareSheet({ title, line, url, track })  opens the sheet for anything
//   <script src="share.js" data-page-share>           also adds a small "Save / share" button under the page's h1
// "Email it to myself" opens the reader's email app addressed to them (the newsletter Worker only saves podcast episodes).
// "Send to a friend" uses the phone's share sheet (app-bridge.js routes it to the app's), else an email.
(() => {
  const SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';
  const track = (n, p) => { try { if (window.eaTrack) window.eaTrack(n, p); } catch (e) { /* no analytics */ } };
  const mk = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text) e.textContent = text; return e; };
  const OK = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  let sheet = null, q = {};

  function build() {
    sheet = mk('dialog', 'sh-sheet');
    sheet.setAttribute('aria-labelledby', 'sh-sheet-h');
    const f = mk('form', 'sh-in'); f.method = 'dialog';
    const h = mk('h2', '', 'Save or share'); h.id = 'sh-sheet-h';
    const t = mk('p', 'sh-t');
    const box = mk('div', 'sh-save');
    const lab = mk('label', '', 'Email it to myself'); lab.htmlFor = 'sh-email';
    const row = mk('div', 'sh-row');
    const inp = mk('input'); inp.id = 'sh-email'; inp.type = 'email'; inp.autocomplete = 'email'; inp.placeholder = 'you@example.com'; inp.enterKeyHint = 'send';
    const send = mk('button', 'btn sh-mail', 'Send'); send.type = 'button';
    row.append(inp, send);
    box.append(lab, row, mk('small', '', "Opens your email app with the link, addressed to you, so it's waiting in your inbox."));
    const friend = mk('button', 'btn sh-friend', 'Send to a friend'); friend.type = 'button';
    const copy = mk('button', 'btn sh-copy', 'Copy link'); copy.type = 'button';
    const msg = mk('p', 'sh-msg'); msg.setAttribute('aria-live', 'polite');
    const x = mk('button', 'sh-x', 'Close'); x.value = 'close';
    f.append(h, t, box, friend, copy, msg, x);
    sheet.append(f);
    document.body.append(sheet);
    sheet.addEventListener('click', (ev) => { if (ev.target === sheet) sheet.close(); });

    const say = (s) => { msg.textContent = s; };
    const mailSelf = () => {
      const email = inp.value.trim();
      if (!OK.test(email)) { say('Type your email address first.'); inp.focus(); return; }
      try { localStorage.setItem('ea-nl-email', email); } catch (e) { /* storage blocked */ }
      track(q.event, { how: 'email_self', kind: q.kind });
      location.href = `mailto:${encodeURIComponent(email).replace('%40', '@')}?subject=${encodeURIComponent('Read later: ' + q.title)}&body=${encodeURIComponent(`${q.line}\n\n${q.url}`)}`;
      say('Opening your email app...');
    };
    send.addEventListener('click', mailSelf);
    inp.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); mailSelf(); } });
    friend.addEventListener('click', async () => {
      track(q.event, { how: 'share', kind: q.kind });
      if (navigator.share) {
        try { await navigator.share({ title: q.title, text: `${q.line}. Thought you'd like this one:`, url: q.url }); sheet.close(); } catch (e) { /* cancelled */ }
      } else {
        location.href = `mailto:?subject=${encodeURIComponent('You have to read this: ' + q.title)}&body=${encodeURIComponent(`${q.line}\n\n${q.url}`)}`;
      }
    });
    copy.addEventListener('click', async () => {
      track(q.event, { how: 'copy', kind: q.kind });
      try { await navigator.clipboard.writeText(q.url); say('Link copied.'); } catch (e) { say(q.url); }
    });
  }

  window.eaShareSheet = (o) => {
    q = { title: o.title || document.title, line: o.line || o.title || document.title, url: o.url || location.href, event: o.event || 'page_share', kind: o.kind || '' };
    if (!sheet) build();
    sheet.querySelector('.sh-t').textContent = q.line;
    sheet.querySelector('.sh-msg').textContent = '';
    const inp = sheet.querySelector('#sh-email');
    try { const saved = localStorage.getItem('ea-nl-email'); if (saved && !inp.value) inp.value = saved; } catch (e) { /* storage blocked */ }
    if (sheet.showModal) sheet.showModal(); else sheet.setAttribute('open', '');
  };

  // ---------- the page's own button ----------
  const me = document.currentScript;
  if (!me || !me.hasAttribute('data-page-share')) return;
  const h1 = document.querySelector('main h1');
  if (!h1) return;
  const canon = document.querySelector('link[rel=canonical]');
  const link = (canon && canon.href) || location.href.split('#')[0].split('?')[0];
  const title = h1.textContent.replace(/\s+/g, ' ').trim();
  const lede = document.querySelector('main .lede');
  const line = lede && lede.textContent.trim().length < 220 ? `${title}: ${lede.textContent.replace(/\s+/g, ' ').trim()}` : title;
  const kind = location.pathname.split('/')[1] || 'home';
  const b = mk('button', 'sh-page'); b.type = 'button';
  b.innerHTML = SVG;
  b.append(mk('span', '', 'Save / share'));
  b.setAttribute('aria-label', 'Save or share this page');
  b.addEventListener('click', () => { track('page_share', { how: 'open', kind }); window.eaShareSheet({ title, line, url: link, kind }); });
  const wrap = mk('p', 'sh-page-row'); wrap.append(b);
  // Under the lede when it comes right after the h1 (or the h1's head row), else straight under the h1.
  let at = h1.parentElement.children.length === 1 || h1.parentElement.matches('[class*="-head"]:not(section)') ? h1.parentElement : h1;
  for (let n = at.nextElementSibling, i = 0; n && i < 3; n = n.nextElementSibling, i++) {
    if (n.matches('.lede')) { at = n; if (n.nextElementSibling && n.nextElementSibling.matches('.byline')) at = n.nextElementSibling; break; }
  }
  at.after(wrap);
})();
