// Report form: creature picker, GPS / map tap / place search, photos re-encoded in the browser (strips
// EXIF and GPS), video links, a local draft (text in localStorage, photos in IndexedDB), Turnstile, and
// edit mode (?edit=<id>) for your own reports. Needs vote.js (window.EA) loaded first.
(function () {
  const form = document.getElementById('report-form');
  const EA = window.EA;
  if (!form || !EA) return;
  const { h, api, store } = EA;
  const $ = (s) => form.querySelector(s);
  const DRAFT = 'ea-report-draft';
  const MAX_PHOTOS = 5, MAX_SIDE = 2000, QUALITY = 0.85;
  const editId = new URLSearchParams(location.search).get('edit');
  let photos = []; // {blob, url} (new) or {id, url, keep} (existing, edit mode)
  let point = null; // {lat, lon, source}
  let restoring = false;

  // ---------- who ----------
  const who = document.querySelector('[data-who]');
  const u = EA.user();
  if (EA.session() && u) {
    who.textContent = `Signed in as ${u.email}. `;
    who.append(h('a', { href: EA.page('?me=1'), text: 'Your reports' }));
    $('[data-email-field]').hidden = true;
  } else {
    who.append('Already sent one? ', h('a', { href: EA.page('?me=1'), text: 'Sign in to follow or edit it' }), '.');
  }

  // ---------- creature picker ----------
  const q = document.getElementById('pick-q');
  const picks = [...form.querySelectorAll('.pick')];
  q.addEventListener('input', () => {
    const t = q.value.trim().toLowerCase();
    for (const p of picks) p.hidden = !!t && !p.dataset.names.includes(t) && !p.classList.contains('pick-other');
    form.querySelectorAll('.pick-group').forEach((g) => { g.hidden = !g.querySelector('.pick:not([hidden])'); });
  });
  form.addEventListener('change', (e) => {
    if (e.target.name === 'creature') {
      $('[data-other]').hidden = e.target.value !== 'other';
      if (e.target.value === 'other') $('#other_what').focus();
    }
    if (e.target.name === 'anonymous') $('[data-name-field]').hidden = e.target.checked;
  });

  // ---------- date default ----------
  const today = () => { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
  $('#seen_date').max = today();
  if (!$('#seen_date').value) $('#seen_date').value = today();

  // ---------- location ----------
  const status = $('[data-loc-status]');
  const mapEl = document.getElementById('rep-map');
  const map = EA.makeMap(mapEl, { zoom: window.innerWidth < 720 ? 2.2 : 3 });
  let marker = null, mapReady = false;
  if (map) {
    map.on('load', () => { mapReady = true; if (point) drawPoint(false); });
    map.on('click', (e) => setPoint(e.lngLat.lat, e.lngLat.lng, 'map'));
  } else {
    mapEl.replaceChildren(h('p', { class: 'hint', text: 'The map didn\'t load. Use your location or search a place instead.' }));
  }
  // Same ~5 km grid the server uses, so the preview shows exactly what the public will see.
  function fuzz(lat, lon) {
    const step = 0.045, plat = Math.round(lat / step) * step;
    const lstep = step / Math.max(0.15, Math.cos((plat * Math.PI) / 180));
    return [plat, Math.round(lon / lstep) * lstep];
  }
  function setPoint(lat, lon, source, fly = false) {
    point = { lat: +lat.toFixed(6), lon: +lon.toFixed(6), source };
    form.lat.value = point.lat; form.lon.value = point.lon; form.loc_source.value = source;
    drawPoint(fly);
    clearErr('location');
    save();
  }
  function drawPoint(fly) {
    if (!point) return;
    const label = { gps: 'from your location', map: 'from the map', place: 'from the place search' }[point.source] || '';
    status.textContent = `Pinned ${label}: ${point.lat.toFixed(4)}, ${point.lon.toFixed(4)}. Drag the pin to fine-tune. The shaded circle is all the public sees.`;
    if (!map) return;
    if (!marker) {
      const dot = h('div', { class: 'pin', 'aria-hidden': 'true' });
      marker = new maplibregl.Marker({ element: dot, draggable: true }).setLngLat([point.lon, point.lat]).addTo(map);
      marker.on('dragend', () => { const ll = marker.getLngLat(); setPoint(ll.lat, ll.lng, point.source === 'gps' ? 'gps' : 'map'); });
    } else marker.setLngLat([point.lon, point.lat]);
    if (mapReady) {
      const [plat, plon] = fuzz(point.lat, point.lon);
      EA.areaLayer(map, 'pub', plon, plat, 3);
    }
    if (fly) map.flyTo({ center: [point.lon, point.lat], zoom: Math.max(map.getZoom(), 11) });
  }
  $('[data-gps]').addEventListener('click', (e) => {
    const b = e.currentTarget;
    if (!navigator.geolocation) { status.textContent = 'This browser can\'t share your location. Tap the map instead.'; return; }
    const label = b.textContent;
    b.textContent = 'Finding you...';
    b.disabled = true;
    navigator.geolocation.getCurrentPosition((pos) => {
      b.textContent = label; b.disabled = false;
      setPoint(pos.coords.latitude, pos.coords.longitude, 'gps', true);
    }, (err) => {
      b.textContent = label; b.disabled = false;
      status.textContent = err.code === 1 ? 'Location is blocked. Allow it in your browser settings, or tap the map.' : 'Couldn\'t get a GPS fix. Try again in the open, or tap the map.';
    }, { enableHighAccuracy: true, timeout: 20000, maximumAge: 60000 });
  });
  // Place search: OpenStreetMap Nominatim, only when the button is pressed (their usage policy).
  const results = $('[data-place-results]');
  async function findPlace() {
    const t = $('#place').value.trim();
    if (t.length < 3) { status.textContent = 'Type a town, park or road first.'; return; }
    results.hidden = false;
    results.replaceChildren(h('li', { class: 'hint', text: 'Searching...' }));
    try {
      const res = await fetch('https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&q=' + encodeURIComponent(t), { headers: { 'accept-language': navigator.language || 'en' } });
      const list = await res.json();
      results.replaceChildren();
      if (!list.length) { results.append(h('li', { class: 'hint', text: 'Nothing found. Try a nearby town, or tap the map.' })); return; }
      for (const p of list) {
        results.append(h('li', {}, h('button', { type: 'button', class: 'linkish', text: p.display_name, onclick: () => {
          setPoint(+p.lat, +p.lon, 'place', true);
          results.hidden = true;
        } })));
      }
      results.append(h('li', { class: 'small muted', text: 'Search by OpenStreetMap Nominatim' }));
    } catch (e) {
      results.replaceChildren(h('li', { class: 'hint', text: 'Search isn\'t reachable right now. Tap the map or use your location.' }));
    }
  }
  $('[data-find]').addEventListener('click', findPlace);
  $('#place').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); findPlace(); } });

  // ---------- story counter ----------
  const count = $('[data-count]');
  const story = $('#story');
  const recount = () => { count.textContent = story.value.trim().length; };
  story.addEventListener('input', recount);

  // ---------- photos ----------
  const thumbs = $('[data-thumbs]');
  const fileIn = document.getElementById('photos');
  // Re-encode through a canvas: drops EXIF/GPS and every other bit of metadata, applies the camera's
  // rotation, shrinks to 2000 px, and always gives a plain JPEG (the only format the server accepts).
  async function reencode(file) {
    let src;
    try {
      src = await createImageBitmap(file, { imageOrientation: 'from-image' });
    } catch (e) {
      src = await new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = URL.createObjectURL(file);
      });
    }
    const w0 = src.width || src.naturalWidth, h0 = src.height || src.naturalHeight;
    const k = Math.min(1, MAX_SIDE / Math.max(w0, h0));
    const c = document.createElement('canvas');
    c.width = Math.round(w0 * k); c.height = Math.round(h0 * k);
    const g = c.getContext('2d');
    g.fillStyle = '#fff';
    g.fillRect(0, 0, c.width, c.height);
    g.drawImage(src, 0, 0, c.width, c.height);
    if (src.close) src.close();
    return new Promise((resolve, reject) => c.toBlob((b) => (b ? resolve(b) : reject(new Error('encode'))), 'image/jpeg', QUALITY));
  }
  fileIn.addEventListener('change', async () => {
    const files = [...fileIn.files];
    fileIn.value = '';
    clearErr('photos');
    for (const f of files) {
      if (photos.filter((p) => !p.removed).length >= MAX_PHOTOS) { showErr('photos', `Up to ${MAX_PHOTOS} photos.`); break; }
      if (f.size > 40 * 1024 * 1024) { showErr('photos', `${f.name} is too large.`); continue; }
      try {
        const blob = await reencode(f);
        photos.push({ blob, url: URL.createObjectURL(blob) });
      } catch (e) {
        showErr('photos', `Couldn't read ${f.name}. If it's a HEIC photo, choose "Most compatible" in your camera settings or send a screenshot of it.`);
      }
    }
    drawThumbs();
    savePhotos();
  });
  function drawThumbs() {
    thumbs.replaceChildren();
    photos.forEach((p, i) => {
      const rm = h('button', { type: 'button', class: 'thumb-x', 'aria-label': p.removed ? 'Keep this photo' : 'Remove this photo', text: p.removed ? 'Undo' : '×' });
      rm.addEventListener('click', () => {
        if (p.id) p.removed = !p.removed; // existing photo in edit mode: toggle
        else { URL.revokeObjectURL(p.url); photos.splice(i, 1); savePhotos(); }
        drawThumbs();
      });
      thumbs.append(h('li', { class: p.removed ? 'removed' : '' }, p.url ? h('img', { src: p.url, alt: `Photo ${i + 1}` }) : h('span', { class: 'ph-wait', text: 'Photo' }), rm));
    });
    $('[data-photo-add]').hidden = !!editId;
  }

  // ---------- videos ----------
  const vbox = $('[data-videos]');
  const VID = /^https?:\/\/((www\.|m\.)?youtube\.com\/(watch\?|shorts\/|live\/)|youtu\.be\/|(www\.)?tiktok\.com\/@[\w.]+\/video\/\d+|(vm|vt)\.tiktok\.com\/\w+|(www\.)?vimeo\.com\/\d+|player\.vimeo\.com\/video\/\d+)/i;
  function addVideo(val = '') {
    if (vbox.children.length >= 5) return;
    const i = h('input', { type: 'url', inputmode: 'url', placeholder: 'https://youtu.be/...', value: val, 'aria-label': 'Video link', class: 'vid-in' });
    i.addEventListener('change', () => {
      i.classList.toggle('bad', !!i.value.trim() && !VID.test(i.value.trim()));
      if (i.classList.contains('bad')) showErr('videos', 'That link isn\'t a YouTube, TikTok or Vimeo video.');
      else clearErr('videos');
    });
    vbox.append(i);
    $('[data-add-video]').hidden = vbox.children.length >= 5;
  }
  $('[data-add-video]').addEventListener('click', () => { addVideo(); vbox.lastChild.focus(); });
  addVideo();

  // ---------- errors ----------
  function showErr(k, text) {
    const el = form.querySelector(`[data-err="${k}"]`);
    if (el) { el.textContent = text; el.closest('fieldset')?.classList.add('has-err'); }
  }
  function clearErr(k) {
    const el = form.querySelector(`[data-err="${k}"]`);
    if (el) { el.textContent = ''; const fs = el.closest('fieldset'); if (fs && !fs.querySelector('.err:not(:empty)')) fs.classList.remove('has-err'); }
  }
  function clearErrs() { form.querySelectorAll('.err').forEach((e) => { e.textContent = ''; }); form.querySelectorAll('.has-err').forEach((f) => f.classList.remove('has-err')); }

  // ---------- collect ----------
  function collect() {
    const f = form;
    return {
      creature: f.creature.value || '', other_what: f.other_what.value, seen_date: f.seen_date.value, seen_time: f.seen_time.value,
      date_approx: f.date_approx.checked, lat: point ? point.lat : '', lon: point ? point.lon : '', loc_source: point ? point.source : 'map',
      place: f.place.value, story: f.story.value, duration: f.duration.value, witnesses: f.witnesses.value || 1,
      sounds: f.sounds.value, smells: f.smells.value, videos: [...vbox.querySelectorAll('input')].map((i) => i.value.trim()).filter(Boolean),
      anonymous: f.anonymous.checked, display_name: f.display_name.value, email: f.email.value.trim(), website: f.website.value,
    };
  }
  function fill(d) {
    restoring = true;
    const f = form;
    if (d.creature) { const r = f.querySelector(`input[name=creature][value="${CSS.escape(d.creature)}"]`); if (r) r.checked = true; }
    $('[data-other]').hidden = d.creature !== 'other';
    for (const k of ['other_what', 'seen_date', 'seen_time', 'place', 'story', 'duration', 'witnesses', 'sounds', 'smells', 'display_name', 'email']) {
      if (d[k] != null && f[k]) f[k].value = d[k];
    }
    f.date_approx.checked = !!d.date_approx;
    f.anonymous.checked = d.anonymous !== false;
    $('[data-name-field]').hidden = f.anonymous.checked;
    if (d.lat !== '' && d.lat != null) setPoint(+d.lat, +d.lon, d.loc_source || 'map', true);
    vbox.replaceChildren();
    (d.videos && d.videos.length ? d.videos : ['']).forEach((v) => addVideo(v));
    recount();
    restoring = false;
  }

  // ---------- draft (this device only) ----------
  const draftStatus = $('[data-draft-status]');
  let saveTimer;
  function save() {
    if (restoring || editId) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      const d = collect();
      delete d.website;
      store.set(DRAFT, JSON.stringify({ ...d, savedAt: Date.now() }));
      draftStatus.textContent = `Draft saved on this device at ${new Date().toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}.`;
    }, 500);
  }
  form.addEventListener('input', save);
  form.addEventListener('change', save);

  // Photos in IndexedDB so a half-finished report survives closing the tab (or losing signal).
  function idb() {
    return new Promise((resolve, reject) => {
      const r = indexedDB.open('ea-report', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('photos');
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => reject(r.error);
    });
  }
  async function savePhotos() {
    if (editId) return;
    try {
      const db = await idb();
      const tx = db.transaction('photos', 'readwrite');
      tx.objectStore('photos').put(photos.filter((p) => p.blob).map((p) => p.blob), 'draft');
    } catch (e) { /* storage blocked: photos just won't be kept */ }
  }
  async function loadPhotos() {
    try {
      const db = await idb();
      const blobs = await new Promise((resolve) => {
        const r = db.transaction('photos').objectStore('photos').get('draft');
        r.onsuccess = () => resolve(r.result || []);
        r.onerror = () => resolve([]);
      });
      photos = blobs.slice(0, MAX_PHOTOS).map((blob) => ({ blob, url: URL.createObjectURL(blob) }));
      drawThumbs();
    } catch (e) { /* none */ }
  }
  async function clearDraft() {
    store.del(DRAFT);
    try { const db = await idb(); db.transaction('photos', 'readwrite').objectStore('photos').delete('draft'); } catch (e) { /* none */ }
  }
  $('[data-draft-clear]').addEventListener('click', async () => {
    await clearDraft();
    location.reload();
  });

  // ---------- submit ----------
  const msg = $('[data-form-msg]');
  const submitBtn = $('[data-submit]');
  const tsSlot = $('[data-ts]');
  if (!editId) EA.human(tsSlot).catch(() => { msg.textContent = 'The spam check didn\'t load. You can keep writing; your draft is saved. Reload when you have signal.'; });

  function check(d) {
    clearErrs();
    const bad = {};
    if (!d.creature) bad.creature = 'Pick what you saw, or "Something else".';
    if (d.creature === 'other' && d.other_what.trim().length < 2) bad.other_what = 'Say what it was, in a few words.';
    if (!d.seen_date) bad.seen_date = 'Enter the date it happened.';
    if (d.lat === '') bad.location = 'Set where it happened: use your location, tap the map, or search a place.';
    if (d.story.trim().length < 30) bad.story = 'Tell us what happened in a few sentences.';
    if (d.videos.some((v) => !VID.test(v))) bad.videos = 'Only YouTube, TikTok or Vimeo links.';
    if (d.email && !/^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i.test(d.email)) bad.email = 'Check your email address.';
    return bad;
  }
  function showBad(bad) {
    for (const [k, v] of Object.entries(bad)) showErr(k, v);
    const first = form.querySelector('.has-err');
    if (first) first.scrollIntoView({ behavior: 'smooth', block: 'start' });
    msg.textContent = 'Check the highlighted parts.';
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const d = collect();
    const bad = check(d);
    if (Object.keys(bad).length) { showBad(bad); return; }
    submitBtn.disabled = true;
    let r;
    if (editId) {
      msg.textContent = 'Saving...';
      r = await api('/api/reports/' + editId, { method: 'PATCH', body: { ...d, remove_photos: photos.filter((p) => p.id && p.removed).map((p) => p.id) } });
    } else {
      msg.textContent = 'Quick spam check...';
      try { d.turnstile = await EA.human(tsSlot); } catch (err) { msg.textContent = 'The spam check didn\'t load. Your draft is saved; try again when you have signal.'; submitBtn.disabled = false; return; }
      if (EA.session()) delete d.email;
      const fd = new FormData();
      fd.append('data', JSON.stringify(d));
      photos.forEach((p, i) => fd.append('photo', p.blob, `photo${i + 1}.jpg`));
      msg.textContent = photos.length ? `Sending your report and ${photos.length} photo${photos.length > 1 ? 's' : ''}...` : 'Sending your report...';
      r = await api('/api/reports', { method: 'POST', form: fd });
      EA.resetHuman(tsSlot);
    }
    submitBtn.disabled = false;
    if (r.status === 200 || r.status === 201) return done(r.data, d);
    if (r.status === 400 && r.data.fields) { showBad(r.data.fields); return; }
    msg.textContent = {
      offline: 'No signal right now. Your report is saved on this device. Press Send again when you\'re back in range.',
      slow: 'Too many reports from this connection. Your draft is saved; try again in an hour.',
      turnstile: 'The spam check failed. Press Send again.',
      too_big: 'The photos are too large together. Remove one and try again.',
      signin: 'Your sign-in expired. Sign in again to save changes.',
    }[r.data.state] || 'Something went wrong on our side. Your draft is saved; try again in a few minutes.';
  });

  async function done(data, d) {
    if (!editId) await clearDraft();
    form.hidden = true;
    const box = document.querySelector('[data-done]');
    const m = box.querySelector('[data-done-msg]');
    if (editId) {
      box.querySelector('h2').textContent = 'Changes saved.';
      m.textContent = 'A moderator will check the changes, then the report goes back on the map.';
    } else if (EA.session()) {
      m.replaceChildren('A moderator will read it soon. Once approved it appears on the map. ', h('a', { href: EA.page('?id=' + data.id), text: 'Follow your report' }), '.');
    } else if (d.email) {
      m.textContent = `A moderator will read it soon. We've emailed ${d.email} a link to follow and edit it.`;
      if (data.dev_link) m.append(' ', h('a', { href: data.dev_link, text: '(dev: open link)' }));
    } else {
      m.textContent = 'A moderator will read it soon. Once it\'s approved it appears on the map and people can vote on it.';
    }
    box.hidden = false;
    box.focus();
    box.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ---------- start: edit mode, or restore a draft ----------
  async function startEdit() {
    document.getElementById('rf-title').textContent = 'Edit your report';
    const banner = $('[data-edit-banner]');
    banner.hidden = false;
    if (!EA.session()) {
      banner.replaceChildren('Sign in to edit your report.');
      form.querySelectorAll('fieldset, .send').forEach((x) => { x.hidden = true; });
      form.append(EA.signinBox({ title: 'Sign in to edit', returnTo: location.href }));
      return;
    }
    const r = await api('/api/reports/' + encodeURIComponent(editId));
    if (r.status !== 200 || !r.data.report.owner) {
      banner.textContent = 'We couldn\'t find that report in your account.';
      form.querySelectorAll('fieldset, .send').forEach((x) => { x.hidden = true; });
      return;
    }
    const R = r.data.report;
    banner.textContent = 'Saving changes sends the report back to a moderator before it shows again.';
    fill({ ...R, lat: R.exact.lat, lon: R.exact.lon, videos: R.videos.map((v) => v.url), anonymous: R.anonymous, display_name: R.display_name });
    photos = R.photos.map((p) => ({ id: p.id, url: p.url ? EA.API + p.url : null }));
    drawThumbs();
    tsSlot.hidden = true;
    submitBtn.textContent = 'Save changes';
    const wd = h('button', { type: 'button', class: 'linkish danger', text: 'Withdraw this report' });
    wd.addEventListener('click', async () => {
      if (!confirm('Withdraw this report? It will be removed from the site and its photos deleted.')) return;
      const x = await api('/api/reports/' + editId, { method: 'DELETE' });
      if (x.status === 200) location.href = EA.page('?me=1');
      else msg.textContent = 'That didn\'t work. Try again.';
    });
    $('.send').append(wd);
  }

  if (editId) startEdit();
  else {
    let d = null;
    try { d = JSON.parse(store.get(DRAFT) || 'null'); } catch (e) { d = null; }
    if (d && (d.story || d.creature || d.lat !== '')) {
      fill(d);
      $('[data-draft-banner]').hidden = false;
    }
    // Arriving from a creature page (?creature=bigfoot): preselect it unless a draft already chose one.
    const pre = new URLSearchParams(location.search).get('creature');
    const r = pre && !(d && d.creature) && form.querySelector(`input[name=creature][value="${CSS.escape(pre)}"]`);
    if (r) { r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); }
    loadPhotos();
  }
})();
