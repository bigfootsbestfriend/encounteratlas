// Shared place lookup for road trip mode and the journal: "Jasper, Alberta", "Jasper AB", "Banff, AB, Canada",
// "Perth, WA", "Inverness, Scotland" all land in the right place. Order: our own town list (/data/cities.json,
// biggest first), then Open-Meteo's free place search. A province, state or country typed after the name must match;
// with none typed, the town nearest the other end of the trip wins (Edmonton to "Jasper" is Jasper, Alberta), else
// the biggest. window.EAPlace = { find, suggest }.
(function () {
  const fold = (t) => String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[.']/g, '').replace(/\s+/g, ' ').trim();
  const round2 = (x) => Math.round(x * 100) / 100;
  const US = { AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California', CO: 'Colorado', CT: 'Connecticut', DE: 'Delaware',
    DC: 'District of Columbia', FL: 'Florida', GA: 'Georgia', HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa', KS: 'Kansas',
    KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland', MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi',
    MO: 'Missouri', MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey', NM: 'New Mexico', NY: 'New York',
    NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio', OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island',
    SC: 'South Carolina', SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont', VA: 'Virginia', WA: 'Washington',
    WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming', PR: 'Puerto Rico' };
  const CAN = { AB: 'Alberta', BC: 'British Columbia', MB: 'Manitoba', NB: 'New Brunswick', NL: 'Newfoundland and Labrador', NS: 'Nova Scotia',
    NT: 'Northwest Territories', NU: 'Nunavut', ON: 'Ontario', PE: 'Prince Edward Island', PEI: 'Prince Edward Island', QC: 'Quebec', PQ: 'Quebec',
    SK: 'Saskatchewan', YT: 'Yukon', NWT: 'Northwest Territories', NFLD: 'Newfoundland and Labrador', Newfoundland: 'Newfoundland and Labrador' };
  const AUS = { NSW: 'New South Wales', VIC: 'Victoria', QLD: 'Queensland', SA: 'South Australia', TAS: 'Tasmania', ACT: 'Australian Capital Territory',
    NT: 'Northern Territory', WA: 'Western Australia' };
  // what each typed word can mean: full region names (with their country) and country names/codes
  const REG = new Map(), add = (k, v) => { k = fold(k); if (!REG.has(k)) REG.set(k, []); REG.get(k).push(v); };
  for (const [tbl, country, cc] of [[US, 'United States', 'US'], [CAN, 'Canada', 'CA'], [AUS, 'Australia', 'AU']]) {
    for (const [ab, full] of Object.entries(tbl)) { add(ab, { admin1: full, cc }); add(full, { admin1: full, cc }); }
    add(country, { cc });
  }
  for (const n of ['England', 'Scotland', 'Wales', 'Northern Ireland']) add(n, { admin1: n, cc: 'GB' });
  for (const [k, cc] of [['us', 'US'], ['usa', 'US'], ['america', 'US'], ['united states of america', 'US'], ['uk', 'GB'], ['gb', 'GB'],
    ['united kingdom', 'GB'], ['britain', 'GB'], ['great britain', 'GB'], ['nz', 'NZ'], ['new zealand', 'NZ'], ['ireland', 'IE'], ['eire', 'IE'],
    ['mexico', 'MX'], ['france', 'FR'], ['germany', 'DE'], ['spain', 'ES'], ['italy', 'IT'], ['japan', 'JP'], ['india', 'IN'], ['brazil', 'BR'],
    ['south africa', 'ZA'], ['netherlands', 'NL'], ['holland', 'NL'], ['norway', 'NO'], ['sweden', 'SE'], ['finland', 'FI'], ['denmark', 'DK'],
    ['iceland', 'IS'], ['belgium', 'BE'], ['switzerland', 'CH'], ['austria', 'AT'], ['poland', 'PL'], ['portugal', 'PT'], ['greece', 'GR'],
    ['russia', 'RU'], ['china', 'CN'], ['philippines', 'PH'], ['argentina', 'AR'], ['chile', 'CL'], ['peru', 'PE']]) add(k, { cc });
  // admin1 names in our list that belong to a country (US states, provinces, Australian states)
  const ADMIN_CC = new Map();
  for (const [tbl, cc] of [[US, 'US'], [CAN, 'CA'], [AUS, 'AU']]) for (const full of Object.values(tbl)) ADMIN_CC.set(fold(full), cc);
  const COUNTRY_CC = new Map([...REG].flatMap(([k, vs]) => vs.filter((v) => !v.admin1).map((v) => [k, v.cc])));

  // "Jasper, Alberta, Canada" / "Jasper AB" -> { name: 'jasper', regs: [[{admin1:'Alberta',cc:'CA'}], [{cc:'CA'}]] }
  // A typed region nobody knows (a county, a small country) is kept as text and matched as a prefix.
  function parse(text) {
    const parts = String(text || '').split(',').map(fold).filter(Boolean);
    if (!parts.length) return null;
    let name = parts[0];
    const rest = parts.slice(1);
    if (!rest.length) {   // no comma: peel known region words off the end ("Jasper Alberta", "Banff AB", "Perth Western Australia")
      const w = name.split(' ');
      for (let n = Math.min(3, w.length - 1); n >= 1; n--) {
        const tail = w.slice(-n).join(' ');
        if (REG.has(tail)) { name = w.slice(0, -n).join(' '); rest.push(tail); break; }
      }
    }
    return { name, regs: rest.map((r) => REG.get(r) || [{ text: r }]) };
  }
  // does a candidate (admin1, country name, country code) fit every region the reader typed?
  function fits(regs, admin1, country, cc) {
    const a = fold(admin1), c = fold(country);
    return regs.every((opts) => opts.some((o) => o.text
      ? (a.startsWith(o.text) || c.startsWith(o.text) || fold(cc) === o.text)
      : (o.admin1 ? a === fold(o.admin1) && (!o.cc || !cc || cc === o.cc) : cc === o.cc)));
  }
  const km = (a, b) => { const k = Math.cos(a[0] * Math.PI / 180); return 111 * Math.hypot(a[0] - b[0], (a[1] - b[1]) * k); };
  const om = new Map();
  function search(name) {
    if (!om.has(name)) om.set(name, fetch('https://geocoding-api.open-meteo.com/v1/search?' + new URLSearchParams({ name: name.slice(0, 80), count: 100, language: 'en' }))
      .then((r) => (r.ok ? r.json() : {})).then((j) => j.results || []).catch(() => { om.delete(name); return []; }));
    return om.get(name);
  }
  // "Jasper, Alberta, Canada", "Roswell, New Mexico" (US states need no country), "Paris, France"
  // (provinces/states only where people say them: US, Canada, Australia, UK nations; elsewhere "Paris, France")
  const label = (n, admin1, country, cc) => [n, admin1 && /^(US|CA|AU|GB)$/.test(cc || '') && fold(admin1) !== fold(country) ? admin1 : '', cc === 'US' && admin1 ? '' : country].filter(Boolean).join(', ');

  // cands(text, list) -> { typed, list: [{ lat, lon, label, pop }] biggest first } or null.
  // Open-Meteo gives populations; our own list (biggest first) is the fallback when offline or when it knows nothing.
  async function cands(text, list) {
    const p = parse(text);
    if (!p || !p.name) return null;
    const out = [], near5 = (lat, lon) => out.some((c) => km([c.lat, c.lon], [lat, lon]) < 5);
    if (typeof navigator === 'undefined' || navigator.onLine !== false) {
      for (const g of await search(p.name)) {
        if (fold(g.name) !== p.name || !fits(p.regs, g.admin1, g.country, g.country_code) || near5(g.latitude, g.longitude)) continue;
        out.push({ lat: g.latitude, lon: g.longitude, label: label(g.name, g.admin1, g.country, g.country_code), pop: g.population || 100 });
      }
    }
    const n = (list || []).length;
    for (let i = 0; i < n; i++) {
      const x = list[i];
      if (fold(x[0]) !== p.name || near5(x[2], x[3])) continue;
      const isAdmin = ADMIN_CC.has(fold(x[1])), cc = ADMIN_CC.get(fold(x[1])) || COUNTRY_CC.get(fold(x[1])) || '';
      const country = isAdmin ? { US: 'United States', CA: 'Canada', AU: 'Australia' }[cc] : x[1];
      if (!fits(p.regs, isAdmin ? x[1] : '', country, cc)) continue;
      out.push({ lat: x[2], lon: x[3], label: label(x[0], isAdmin ? x[1] : '', country, cc), pop: 15000 * (n - i) / n + 1000 });
    }
    out.sort((x, y) => y.pop - x.pop);
    return out.length ? { typed: p.regs.length > 0, list: out } : null;
  }
  // The pair of places a trip most likely means: road distance-ish plus 300 km for every tenfold drop in size from the
  // best-known place of that name. Edmonton to Jasper is Jasper, Alberta; Toronto to London is London, Ontario;
  // Indianapolis to Jasper is Jasper, Indiana. A place typed with its region, or found by GPS, only has its own options.
  const cost = (c, top) => 300 * Math.log10(top.pop / c.pop);
  function pair(A, B) {
    let best = null;
    for (const a of A.list.slice(0, 12)) for (const b of B.list.slice(0, 12)) {
      const s = km([a.lat, a.lon], [b.lat, b.lon]) + cost(a, A.list[0]) + cost(b, B.list[0]);
      if (!best || s < best.s) best = { s, a, b };
    }
    return best;
  }
  const out = (c) => [round2(c.lat), round2(c.lon), c.label];
  // find(text, list, near?) -> [lat, lon, label] or null. list = cities.json rows [name, region, lat, lon], biggest first.
  async function find(text, list, near) {
    const A = await cands(text, list);
    if (!A) return null;
    if (!near) return out(A.list[0]);
    return out(pair(A, { list: [{ lat: near[0], lon: near[1], pop: 1 }] }).a);
  }
  // trip(fromText | [lat, lon, label], toText, list) -> [from, to] (either may be null when that place can't be found)
  async function trip(from, to, list) {
    const A = Array.isArray(from) ? { list: [{ lat: from[0], lon: from[1], label: from[2], pop: 1 }] } : await cands(from, list);
    const B = await cands(to, list);
    if (!A || !B) return [A && out(A.list[0]), B && out(B.list[0])];
    const p = pair(A, B);
    return [out(p.a), out(p.b)];
  }
  // suggest(text) -> up to 8 "Name, Region, Country" strings from Open-Meteo, for the typing list (adds small towns our list lacks)
  async function suggest(text) {
    const p = parse(text);
    if (!p || p.name.length < 3) return [];
    const out = [], hits = (await search(p.name)).filter((g) => fold(g.name).startsWith(p.name) && /^PPL/.test(g.feature_code || 'PPL') && fits(p.regs, g.admin1, g.country, g.country_code));
    // biggest place in each country first, so Jasper, Alberta isn't buried under eight American Jaspers
    const seen = new Set(), firsts = hits.filter((g) => !seen.has(g.country_code) && seen.add(g.country_code));
    for (const g of [...firsts, ...hits]) {
      const l = label(g.name, g.admin1, g.country, g.country_code);
      if (!out.includes(l)) out.push(l);
      if (out.length >= 8) break;
    }
    return out;
  }
  window.EAPlace = { find, trip, suggest, parse };
})();
