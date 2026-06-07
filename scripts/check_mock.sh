#!/usr/bin/env bash
# scripts/check_mock.sh
#
# GATE: Prism mock smoke test (two-way validation).
#
# Boots the Prism static mock from ./openapi.yml and exercises every endpoint
# with a realistic request (the examples/** fixtures). Prism validates BOTH the
# incoming request and the outgoing response against the schema, so a wrong
# fixture or an unexpected status code fails the smoke. Confirms:
#   - the mock comes up from the canonical contract,
#   - public auth endpoints respond without a token,
#   - secured article endpoints enforce bearer auth (401 without it),
#   - documented success status codes are returned.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

PORT="${PRISM_PORT:-4010}"
BASE="http://127.0.0.1:${PORT}"
LOG="$(mktemp -t prism-mock.XXXXXX.log)"
CT='Content-Type: application/json'
AUTH='Authorization: Bearer testtoken'

if [[ ! -f openapi.yml ]]; then
  echo "[mock] FAIL: ./openapi.yml is missing. Run: npm run api:compile && npm run api:bundle"
  exit 1
fi

# --- boot Prism in the background -------------------------------------------
npx --no-install prism mock openapi.yml -p "$PORT" > "$LOG" 2>&1 &
PRISM_PID=$!

cleanup() {
  kill "$PRISM_PID" >/dev/null 2>&1
  wait "$PRISM_PID" 2>/dev/null
  rm -f "$LOG"
}
trap cleanup EXIT INT TERM

# --- wait for readiness (up to ~30s) ----------------------------------------
ready=0
for _ in $(seq 1 30); do
  if ! kill -0 "$PRISM_PID" >/dev/null 2>&1; then
    echo "[mock] FAIL: Prism exited during startup. Log:"
    cat "$LOG"
    exit 1
  fi
  if curl -s -o /dev/null -m 2 -X POST "${BASE}/api/v1/auth/login" \
        -H "$CT" -d @examples/auth/login.request.json 2>/dev/null; then
    ready=1
    break
  fi
  sleep 1
done

if [[ "$ready" -ne 1 ]]; then
  echo "[mock] FAIL: Prism did not become ready on ${BASE} within 30s. Log:"
  cat "$LOG"
  exit 1
fi

# --- endpoint checks --------------------------------------------------------
FAILS=0

# check <label> <expected-code> <curl-args...>
check() {
  local label="$1" expected="$2"; shift 2
  local got
  got="$(curl -s -o /dev/null -w '%{http_code}' -m 10 "$@")"
  if [[ "$got" == "$expected" ]]; then
    printf '  [ok]   %-34s %s\n' "$label" "$got"
  else
    printf '  [FAIL] %-34s expected %s, got %s\n' "$label" "$expected" "$got"
    FAILS=$((FAILS + 1))
  fi
}

echo "[mock] smoke against ${BASE}"

# Public auth endpoints (no token required).
check "POST /api/v1/auth/register" 201 -X POST "${BASE}/api/v1/auth/register" \
  -H "$CT" -H 'Prefer: code=201' -d @examples/auth/register.request.json
check "POST /api/v1/auth/login" 200 -X POST "${BASE}/api/v1/auth/login" \
  -H "$CT" -H 'Prefer: code=200' -d @examples/auth/login.request.json
check "POST /api/v1/auth/refresh" 200 -X POST "${BASE}/api/v1/auth/refresh" \
  -H "$CT" -H 'Prefer: code=200' -d @examples/auth/refresh.request.json
check "POST /api/v1/auth/token" 200 -X POST "${BASE}/api/v1/auth/token" \
  -H "$CT" -H 'Prefer: code=200' -d @examples/auth/token.request.json
check "POST /api/v1/auth/logout" 204 -X POST "${BASE}/api/v1/auth/logout" \
  -H "$AUTH" -H "$CT" -d @examples/auth/refresh.request.json

# Secured article endpoints — bearer required (Prism enforces security).
check "GET /api/v1/articles (no auth=401)" 401 "${BASE}/api/v1/articles"
check "GET /api/v1/articles" 200 "${BASE}/api/v1/articles" -H "$AUTH"
check "POST /api/v1/articles" 201 -X POST "${BASE}/api/v1/articles" \
  -H "$AUTH" -H "$CT" -H 'Prefer: code=201' -d @examples/articles/create.request.json
check "GET /api/v1/articles/{id}" 200 "${BASE}/api/v1/articles/art_1" \
  -H "$AUTH" -H 'Prefer: code=200'
check "PATCH /api/v1/articles/{id}" 200 -X PATCH "${BASE}/api/v1/articles/art_1" \
  -H "$AUTH" -H "$CT" -H 'Prefer: code=200' -d @examples/articles/update.request.json
check "DELETE /api/v1/articles/{id}" 204 -X DELETE "${BASE}/api/v1/articles/art_1" \
  -H "$AUTH" -H 'Prefer: code=204'

# --- summary ----------------------------------------------------------------
if [[ "$FAILS" -gt 0 ]]; then
  echo "[mock] FAIL: ${FAILS} endpoint(s) did not match. Prism log tail:"
  tail -n 20 "$LOG"
  exit 1
fi

echo "[mock] OK: all endpoints returned their expected status codes."
exit 0
