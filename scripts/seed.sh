#!/usr/bin/env bash
# Seed a reviewed public manifest; preserve existing project files/customizations.
# Usage: bash scripts/seed.sh [TARGET] [--ref REF] [--url URL] [--force]
# --force is retained for compatibility but NEVER bypasses ownership conflicts.
# Requires Python 3.13+, Git, and Bash (explicit Git Bash on native Windows).
# No target Git operations, env sourcing, npm execution or workflow activation.
set -euo pipefail
UPSTREAM_URL="${CLAUDE_API_CONTRACT_URL:-https://github.com/VadayI/claude-api-contract.git}"
REF=main
TARGET=.
while [ "$#" -gt 0 ]; do
  case "$1" in
    --ref) REF="${2:?--ref requires a value}"; shift 2 ;;
    --url) UPSTREAM_URL="${2:?--url requires a value}"; shift 2 ;;
    --force) echo '[seed] --force cannot overwrite customized files; normal preflight applies.'; shift ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    -*) echo "Unknown option: $1" >&2; exit 2 ;;
    *) TARGET="$1"; shift ;;
  esac
done
command -v git >/dev/null || { echo 'Git is required' >&2; exit 2; }
command -v python >/dev/null || { echo 'Python 3.13+ is required' >&2; exit 2; }
python -c 'import sys; sys.exit(0 if sys.version_info >= (3,13) else 2)'
# The clone directory is deliberately retained for review/recovery; no recursive
# shell deletion of computed paths. The printed exact path can be removed later.
CLONE="$(mktemp -d)"
echo "[seed] Temporary reviewed source: $CLONE"
git clone --quiet --depth 1 --branch "$REF" -- "$UPSTREAM_URL" "$CLONE"
# Python handles containment, symlink/junction rejection, all-file preflight and
# source digests. TARGET remains one argv even with spaces/Unicode.
python "$CLONE/scripts/ai/production.py" --target "$TARGET" --apply
echo '[seed] Complete. No remote was created and no workflows were activated.'
echo '[seed] Next: cd to the target; python scripts/ai/launch.py claude (or codex).'
echo '[seed] Use the local doctor/bootstrap procedures. Resolve CI choice and'
echo '[seed] review workflow materialization before the first push (P06 pending).'
