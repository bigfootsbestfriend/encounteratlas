# Encounter reports + "Real or hoax?" voting: deploy checklist

Nothing here has been deployed. No D1 database, Turnstile widget, DNS record or email exists yet.
Everything was built and tested locally (`wrangler dev --local`).

## What it is

- **Worker `encounters`** (`src/index.js`) at `https://api.encounteratlas.com`: the reports API, email sign-in,
  and voting. Photos and videos are links only; nothing is uploaded or stored.
- **D1 `encounters`** (`schema.sql`): users, reports (with photo links), votes, items (freeze/flags), flags, hits (rate limits), used_links.
- **Moderation page**: `https://api.encounteratlas.com/mod`. It is on the Worker, not the static site, and uses the `MOD_PASSWORD` secret.
- **Site pages** (`site/sections/reports.py`): `/report/` (the form) and `/reports/` (list; `?id=` one report; `?me=1` your reports; `?signin=` link landing).

## Steps for Mike (in order)

1. **R2:** not needed. Photo uploads are off (links only).
2. **D1:** run `npx wrangler@4 d1 create encounters`. Paste the printed `database_id` into `wrangler.toml`.
3. **Turnstile:** in the dashboard, go to Turnstile and add a widget named "Encounter Atlas". Hostnames: `encounteratlas.com`, plus the
   GitHub Pages preview host if you use it. Mode: Managed. This gives you:
   - the **site key** (public). Put it in `wrangler.toml` `TURNSTILE_SITEKEY`, **and** build the site with
     `TURNSTILE_SITEKEY=<key>` (env var read by `site/sections/reports.py`; otherwise change the default there).
     The current default `1x00000000000000000000AA` is Cloudflare's always-pass test key. Real submissions fail with it.
   - the **secret key**: `npx wrangler@4 secret put TURNSTILE_SECRET`
4. **Resend:** add and verify `encounteratlas.com` as a sending domain. That means adding the SPF/DKIM (and optionally DMARC) DNS records that
   Resend shows; `newsletter/setup_resend.py` already does this for other domains. Then
   `npx wrangler@4 secret put RESEND_API_KEY` (a sending-access key is enough). The sender is `FROM` in wrangler.toml
   (`hello@encounteratlas.com`).
5. **Other secrets:**
   - `npx wrangler@4 secret put TOKEN_SECRET`: a long random value (`openssl rand -base64 48`). It signs sign-in links, sessions and
     IP hashes. Changing it later signs everyone out.
   - `npx wrangler@4 secret put MOD_PASSWORD`: the moderation page password.
   - Optional: set `OWNER_EMAIL` in wrangler.toml to get an email for every new report.
6. **DNS / route:** `api.encounteratlas.com` needs the domain's zone on Cloudflare. Then uncomment the `routes` line in wrangler.toml.
   Until then the Worker answers at `encounters.<account>.workers.dev`. Build the site with `EA_API=<that URL>` meanwhile.
7. **Deploy:** run `./deploy.sh`. It refuses to run while the placeholder database id is still in place. It regenerates `src/creatures.js` from
   `data/creatures.json`, applies `schema.sql` (safe to re-run) and deploys.
8. **CORS:** `SITE` and `EXTRA_ORIGINS` in wrangler.toml must list every origin that serves the pages. The GitHub Pages preview origin is a guess
   (now `https://www.encounteratlas.com`; the github.io preview redirects to the apex), so check it.
9. **Site build:** set `EA_API` and `TURNSTILE_SITEKEY` in the build workflow's environment (both default to production values except the test site key).
10. **Before taking real reports:** the privacy page (/privacy/) is done. A DMCA agent ($6, copyright.gov) is optional with links only.
11. **Smoke test in production:** submit a report, approve it at `/mod`, vote with two accounts, then reject it again.

Not done (outside my files, for whoever owns them):
- A nav link to `/reports/` (build.py `NAV` currently points "Report" at `/report/`).
- Report dots on the main `/map/` (map.js). Add a source `{type:'geojson', data: EA_API + '/api/reports.geojson'}`. Properties per feature:
  `id` (link to `/reports/?id=<id>`), `c` creature slug, `n` creature name, `t` place, `d` date.

