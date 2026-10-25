#!/usr/bin/env bash
# One-time (2026-10-25): add reports.podcast_ok to the live D1, then deploy the Worker that reads/writes it.
# Safe to re-run: the ALTER is skipped if the column already exists.
set -euo pipefail
cd "$(dirname "$0")"
set -a; . ~/.config/kitchen-magpie/cloudflare.env; set +a
export CLOUDFLARE_ACCOUNT_ID=f400124b466f991834ee7f05e61ae247
if npx -y wrangler@4 d1 execute encounters --remote --json --command "SELECT name FROM pragma_table_info('reports') WHERE name='podcast_ok'" | grep -q podcast_ok; then
  echo "podcast_ok already there"
else
  npx -y wrangler@4 d1 execute encounters --remote --command "ALTER TABLE reports ADD COLUMN podcast_ok INTEGER NOT NULL DEFAULT 0"
fi
bash ./deploy.sh
