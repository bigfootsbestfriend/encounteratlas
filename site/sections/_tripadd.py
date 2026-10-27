"""Shared bits for state, province and place pages: the "Add to road trip" button (static/tripadd.js) and a mini map of
an area's spots (static/spotmap.js). The map starts as a static dot picture drawn here, so the page stays light; MapLibre
only loads when someone taps "Show map". Not a page builder (the underscore keeps build.py from running it)."""
import json, math, os

KINDS = {  # same colours as the road trip planner's stops
    'place': ('Place to visit', '#9CC46B'),
    'case': ('Famous case', '#D9A05B'),
    'encounter': ('Close encounter', '#8E8CF0'),
    'mystery': ('Mystery', '#E07A4F'),
    'military': ('Military encounter', '#4FB3A9'),
}
CAR = ('<svg viewBox="0 0 24 24" aria-hidden="true" class="trip-add-i"><path d="M5 11l1.6-4.2A2 2 0 0 1 8.5 5.5h7a2 2 0 0 1 1.9 1.3L19 11'
       'M4 11h16v5H4zM6.5 16v2M17.5 16v2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
       '<circle cx="7.5" cy="13.5" r="1" fill="currentColor"/><circle cx="16.5" cy="13.5" r="1" fill="currentColor"/></svg>')


def head(ctx, spotmap=False):
    U = ctx.url
    return (f'<link rel="stylesheet" href="{U("/static/tripadd.css")}"><script src="{U("/static/tripadd.js")}" defer></script>'
            + (f'<script src="{U("/static/spotmap.js")}" defer></script>' if spotmap else ''))


def button(ctx, lat, lon, name, path, cls=''):
    """Hidden until tripadd.js runs, so there's never a dead button with JS off."""
    if lat is None or lon is None:
        return ''
    stop = json.dumps([round(float(lat), 4), round(float(lon), 4), name, ctx.url(path)], ensure_ascii=False)
    return (f'<button type="button" class="trip-add{(" " + cls) if cls else ""}" data-trip-add="{ctx.esc(stop)}" data-base="{ctx.BASE}" '
            f'aria-pressed="false" hidden>{CAR}<span class="trip-add-t">Add to road trip</span></button>')


_SHAPES = {}


def shapes(ctx):
    """data/region_shapes.json (made by tools/region_shapes.py): simplified, pre-projected state and province outlines."""
    if not _SHAPES:
        path = os.path.join(ctx.ROOT, 'data', 'region_shapes.json')
        _SHAPES.update(json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {'_': None})
    return _SHAPES


def spot_map(ctx, spots, area, key=''):
    """spots: [(kind, lat, lon, name, path)]. The area's outline with the spots as dots (same projection as the
    outline, from tools/region_shapes.py), then a "Show map" button. key is the GeoNames admin1 code (US.CA, CA.02)."""
    E = ctx.esc
    pts = [(k, float(a), float(o), n, p) for k, a, o, n, p in spots if a is not None and o is not None]
    if len(pts) < 2:
        return ''
    sh = shapes(ctx).get(key)
    if sh:
        W, H = sh['w'], sh['h']
        kx, minx, maxy, sc, pad = sh['proj']
        proj = lambda a, o: ((((o - 360 if sh['wrap'] and o > 0 else o) * kx) - minx) * sc + pad, (maxy - a) * sc + pad)
        outline = f'<path class="spot-shape" d="{sh["d"]}"/>'
    else:  # no outline: fit the dots on their own
        lat0 = sum(a for _, a, _, _, _ in pts) / len(pts)
        kx = math.cos(math.radians(lat0))
        xs, ys = [o * kx for _, _, o, _, _ in pts], [-a for _, a, _, _, _ in pts]
        span = max(max(xs) - min(xs), max(ys) - min(ys), 0.5)
        W, H, pad = 600, 340, 26
        sc = min((W - 2 * pad) / max(max(xs) - min(xs), span * .3), (H - 2 * pad) / max(max(ys) - min(ys), span * .3))
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        proj = lambda a, o: (W / 2 + (o * kx - cx) * sc, H / 2 + (-a - cy) * sc)
        outline = ''
    dots = ''
    for k, a, o, n, p in sorted(pts, key=lambda t: t[0] == 'place'):
        px, py = proj(a, o)
        px, py = min(max(px, 6), W - 6), min(max(py, 6), H - 6)  # a spot just offshore still shows
        dots += (f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{8 if k == "place" else 6}" fill="{KINDS[k][1]}" stroke="#13261F" stroke-width="2">'
                 f'<title>{E(n)}</title></circle>')
    used = [k for k in KINDS if any(t[0] == k for t in pts)]
    legend = ''.join(f'<li><i style="--k:{KINDS[k][1]}"></i>{E(KINDS[k][0])} <b>{sum(1 for t in pts if t[0] == k)}</b></li>' for k in used)
    data = json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(o, 4), round(a, 4)]},
         'properties': {'k': k, 'n': n, 'u': ctx.url(p), 'col': KINDS[k][1], 'kl': KINDS[k][0]}} for k, a, o, n, p in pts]},
        ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return f'''<section class="spot-map" aria-labelledby="spot-map-h">
  <div class="spot-map-top"><h2 id="spot-map-h">Map of {E(area)}'s strange spots</h2>
    <button type="button" class="btn btn-sm spot-map-go" hidden>Show map</button></div>
  <div class="spot-map-box"><svg class="spot-map-pre" viewBox="0 0 {W} {H}" role="img" aria-label="Outline of {E(area)} with its {len(pts)} spots as dots">
    {outline}{dots}</svg></div>
  <ul class="spot-legend">{legend}</ul>
  <script type="application/json" class="spot-data">{data}</script>
</section>'''
