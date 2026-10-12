// UFOs hub: shape chips filter the famous-sighting cards (all cards are in the HTML).
(function () {
  const cards = [...document.querySelectorAll('.uh-card')];
  const chips = [...document.querySelectorAll('.uh-chips .ce-chip')];
  const status = document.querySelector('.ce-status');
  chips.forEach((chip) => chip.addEventListener('click', () => {
    const f = chip.dataset.f;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
    let n = 0;
    cards.forEach((c) => { const ok = !f || c.dataset.f === f; c.hidden = !ok; if (ok) n++; });
    document.querySelectorAll('.ufo-hub .ce-dec').forEach((g) => { g.hidden = !g.querySelector('.uh-card:not([hidden])'); });
    if (status) status.textContent = f ? `Showing ${n} sighting${n === 1 ? '' : 's'}.` : '';
  }));
})();