## Local development

```
cd worker
cp .dev.vars.example .dev.vars        # DEV=1, EMAIL_MODE=log, Turnstile test secret, local MOD_PASSWORD
npm run dev                           # gen creatures + local schema + wrangler dev --local on :8787
node test/seed.mjs                    # optional: 4 demo reports (labelled [Demo report]), 12 votes, 1 pending
EA_API=http://127.0.0.1:8787 OUT_DIR=/tmp/site python3 ../site/build.py && python3 -m http.server 8825 -d /tmp/site
```
`.dev.vars` sets `SITE=http://127.0.0.1:8825`, so sign-in links point at the local site. With `EMAIL_MODE=log` no email is sent:
the API returns `dev_link` and the page shows a "(dev: open link)" link. `DEV=1` also allows the `x-test-ip` header and the
offline Turnstile test-secret shortcut. **Never set DEV, EMAIL_MODE or the test secret in production.**

Tests: `npm test` (or `bash test/run.sh`). This starts a throwaway Worker on :8788 with a fresh database and small vote limits,
then runs `test/api.test.mjs`.

## Security notes

- **Photos and videos: links only.** Nothing is uploaded; the API refuses file parts. Photo links must be `https://` with a real
  hostname (no IP addresses, localhost, credentials or ports), at most 500 characters and 5 per report; the `#fragment` is dropped.
  They are shown as plain "View photo on <host>" buttons with `rel="noopener nofollow ugc noreferrer"`, never embedded.
  Moderators check each link before approving. `src/jpeg.js` and the `/img` route are left from the upload version; `/img` always 404s
  without a PHOTOS binding.
- **Location.** The exact point is stored for moderators only. Every public output (report JSON, GeoJSON, list) uses a point snapped to a
  ~5 km grid. Snapping is deterministic, so repeated edits can't be averaged out. The place name the user types is public, and the form says so.
- **Accounts.** These are HMAC-signed magic links: single use and valid 30 minutes. They point at the site's `/reports/?signin=`, which POSTs the token,
  so email link-scanners can't use them up. Sessions are signed bearer tokens (90 days) kept in localStorage.
- **Rate limits** (all can be changed with Worker vars):
  - Reports: 3/hour and 10/day per IP; 6/day per account.
  - Sign-in emails: 6/hour per IP and 3/hour per address.
  - Votes: 40/hour and 200/day per account; 60/hour per IP.
  - Flags: 30/day.
  - Moderator login: 8 tries per 15 minutes.
- **Voting.**
  - One vote per account per item: `UNIQUE(item, user_id)` in D1.
  - Turnstile on the first vote. After that, a 30-minute signed "pass" so each vote doesn't need a new challenge.
  - Vote weight is set when the vote is cast:
    - under 1 day old: 0.2 (0.5 if the account has an approved report or 10+ votes)
    - under 7 days old: 0.5 (0.8 if active)
    - otherwise: 1.
  - Results are hidden until you have voted **and** there are 10+ counted votes (`VOTE_THRESHOLD`).
  - Network bursts: after 3 votes on one item from one /24 (IPv6 /48) in 24 hours, further votes are held and the item is flagged `burst`.
  - Swing: once an item has 10+ votes older than an hour, 5+ new votes in the last hour that shift any choice by 25+ points freeze it
    and flag it `swing`. A brand-new item with 40+ votes in an hour is flagged `surge` (not frozen).
  - AI flags: "Looks AI-generated?" and Misidentified votes with reason "CGI or AI" put the item at the top of the moderators' Flagged tab.
  - Moderator tools: approve, reject or unpublish; unfreeze; clear a flag; count or void held votes; void votes from the last N minutes.
- **Moderation page.** The session is an HttpOnly, Secure, SameSite=Strict cookie scoped to `/mod`. POSTs need a same-origin `Origin` header.
  The page has a strict CSP and `frame-ancestors 'none'`, and every value is HTML-escaped.
- **Edits.** Owner edits send a report back to `pending`. Withdrawing removes the report.
