#!/usr/bin/env bash
# Deploy the encounters Worker and apply the D1 schema (safe to re-run). Do the one-time steps in
# DEPLOY.md first (D1 id in wrangler.toml, R2 bucket, secrets).
set -euo pipefail
cd "$(dirname "$0")"
set -a; . ~/.config/kitchen-magpie/cloudflare.env; set +a
export CLOUDFLARE_ACCOUNT_ID=f400124b466f991834ee7f05e61ae247
if grep -q '00000000-0000-0000-0000-000000000000' wrangler.toml; then echo "Set database_id in wrangler.toml first (DEPLOY.md step 2)"; exit 1; fi
node gen-creatures.mjs
npx -y wrangler@4 d1 execute encounters --remote --file schema.sql
npx -y wrangler@4 deploy
