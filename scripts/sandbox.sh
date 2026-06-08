#!/usr/bin/env bash
# scripts/sandbox.sh
#
# Clone this template into a throwaway temp directory and install dependencies.
# Use this to test the template from scratch without touching your working copy.
#
# Usage:
#   bash scripts/sandbox.sh                  # clone → /tmp/cac-sandbox.XXXXXX
#   bash scripts/sandbox.sh /my/path         # clone → /my/path (must not exist)
#   bash scripts/sandbox.sh --ref v0.2.1     # clone a specific tag/branch
#   bash scripts/sandbox.sh --ref main /my/path
#
# Requires: git, node (20.19+), npm.
set -uo pipefail

# --------------------------------------------------------------------------- #
# Parse arguments
# --------------------------------------------------------------------------- #
REF=""
DEST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      REF="$2"; shift 2 ;;
    --ref=*)
      REF="${1#--ref=}"; shift ;;
    -*)
      echo "[sandbox] Unknown flag: $1" >&2; exit 1 ;;
    *)
      DEST="$1"; shift ;;
  esac
done

# --------------------------------------------------------------------------- #
# Resolve repo URL (prefer the origin of the current clone if inside one)
# --------------------------------------------------------------------------- #
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

REPO_URL=""
if git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  REPO_URL="$(git -C "$ROOT" remote get-url origin 2>/dev/null || true)"
fi
if [[ -z "$REPO_URL" ]]; then
  REPO_URL="https://github.com/VadayI/claude-api-contract"
fi

# --------------------------------------------------------------------------- #
# Create or validate destination
# --------------------------------------------------------------------------- #
if [[ -z "$DEST" ]]; then
  DEST="$(mktemp -d -t cac-sandbox.XXXXXX)"
  DEST_WAS_AUTO=true
else
  DEST_WAS_AUTO=false
fi

if [[ "$DEST_WAS_AUTO" == false && -e "$DEST" ]]; then
  echo "[sandbox] ERROR: '$DEST' already exists. Provide a path that does not exist." >&2
  exit 1
fi

# --------------------------------------------------------------------------- #
# Clone
# --------------------------------------------------------------------------- #
echo "[sandbox] Cloning $REPO_URL"
if [[ -n "$REF" ]]; then
  echo "[sandbox]   ref: $REF"
  # Full clone so tags are available for 'npm run breaking'
  git clone --no-local "$REPO_URL" "$DEST" 2>&1
  git -C "$DEST" checkout "$REF" 2>&1
else
  git clone --no-local "$REPO_URL" "$DEST" 2>&1
fi

echo "[sandbox] Cloned to: $DEST"

# --------------------------------------------------------------------------- #
# Install dependencies
# --------------------------------------------------------------------------- #
echo "[sandbox] Installing dependencies..."
bash "$DEST/scripts/install.sh"

# --------------------------------------------------------------------------- #
# Detect environment (writes .claude/memory/env-detect.json)
# --------------------------------------------------------------------------- #
echo "[sandbox] Running environment detection..."
node "$DEST/scripts/detect-env.mjs" 2>/dev/null || true

# --------------------------------------------------------------------------- #
# Done
# --------------------------------------------------------------------------- #
echo ""
echo "[sandbox] ✓ Sandbox ready."
echo "[sandbox]   Path: $DEST"
echo "[sandbox]   Next: cd $DEST"
echo "[sandbox]         npm run validate   # will fail until spec/ is authored (/bootstrap)"
echo "[sandbox]   To clean up: rm -rf $DEST"
