"""Guide diagrams, drawn to scale as clean SVG (no hand-placed blobs).

  python3 tools/diagrams.py        writes data/guides/diagrams/<name>.svg
Guides embed them with {{diagram:<name>}} (site/sections/guides.py inlines the file, so text uses the site fonts
and the dg-* classes in static/guides.css).

Proportions:
- Footprint: a large reported track, 15 in long, 7 in across the ball, 4.75 in across the heel; toes as separate pads
  with the big toe on the inside (medial) edge, as in a human-like print.
- Trackway: step 44 in (heel to heel, left to right), stride 88 in (heel to heel, same foot), feet 4.5 in either side
  of the line of travel. Every length in the drawing comes from those numbers at one scale, with a scale bar.
- Study area: 500 m = 150 px, contour interval 20 m.
"""
import math, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'data', 'guides', 'diagrams')

INK, SPRUCE, MUTED, ACC = '#15241E', '#13261F', '#4D6157', '#7A4E00'
FOOT_FILL, FOOT_LINE = '#D8C3A0', '#7C5C3E'
WATER, ROAD, CUT = '#4FB3A9', '#A47B4F', '#E9E2C8'


def f(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


def smooth(pts, closed=True):
    """Catmull-Rom spline through pts -> SVG path."""
    n = len(pts)
    d = f'M{f(pts[0][0])} {f(pts[0][1])}'
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        if not closed:
            p0 = pts[max(i - 1, 0)]
            p3 = pts[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f'C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(p2[0])} {f(p2[1])}'
    return d + ('Z' if closed else '')


# Right foot, heel at (0,0), toes toward +x, big toe toward -y. Units of foot length.
SOLE = [(0.0, 0.0), (0.03, -0.11), (0.14, -0.155), (0.32, -0.12), (0.50, -0.15), (0.66, -0.225), (0.75, -0.21),
        (0.785, -0.10), (0.79, 0.02), (0.765, 0.14), (0.70, 0.215), (0.50, 0.19), (0.30, 0.17), (0.12, 0.155), (0.03, 0.11)]
TOES = [(0.838, -0.148, 0.066, 0.058), (0.854, -0.042, 0.044, 0.039), (0.846, 0.040, 0.040, 0.036),
        (0.822, 0.112, 0.036, 0.032), (0.784, 0.170, 0.032, 0.029)]


def foot(x, y, length, side='R', angle=0.0, cls='dg-print'):
    """SVG group for one footprint: heel at (x, y), pointing at `angle` degrees (0 = +x)."""
    sy = 1 if side == 'R' else -1
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def T(u, v):
        u, v = u * length, v * length * sy
        return (x + u * ca - v * sa, y + u * sa + v * ca)
    sole = smooth([T(u, v) for u, v in SOLE])
    toes = ''.join(f'<ellipse cx="{f(T(u, v)[0])}" cy="{f(T(u, v)[1])}" rx="{f(rx * length)}" ry="{f(ry * length)}" '
                   f'transform="rotate({f(angle)} {f(T(u, v)[0])} {f(T(u, v)[1])})"/>' for u, v, rx, ry in TOES)
    return f'<g class="{cls}"><path d="{sole}"/>{toes}</g>'


def dim_h(x1, x2, y, label, sub='', above=True, tick=7):
    """Horizontal dimension line with end ticks and arrowheads, label centred."""
    ty = y - 8 if above else y + 17
    out = (f'<g class="dg-dim"><path d="M{f(x1)} {f(y - tick)}V{f(y + tick)}M{f(x2)} {f(y - tick)}V{f(y + tick)}M{f(x1)} {f(y)}H{f(x2)}"/>'
           f'<path class="dg-arrow" d="M{f(x1)} {f(y)}l8 -4v8ZM{f(x2)} {f(y)}l-8 -4v8Z"/></g>')
    out += f'<text x="{f((x1 + x2) / 2)}" y="{f(ty)}" text-anchor="middle" class="dg-txt-b">{label}</text>'
    if sub:
        out += f'<text x="{f((x1 + x2) / 2)}" y="{f(ty + (14 if not above else -15))}" text-anchor="middle" class="dg-txt-s">{sub}</text>'
    return out


def dim_v(x, y1, y2, label, sub='', right=True, tick=7):
    tx = x + 12 if right else x - 12
    anchor = 'start' if right else 'end'
    out = (f'<g class="dg-dim"><path d="M{f(x - tick)} {f(y1)}H{f(x + tick)}M{f(x - tick)} {f(y2)}H{f(x + tick)}M{f(x)} {f(y1)}V{f(y2)}"/>'
           f'<path class="dg-arrow" d="M{f(x)} {f(y1)}l-4 8h8ZM{f(x)} {f(y2)}l-4 -8h8Z"/></g>')
    out += f'<text x="{f(tx)}" y="{f((y1 + y2) / 2)}" text-anchor="{anchor}" class="dg-txt-b">{label}</text>'
    if sub:
        out += f'<text x="{f(tx)}" y="{f((y1 + y2) / 2 + 15)}" text-anchor="{anchor}" class="dg-txt-s">{sub}</text>'
    return out


def scale_bar(x, y, px_per_unit, units, label_unit, step):
    n = int(units / step)
    w = px_per_unit * units
    segs = ''.join(f'<rect x="{f(x + i * w / n)}" y="{f(y)}" width="{f(w / n)}" height="6" fill="{SPRUCE if i % 2 == 0 else "#fff"}"/>' for i in range(n))
    labels = ''.join(f'<text x="{f(x + i * w / n)}" y="{f(y + 19)}" text-anchor="middle" class="dg-txt-s">{i * step:g}</text>' for i in range(n + 1))
    return (f'<g>{segs}<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="6" fill="none" stroke="{SPRUCE}" stroke-width="1"/>{labels}'
            f'<text x="{f(x + w + 8)}" y="{f(y + 7)}" class="dg-txt-s">{label_unit}</text></g>')


def svg(name, w, h, title, body):
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="{name}-t" class="dg">'
            f'<title id="{name}-t">{title}</title>{body}</svg>')


# ---------------------------------------------------------------- trackway
def trackway():
    W, H = 720, 360
    s = 5.4                      # px per inch
    L, step, off = 15, 44, 4.5   # inches
    x0, cy = 64, 178
    body = f'<rect width="{W}" height="{H}" fill="#F7F4EA" rx="6"/>'
    body += ''.join(f'<circle cx="{(i * 97) % W}" cy="{30 + (i * 53) % (H - 60)}" r="{1 + i % 2}" fill="#E4DCC6"/>' for i in range(70))
    body += f'<line x1="20" y1="{cy}" x2="{W - 24}" y2="{cy}" class="dg-center"/><path d="M{W - 20} {cy}l-12 -6v12Z" fill="{MUTED}"/>'
    heels = []
    for i in range(3):
        side = 'L' if i % 2 == 0 else 'R'
        hx = x0 + i * step * s
        hy = cy + (-off if side == 'L' else off) * s
        heels.append((hx, hy, side))
        body += foot(hx, hy, L * s, side)
    body += ''.join(f'<circle cx="{f(hx)}" cy="{f(hy)}" r="3.5" fill="{ACC}"/>' for hx, hy, _ in heels)
    body += f'<text x="{f(heels[0][0] + L * s / 2)}" y="{f(heels[0][1] - 0.24 * L * s - 8)}" text-anchor="middle" class="dg-txt-s">left foot</text>'
    body += f'<text x="{f(heels[1][0] + L * s / 2)}" y="{f(heels[1][1] + 0.24 * L * s + 16)}" text-anchor="middle" class="dg-txt-s">right foot</text>'
    body += f'<text x="{f(heels[2][0] + L * s / 2)}" y="{f(heels[2][1] - 0.24 * L * s - 8)}" text-anchor="middle" class="dg-txt-s">left foot</text>'
    body += f'<text x="{f(heels[0][0] + L * s + 24)}" y="{cy - 7}" class="dg-txt-s">line of travel</text>'
    (ax, ay, _), (bx, by, _), (cx_, cy_, _) = heels
    yS = 46
    body += f'<path d="M{f(ax)} {f(ay - 5)}V{yS + 8}M{f(cx_)} {f(cy_ - 5)}V{yS + 8}" class="dg-ext"/>'
    body += dim_h(ax, cx_, yS, 'Stride ≈ 88 in', 'heel to heel, same foot (two steps)')
    yT = H - 58
    body += f'<path d="M{f(ax)} {f(ay + 5)}V{yT - 8}M{f(bx)} {f(by + 5)}V{yT - 8}" class="dg-ext"/>'
    body += dim_h(ax, bx, yT, 'Step ≈ 44 in', 'heel to heel, left to right', above=False)
    # straddle across the outside edges of the last two prints
    top = heels[2][1] - 0.225 * L * s
    bot = heels[1][1] + 0.215 * L * s
    xD = W - 40
    body += f'<path d="M{f(heels[2][0] + 0.70 * L * s)} {f(top)}H{xD + 8}M{f(heels[1][0] + 0.70 * L * s)} {f(bot)}H{xD + 8}" class="dg-ext"/>'
    body += dim_v(xD, top, bot, '')
    body += f'<text x="{xD - 10}" y="{f(bot + 30)}" text-anchor="end" class="dg-txt-b">Straddle ≈ 16 in</text>'
    body += f'<text x="{xD - 10}" y="{f(bot + 45)}" text-anchor="end" class="dg-txt-s">outside edge to outside edge</text>'
    body += scale_bar(W - 250, H - 30, s, 36, 'inches', 12)
    body += f'<text x="{W - 250}" y="{H - 40}" class="dg-txt-s">Drawn to scale: 15 in prints</text>'
    return svg('trackway', W, H, 'Trackway diagram, drawn to scale, showing step, stride and straddle between alternating left and right footprints', body)


# ---------------------------------------------------------------- one footprint, measured
def footprint():
    W, H = 660, 380
    s = 20                         # px per inch
    L = 15
    hx, hy = 150, 190
    body = f'<rect width="{W}" height="{H}" fill="#F7F4EA" rx="6"/>'
    body += foot(hx, hy, L * s, 'R', 0, 'dg-print dg-print-big')
    # length: heel back to tip of the longest toe (big toe here)
    tip = hx + (TOES[0][0] + TOES[0][2]) * L * s
    yL = 42
    body += f'<path d="M{hx} {hy - 20}V{yL + 8}M{f(tip)} {f(hy - 0.15 * L * s - 8)}V{yL + 8}" class="dg-ext"/>'
    body += dim_h(hx, tip, yL, 'Length 15 in (38 cm)', 'back of the heel to the tip of the longest toe')
    # ball width at x = 0.70
    bx = hx + 0.70 * L * s
    b1, b2 = hy - 0.225 * L * s, hy + 0.215 * L * s
    body += f'<path d="M{f(bx)} {f(b1)}V{f(b1)}M{f(bx)} {f(b2)}" class="dg-ext"/>'
    body += dim_v(bx + 0, b1, b2, '', right=True)
    body += f'<path d="M{f(bx)} {f(b2)}L{f(bx + 70)} {H - 70}" class="dg-dim-thin"/>'
    body += f'<text x="{f(bx + 74)}" y="{H - 66}" class="dg-txt-b">Ball width 7 in</text><text x="{f(bx + 74)}" y="{H - 51}" class="dg-txt-s">widest point behind the toes</text>'
    # heel width at x = 0.10
    kx = hx + 0.10 * L * s
    k1, k2 = hy - 0.150 * L * s, hy + 0.140 * L * s
    body += dim_v(kx, k1, k2, '', right=False)
    body += f'<path d="M{f(kx)} {f(k2)}L{f(kx - 30)} {H - 70}" class="dg-dim-thin"/>'
    body += f'<text x="{f(kx - 34)}" y="{H - 66}" text-anchor="middle" class="dg-txt-b">Heel width 4¾ in</text>'
    # midfoot crease
    mx = hx + 0.47 * L * s
    body += f'<path d="M{f(mx - 6)} {f(hy - 0.14 * L * s)}Q{f(mx + 8)} {hy} {f(mx - 4)} {f(hy + 0.17 * L * s)}" class="dg-crease"/>'
    body += f'<path d="M{f(mx + 4)} {f(hy - 0.10 * L * s)}L{f(mx + 40)} 96" class="dg-dim-thin"/>'
    body += f'<text x="{f(mx + 44)}" y="92" class="dg-txt">Midfoot: note any crease or ridge</text>'
    # toes callout
    tx = hx + 0.9 * L * s
    body += f'<path d="M{f(tx + 18)} {f(hy + 0.05 * L * s)}L{W - 128} {hy + 30}" class="dg-dim-thin"/>'
    body += f'<text x="{W - 124}" y="{hy + 34}" class="dg-txt">Toes: count them</text><text x="{W - 124}" y="{hy + 49}" class="dg-txt-s">spread, bent, missing?</text>'
    body += f'<text x="{f(hx + 0.88 * L * s)}" y="{f(hy - 0.24 * L * s - 6)}" text-anchor="middle" class="dg-txt-s">big toe (inside edge)</text>'
    body += scale_bar(24, H - 30, s, 6, 'inches', 1)
    body += f'<text x="{W - 20}" y="{H - 14}" text-anchor="end" class="dg-txt-s">Right foot, drawn to scale</text>'
    return svg('footprint', W, H, 'A 15 inch right footprint drawn to scale with length, ball width and heel width marked', body)


# ---------------------------------------------------------------- study area map
def ring(cx, cy, r, wob, seed, n=64):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        rr = r * (1 + wob * (0.55 * math.sin(2 * t + seed) + 0.3 * math.sin(3 * t + 2 * seed) + 0.15 * math.cos(5 * t + seed)))
        pts.append((cx + rr * math.cos(t) * 1.35, cy + rr * math.sin(t)))
    return smooth(pts)


def study_area():
    W, H = 720, 430
    m = 150 / 500                   # px per metre
    body = f'<defs><pattern id="cut" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><path d="M0 0V8" stroke="#C9B98A" stroke-width="2"/></pattern>'
    body += '<clipPath id="sa-clip"><rect width="720" height="430" rx="6"/></clipPath></defs>'
    body += f'<g clip-path="url(#sa-clip)"><rect width="{W}" height="{H}" fill="#F1F5EE"/>'
    # contours around a knob, plus a ridge running off the top
    kx, ky = 470, 140
    for i, r in enumerate([20, 42, 66, 92, 120]):
        body += f'<path d="{ring(kx, ky, r, 0.10 + i * 0.012, 0.7)}" class="{"dg-contour-i" if i % 5 == 3 else "dg-contour"}"/>'
    body += f'<text x="{kx - 112}" y="{ky - 44}" class="dg-elev">1240 m</text><text x="{kx - 168}" y="{ky + 40}" class="dg-elev">1160</text>'
    # second, lower hill bottom-left
    for i, r in enumerate([20, 44, 70]):
        body += f'<path d="{ring(120, 360, r, 0.12, 2.1)}" class="dg-contour"/>'
    # creek in the valley bottom, west to south-east, with a tributary
    creek = [(-10, 205), (60, 214), (130, 236), (200, 250), (275, 262), (350, 286), (420, 318), (500, 340), (590, 352), (730, 362)]
    body += f'<path d="{smooth(creek, closed=False)}" fill="none" stroke="{WATER}" stroke-width="6" stroke-linecap="round"/>'
    body += f'<path d="{smooth([(236, 96), (244, 160), (254, 214), (268, 258)], closed=False)}" fill="none" stroke="{WATER}" stroke-width="3" stroke-linecap="round"/>'
    body += f'<path d="M560 349l14 2-12 7Z" fill="{WATER}"/><text x="510" y="376" class="dg-txt-s" fill="#2F7F78">flow</text>'
    body += f'<text x="26" y="236" class="dg-label-w">Bear Creek</text>'
    # old clearcut (hatched) on the north-east slope
    body += f'<path d="M560 40L700 30L712 128L600 150L548 98Z" fill="url(#cut)" stroke="#BDA978" stroke-width="1.5"/>'
    body += f'<text x="604" y="62" class="dg-label">old clearcut</text>'
    # gated logging road from the south-west, ending at a landing
    road = [(-10, 420), (60, 392), (150, 330), (215, 300), (262, 272), (300, 250), (330, 236)]
    body += f'<path d="{smooth(road, closed=False)}" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round"/>'
    body += f'<path d="{smooth(road, closed=False)}" fill="none" stroke="{ROAD}" stroke-width="3" stroke-dasharray="10 6" stroke-linecap="round"/>'
    body += f'<g transform="translate(92 371) rotate(-30)"><rect x="-12" y="-3" width="24" height="6" fill="#B3261E"/><circle cx="-14" cy="0" r="4" fill="{SPRUCE}"/></g>'
    body += f'<text x="104" y="404" class="dg-label">gate</text><text x="150" y="350" class="dg-label" transform="rotate(-27 150 350)">logging road</text>'
    # game trail: from the creek crossing up the slope to the clearcut edge
    trail = [(226, 252), (270, 222), (340, 208), (420, 214), (500, 222), (548, 176), (568, 128)]
    body += f'<path d="{smooth(trail, closed=False)}" fill="none" stroke="{ACC}" stroke-width="1.8" stroke-dasharray="2 5" stroke-linecap="round"/>'
    body += f'<text x="366" y="230" class="dg-label">game trail</text>'
    # camp at the landing, well back from the water
    body += f'<g transform="translate(318 228)"><path d="M-13 9L0 -11L13 9Z" fill="{ACC}"/><path d="M0 -11V9" stroke="#F7E3B6" stroke-width="1.5"/></g>'
    body += f'<text x="336" y="240" class="dg-label-b">Camp</text><text x="336" y="254" class="dg-txt-s">60 m+ from water</text>'
    # cameras with view cones, aimed along the trail / crossing / edge

    def cam(x, y, ang, label, lx, ly, anchor='start'):
        a = math.radians(ang)
        r = 42
        p1 = (x + r * math.cos(a - 0.45), y + r * math.sin(a - 0.45))
        p2 = (x + r * math.cos(a + 0.45), y + r * math.sin(a + 0.45))
        return (f'<path d="M{x} {y}L{f(p1[0])} {f(p1[1])}A{r} {r} 0 0 1 {f(p2[0])} {f(p2[1])}Z" class="dg-cone"/>'
                f'<rect x="{x - 6}" y="{y - 5}" width="12" height="10" rx="2" class="dg-cam"/><circle cx="{x}" cy="{y}" r="2.2" fill="#F2B33D"/>'
                f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" class="dg-label-b">{label}</text>')
    body += cam(200, 228, 30, 'Camera 1: creek crossing', 192, 212, 'end')
    body += cam(522, 214, 195, 'Camera 2: game trail', 532, 240)
    body += cam(556, 112, -40, 'Camera 3: clearcut edge', 544, 84, 'end')
    # listening post on the knob, with sound arcs
    body += f'<circle cx="{kx}" cy="{ky}" r="7" fill="#F2B33D" stroke="{ACC}" stroke-width="2"/>'
    body += ''.join(f'<path d="M{kx - r * 0.7} {ky - r * 0.7}A{r} {r} 0 0 1 {kx + r * 0.7} {ky - r * 0.7}" fill="none" stroke="{ACC}" stroke-width="1.2" opacity="{0.8 - i * 0.2}"/>' for i, r in enumerate([16, 24, 32]))
    body += f'<text x="{kx + 14}" y="{ky + 20}" class="dg-label-b">Listening post</text><text x="{kx + 14}" y="{ky + 34}" class="dg-txt-s">sound carries from here</text>'
    # past reports
    for x, y, yr in ((150, 262, '1998'), (410, 290, '2009'), (652, 206, '2017')):
        body += f'<circle cx="{x}" cy="{y}" r="6" fill="#B98ACB" stroke="#fff" stroke-width="1.5"/><text x="{x + 9}" y="{y + 4}" class="dg-txt-s">{yr}</text>'
    # north arrow
    body += f'<g transform="translate(674 362)"><circle r="20" fill="#fff" stroke="{MUTED}"/><path d="M0 -15L7 8L0 3L-7 8Z" fill="{SPRUCE}"/><text y="-23" text-anchor="middle" class="dg-label-b">N</text></g>'
    # legend + scale
    body += f'<g transform="translate(14 14)"><rect width="196" height="112" rx="6" fill="#fff" stroke="#D3DED7"/>'
    body += f'<circle cx="16" cy="18" r="5" fill="#B98ACB"/><text x="30" y="22" class="dg-txt-s">past report (year)</text>'
    body += f'<rect x="10" y="33" width="12" height="10" rx="2" fill="{SPRUCE}"/><path d="M16 38l20 -8v16Z" fill="rgba(242,179,61,.35)"/><text x="42" y="42" class="dg-txt-s">trail camera + view</text>'
    body += f'<path d="M10 58h26" stroke="{ROAD}" stroke-width="3" stroke-dasharray="6 4"/><text x="42" y="62" class="dg-txt-s">gated road (walk in)</text>'
    body += f'<path d="M10 78h26" stroke="{ACC}" stroke-width="1.8" stroke-dasharray="2 4"/><text x="42" y="82" class="dg-txt-s">game trail</text>'
    body += f'<path d="M10 98h26" class="dg-contour"/><text x="42" y="102" class="dg-txt-s">contour, every 20 m</text></g>'
    body += scale_bar(470, 404, m, 500, 'metres', 250)
    body += '</g>'
    return svg('study-area', W, H, 'Map of a sample study area: contours, a creek, a gated road, camp, three trail cameras with view cones, a listening post and past reports', body)


# ---------------------------------------------------------------- casting steps
def casting_steps():
    W, H = 720, 250
    pw = W / 4
    steps = [
        ('1', 'Clean and dam', 'Pick out loose debris, then ring the print with a strip'),
        ('2', 'Mix in the bag', 'Water into the powder; knead to pancake batter'),
        ('3', 'Pour beside it', 'Over a spoon held low; fill to 1 in thick'),
        ('4', 'Wait, then lift', '20–30 min until it goes "tock"; lift from below'),
    ]
    body = f'<rect width="{W}" height="{H}" fill="#F7F4EA" rx="6"/>'
    for i, (n, t, sub) in enumerate(steps):
        x = i * pw
        cx, cy = x + pw / 2, 104
        if i:
            body += f'<path d="M{f(x)} 30V200" stroke="#E2D8BE"/>'
        if i == 0:   # print from above, dam ring around it, debris being lifted out
            body += f'<ellipse cx="{f(cx)}" cy="{cy}" rx="72" ry="54" fill="#E4DCC6"/>'
            body += foot(cx - 52, cy, 104, 'R', 0, 'dg-print dg-print-mud')
            body += f'<ellipse cx="{f(cx)}" cy="{cy}" rx="66" ry="38" fill="none" stroke="{ACC}" stroke-width="4"/>'
            body += f'<path d="M{f(cx + 8)} {cy - 6}l10 -5" stroke="#6E523B" stroke-width="3" stroke-linecap="round"/>'
            body += f'<path d="M{f(cx + 14)} {cy - 12}q10 -26 30 -36" fill="none" stroke="{MUTED}" stroke-width="1.6" marker-end="url(#ah)"/>'
            body += f'<text x="{f(cx + 50)}" y="{cy - 50}" class="dg-txt-s">twig out</text>'
            body += f'<text x="{f(cx - 64)}" y="{cy + 58}" class="dg-txt-s">dam strip</text>'
        elif i == 1:  # zip bag of powder, water pouring in, knead arrows
            bx, by = cx + 6, cy - 4
            body += f'<path d="M{f(bx - 38)} {f(by - 44)}h76v86q0 8 -8 8h-60q-8 0 -8 -8Z" fill="#fff" stroke="{SPRUCE}" stroke-width="2"/>'
            body += f'<path d="M{f(bx - 38)} {f(by - 36)}h76" stroke="{SPRUCE}" stroke-width="1.5" stroke-dasharray="3 2"/>'
            body += f'<path d="M{f(bx - 32)} {f(by - 4)}q32 -8 64 0v40q0 6 -6 6h-52q-6 0 -6 -6Z" fill="#E6E1D4"/>'
            body += f'<text x="{f(bx)}" y="{f(by + 22)}" text-anchor="middle" class="dg-txt-s">powder</text>'
            body += f'<path d="M{f(bx - 70)} {f(by - 70)}l22 8l-4 12l-22 -8Z" fill="{WATER}" opacity=".9"/>'
            body += f'<path d="M{f(bx - 48)} {f(by - 56)}q12 2 16 18v26" fill="none" stroke="{WATER}" stroke-width="4" stroke-linecap="round"/>'
            body += f'<path d="M{f(bx - 52)} {f(by + 18)}a20 20 0 0 1 0 -26M{f(bx + 52)} {f(by - 8)}a20 20 0 0 1 0 26" fill="none" stroke="{ACC}" stroke-width="2" marker-end="url(#ahA)"/>'
            body += f'<text x="{f(bx - 24)}" y="{f(by - 54)}" class="dg-txt-s">water in</text><text x="{f(bx + 50)}" y="{f(by + 34)}" class="dg-txt-s">knead</text>'
        elif i == 2:  # pour onto a spoon at the edge, mix flows into the print
            body += f'<ellipse cx="{f(cx)}" cy="{cy + 6}" rx="72" ry="54" fill="#E4DCC6"/>'
            body += foot(cx - 52, cy + 6, 104, 'R', 0, 'dg-print dg-print-mud')
            body += f'<ellipse cx="{f(cx)}" cy="{cy + 6}" rx="66" ry="38" fill="none" stroke="{ACC}" stroke-width="4"/>'
            body += f'<path d="M{f(cx - 40)} {cy + 6}q24 -10 46 4q20 12 34 -2v12q-30 22 -80 -2Z" fill="#F1EEE6" opacity=".95"/>'
            body += f'<ellipse cx="{f(cx - 52)}" cy="{cy - 14}" rx="13" ry="7" fill="#C9CED1" stroke="{SPRUCE}" stroke-width="1.5"/>'
            body += f'<path d="M{f(cx - 64)} {cy - 16}l-26 -14" stroke="{SPRUCE}" stroke-width="4" stroke-linecap="round"/>'
            body += f'<path d="M{f(cx - 52)} {cy - 66}q4 26 0 48" fill="none" stroke="#F1EEE6" stroke-width="7" stroke-linecap="round"/>'
            body += f'<path d="M{f(cx - 52)} {cy - 66}q4 26 0 48" fill="none" stroke="#B9B09A" stroke-width="1" stroke-linecap="round"/>'
            body += f'<path d="M{f(cx - 40)} {cy - 10}q16 2 22 12" fill="none" stroke="{MUTED}" stroke-width="1.6" marker-end="url(#ah)"/>'
            body += f'<text x="{f(cx - 44)}" y="{cy - 70}" class="dg-txt-s">pour low, onto a spoon</text>'
        else:         # side view: cast lifted out of the ground from underneath
            gy = cy + 34
            body += f'<path d="M{f(x + 14)} {gy}H{f(x + pw - 14)}V{gy + 34}H{f(x + 14)}Z" fill="#E4DCC6"/>'
            body += f'<path d="M{f(cx - 58)} {gy}q58 26 116 0" fill="#CDBB98"/>'
            body += f'<path d="M{f(cx - 60)} {gy - 38}h120v14q-60 22 -120 0Z" fill="#F1EEE6" stroke="#B9B09A" stroke-width="2"/>'
            body += ''.join(f'<path d="M{f(cx + dx)} {gy + 6}v-30" stroke="{ACC}" stroke-width="2.5" marker-end="url(#ahA)"/>' for dx in (-70, 70))
            body += f'<text x="{f(cx)}" y="{gy - 46}" text-anchor="middle" class="dg-txt-s">knuckle tap: "tock" = ready</text>'
            body += f'<text x="{f(cx)}" y="{gy + 26}" text-anchor="middle" class="dg-txt-s">lift from below</text>'
        body += f'<circle cx="{f(x + 22)}" cy="28" r="13" fill="{SPRUCE}"/><text x="{f(x + 22)}" y="33" text-anchor="middle" class="dg-num">{n}</text>'
        body += f'<text x="{f(cx)}" y="196" text-anchor="middle" class="dg-txt-b">{t}</text>'
        words, line, lines = sub.split(), '', []
        for w_ in words:
            if len(line + ' ' + w_) > 28:
                lines.append(line)
                line = w_
            else:
                line = (line + ' ' + w_).strip()
        lines.append(line)
        body += ''.join(f'<text x="{f(cx)}" y="{214 + k * 14}" text-anchor="middle" class="dg-txt-s">{l}</text>' for k, l in enumerate(lines))
    body = f'<defs><marker id="ah" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8Z" fill="{MUTED}"/></marker><marker id="ahA" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8Z" fill="{ACC}"/></marker></defs>' + body
    return svg('casting-steps', W, H, 'Casting a track in four steps: clean and dam, mix in the bag, pour beside the print, wait and lift from below', body)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (('trackway', trackway), ('footprint', footprint), ('study-area', study_area), ('casting-steps', casting_steps)):
        open(os.path.join(OUT, name + '.svg'), 'w', encoding='utf-8').write(fn())
        print('wrote', name)


if __name__ == '__main__':
    main()
