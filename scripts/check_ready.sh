#!/usr/bin/env bash
# scripts/check_ready.sh
#
# GATE: contract readiness — answers "is this contract ready for backend and
# frontend to start parallel work against?". Runs all five quality gates plus
# artifact presence checks, then warns if no release tag exists yet.
#
# Passes (exit 0) when:
#   1. npm run validate      — compile + TypeSpec drift + Spectral lint + examples
#   2. check_mock.sh         — Prism smoke (boots mock, exercises all endpoints)
#   3. check_breaking.sh     — oasdiff ERR gate (SKIP on first release is a pass)
#   4. Artifacts present     — openapi.yml + .claude/memory/endpoints.json (non-empty)
#   4b. Registry coverage    — npm run check:endpoints (every openapi.yml operation is in endpoints.json)
#   5. Auth paths present    — /api/v1/auth/login, /api/v1/auth/refresh, /api/v1/auth/token
#
# WARN (non-blocking, exit 0 otherwise) when HEAD is not on any v* tag.
#
# Usage: bash scripts/check_ready.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

FAILS=0

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
ok()   { echo "[ready] OK: $*"; }
fail() { echo "[ready] FAIL: $*"; FAILS=$((FAILS + 1)); }
warn() { echo "[ready] WARN: $*"; }

# ---------------------------------------------------------------------------
# 1. npm run validate (compile + drift + spectral + examples)
# ---------------------------------------------------------------------------
echo "[ready] --- 1/5  npm run validate ---"
if npm run validate --silent; then
  ok "npm run validate passed."
else
  fail "npm run validate failed. Run: npm run validate  (for details)."
fi

# ---------------------------------------------------------------------------
# 2. Prism mock smoke test
# ---------------------------------------------------------------------------
echo "[ready] --- 2/5  Prism mock smoke (check_mock.sh) ---"
if bash scripts/check_mock.sh; then
  ok "Prism mock smoke passed."
else
  fail "Prism mock smoke failed. Run: bash scripts/check_mock.sh  (for details)."
fi

# ---------------------------------------------------------------------------
# 3. Breaking-change gate (SKIP on first release counts as pass)
# ---------------------------------------------------------------------------
echo "[ready] --- 3/5  breaking-change gate (check_breaking.sh) ---"
if bash scripts/check_breaking.sh; then
  ok "Breaking-change gate passed."
else
  fail "Breaking-change gate failed. Run: bash scripts/check_breaking.sh  (for details). Requires a MAJOR version bump or an entry in .oasdiff-ignore.txt."
fi

# ---------------------------------------------------------------------------
# 4. Artifact checks
# ---------------------------------------------------------------------------
echo "[ready] --- 4/5  artifact checks ---"

# openapi.yml present
if [[ -f openapi.yml ]]; then
  ok "openapi.yml present."
else
  fail "openapi.yml missing. Run: npm run api:compile && npm run api:bundle"
fi

# .claude/memory/endpoints.json present and non-empty (contains at least one endpoint object)
ENDPOINTS_JSON=".claude/memory/endpoints.json"
if [[ ! -f "$ENDPOINTS_JSON" ]]; then
  fail "$ENDPOINTS_JSON missing. The api-architect agent must record endpoints before the contract is ready."
elif ! grep -q '"method"' "$ENDPOINTS_JSON"; then
  fail "$ENDPOINTS_JSON exists but contains no endpoint entries (empty array or malformed). Run the pipeline to populate it."
else
  ok "$ENDPOINTS_JSON present and non-empty."
fi

# ---------------------------------------------------------------------------
# 4b. Endpoints registry coverage (mirror CI verification — verification.md)
# ---------------------------------------------------------------------------
echo "[ready] --- 4b   endpoints registry coverage (check:endpoints) ---"
if [[ -f openapi.yml && -f "$ENDPOINTS_JSON" ]]; then
  if npm run check:endpoints --silent; then
    ok "endpoints registry covers all operations."
  else
    fail "endpoints registry incomplete. Run: npm run check:endpoints  (an operation in openapi.yml has no entry in $ENDPOINTS_JSON)."
  fi
else
  warn "registry coverage skipped — openapi.yml or $ENDPOINTS_JSON absent (counted above)."
fi

# ---------------------------------------------------------------------------
# 5. Auth endpoints present in openapi.yml
# ---------------------------------------------------------------------------
echo "[ready] --- 5/5  auth endpoint presence ---"
if [[ -f openapi.yml ]]; then
  for path in "/api/v1/auth/login" "/api/v1/auth/refresh" "/api/v1/auth/token"; do
    if grep -qE "^\s+${path}\s*:" openapi.yml; then
      ok "auth path $path found."
    else
      fail "auth path $path missing from openapi.yml. The mock cannot issue tokens without it. Fix spec/auth.tsp and recompile."
    fi
  done
else
  fail "openapi.yml missing — auth path check skipped (already counted above)."
fi

# ---------------------------------------------------------------------------
# tag warning (non-blocking)
# ---------------------------------------------------------------------------
if ! git tag --points-at HEAD | grep -q '^v'; then
  warn "HEAD is not on any v* release tag — consumers have no CONTRACT_VERSION to pin."
  warn "When all gates are green, run /release (or: npm run validate && oasdiff changelog ... && git tag vX.Y.Z && git push origin vX.Y.Z)."
fi

# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------
echo ""
if [[ "$FAILS" -eq 0 ]]; then
  ok "contract is ready — backend and frontend can start."
  exit 0
else
  echo "[ready] FAIL: ${FAILS} check(s) failed."
  exit 1
fi
