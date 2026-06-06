#!/usr/bin/env bash
# scripts/check_typespec_drift.sh
#
# GATE: TypeSpec drift. Recompiles spec/ to a temp dir and diffs the freshly
# emitted OpenAPI against the committed ./openapi.yml. RED (exit 1) on any
# difference — the canonical contract must always equal what the source emits.
#
# Rationale: openapi.yml is generated from spec/**/*.tsp. If they drift, the
# committed contract no longer reflects its source and the single-source-of-
# truth guarantee is broken.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

if [[ ! -f openapi.yml ]]; then
  echo "[drift] FAIL: ./openapi.yml is missing. Run: npm run api:compile && npm run api:bundle"
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Recompile into the temp dir.
if ! npx --no-install tsp compile spec --emit @typespec/openapi3 --output-dir "$TMP" >/dev/null 2>&1; then
  echo "[drift] FAIL: tsp compile failed. Fix the TypeSpec source in spec/ first."
  exit 1
fi

FRESH="$(find "$TMP" -name 'openapi.yaml' -o -name 'openapi.yml' | head -n1)"
if [[ -z "$FRESH" ]]; then
  echo "[drift] FAIL: emitter produced no OpenAPI file."
  exit 1
fi

if ! diff -u openapi.yml "$FRESH" > "$TMP/diff.txt"; then
  echo "[drift] FAIL: committed openapi.yml differs from spec/ output."
  echo "[drift] Run: npm run api:compile && npm run api:bundle  (then commit openapi.yml)"
  echo "----- diff (committed vs fresh) -----"
  cat "$TMP/diff.txt"
  exit 1
fi

echo "[drift] OK: openapi.yml matches spec/ output."
