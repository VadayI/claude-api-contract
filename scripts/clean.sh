#!/usr/bin/env bash
# scripts/clean.sh
#
# Remove temporary / installation-only files from the contract repo.
#
# Two modes:
#   Default (Class A — always safe, fully regenerable):
#     node_modules/  tsp-output/  .tsp/
#     .claude/memory/env-detect.json  .claude/memory/command-log.jsonl
#
#   --reset-to-clone (Class A + Class B — brings the working copy to fresh-clone
#     state; DESTRUCTIVE — deletes spec/, examples/, openapi.yml and local artifacts):
#     LOCAL/  spec/  examples/  openapi.yml  docs/decisions/0002–0004
#     .claude/memory/endpoints.json  .env  .claude/settings.local.json
#     Requires confirmation (--yes to skip).
#
# Flags:
#   --reset-to-clone   also remove Class B items
#   --yes              skip the confirmation prompt (use in CI / scripting)
#   --dry-run          print what would be deleted; make no changes
#
# Usage:
#   bash scripts/clean.sh
#   bash scripts/clean.sh --dry-run
#   bash scripts/clean.sh --reset-to-clone
#   bash scripts/clean.sh --reset-to-clone --yes
set -uo pipefail

# --------------------------------------------------------------------------- #
# Parse flags
# --------------------------------------------------------------------------- #
RESET_TO_CLONE=false
YES=false
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --reset-to-clone) RESET_TO_CLONE=true ;;
    --yes)            YES=true ;;
    --dry-run)        DRY_RUN=true ;;
    *) echo "[clean] Unknown flag: $arg" >&2; exit 1 ;;
  esac
done

# --------------------------------------------------------------------------- #
# Must run from the repo root
# --------------------------------------------------------------------------- #
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ROOT" ]]; then
  echo "[clean] ERROR: not inside a git repository. Run from the repo root." >&2
  exit 1
fi
cd "$ROOT"

# --------------------------------------------------------------------------- #
# Helper: remove one item with optional dry-run
# --------------------------------------------------------------------------- #
remove() {
  local target="$1"
  if [[ -e "$target" || -L "$target" ]]; then
    if [[ "$DRY_RUN" == true ]]; then
      echo "[clean] (dry-run) would remove: $target"
    else
      rm -rf -- "$target"
      echo "[clean] removed: $target"
    fi
  fi
}

# --------------------------------------------------------------------------- #
# Class A — regenerable build / session artifacts (always safe)
# --------------------------------------------------------------------------- #
if [[ "$DRY_RUN" == true ]]; then
  echo "[clean] --- Class A (build / session artifacts) ---"
fi

remove node_modules
remove tsp-output
remove .tsp
remove .claude/memory/env-detect.json
remove .claude/memory/command-log.jsonl

# --------------------------------------------------------------------------- #
# Class B — template-dev leftovers (only on the template's own working copy)
# --------------------------------------------------------------------------- #
if [[ "$RESET_TO_CLONE" == true ]]; then
  echo ""
  echo "[clean] ⚠  --reset-to-clone: This will DELETE:"
  echo "[clean]    spec/           ← TypeSpec source (the contract!)"
  echo "[clean]    examples/       ← request/response examples"
  echo "[clean]    openapi.yml     ← canonical build output"
  echo "[clean]    LOCAL/          ← local developer notes"
  echo "[clean]    docs/decisions/0002–0004 ← project-level ADRs"
  echo "[clean]    .env            ← local secrets"
  echo "[clean]    .claude/settings.local.json"
  echo "[clean]    .claude/memory/endpoints.json"
  echo "[clean]"
  echo "[clean]    After this, the working copy matches a fresh git clone."
  echo "[clean]    This is IRREVERSIBLE (unless you have git stash / backup)."

  if [[ "$YES" == false && "$DRY_RUN" == false ]]; then
    read -r -p "[clean] Proceed? [y/N] " ANSWER
    if [[ "${ANSWER,,}" != "y" ]]; then
      echo "[clean] Aborted."
      exit 0
    fi
  fi

  if [[ "$DRY_RUN" == true ]]; then
    echo ""
    echo "[clean] --- Class B (template-dev leftovers) ---"
  fi

  remove LOCAL
  remove spec
  remove examples
  remove openapi.yml
  remove .env
  remove .claude/settings.local.json
  remove .claude/memory/endpoints.json
  remove docs/decisions/0002-contract-first-source-of-truth.md
  remove docs/decisions/0003-auth-bearer-jwt-refresh-in-body.md
  remove docs/decisions/0004-version-prefix-auth-paths.md
fi

# --------------------------------------------------------------------------- #
# Done
# --------------------------------------------------------------------------- #
echo ""
if [[ "$DRY_RUN" == true ]]; then
  echo "[clean] Dry-run complete. No files were removed."
else
  echo "[clean] Done."
  if [[ "$RESET_TO_CLONE" == false ]]; then
    echo "[clean] Regenerable with: npm ci  (node_modules)"
    echo "[clean]                   npm run api:compile && npm run api:bundle  (tsp-output, openapi.yml)"
    echo "[clean]                   SessionStart hook  (env-detect.json)"
  fi
fi
