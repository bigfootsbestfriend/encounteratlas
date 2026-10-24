"""/tools/skywatch/: tonight's skywatch forecast, a score out of 10 for the visitor's place.

Full HTML at load (indexable): how the score works, the meteor shower calendar for the next 12 months and the Moon's
phases for the next 30 days, both worked out here at build time (low-precision Sun and Moon formulas from Meeus,
good to well under an hour for phase times, which is plenty for a list of dates).
static/skywatch.js only runs when a control is used: "Use my location" or "Pick a place" (static/data/cities.json,
copied there by skycheck.py), then Open-Meteo for hourly cloud cover (free, no key), astronomy-engine for the Sun and
Moon, satellite.js plus a Celestrak orbit for Space Station passes (both lazy-loaded, same CDN and versions as
skycore.js) and the shower table below (passed in as JSON, so there's one source).
"""
import datetime, json, math

ASTRO = 'https://cdn.jsdelivr.net/npm/astronomy-engine@2.1.19/astronomy.browser.min.js'
SATJS = 'https://cdn.jsdelivr.net/npm/satellite.js@6.0.2/dist/satellite.min.js'

# Meteor showers (International Meteor Organization working list). Peak dates move by a day or so from year to year.
# key, name, start (month, day), peak, end, typical ZHR, radiant RA (hours), radiant dec (degrees), parent, where it's best
SHOWERS = [
    ('qua', 'Quadrantids', (12, 28), (1, 3), (1, 12), 80, 15.33, 49, 'asteroid 2003 EH1', 'Northern Hemisphere only'),
    ('lyr', 'Lyrids', (4, 14), (4, 22), (4, 30), 18, 18.07, 34, 'Comet Thatcher', 'Best from the north'),
    ('eta', 'Eta Aquariids', (4, 19), (5, 6), (5, 28), 50, 22.53, -1, "Halley's Comet", 'Best from the south and the tropics'),
    ('sda', 'Southern Delta Aquariids', (7, 12), (7, 30), (8, 23), 25, 22.67, -16, 'Comet 96P/Machholz', 'Best from the south and the tropics'),
    ('per', 'Perseids', (7, 17), (8, 12), (8, 24), 100, 3.2, 58, 'Comet Swift-Tuttle', 'Northern Hemisphere'),
    ('ori', 'Orionids', (10, 2), (10, 21), (11, 7), 20, 6.33, 16, "Halley's Comet", 'Both hemispheres'),
    ('sta', 'Southern Taurids', (9, 10), (10, 10), (11, 20), 5, 2.13, 13, 'Comet Encke', 'Both hemispheres, known for fireballs'),
    ('nta', 'Northern Taurids', (10, 20), (11, 12), (12, 10), 5, 3.47, 22, 'Comet Encke', 'Both hemispheres, known for fireballs'),
    ('leo', 'Leonids', (11, 6), (11, 17), (11, 30), 15, 10.27, 22, 'Comet Tempel-Tuttle', 'Both hemispheres'),
    ('gem', 'Geminids', (12, 4), (12, 14), (12, 20), 150, 7.53, 33, 'asteroid 3200 Phaethon', 'Both, best from the north'),
    ('urs', 'Ursids', (12, 17), (12, 22), (12, 26), 10, 14.53, 75, 'Comet Tuttle', 'Northern Hemisphere only'),
]

PHASE_NAMES = {0: 'New Moon', 90: 'First quarter', 180: 'Full Moon', 270: 'Last quarter'}


# ---------------------------------------------------------------- Sun and Moon (low precision)
def jd(dt):
    return dt.timestamp() / 86400 + 2440587.5


def elongation(dt):
    """Moon's ecliptic longitude minus the Sun's, in degrees 0-360 (0 = new, 180 = full)."""
    T = (jd(dt) - 2451545.0) / 36525
    r = math.radians
    M = r(357.5291092 + 35999.0502909 * T)
    L0 = 280.46646 + 36000.76983 * T
    sun = L0 + (1.914602 - 0.004817 * T) * math.sin(M) + 0.019993 * math.sin(2 * M) + 0.000289 * math.sin(3 * M)
    Lp = 218.3164477 + 481267.88123421 * T
    D = r(297.8501921 + 445267.1114034 * T)
    Mp = r(134.9633964 + 477198.8675055 * T)
    F = r(93.2720950 + 483202.0175233 * T)
    moon = (Lp + 6.288774 * math.sin(Mp) + 1.274027 * math.sin(2 * D - Mp) + 0.658314 * math.sin(2 * D)
            + 0.213618 * math.sin(2 * Mp) - 0.185116 * math.sin(M) - 0.114332 * math.sin(2 * F)
            + 0.058793 * math.sin(2 * D - 2 * Mp) + 0.057066 * math.sin(2 * D - M - Mp) + 0.053322 * math.sin(2 * D + Mp)
            + 0.045758 * math.sin(2 * D - M) - 0.040923 * math.sin(M - Mp) - 0.034720 * math.sin(D) - 0.030383 * math.sin(M + Mp))
    return (moon - sun) % 360


