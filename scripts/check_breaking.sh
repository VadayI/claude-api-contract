#!/usr/bin/env bash
# scripts/check_breaking.sh
#
# GATE: breaking-change detection. Runs oasdiff between the previous release
# tag's openapi.yml and the working-tree openapi.yml. `--fail-on ERR` makes
# oasdiff exit 1 on any ERR-level breaking change — that is the major-bump gate
# (decision #7 / D3). Consciously allowed breaking changes go through an
# --err-ignore config, not by removing this gate.
#
# Usage: scripts/check_breaking.sh [base-ref]
#   base-ref defaults to the latest semver tag (vX.Y.Z).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

if ! command -v oasdiff >/dev/null 2>&1; then
  echo "[breaking] FAIL: oasdiff not installed. See scripts/setup-wsl.sh or https://github.com/oasdiff/oasdiff"
  exit 1
fi

if [[ ! -f openapi.yml ]]; then
  echo "[breaking] FAIL: ./openapi.yml is missing."
  exit 1
fi

BASE_REF="${1:-}"
if [[ -z "$BASE_REF" ]]; then
  BASE_REF="$(git tag --list 'v*' --sort=-version:refname | head -n1)"
fi

if [[ -z "$BASE_REF" ]]; then
  echo "[breaking] SKIP: no previous v* tag found — nothing to compare against (first release)."
  exit 0
fi

BASE_FILE="$(mktemp)"
trap 'rm -f "$BASE_FILE"' EXIT
if ! git show "$BASE_REF:openapi.yml" > "$BASE_FILE" 2>/dev/null; then
  echo "[breaking] SKIP: $BASE_REF has no openapi.yml at root — nothing to compare."
  exit 0
fi

IGNORE=()
[[ -f .oasdiff-ignore.txt ]] && IGNORE=(--err-ignore .oasdiff-ignore.txt)

echo "[breaking] comparing $BASE_REF -> working tree (openapi.yml)"
if ! oasdiff breaking "$BASE_FILE" openapi.yml --fail-on ERR "${IGNORE[@]}"; then
  echo "[breaking] FAIL: ERR-level breaking change vs $BASE_REF. Requires a MAJOR version bump."
  exit 1
fi

echo "[breaking] OK: no ERR-level breaking changes vs $BASE_REF."
