// /journal/: field journal. Entries live on this device only (IndexedDB, or localStorage if IndexedDB is missing or
// blocked) and are never sent to us. Outside calls, only when needed: Open-Meteo for weather (coordinates rounded to
// 0.01 deg, about 1 km) and, for a typed place that isn't in our town list, Open-Meteo's place search (just the name).
// The moon phase is a small client-side calculation. Export CSV / JSON, import JSON, and hand an entry to /report/.
(function () {
  const form = document.getElementById('jn-form');
  if (!form) return;
  const $ = (id) => document.getElementById(id);
  let CFG = {};
  try { CFG = JSON.parse($('jn-config').textContent); } catch (e) { CFG = {}; }
  const track = (name, p) => { try { if (window.gtag) window.gtag('event', name, { page_type: 'journal', ...p }); } catch (e) { /* no analytics */ } };
  const round2 = (x) => Math.round(x * 100) / 100;
  const pad = (n) => String(n).padStart(2, '0');
  const localNow = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const uid = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));
  const devTz = (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) { return ''; } })();

  // ---------- storage: IndexedDB with a localStorage fallback ----------
  const DB = 'ea-journal', ST = 'entries', LS = 'ea-journal-entries';
  let dbp = null;
  function idb() {
    if (dbp) return dbp;
    dbp = new Promise((res) => {
      try {
        if (!window.indexedDB) return res(null);
        const r = indexedDB.open(DB, 1);
        r.onupgradeneeded = () => r.result.createObjectStore(ST, { keyPath: 'id' });
        r.onsuccess = () => res(r.result);
        r.onerror = () => res(null);
        r.onblocked = () => res(null);
      } catch (e) { res(null); }
    });
    return dbp;
  }
  const lsAll = () => { try { return JSON.parse(localStorage.getItem(LS) || '[]'); } catch (e) { return []; } };
  const lsPut = (list) => { localStorage.setItem(LS, JSON.stringify(list)); };
  function tx(db, mode, fn) {
    return new Promise((res, rej) => {
      const t = db.transaction(ST, mode), s = t.objectStore(ST), out = fn(s);
      t.oncomplete = () => res(out && out.result);
      t.onerror = () => rej(t.error);
      t.onabort = () => rej(t.error);
    });
  }
  const store = {
    async all() { const db = await idb(); return db ? (await tx(db, 'readonly', (s) => s.getAll())) || [] : lsAll(); },
    async put(e) {
      const db = await idb();
      if (db) return tx(db, 'readwrite', (s) => s.put(e));
      const l = lsAll().filter((x) => x.id !== e.id); l.push(e); lsPut(l);
    },
    async del(id) {
      const db = await idb();
      if (db) return tx(db, 'readwrite', (s) => s.delete(id));
      lsPut(lsAll().filter((x) => x.id !== id));
    },
  };
  let entries = [];
  const load = async () => { entries = await store.all(); entries.sort((a, b) => (b.when || '').localeCompare(a.when || '')); };

  // ---------- moon phase (mean synodic month from a known new moon; good to within about half a day) ----------
  const SYN = 29.530588853, NEW0 = Date.UTC(2000, 0, 6, 18, 14) / 86400000;
  const PHASES = ['New moon', 'Waxing crescent', 'First quarter', 'Waxing gibbous', 'Full moon', 'Waning gibbous', 'Last quarter', 'Waning crescent'];
  function moon(when) {
    const t = new Date(when).getTime();
    if (!Number.isFinite(t)) return null;
    let age = ((t / 86400000 - NEW0) % SYN + SYN) % SYN;
    const illum = Math.round((1 - Math.cos(2 * Math.PI * age / SYN)) / 2 * 100);
    return { phase: PHASES[Math.floor((age / SYN) * 8 + 0.5) % 8], illum, age: Math.round(age * 10) / 10 };
  }
  const moonText = (m) => m ? `${m.phase}, ${m.illum}% lit` : '';

  // ---------- weather (Open-Meteo, free and keyless) ----------
  const WMO = { 0: 'Clear', 1: 'Mostly clear', 2: 'Partly cloudy', 3: 'Overcast', 45: 'Fog', 48: 'Freezing fog', 51: 'Light drizzle', 53: 'Drizzle',
    55: 'Heavy drizzle', 56: 'Freezing drizzle', 57: 'Freezing drizzle', 61: 'Light rain', 63: 'Rain', 65: 'Heavy rain', 66: 'Freezing rain',
    67: 'Freezing rain', 71: 'Light snow', 73: 'Snow', 75: 'Heavy snow', 77: 'Snow grains', 80: 'Rain showers', 81: 'Rain showers',
    82: 'Heavy showers', 85: 'Snow showers', 86: 'Heavy snow showers', 95: 'Thunderstorm', 96: 'Thunderstorm with hail', 99: 'Thunderstorm with hail' };
  async function weather(lat, lon, when) {
    const date = when.slice(0, 10);
    let hh = +when.slice(11, 13), mm = +when.slice(14, 16);
    if (mm >= 30 && hh < 23) hh += 1;
    const days = (Date.now() - new Date(date + 'T12:00').getTime()) / 86400000;
    if (days < -15) return { none: 'That date is too far ahead for a forecast.' };
    if (new Date(date).getFullYear() < 1940) return { none: 'No weather records go back that far.' };
    const host = days > 80 ? 'https://archive-api.open-meteo.com/v1/archive' : 'https://api.open-meteo.com/v1/forecast';
    const q = new URLSearchParams({ latitude: round2(lat), longitude: round2(lon), start_date: date, end_date: date, timezone: 'auto',
      hourly: 'temperature_2m,relative_humidity_2m,cloud_cover,precipitation,wind_speed_10m,weather_code', wind_speed_unit: 'kmh' });
    const r = await fetch(`${host}?${q}`);
    if (!r.ok) throw new Error('weather ' + r.status);
    const j = await r.json(), H = j.hourly || {};
    const i = (H.time || []).indexOf(`${date}T${pad(hh)}:00`);
    if (i < 0 || H.temperature_2m[i] == null) return { none: 'No weather on record for that hour yet. Try again in a few days.' };
    return { temp: H.temperature_2m[i], rh: H.relative_humidity_2m[i], cloud: H.cloud_cover[i], precip: H.precipitation[i], wind: H.wind_speed_10m[i],
      code: H.weather_code[i], tz: j.timezone || '', src: 'Open-Meteo' };
  }
  let imperial = localStorage.getItem('ea-journal-units') === 'us';
  const tempTxt = (c) => imperial ? `${Math.round(c * 9 / 5 + 32)}°F` : `${Math.round(c)}°C`;
  const windTxt = (k) => imperial ? `wind ${Math.round(k / 1.609)} mph` : `wind ${Math.round(k)} km/h`;
  const rainTxt = (mmv) => mmv > 0 ? (imperial ? `${(mmv / 25.4).toFixed(2)} in rain` : `${mmv} mm rain`) : 'no rain';
  const wxText = (w) => !w || w.none ? '' : `${WMO[w.code] || 'Weather'}, ${tempTxt(w.temp)}, ${w.cloud}% cloud, ${windTxt(w.wind)}, ${rainTxt(w.precip)}`;

  // ---------- place: our town list first, then Open-Meteo's place search ----------
  let cities = null;
  const fold = (t) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const loadCities = () => cities || (cities = fetch(CFG.cities).then((r) => r.json()).catch(() => []));
  const placeIn = $('jn-place');
  placeIn.addEventListener('focus', loadCities, { once: true });
  placeIn.addEventListener('input', async () => {
    pt = null;
    const q = fold(placeIn.value.trim());
    if (q.length < 2) return;
    const list = await loadCities(), hits = [];
    for (const c of list) { if (fold(c[0]).startsWith(q)) { hits.push(c); if (hits.length >= 10) break; } }
    $('jn-cities').replaceChildren(...hits.map((c) => { const o = document.createElement('option'); o.value = c[0] + ', ' + c[1]; return o; }));
  });
  async function geocode(text) {
    const v = fold(text.trim());
    if (!v) return null;
    const list = await loadCities();
    const [name, reg] = v.split(',').map((s) => s.trim());
    const c = list.find((x) => fold(x[0]) === name && (!reg || fold(x[1]).startsWith(reg))) || list.find((x) => fold(x[0]) === name);
    if (c) return { lat: round2(c[2]), lon: round2(c[3]), src: 'town' };
    if (!navigator.onLine) return null;
    try {
      const r = await fetch('https://geocoding-api.open-meteo.com/v1/search?' + new URLSearchParams({ name: text.split(',')[0].trim().slice(0, 80), count: 1, language: 'en' }));
      const g = (await r.json()).results;
      if (g && g[0]) return { lat: round2(g[0].latitude), lon: round2(g[0].longitude), src: 'search' };
    } catch (e) { /* offline or blocked */ }
    return null;
  }

  // ---------- form ----------
  const whenIn = $('jn-when'), locMsg = $('jn-loc'), wxEl = $('jn-wx'), moonEl = $('jn-moon'), wxBtn = $('jn-wx-btn'), msg = $('jn-msg');
  let pt = null, wx = null, editing = null, wxSeq = 0, wxTimer;
  whenIn.value = localNow();
  const showMoon = () => { const m = moon(whenIn.value); moonEl.textContent = m ? 'Moon: ' + moonText(m) : ''; };
  showMoon();

  $('jn-locate').addEventListener('click', () => {
    if (!navigator.geolocation) { locMsg.textContent = 'This browser can\'t share your location. Type a place instead.'; return; }
    locMsg.textContent = 'Finding you...';
    navigator.geolocation.getCurrentPosition((p) => {
      pt = { lat: round2(p.coords.latitude), lon: round2(p.coords.longitude), src: 'gps' };
      if (!placeIn.value.trim()) placeIn.value = `Near ${pt.lat}, ${pt.lon}`;
      locMsg.textContent = `Got it: ${pt.lat}, ${pt.lon} (rounded to about 1 km).`;
      track('journal_locate', {});
      queueWx(0);
    }, (err) => {
      locMsg.textContent = err && err.code === 1 ? 'Location is blocked. Allow it in your browser settings, or type a place.' : 'Couldn\'t find your location. Type a place instead.';
    }, { timeout: 12000, maximumAge: 300000 });
  });

  async function fetchWx() {
    const seq = ++wxSeq;
    wxBtn.hidden = true;
    if (!whenIn.value) return;
    if (!pt && placeIn.value.trim()) {
      pt = await geocode(placeIn.value);
      if (seq !== wxSeq) return;
      if (pt) locMsg.textContent = pt.src === 'town' ? `Using ${placeIn.value.trim()} for the weather.` : `Found that place (about ${pt.lat}, ${pt.lon}) for the weather.`;
    }
    if (!pt) { wx = null; wxEl.textContent = placeIn.value.trim() ? 'Couldn\'t place that for the weather. Try a nearby town, or use your location.' : 'Weather fills in here once there\'s a place and a time, if you have a signal.'; return; }
    if (!navigator.onLine) { wx = null; wxEl.textContent = 'No signal right now. Save anyway and the weather fills in next time you open the journal online.'; return; }
    wxEl.textContent = 'Getting the weather...';
    try {
      const w = await weather(pt.lat, pt.lon, whenIn.value);
      if (seq !== wxSeq) return;
      wx = w.none ? null : w;
      wxEl.textContent = w.none || 'Weather: ' + wxText(w);
    } catch (e) {
      if (seq !== wxSeq) return;
      wx = null; wxEl.textContent = 'Couldn\'t get the weather just now.'; wxBtn.hidden = false;
    }
  }
  const queueWx = (ms = 700) => { clearTimeout(wxTimer); wxTimer = setTimeout(fetchWx, ms); };
  whenIn.addEventListener('change', () => { showMoon(); wx = null; queueWx(); });
  placeIn.addEventListener('change', () => { pt = null; wx = null; queueWx(); });
  wxBtn.addEventListener('click', () => fetchWx());

  function resetForm() {
    form.reset();
    editing = null; pt = null; wx = null; wxSeq++;
    whenIn.value = localNow();
    $('jn-editing').hidden = true;
    $('jn-save').textContent = 'Save to my journal';
    wxEl.textContent = 'Weather fills in here once there\'s a place and a time, if you have a signal.';
    wxBtn.hidden = true;
    locMsg.textContent = 'Type a place, or use your location (rounded to about 1 km) so the journal can look up the weather.';
    showMoon();
  }
  $('jn-cancel').addEventListener('click', resetForm);

  const num = (v, lo, hi) => { const n = parseFloat(v); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : null; };
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if (!whenIn.value) { msg.textContent = 'Add the date and time you went out.'; whenIn.focus(); return; }
    const f = form.elements;
    const old = editing && entries.find((x) => x.id === editing);
    const placeChanged = old && (old.place || '') !== placeIn.value.trim();
    const e = {
      id: editing || uid(), when: whenIn.value, tz: (wx && wx.tz) || (old && !placeChanged && old.tz) || devTz,
      place: placeIn.value.trim().slice(0, 120),
      lat: pt ? pt.lat : (old && !placeChanged ? old.lat : null), lon: pt ? pt.lon : (old && !placeChanged ? old.lon : null),
      hours: num(f.hours.value, 0, 72), with: Math.round(num(f.with.value, 0, 99) || 0),
      looking: f.looking.value || 'out', happened: f.happened.value || 'nothing', cond: +f.cond.value || null,
      notes: f.notes.value.slice(0, 4000), moon: moon(whenIn.value),
      wx: wx || (old && !placeChanged && old.when === whenIn.value ? old.wx : null),
      created: old ? old.created : Date.now(), updated: Date.now(),
    };
    try {
      await store.put(e);
      track(editing ? 'journal_edit' : 'journal_save', { happened: e.happened, looking: e.looking, weather: e.wx ? 'yes' : 'no' });
      const was = !!editing;
      resetForm();
      await render();
      msg.textContent = was ? 'Entry updated.' : 'Saved. It\'s in your journal below.';
    } catch (err) {
      msg.textContent = 'Couldn\'t save on this device. Private browsing can block storage.';
    }
  });

  function startEdit(e) {
    editing = e.id;
    whenIn.value = e.when;
    placeIn.value = e.place || '';
    pt = e.lat != null ? { lat: e.lat, lon: e.lon, src: 'saved' } : null;
    wx = e.wx || null;
    const f = form.elements;
    f.hours.value = e.hours ?? '';
    f.with.value = e.with ?? 0;
    for (const [n, v] of [['looking', e.looking], ['happened', e.happened], ['cond', String(e.cond || 3)]]) {
      const r = form.querySelector(`input[name=${n}][value="${CSS.escape(String(v))}"]`); if (r) r.checked = true;
    }
    f.notes.value = e.notes || '';
    showMoon();
    wxEl.textContent = e.wx ? 'Weather: ' + wxText(e.wx) : 'No weather saved for this one yet.';
    $('jn-editing').hidden = false;
    $('jn-save').textContent = 'Save changes';
    msg.textContent = '';
    form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setTimeout(() => whenIn.focus({ preventScroll: true }), 400);
  }

  // ---------- list and stats ----------
  const LOOK = { ufo: 'UFOs', creature: 'A creature', out: 'Just out there' };
  const HAP = { nothing: 'Nothing', heard: 'Heard something', saw: 'Saw something' };
  const LOOKING_FOR = { ufo: 'looking for UFOs', creature: 'looking for a creature', out: 'just out there' };
  const COND = ['', 'Rough', 'Poor', 'OK', 'Good', 'Perfect'];
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const fmtWhen = (w) => {
    const d = new Date(w);
    if (!Number.isFinite(d.getTime())) return w;
    return d.toLocaleString(undefined, { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  };
  const hoursTxt = (h) => h == null ? '' : (h === 1 ? '1 hour' : `${+h.toFixed(2)} hours`);

  async function render() {
    await load();
    const ol = $('jn-entries');
    ol.replaceChildren(...entries.map((e) => {
      const li = el('li', 'jn-entry jn-h-' + e.happened);
      const top = el('div', 'jn-e-top');
      top.append(el('b', 'jn-e-when', fmtWhen(e.when)), el('span', 'jn-tag jn-tag-' + e.happened, HAP[e.happened] || ''));
      li.append(top);
      const meta = [e.place, hoursTxt(e.hours), e.with ? `with ${e.with} other${e.with === 1 ? '' : 's'}` : 'on my own', LOOKING_FOR[e.looking]]
        .filter(Boolean).join(' · ');
      li.append(el('p', 'jn-e-meta', meta));
      const sky = [e.wx ? wxText(e.wx) : '', e.moon ? moonText(e.moon) : '', e.cond ? `Conditions ${e.cond}/5 (${COND[e.cond]})` : ''].filter(Boolean).join(' · ');
      if (sky) li.append(el('p', 'jn-e-sky', sky));
      if (e.notes) li.append(el('p', 'jn-e-notes', e.notes));
      const act = el('div', 'jn-e-act');
      const b = (t, fn, cls = '') => { const x = el('button', 'jn-act ' + cls, t); x.type = 'button'; x.addEventListener('click', fn); act.append(x); return x; };
      b('Edit', () => startEdit(e));
      b('Delete', async () => {
        if (!confirm('Delete this entry? This can\'t be undone.')) return;
        await store.del(e.id); track('journal_delete', {}); await render(); $('jn-list-msg').textContent = 'Entry deleted.';
      }, 'jn-del');
      if (e.happened !== 'nothing') b('Turn this into a report', () => toReport(e), 'jn-rep');
      li.append(act);
      return li;
    }));
    $('jn-empty').hidden = entries.length > 0;
    const days = new Set(entries.map((e) => (e.when || '').slice(0, 10)));
    const s = { nights: days.size, hours: +entries.reduce((a, e) => a + (e.hours || 0), 0).toFixed(1),
      heard: entries.filter((e) => e.happened === 'heard').length, saw: entries.filter((e) => e.happened === 'saw').length };
    for (const k in s) document.querySelector(`#jn-stats [data-s=${k}]`).textContent = s[k].toLocaleString();
  }

  // Fill in weather for entries saved offline, a few at a time, once there's a signal.
  async function backfill() {
    if (!navigator.onLine) return;
    const todo = entries.filter((e) => !e.wx && e.lat != null && !e.wxTried && new Date(e.when).getTime() < Date.now() - 3600000).slice(0, 5);
    let changed = false;
    for (const e of todo) {
      try {
        const w = await weather(e.lat, e.lon, e.when);
        if (w.none) { e.wxTried = Date.now(); } else { e.wx = w; e.tz = w.tz || e.tz; changed = true; }
        await store.put(e);
      } catch (err) { break; }
    }
    if (changed) await render();
  }
  window.addEventListener('online', backfill);

  // ---------- units ----------
  const unitsBtn = $('jn-units');
  const setUnits = () => { unitsBtn.setAttribute('aria-pressed', String(imperial)); unitsBtn.textContent = imperial ? 'Show °C and km/h' : 'Show °F and mph'; };
  setUnits();
  unitsBtn.addEventListener('click', () => {
    imperial = !imperial;
    try { localStorage.setItem('ea-journal-units', imperial ? 'us' : 'metric'); } catch (e) { /* storage off */ }
    setUnits(); render(); if (wx) wxEl.textContent = 'Weather: ' + wxText(wx);
    track('journal_units', { value: imperial ? 'us' : 'metric' });
  });

  // ---------- export / import ----------
  const stamp = () => new Date().toISOString().slice(0, 10);
  function download(name, text, type) {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = el('a'); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }
  const csvCell = (v) => {
    let s = v == null ? '' : String(v);
    if (typeof v === 'string' && /^[=+\-@\t\r]/.test(s)) s = "'" + s;   // keep spreadsheets from treating notes as formulas
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  $('jn-csv').addEventListener('click', () => {
    if (!entries.length) { $('jn-list-msg').textContent = 'Nothing to export yet.'; return; }
    const cols = ['date_time', 'time_zone', 'place', 'lat', 'lon', 'hours', 'people_with_you', 'looking_for', 'what_happened', 'conditions_1_to_5',
      'notes', 'weather', 'temp_c', 'cloud_pct', 'wind_kmh', 'precip_mm', 'humidity_pct', 'moon_phase', 'moon_lit_pct'];
    const rows = entries.map((e) => [e.when, e.tz, e.place, e.lat, e.lon, e.hours, e.with, LOOK[e.looking], HAP[e.happened], e.cond, e.notes,
      e.wx ? WMO[e.wx.code] : '', e.wx && e.wx.temp, e.wx && e.wx.cloud, e.wx && e.wx.wind, e.wx && e.wx.precip, e.wx && e.wx.rh,
      e.moon && e.moon.phase, e.moon && e.moon.illum].map(csvCell).join(','));
    download(`field-journal-${stamp()}.csv`, '﻿' + [cols.join(','), ...rows].join('\r\n'), 'text/csv;charset=utf-8');
    track('journal_export', { format: 'csv' });
  });
  $('jn-json').addEventListener('click', () => {
    if (!entries.length) { $('jn-list-msg').textContent = 'Nothing to export yet.'; return; }
    download(`field-journal-${stamp()}.json`, JSON.stringify({ app: 'encounteratlas-field-journal', version: 1, exported: new Date().toISOString(), entries }, null, 1), 'application/json');
    track('journal_export', { format: 'json' });
  });

  const str = (v, n) => typeof v === 'string' ? v.slice(0, n) : '';
  const fin = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
  function clean(x) {
    if (!x || typeof x !== 'object' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(x.when || '')) return null;
    const lat = fin(x.lat), lon = fin(x.lon);
    const w = x.wx && typeof x.wx === 'object' && fin(x.wx.temp) != null ? { temp: fin(x.wx.temp), rh: fin(x.wx.rh), cloud: fin(x.wx.cloud), precip: fin(x.wx.precip),
      wind: fin(x.wx.wind), code: fin(x.wx.code), tz: str(x.wx.tz, 60), src: 'Open-Meteo' } : null;
    return {
      id: str(x.id, 64) || uid(), when: x.when.slice(0, 16), tz: str(x.tz, 60), place: str(x.place, 120),
      lat: lat != null && Math.abs(lat) <= 90 ? round2(lat) : null, lon: lon != null && Math.abs(lon) <= 180 ? round2(lon) : null,
      hours: fin(x.hours) != null ? Math.min(72, Math.max(0, x.hours)) : null, with: Math.min(99, Math.max(0, Math.round(fin(x.with) || 0))),
      looking: LOOK[x.looking] ? x.looking : 'out', happened: HAP[x.happened] ? x.happened : 'nothing',
      cond: [1, 2, 3, 4, 5].includes(x.cond) ? x.cond : null, notes: str(x.notes, 4000), moon: moon(x.when.slice(0, 16)), wx: w,
      created: fin(x.created) || Date.now(), updated: fin(x.updated) || Date.now(),
    };
  }
  $('jn-file').addEventListener('change', async (ev) => {
    const file = ev.target.files && ev.target.files[0];
    ev.target.value = '';
    const out = $('jn-list-msg');
    if (!file) return;
    if (file.size > 5e6) { out.textContent = 'That file is too big to be a journal export.'; return; }
    let data;
    try { data = JSON.parse(await file.text()); } catch (e) { out.textContent = 'That isn\'t a JSON file this journal can read.'; return; }
    const list = Array.isArray(data) ? data : (data && Array.isArray(data.entries) ? data.entries : null);
    if (!list) { out.textContent = 'No journal entries in that file.'; return; }
    const have = new Map(entries.map((e) => [e.id, e]));
    let added = 0, updated = 0, skipped = 0;
    for (const raw of list.slice(0, 5000)) {
      const e = clean(raw);
      if (!e) { skipped++; continue; }
      const cur = have.get(e.id);
      if (cur && (cur.updated || 0) >= e.updated) { skipped++; continue; }
      await store.put(e);
      cur ? updated++ : added++;
    }
    await render();
    out.textContent = `Imported ${added} new ${added === 1 ? 'entry' : 'entries'}${updated ? `, updated ${updated}` : ''}${skipped ? `, skipped ${skipped} (already here or unreadable)` : ''}.`;
    track('journal_import', { count: added + updated });
  });

  // ---------- hand an entry to the report form ----------
  // /report/ reads ?at=lat,lon (opens its map there, no pin) and ?place=. The other params (date, time, duration,
  // witnesses, story) are ignored by report.js for now; they're sent so the form can pick them up later. The notes are
  // also copied to the clipboard so they can be pasted into "What happened?".
  async function toReport(e) {
    const q = new URLSearchParams();
    if (e.lat != null) q.set('at', `${e.lat},${e.lon}`);
    if (e.place) q.set('place', e.place);
    q.set('date', e.when.slice(0, 10));
    q.set('time', e.when.slice(11, 16));
    if (e.hours) q.set('duration', `I was out about ${hoursTxt(e.hours)}`);
    q.set('witnesses', String(1 + (e.with || 0)));
    if (e.notes) q.set('story', e.notes.slice(0, 1500));
    q.set('from', 'journal');
    let copied = false;
    if (e.notes && navigator.clipboard) { try { await navigator.clipboard.writeText(e.notes); copied = true; } catch (err) { copied = false; } }
    track('journal_to_report', { happened: e.happened });
    if (copied) {
      $('jn-list-msg').textContent = 'Your notes are copied. Paste them into "What happened?" on the report form.';
      setTimeout(() => { location.href = CFG.report + '?' + q; }, 900);
    } else location.href = CFG.report + '?' + q;
  }

  render().then(backfill).catch(() => { $('jn-list-msg').textContent = 'Couldn\'t open the journal on this device. Private browsing can block storage.'; });
})();
