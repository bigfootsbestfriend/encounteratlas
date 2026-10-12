#!/usr/bin/env bash
# Runs the API tests against a throwaway local Worker (fresh D1 + R2 under .wrangler/test-state).
# Nothing touches Cloudflare: wrangler dev --local, Turnstile test secret, emails logged not sent.
set -euo pipefail
cd "$(dirname "$0")/.."
STATE=.wrangler/test-state
PORT=${PORT:-8788}
rm -rf "$STATE"
[ -f .dev.vars ] || cp .dev.vars.example .dev.vars
node gen-creatures.mjs
npx -y wrangler@4 d1 execute encounters --local --persist-to "$STATE" --file schema.sql > /dev/null
# Small limits so the rate-limit tests don't need hundreds of requests.
npx -y wrangler@4 dev --local --ip 127.0.0.1 --port "$PORT" --persist-to "$STATE" \
  --var VOTE_USER_HOUR:4 --var VOTE_IP_HOUR:6 > "$STATE.log" 2>&1 &
WR=$!
trap 'kill $WR 2>/dev/null; wait $WR 2>/dev/null || true' EXIT
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/api/config" > /dev/null && break; sleep 0.5; done
API="http://127.0.0.1:$PORT" PERSIST="$STATE" node test/api.test.mjs
