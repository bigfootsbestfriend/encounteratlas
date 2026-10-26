#!/usr/bin/env bash
# Runs the API tests against a throwaway local Worker (fresh D1 under .wrangler/test-state).
# Nothing touches Cloudflare: wrangler dev --local, Turnstile test secret, emails logged not sent.
set -euo pipefail
cd "$(dirname "$0")/.."
STATE=.wrangler/test-state
# WR_CMD="node path/to/wrangler.js" if npx is slow to resolve wrangler@4.
export WR_CMD=${WR_CMD:-npx -y wrangler@4}
PORT=${PORT:-8788}
rm -rf "$STATE"
[ -f .dev.vars ] || cp .dev.vars.example .dev.vars
node gen-creatures.mjs
$WR_CMD d1 execute encounters --local --persist-to "$STATE" --file schema.sql > /dev/null
# Small limits so the rate-limit tests don't need hundreds of requests.
$WR_CMD dev --local --ip 127.0.0.1 --port "$PORT" --persist-to "$STATE" \
  --var VOTE_USER_HOUR:4 --var VOTE_IP_HOUR:6 --var REVIEW_EMAIL:review@example.test --var REVIEW_CODE:test-review-code > "$STATE.log" 2>&1 &
WR=$!
trap 'kill $WR 2>/dev/null; wait $WR 2>/dev/null || true' EXIT
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/api/config" > /dev/null && break; sleep 0.5; done
API="http://127.0.0.1:$PORT" PERSIST="$STATE" node test/api.test.mjs
API="http://127.0.0.1:$PORT" node test/nearby.test.mjs
API="http://127.0.0.1:$PORT" PERSIST="$STATE" LOG="$STATE.log" node test/push.test.mjs
node test/fcm.test.mjs
API="http://127.0.0.1:$PORT" node test/motd.test.mjs
API="http://127.0.0.1:$PORT" LOG="$STATE.log" node test/clusters.test.mjs
