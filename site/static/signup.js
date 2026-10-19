// Weekly email prompts. The hello bar above the header (in build.py's page()) and one slide-in card that appears
// once someone has read half a page or spent 30 seconds on it, never while another signup form is on screen.
// Closing either keeps it away for 14 days; signing up hides both for good.
(() => {
  const DAYS14 = 12096e5;
  const store = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
  if (/^#confirmed/.test(location.hash) && location.pathname.indexOf('/newsletter/') !== -1) store('ea-subbed', '1');
  const subbed = () => !!store('ea-subbed');

  document.addEventListener('submit', (e) => {
    const f = e.target.closest('form[data-nl]');
    if (!f) return;
    store('ea-subbed', '1');
    if (window.gtag) window.gtag('event', 'sign_up', { method: 'email', placement: f.closest('.hello') ? 'bar' : f.closest('.nl-slide') ? 'slide' : 'box' });
  });

  const hello = document.getElementById('hello');
  if (hello) hello.querySelector('.hello-x').addEventListener('click', () => { store('ea-hello', String(Date.now())); hello.remove(); });

  if (subbed() || Date.now() - (+store('ea-slide') || 0) < DAYS14 || location.pathname.indexOf('/newsletter/') !== -1) return;
  const api = document.querySelector('form[data-nl]');
  if (!api) return;
  const card = document.createElement('aside');
  card.className = 'nl-slide';
  card.setAttribute('aria-label', 'Weekly email');
  card.hidden = true;
  card.innerHTML = '<button type="button" class="hello-x" aria-label="No thanks">&times;</button>' +
    '<h2>Like strange stories?</h2><p>One short email every Thursday: monsters from the old newspapers, a creature of the week and the newest reader reports from around the world. Free, unsubscribe in one click.</p>' +
    `<form action="${api.action}" method="post" data-nl><input type="hidden" name="site" value="encounteratlas">` +
    '<input class="visually-hidden" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">' +
    '<label for="slide-email" class="visually-hidden">Email address</label>' +
    '<input id="slide-email" name="email" type="email" required placeholder="you@example.com" autocomplete="email">' +
    '<button type="submit" class="btn">Sign me up</button></form>';
  document.body.appendChild(card);
  const close = () => { store('ea-slide', String(Date.now())); card.classList.remove('in'); setTimeout(() => card.remove(), 400); };
  card.querySelector('.hello-x').addEventListener('click', close);
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && card.classList.contains('in')) close(); });

  // Any signup form (the hello bar or an in-page box) on screen means no slide-in right now.
  let onScreen = 0, shown = false;
  const io = new IntersectionObserver((es) => es.forEach((en) => { onScreen += en.isIntersecting ? 1 : -1; if (onScreen < 0) onScreen = 0; }));
  document.querySelectorAll('.signup, #hello').forEach((el) => io.observe(el));
  const show = () => {
    if (shown || onScreen > 0 || subbed() || document.querySelector('.report-form:focus-within, form:focus-within')) return;
    shown = true;
    store('ea-slide', String(Date.now())); // counts as offered even if ignored
    card.hidden = false;
    requestAnimationFrame(() => requestAnimationFrame(() => card.classList.add('in')));
  };
  setTimeout(show, 30000);
  addEventListener('scroll', () => {
    if (scrollY > (document.documentElement.scrollHeight - innerHeight) * 0.5 && scrollY > 600) show();
  }, { passive: true });
})();
