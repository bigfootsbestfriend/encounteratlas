// Contact form: Turnstile, then POST /api/contact on the reports Worker (EA from vote.js).
(function () {
  const form = document.querySelector('.contact-form');
  if (!form || !window.EA) return;
  const slot = form.querySelector('.ts-slot'), msg = form.querySelector('.c-msg'), btn = form.querySelector('button[type=submit]');
  EA.human(slot).catch(() => { msg.textContent = 'The spam check did not load. Check your connection and reload the page.'; });
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(form));
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(d.email || '')) { msg.textContent = 'Enter your email address so we can reply.'; return; }
    if ((d.message || '').trim().length < 10) { msg.textContent = 'Write a little more in the message.'; return; }
    btn.disabled = true; msg.textContent = 'Sending...';
    try { d.turnstile = await EA.human(slot); } catch (err) { msg.textContent = 'The spam check did not load. Reload and try again.'; btn.disabled = false; return; }
    const r = await EA.api('/api/contact', { method: 'POST', body: d, auth: false });
    EA.resetHuman(slot); btn.disabled = false;
    if (r.status === 200) { window.eaTrack && eaTrack('contact_send', { topic: d.topic || 'general', form: form.classList.contains('compact') ? 'about' : 'contact' }); form.reset(); msg.textContent = 'Thanks, your message is on its way. We reply from hello@encounteratlas.com.'; }
    else msg.textContent = { email: 'That email address doesn\'t look right.', message: 'Write a little more in the message.', slow: 'Too many messages. Try again in an hour.',
      turnstile: 'The spam check failed. Press Send again.', offline: 'No connection. Try again when you have signal.' }[r.data.state] || 'Something went wrong. Email hello@encounteratlas.com instead.';
  });
})();
