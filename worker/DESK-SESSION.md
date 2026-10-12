# Desk session: switch on reports (about 20 minutes)

Mike approved steps 1-6 on 2026-10-12, to be done together at the desk. Nothing is created before then.
Step 7 (DMCA agent, privacy note) is separate and still pending.

Who does what: **Mike** clicks in a browser. **Claude** runs commands in the terminal.
DNS and domain changes trigger a permission prompt in Claude's session, so Mike approves those at the terminal
(or adds the records himself in the Cloudflare dashboard).

## 0. Before starting (Claude, 1 min)
- `cd worker && npm test`: should say 64 passed.
- Check the Cloudflare API token can edit Workers, D1, R2 and Turnstile for account f400124b…
  If it can't, Mike adds those permissions at dash.cloudflare.com → My Profile → API Tokens → edit token.

## 1. R2 photo storage (Mike 2 min, Claude 1 min)
- **Mike:** dash.cloudflare.com → R2 Object Storage → "Enable R2". This needs a payment method on file; the free tier covers 10 GB and 1M writes a month.
- **Claude:** `npx wrangler@4 r2 bucket create encounter-photos`

## 2. Database (Claude, 1 min)
- **Claude:** `npx wrangler@4 d1 create encounters`, paste the `database_id` into `wrangler.toml`

## 3. Turnstile spam check (Mike 2 min)
- **Mike:** dash → Turnstile → Add widget. Name: Encounter Atlas. Hostnames: `encounteratlas.com` and `bigfootsbestfriend.github.io`. Mode: Managed.
- **Mike:** paste the **site key** into chat (it's public). Paste the **secret key** only at the terminal prompt in the next step, never in chat.
- **Claude:** put the site key in `wrangler.toml` and in the deploy workflow env (`TURNSTILE_SITEKEY`).
  Then Claude runs `npx wrangler@4 secret put TURNSTILE_SECRET` and Mike pastes the secret into the prompt.

## 4. Sign-in email via Resend (Mike 3 min, Claude 2 min)
- **Claude:** add domain `encounteratlas.com` in Resend through the API (same as newsletter/setup_resend.py), then
  print the SPF/DKIM records. **Mike** approves the DNS prompt (or adds the records in the dashboard).
- **Claude:** wait for Resend to verify, then `secret put RESEND_API_KEY` (a sending-only key, created through the API).

## 5. Secrets (Claude, 1 min; Mike chooses a password)
- **Claude:** `openssl rand -base64 48 | npx wrangler@4 secret put TOKEN_SECRET` (the value never appears on screen).
- **Mike:** types a moderator password at the `secret put MOD_PASSWORD` prompt.
- Optional: set `OWNER_EMAIL` to get one email per new report (recommended while volume is low).

## 6. API address, deploy, switch on (Claude 5 min; Mike approves the domain prompt)
- **Claude:** uncomment the `api.encounteratlas.com` custom-domain route in `wrangler.toml`. This creates a DNS record, so **Mike approves** it.
- **Claude:** `./deploy.sh`, then check that `https://api.encounteratlas.com/api/reports.geojson` returns an empty FeatureCollection.
- **Claude:** set repo variable `EA_API=https://api.encounteratlas.com` and pass it plus `TURNSTILE_SITEKEY` into the build in deploy.yml.
  Then push. The `/report/` form and `/reports/` go live and "opens soon" disappears.
- **Smoke test together:** Mike files a test report from his phone, approves it at `https://api.encounteratlas.com/mod`,
  votes from two accounts, then rejects it.

## 7. Before launch (separate approval)
- DMCA agent: copyright.gov/dmca-directory, $6, in Mike's name and address. **Mike only.**
- A privacy note page (Claude drafts it, Mike approves): what is stored (email, exact location seen only by moderators, hashed IP) and who sees it.
