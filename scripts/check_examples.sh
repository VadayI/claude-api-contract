#!/usr/bin/env bash
# scripts/check_examples.sh
#
# GATE: example validity. Spectral's spectral:oas ruleset includes
# oas3-valid-schema-example / oas3-valid-media-type-examples, which validate
# every `example`/`examples` payload against its schema. Running spectral with
# those rules is the contract-level guarantee that examples in openapi.yml (and
# the inline examples that feed the Prism mock) conform to the schema.
#
# Standalone example files under examples/** are validated by Prism's two-way
# validation during the mock smoke test (scripts run by /mock + CI).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

if [[ ! -f openapi.yml ]]; then
  echo "[examples] FAIL: ./openapi.yml is missing. Run: npm run api:compile && npm run api:bundle"
  exit 1
fi

RULESET=".spectral.yaml"
[[ -f "$RULESET" ]] || RULESET="spectral:oas"

# Fail only on the example-validity rules; full style lint is the separate `npm run lint` gate.
if ! npx --no-install spectral lint openapi.yml --ruleset "$RULESET" \
      --fail-severity warn > /dev/null 2>&1; then
  echo "[examples] Spectral reported problems (examples and/or style). Full output:"
  npx --no-install spectral lint openapi.yml --ruleset "$RULESET"
  exit 1
fi

echo "[examples] OK: examples validate against their schemas."
