"""Build the Encounter Atlas logo files: a square folded field map with a dashed trail to a big footprint
(Mike's pick, 2026-10-12, from logo round 3; the earlier Dogman tile is kept as tile() for reference).

Writes site/static/logo-mark.svg (header/footer), favicon.svg (bolder, for 16-32px), app-icon.svg and the
app-192/app-512/apple-touch-icon PNGs. The Dogman silhouette is inlined so the SVGs work as <img> and favicons.
"""
import os, re, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, 'site', 'static')
art = open(os.path.join(S, 'art', 'dogman.svg')).read()
paths = ''.join(re.findall(r'<path[^>]*/>', art, re.S)).replace('#14211B', '#0E1712')
SKY = ('#3B4C6B', '#1B2A3A')
MOON, CREAM, RIDGE, PINES = '#F3E3B8', '#F3E3B8', '#5E4A3A', '#1E3A2F'


def tile(frame=4, inset=6, rx=10, dog=(22, 26, 160), ridge=True, pines=True, moon=(150, 52, 24)):
    x, y, w = dog
    e = 200 - 2 * inset
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
            f'<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{SKY[0]}"/><stop offset="1" stop-color="{SKY[1]}"/></linearGradient>'
            f'<clipPath id="c"><rect x="{inset}" y="{inset}" width="{e}" height="{e}" rx="{rx}"/></clipPath></defs>'
            f'<g clip-path="url(#c)"><rect width="200" height="200" fill="url(#s)"/><circle cx="{moon[0]}" cy="{moon[1]}" r="{moon[2]}" fill="{MOON}" opacity=".92"/>'
            + (f'<path d="M0 152L30 120 55 138 85 104 120 134 150 110 200 142V200H0Z" fill="{RIDGE}" opacity=".55"/>' if ridge else '')
            + (f'<path d="M0 182L14 146 28 182 40 138 54 182 146 182 160 132 174 182 188 142 200 182V200H0Z" fill="{PINES}"/>' if pines else
               f'<rect y="178" width="200" height="22" fill="{PINES}"/>')
            + f'<svg x="{x}" y="{y}" width="{w}" height="{w}" viewBox="0 0 800 800">{paths}</svg></g>'
            + (f'<rect x="{inset}" y="{inset}" width="{e}" height="{e}" rx="{rx}" fill="none" stroke="{CREAM}" stroke-width="{frame}"/>' if frame else '')
            + '</svg>')


def w(name, svg):
    open(os.path.join(S, name), 'w').write(svg)


FOOT = ('<path d="M30 26c-14 0-20 12-19 26 1 12 4 20 4 28 0 9 6 14 13 14s14-6 14-16c0-11 8-19 8-31 0-12-8-21-20-21Z"/>'
        '<circle cx="13" cy="18" r="6"/><circle cx="23" cy="11" r="6.2"/><circle cx="34" cy="9.5" r="6"/><circle cx="44" cy="13" r="5.4"/><circle cx="51" cy="21" r="4.6"/>')
ROUTE, X, CRE1, CRE2, LINE = '#13261F', '#B4471E', '#E9DFC4', '#D8CBA6', '#8C7B4E'


def fieldmap(bg=None, pad=0, bold=1.0, contours=True):
    """Square folded map: 4 creased panels, faint contours, a dashed trail from a red X to a footprint."""
    k = (200 - 2 * pad) / 200
    s = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
    if bg:
        s += f'<rect width="200" height="200" rx="40" fill="{bg}"/>'
    s += f'<g transform="translate({pad} {pad}) scale({k})">'
    for i in range(4):
        x0, x1 = i * 50, (i + 1) * 50
        a, b = (10, 0) if i % 2 == 0 else (0, 10)
        s += f'<path d="M{x0} {a}L{x1} {b}V{190 + b}L{x0} {190 + a}Z" fill="{CRE2 if i % 2 else CRE1}"/>'
    if contours:
        s += (f'<g fill="none" stroke="{LINE}" stroke-width="3" opacity=".4"><path d="M8 62q50-22 100 4t86-8"/>'
              f'<path d="M8 128q60 26 120-4t66 12"/></g>')
    s += (f'<path d="M30 168C56 136 66 176 92 146S112 92 124 100" fill="none" stroke="{ROUTE}" stroke-width="{7 * bold}" '
          f'stroke-dasharray="{9 * bold} {8 * bold}" stroke-linecap="round"/>'
          f'<g transform="rotate(14 150 74) translate(116 18) scale(1.12)" fill="{ROUTE}">{FOOT}</g>'
          f'<path d="M18 178l18-18M18 160l18 18" stroke="{X}" stroke-width="{8 * bold}" stroke-linecap="round"/></g></svg>')
    return s


w('logo-mark.svg', fieldmap())
# Favicon: bigger Dogman, thick frame, no back ridge, so it still reads at 16px
w('favicon.svg', fieldmap(bg='#13261F', pad=18, bold=1.5, contours=False))
# App icon: full bleed (platforms add their own rounding), frame inset
w('app-icon.svg', fieldmap(bg='#13261F', pad=26).replace('rx="40"', 'rx="0"'))
for px, name in ((192, 'app-192.png'), (512, 'app-512.png'), (180, 'apple-touch-icon.png')):
    subprocess.run(['rsvg-convert', '-w', str(px), '-h', str(px), '-o', os.path.join(S, name), os.path.join(S, 'app-icon.svg')], check=True)
print('logo files written')
