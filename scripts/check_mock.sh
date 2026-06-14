#!/usr/bin/env bash
# scripts/check_mock.sh
#
# GATE: Prism mock smoke test (two-way validation).
#
# Boots the Prism static mock from ./openapi.yml and exercises endpoints. Prism
# validates BOTH the incoming request and the outgoing response against the
# schema, so a wrong fixture or an unexpected status code fails the smoke.
#
# Two modes, auto-detected:
#   - REFERENCE contract (this template's sample: auth + articles) → run the full
#     hardcoded endpoint smoke with the examples/** fixtures.
#   - DERIVED / custom contract (reference paths absent) → run a generic liveness
#     smoke (the mock boots from the contract and serves its routes) and print a
#     reminder to add project-specific endpoint checks. Avoids a false failure on
#     a contract that simply has different resources.
#
# Readiness is probed generically (any HTTP response on the base = up), so the
# gate works for any contract, not only the reference one.
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

# --- wait for readiness (up to ~30s) — generic: any HTTP response = up -------
ready=0
for _ in $(seq 1 30); do
  if ! kill -0 "$PRISM_PID" >/dev/null 2>&1; then
    echo "[mock] FAIL: Prism exited during startup. Log:"
    cat "$LOG"
    exit 1
  fi
  # curl exits 0 as soon as the server returns ANY response (even 404),
  # which means the mock is listening — independent of the contract's paths.
  if curl -s -o /dev/null -m 2 "${BASE}/" 2>/dev/null; then
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

# --- detect the reference contract ------------------------------------------
REFERENCE=0
if grep -qE '^[[:space:]]+/api/v1/auth/login:' openapi.yml \
   && grep -qE '^[[:space:]]+/api/v1/articles:' openapi.yml; then
  REFERENCE=1
fi

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

if [[ "$REFERENCE" -eq 1 ]]; then
  echo "[mock] reference contract detected — full endpoint smoke against ${BASE}"

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
else
  echo "[mock] custom/derived contract — generic liveness smoke against ${BASE}"
  echo "[mock] NOTE: the mock boots and serves the contract. Add project-specific"
  echo "[mock]       endpoint checks (method + fixture + expected code) for full"
  echo "[mock]       coverage, like the reference smoke does for auth + articles."
  # Informational readout: hit each parameterless GET path; report Prism's status.
  paths="$(grep -oE '^  (/[A-Za-z0-9_/.-]+):' openapi.yml | tr -d ' :' | grep -v '{' || true)"
  if [[ -n "$paths" ]]; then
    while IFS= read -r p; do
      [[ -n "$p" ]] || continue
      code="$(curl -s -o /dev/null -w '%{http_code}' -m 10 "${BASE}${p}" -H "$AUTH" 2>/dev/null)"
      printf '  [info] GET %-40s %s\n' "$p" "$code"
    done <<< "$paths"
  fi
fi

# --- summary ----------------------------------------------------------------
if [[ "$FAILS" -gt 0 ]]; then
  echo "[mock] FAIL: ${FAILS} endpoint(s) did not match. Prism log tail:"
  tail -n 20 "$LOG"
  exit 1
fi

echo "[mock] OK: mock smoke passed."
exit 0