def lit(dt):
    """Share of the Moon's disc that's lit (0-1) and whether it's waxing."""
    e = elongation(dt)
    return (1 - math.cos(math.radians(e))) / 2, e < 180


def phases(start, days):
    """Principal phases between start and start + days: [(datetime UTC, angle)]."""
    out, step = [], datetime.timedelta(hours=3)
    t, end = start, start + datetime.timedelta(days=days)
    rel = lambda dt, a: (elongation(dt) - a + 180) % 360 - 180
    while t < end:
        t2 = t + step
        for a in (0, 90, 180, 270):
            x, y = rel(t, a), rel(t2, a)
            if x < 0 <= y and y - x < 90:
                lo, hi = t, t2
                for _ in range(20):
                    mid = lo + (hi - lo) / 2
                    if rel(mid, a) < 0: lo = mid
                    else: hi = mid
                out.append((lo, a))
        t = t2
    return out


def moon_svg(k, waxing, size=34, cls='sw-moon'):
    """A little Moon drawing, k = lit share. Lit on the right when waxing (as seen from the north)."""
    r = 10
    rx = abs(1 - 2 * k) * r
    if k < 0.02:
        lit_path = ''
    elif k > 0.98:
        lit_path = f'<circle r="{r}" class="lit"/>'
    else:
        # right half from top to bottom, then the terminator back up (bulging right for a crescent, left for gibbous)
        sweep = 0 if k < 0.5 else 1
        flip = '' if waxing else ' transform="scale(-1 1)"'
        lit_path = f'<path class="lit" d="M0 -{r}A{r} {r} 0 0 1 0 {r}A{rx:.2f} {r} 0 0 {sweep} 0 -{r}Z"{flip}/>'
    return (f'<svg class="{cls}" viewBox="-11 -11 22 22" width="{size}" height="{size}" aria-hidden="true">'
            f'<circle r="{r}" class="dark"/>{lit_path}</svg>')


# ---------------------------------------------------------------- showers
def occurrences(today):
    """Next occurrence of each shower that hasn't ended yet, peaking within a year; sorted by peak."""
    rows = []
    for s in SHOWERS:
        key, name, st, pk, en = s[:5]
        for y in (today.year - 1, today.year, today.year + 1):
            peak = datetime.date(y, *pk)
            start = datetime.date(y - (1 if st > pk else 0), *st)
            end = datetime.date(y + (1 if en < pk else 0), *en)
            if end >= today and peak <= today + datetime.timedelta(days=365):
                rows.append((peak, start, end, s))
                break
    return sorted(rows, key=lambda r: r[0])


def fmt(d, year=True):
    return d.strftime('%b %-d, %Y' if year else '%b %-d')


