// Report places never show a street address (Mike, 2026-10-22). When a reader types something that looks like an
// address ("123 Main St", "Улица Дубровинского, 64", "Николая Островского, 66к2"), it is replaced before saving with
// the area around it (neighbourhood or district + city + country, from OpenStreetMap), and the stored point is
// snapped to a ~1 km cell (0.01 deg) so the house can't be found from it either. The public point is coarser still
// (the ~5 km cell from fuzz()). publicPlace() is the read-side backstop for anything saved before this rule.

const STREET = new RegExp(
  '\\b(st|street|rd|road|ave|avenue|blvd|boulevard|ln|lane|dr|drive|way|ct|court|cres|crescent|pl|place|terr?|terrace|' +
  'cir|circle|pkwy|parkway|apt|suite|unit|rue|calle|avenida|rua|via|viale|strasse|straße|str|gasse|weg|laan|straat|' +
  'ul|ulitsa|ulica|prospekt|pereulok)\\b\\.?|(улица|ул\\.|проспект|пр-т|переулок|пер\\.|шоссе|бульвар|набережная|площадь|' +
  'вулиця|вул\\.)', 'iu');
// Street words glued onto the name: Hauptstraße, Kirchgasse, Dorpsstraat, Storgatan, Mannerheimintie...
const GLUED = /\p{L}{2,}(straße|strasse|str\.|gasse|weg|straat|laan|vej|gatan|gata|katu|tie)(?![\p{L}])/iu;
const HOUSE_NO = /(^|[\s,#№])\d{1,5}(\s?[a-zа-я](?![a-zа-я])|[\/-]\d{1,4}|\s?к\s?\d{1,3}|\s?стр\.?\s?\d{1,3})?(?=[\s,]|$)/iu;
const ENDS_WITH_NO = /,\s*(д\.?\s*)?\d{1,5}(\s?[a-zа-я]|\s?к\s?\d{1,3}|[\/-]\d{1,4})?\s*$/iu;

export function looksLikeAddress(place) {
  const p = String(place || '').trim();
  if (!p) return false;
  return ENDS_WITH_NO.test(p) || ((STREET.test(p) || GLUED.test(p)) && HOUSE_NO.test(p));
}

export const snap = (x) => Math.round(x * 100) / 100;

// "Sovetsky District, Astrakhan, Russia". Nominatim is free but asks for a real User-Agent and light use; reports
// are a handful a day. Any failure falls back to a neutral label the moderator can fix.
export async function areaName(lat, lon) {
  try {
    const u = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=14&accept-language=en&lat=${snap(lat)}&lon=${snap(lon)}`;
    const res = await fetch(u, { headers: { 'user-agent': 'EncounterAtlas/1.0 (hello@encounteratlas.com)' }, signal: AbortSignal.timeout(5000) });
    if (!res.ok) throw new Error('geocode ' + res.status);
    const a = (await res.json()).address || {};
    const area = a.suburb || a.neighbourhood || a.quarter || a.city_district || a.borough || a.hamlet || '';
    const city = a.city || a.town || a.village || a.municipality || a.county || '';
    const parts = [area, city, a.state && !city ? a.state : '', a.country].filter(Boolean);
    const out = [...new Set(parts)].join(', ');
    if (out && !looksLikeAddress(out)) return out.slice(0, 120);
  } catch (e) { console.error('areaName', e.message || e); }
  return 'Approximate area';
}

// Before saving a submitted or edited report: swap an address for its area and snap the stored point.
export async function privatizePlace(f) {
  if (!looksLikeAddress(f.place)) return false;
  f.lat = snap(f.lat);
  f.lon = snap(f.lon);
  f.place = await areaName(f.lat, f.lon);
  return true;
}

// Read side: never hand an address-like place to the public, even from older rows.
export const publicPlace = (place) => (looksLikeAddress(place) ? 'Approximate area' : place || '');
