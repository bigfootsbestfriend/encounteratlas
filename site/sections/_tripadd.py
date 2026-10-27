"""Shared bits for state, province and place pages: the "Add to road trip" button (static/tripadd.js) and a mini map of
an area's spots (static/spotmap.js). The map starts as a static dot picture drawn here, so the page stays light; MapLibre
only loads when someone taps "Show map". Not a page builder (the underscore keeps build.py from running it)."""
import json, math

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


def spot_map(ctx, spots, area):
    """spots: [(kind, lat, lon, name, path)]. Static SVG preview with a legend, then a "Show map" button."""
    E = ctx.esc
    pts = [(k, float(a), float(o), n, p) for k, a, o, n, p in spots if a is not None and o is not None]
    if len(pts) < 2:
        return ''
    lat0 = sum(a for _, a, _, _, _ in pts) / len(pts)
    kx = math.cos(math.radians(lat0))
    xs = [o * kx for _, _, o, _, _ in pts]
    ys = [-a for _, a, _, _, _ in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(x1 - x0, y1 - y0, 0.5)
    W, H, pad = 600, 340, 26
    s = min((W - 2 * pad) / max(x1 - x0, span * .3), (H - 2 * pad) / max(y1 - y0, span * .3))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dots = ''
    for (k, a, o, n, p), x, y in sorted(zip(pts, xs, ys), key=lambda t: t[0][0] == 'place'):
        px, py = W / 2 + (x - cx) * s, H / 2 + (y - cy) * s
        dots += (f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{8 if k == "place" else 6}" fill="{KINDS[k][1]}" stroke="#13261F" stroke-width="2">'
                 f'<title>{E(n)}</title></circle>')
    grid = ''.join(f'<line x1="{i}" y1="0" x2="{i}" y2="{H}"/>' for i in range(0, W + 1, 60)) + \
           ''.join(f'<line x1="0" y1="{j}" x2="{W}" y2="{j}"/>' for j in range(0, H + 1, 60))
    used = [k for k in KINDS if any(t[0] == k for t in pts)]
    legend = ''.join(f'<li><i style="--k:{KINDS[k][1]}"></i>{E(KINDS[k][0])} <b>{sum(1 for t in pts if t[0] == k)}</b></li>' for k in used)
    data = json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(o, 4), round(a, 4)]},
         'properties': {'k': k, 'n': n, 'u': ctx.url(p), 'col': KINDS[k][1], 'kl': KINDS[k][0]}} for k, a, o, n, p in pts]},
        ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return f'''<section class="spot-map" aria-labelledby="spot-map-h">
  <div class="spot-map-top"><h2 id="spot-map-h">Map of {E(area)}'s strange spots</h2>
    <button type="button" class="btn btn-sm spot-map-go" hidden>Show map</button></div>
  <div class="spot-map-box"><svg class="spot-map-pre" viewBox="0 0 {W} {H}" role="img" aria-label="Where {len(pts)} spots in {E(area)} sit, as a dot picture">
    <g class="spot-grid">{grid}</g>{dots}</svg></div>
  <ul class="spot-legend">{legend}</ul>
  <script type="application/json" class="spot-data">{data}</script>
</section>'''