def build(ctx):
    E, U = ctx.esc, ctx.url
    now = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
    today = now.date()

    # ---- meteor shower calendar
    trs = []
    for peak, start, end, s in occurrences(today):
        key, name, _, _, _, zhr, ra, dec, parent, best = s
        k, wax = lit(datetime.datetime(peak.year, peak.month, peak.day, 6, tzinfo=datetime.timezone.utc))
        moon_note = 'dark sky' if k < 0.25 else 'some moonlight' if k < 0.6 else 'bright Moon'
        trs.append(f'<tr data-start="{start}" data-end="{end}" data-peak="{peak}"><th scope="row">{E(name)}<span class="sw-now" hidden>On now</span></th>'
                   f'<td>{fmt(peak)}</td><td>{fmt(start, False)} to {fmt(end, False)}</td><td>{zhr}</td>'
                   f'<td class="sw-tmoon">{moon_svg(k, wax, 22)}<span>{round(k * 100)}% lit, {moon_note}</span></td>'
                   f'<td>{E(best)}</td><td>{E(parent)}</td></tr>')
    shower_table = (f'<div class="sw-tablewrap" tabindex="0" role="region" aria-label="Meteor shower calendar">'
                    f'<table class="sw-table"><thead><tr><th scope="col">Shower</th><th scope="col">Peak night</th><th scope="col">Active</th>'
                    f'<th scope="col">Meteors an hour at best</th><th scope="col">Moon at peak</th><th scope="col">Where it\'s best</th>'
                    f'<th scope="col">Comes from</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>')

    # ---- Moon, next 30 days
    start = now.replace(hour=0)
    ph = phases(start, 30)
    ph_items = ''.join(
        f'<li>{moon_svg(*lit(t + datetime.timedelta(hours=1)), 40)}<span><b>{PHASE_NAMES[a]}</b>'
        f'<time datetime="{t.strftime("%Y-%m-%dT%H:%MZ")}" data-t="{int(t.timestamp())}">{t.strftime("%a %b %-d, %H:%M")} UTC</time></span></li>'
        for t, a in ph)
    days = []
    for i in range(30):
        d = start + datetime.timedelta(days=i, hours=12)
        k, wax = lit(d)
        days.append(f'<li>{moon_svg(k, wax, 30)}<span class="sw-dd">{d.strftime("%a")}<br>{d.strftime("%b %-d")}</span><span class="sw-dp">{round(k * 100)}%</span></li>')

    cfg = json.dumps({'cities': U('/data/cities.json'), 'astro': ASTRO, 'sat': SATJS, 'planet': U('/tools/was-it-a-planet/'),
                      'showers': [{'k': s[0], 'n': s[1], 's': s[2], 'p': s[3], 'e': s[4], 'z': s[5], 'ra': s[6], 'dec': s[7]} for s in SHOWERS]},
                     separators=(',', ':')).replace('</', '<\\/')

    body = f'''
<section class="sw-hero" data-area="skywatch-hero">
  <div class="wrap">
    <p class="crumb"><a href="{U('/tools/')}">Tools</a> / Skywatch forecast</p>
    <h1>Tonight's skywatch forecast</h1>
    <p class="lede">Is tonight worth going out to look up? Use your location or pick a town anywhere in the world and you'll get a score out of 10,
    the best time to be outside, the clouds hour by hour, the Moon, any meteor shower that's on and when the Space Station flies over.</p>
  </div>
</section>
<section class="sw-tool" data-area="skywatch-tool" aria-label="Get tonight's forecast">
  <div class="wrap">
    <div class="sw-where">
      <button type="button" class="btn sw-locate" id="sw-locate"><svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><circle cx="12" cy="12" r="4" fill="currentColor"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/></svg><span>Use my location</span></button>
      <form class="sw-pick" id="sw-pick" role="search" onsubmit="return false">
        <label for="sw-place" class="sw-label">Or pick a place</label>
        <div class="sw-pick-row"><input type="text" id="sw-place" list="sw-cities" placeholder="Town or city" autocomplete="off" enterkeyhint="search">
        <datalist id="sw-cities"></datalist><button type="submit" class="btn btn-ghost sw-go">Go</button></div>
      </form>
    </div>
    <p class="sw-status" id="sw-status" role="status" aria-live="polite"></p>
    <div class="sw-out" id="sw-out" aria-live="polite" hidden></div>
    <noscript><p class="sw-status">The forecast needs JavaScript. How the score works, the meteor shower dates and the Moon's phases are all below.</p></noscript>
  </div>
</section>
<section class="band band-mist" data-area="how">
  <div class="wrap prose">
    <h2>How the score works</h2>
    <p>Here's the thing about skywatching. Most nights aren't worth the cold, and the ones that are can be gone in an hour when the clouds roll in.
    So I wanted one number that tells you whether to bother. The score is out of 10 and it rates the best three hours of the night, not the whole
    thing, because almost nobody stays out from sunset to sunrise.</p>
    <h3>Clouds, up to 5 points</h3>
    <p>Half the score is clouds because if it's overcast nothing else matters. We pull the hourly cloud forecast from Open-Meteo for the spot you picked.
    A clear sky gets all 5 points and a sky that's completely covered gets none.</p>
    <h3>The Moon, up to 3 points</h3>
    <p>A full Moon high in the sky washes out faint stars and most meteors. A thin crescent, or a Moon that hasn't risen yet, costs you almost nothing.
    The points depend on how much of the Moon is lit and how high it is during your best three hours.</p>
    <h3>Darkness, up to 2 points</h3>
    <p>The sky isn't properly dark until the Sun is 18 degrees below the horizon (astronomers call that the end of astronomical twilight).
    Up north in summer that never happens, so a clear June night in Edmonton or Edinburgh still won't score a 10. Sorry, I don't make the rules.</p>
    <p>One catch. The Moon, darkness and bonus points all shrink as the clouds build up, so a dark moonless night under total cloud still scores low.
    That's on purpose.</p>
    <h3>Bonus points</h3>
    <p>A meteor shower near its peak adds up to 1 point if its radiant (the spot the meteors seem to come from) gets up above your horizon.
    A visible Space Station pass adds half a point. A pass only counts when the station is still in sunlight and you're in the dark, which is the only
    time you can actually see it. The orbit comes from Celestrak and the math runs on your phone. The total tops out at 10.</p>
    <h3>What it can't tell you</h3>
    <p>Light pollution. A 9 in the middle of a city is still a city sky, so get out of town if you can. It also can't tell you about smoke, haze or fog,
    and a cloud forecast is only a forecast, so check again before you head out. Every time on the forecast is shown in the local time
    of the place you picked.</p>
    <p>Saw something odd while you were out there? <a href="{U('/tools/was-it-a-planet/')}">Check if it was a planet first</a>. Venus has fooled
    more people than every other "UFO" put together.</p>
  </div>
</section>
<section class="band band-dark" data-area="showers">
  <div class="wrap">
    <h2 id="meteor-showers">Meteor shower calendar for the next 12 months</h2>
    <p class="sw-p">These are the dates the International Meteor Organization lists, and the peaks can move a day either way from year to year.
    The meteors an hour figure is the best case, under a perfectly dark sky with the radiant straight overhead. Real life is usually a third of that or less.
    A bright Moon on the peak night cuts it down even more, which is why I put the Moon in the table.</p>
    {shower_table}
    <p class="small muted">Dates in UTC. Calendar worked out {today.strftime('%B %-d, %Y')}.</p>
  </div>
</section>
<section class="band band-mist" data-area="moon">
  <div class="wrap">
    <h2 id="moon-phases">Moon phases for the next 30 days</h2>
    <p class="lede-dark">The best nights for faint stuff are the week around the New Moon. Times below are switched to your time zone if your browser allows it.</p>
    <ul class="sw-phases">{ph_items}</ul>
    <h3>How much of the Moon is lit each day</h3>
    <ul class="sw-days" tabindex="0" aria-label="Moon brightness for each of the next 30 days">{"".join(days)}</ul>
    <p class="small muted">Drawn as seen from the Northern Hemisphere. From the south it's flipped left to right.</p>
  </div>
</section>
<section class="band band-dark sw-credits" data-area="sources">
  <div class="wrap">
    <h2>Where the numbers come from</h2>
    <ul class="sw-src">
      <li><b>Cloud forecast</b>: <a href="https://open-meteo.com/">weather data by Open-Meteo.com</a> (CC BY 4.0). We send it your spot rounded to about 1 km and nothing else.</li>
      <li><b>Sun, Moon and twilight</b>: astronomy-engine by Don Cross (MIT licence), running in your browser.</li>
      <li><b>Space Station</b>: satellite.js (MIT licence) with the latest orbit from Celestrak.</li>
      <li><b>Meteor showers</b>: the <a href="https://www.imo.net/resources/calendar/">International Meteor Organization</a> calendar.</li>
    </ul>
    <p>Your location stays on your device apart from that rounded spot for the weather. Picking a place uses a town list on this site, not an outside service.</p>
    <p><a class="btn" href="{U('/tools/was-it-a-planet/')}">Saw something? Check it here first</a> <a class="btn btn-ghost" href="{U('/guides/skywatching/')}">Skywatching guide</a></p>
  </div>
</section>
<script type="application/json" id="sw-config">{cfg}</script>'''

    head = (f'<link rel="stylesheet" href="{U("/static/skywatch.css")}">'
            f'<script src="{U("/static/skywatch.js")}" defer></script>')
    ctx.write('/tools/skywatch/', ctx.page('/tools/skywatch/', "Tonight's skywatch forecast: clouds, Moon, meteor showers and the ISS", body,
                                           'A sky-watching score out of 10 for tonight anywhere in the world: hourly clouds, the Moon, darkness, meteor showers and Space Station passes, plus a meteor shower calendar.',
                                           body_class='skywatch', head_extra=head, viewport_fit=True))
