"""Build the Encounter Atlas logo files from the Dogman park-poster tile (Mike's pick, 2026-10-12).

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


w('logo-mark.svg', tile(frame=7, inset=4, rx=14))
# Favicon: bigger Dogman, thick frame, no back ridge, so it still reads at 16px
w('favicon.svg', tile(frame=14, inset=7, rx=26, dog=(8, 14, 186), ridge=False, moon=(152, 50, 30)))
# App icon: full bleed (platforms add their own rounding), frame inset
w('app-icon.svg', tile(frame=8, inset=14, rx=18, dog=(16, 18, 172)).replace('<g clip-path', '<rect width="200" height="200" fill="#1B2A3A"/><g clip-path', 1))
for px, name in ((192, 'app-192.png'), (512, 'app-512.png'), (180, 'apple-touch-icon.png')):
    subprocess.run(['rsvg-convert', '-w', str(px), '-h', str(px), '-o', os.path.join(S, name), os.path.join(S, 'app-icon.svg')], check=True)
print('logo files written')
