# Section modules

Each `*.py` here is loaded by `site/build.py` after the core pages and must define `build(ctx)`.

`ctx` fields: ROOT, OUT, STATIC, SITE_URL, BASE, page(path, title, body_html, desc='', body_class='', head_extra=''),
write(path, html), url(path), esc(text), icon(name, cls), slugify(text), badge(creature, size), creature_card(creature),
creatures (list), by_slug (dict), bluebook (list), military (list), CATS, MONTHS.

Rules: keep data in `data/<section>*.json`, styles in `site/static/<section>.css` (load it via page(..., head_extra=...)),
scripts in `site/static/<section>.js`. Reuse the classes in site.css (band band-dark / band-mist, wrap, lede, btn,
crit-grid, timeline, signs, facts, prose) so every page looks like one site. Never edit build.py or site.css.
