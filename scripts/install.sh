#!/usr/bin/env bash
# scripts/install.sh
#
# Install the contract toolchain locally (idempotent).
#   - npm dependencies (TypeSpec, Spectral, Prism) via `npm ci` (or `npm install`).
#   - oasdiff (Go binary) — checked, with install hints if missing.
#
# Run from the repo root: bash scripts/install.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

if ! command -v node >/dev/null 2>&1; then
  echo "[install] ERROR: node not found. Install Node 20.19+ (see scripts/setup-wsl.sh) and re-run."
  exit 1
fi

echo "[install] Installing npm dependencies..."
if [[ -f package-lock.json ]]; then
  npm ci || npm install
else
  npm install
fi

if command -v oasdiff >/dev/null 2>&1; then
  echo "[install] oasdiff present: $(oasdiff --version 2>/dev/null | head -n1)"
else
  echo "[install] NOTE: oasdiff not installed (needed for the breaking-change gate)."
  echo "[install]   Go:    go install github.com/oasdiff/oasdiff@latest"
  echo "[install]   Brew:  brew tap oasdiff/homebrew-oasdiff && brew install oasdiff"
  echo "[install]   Or download a release binary: https://github.com/oasdiff/oasdiff/releases"
fi

echo "[install] Done. Try: npm run validate"
