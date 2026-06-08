#!/usr/bin/env bash
# scripts/personalize.sh
#
# Rewrite template identity strings to match a new project cloned from this template.
# Run once after cloning (or invoked by /personalize / /bootstrap in Claude Code).
#
# Usage:
#   bash scripts/personalize.sh                    # resolve from git remote, confirm
#   bash scripts/personalize.sh --dry-run          # show changes without applying them
#   bash scripts/personalize.sh --yes              # skip confirmation prompt
#   bash scripts/personalize.sh --name my-api      # override repo slug (package name)
#   bash scripts/personalize.sh --owner acme       # override GitHub owner / org
#   bash scripts/personalize.sh --title "My API"   # override human-readable project title
#   bash scripts/personalize.sh --description "..."# override package.json description
#   bash scripts/personalize.sh --force            # allow running against VadayI/claude-api-contract
#   bash scripts/personalize.sh --no-tier3         # skip Tier 3 (.claude/ tag rewrites)
#
# Tiers:
#   1 — identity  : VadayI/claude-api-contract URLs · package.json name/desc · README H1
#   2 — reset     : package.json version → 0.0.0 · delete template audit docs
#   3 — deep clean: [claude-api-contract] → [{slug}] in .claude/ frontmatter (~40 files)
#
# NOT touched (requires /personalize prose pass via docs-writer agent):
#   README prose: self-description, consumer names, status line
#   CLAUDE.md consumer section, contract-first.md diagram
#
# Requires: bash, python3, git
set -uo pipefail

# --------------------------------------------------------------------------- #
# Parse flags
# --------------------------------------------------------------------------- #
DRY_RUN=false
YES=false
FORCE=false
TIER3=true
ARG_OWNER=""
ARG_NAME=""
ARG_TITLE=""
ARG_DESCRIPTION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)         DRY_RUN=true; shift ;;
    --yes)             YES=true; shift ;;
    --force)           FORCE=true; shift ;;
    --no-tier3)        TIER3=false; shift ;;
    --owner)           ARG_OWNER="$2"; shift 2 ;;
    --owner=*)         ARG_OWNER="${1#--owner=}"; shift ;;
    --name)            ARG_NAME="$2"; shift 2 ;;
    --name=*)          ARG_NAME="${1#--name=}"; shift ;;
    --title)           ARG_TITLE="$2"; shift 2 ;;
    --title=*)         ARG_TITLE="${1#--title=}"; shift ;;
    --description)     ARG_DESCRIPTION="$2"; shift 2 ;;
    --description=*)   ARG_DESCRIPTION="${1#--description=}"; shift ;;
    *) echo "[personalize] Unknown flag: $1" >&2; exit 1 ;;
  esac
done

# --------------------------------------------------------------------------- #
# Must run from the repo root
# --------------------------------------------------------------------------- #
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ROOT" ]]; then
  echo "[personalize] ERROR: not inside a git repository. Run from the repo root." >&2
  exit 1
fi
cd "$ROOT"

# --------------------------------------------------------------------------- #
# Resolve OWNER and SLUG from git remote origin
# --------------------------------------------------------------------------- #
REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"
DETECTED_OWNER=""
DETECTED_SLUG=""

if [[ -n "$REMOTE_URL" ]]; then
  # Handles https://github.com/OWNER/SLUG[.git] and git@github.com:OWNER/SLUG[.git]
  DETECTED_OWNER="$(echo "$REMOTE_URL" | sed -E \
    's|https://[^/]+/([^/]+)/.*|\1|; t done
     s|git@[^:]+:([^/]+)/.*|\1|
     :done')"
  DETECTED_SLUG="$(echo "$REMOTE_URL" | sed -E \
    's|https://[^/]+/[^/]+/([^/]+)$|\1|; t done
     s|git@[^:]+:[^/]+/([^/]+)$|\1|
     :done')"
  # Strip trailing .git suffix (present in clone URLs)
  DETECTED_SLUG="${DETECTED_SLUG%.git}"
fi

OWNER="${ARG_OWNER:-${DETECTED_OWNER}}"
SLUG="${ARG_NAME:-${DETECTED_SLUG}}"

# Fallback: use the directory name
if [[ -z "$SLUG" ]]; then
  SLUG="$(basename "$ROOT")"
fi
if [[ -z "$OWNER" ]]; then
  OWNER="your-github-username"
fi

# --------------------------------------------------------------------------- #
# Guard: refuse to run against the template itself (without --force)
# --------------------------------------------------------------------------- #
TEMPLATE_OWNER_SLUG="VadayI/claude-api-contract"

if [[ "$OWNER/$SLUG" == "$TEMPLATE_OWNER_SLUG" && "$FORCE" != true ]]; then
  echo "[personalize] ERROR: This script is for projects cloned from the template," >&2
  echo "[personalize]   not for the template itself (VadayI/claude-api-contract)." >&2
  echo "[personalize]   Use --force to override (template development only)." >&2
  exit 1
fi

NEW_OWNER_SLUG="${OWNER}/${SLUG}"

# --------------------------------------------------------------------------- #
# Resolve TITLE and DESCRIPTION
# --------------------------------------------------------------------------- #
TITLE_FROM_PROJECT=""
DESC_FROM_PROJECT=""

if [[ -f "PROJECT.md" ]]; then
  H1="$(grep -m1 '^# ' PROJECT.md | sed 's/^# //' || true)"
  if [[ -n "$H1" && "$H1" != "<Project>"* && "$H1" != "claude-api-contract" ]]; then
    TITLE_FROM_PROJECT="$H1"
  fi
  PURPOSE="$(awk '/^## 1\. Purpose/{found=1; next} found && NF && !/^#/{print; exit}' PROJECT.md || true)"
  if [[ -n "$PURPOSE" && "$PURPOSE" != "<"* ]]; then
    DESC_FROM_PROJECT="$PURPOSE"
  fi
fi

TITLE="${ARG_TITLE:-${TITLE_FROM_PROJECT:-${SLUG}}}"
DESCRIPTION="${ARG_DESCRIPTION:-${DESC_FROM_PROJECT:-"Single source of truth for the ${TITLE} REST API contract."}}"

# --------------------------------------------------------------------------- #
# Summary / confirmation
# --------------------------------------------------------------------------- #
echo ""
echo "[personalize] Proposed identity:"
echo "[personalize]   owner/slug : ${NEW_OWNER_SLUG}"
echo "[personalize]   title      : ${TITLE}"
echo "[personalize]   description: ${DESCRIPTION}"
echo "[personalize]   tier3      : ${TIER3}"
echo ""

if [[ "$DRY_RUN" == true ]]; then
  echo "[personalize] --- DRY RUN (no files will be modified) ---"
  echo ""
fi

if [[ "$DRY_RUN" == false && "$YES" == false ]]; then
  read -r -p "[personalize] Apply? [y/N] " ANSWER
  if [[ "${ANSWER,,}" != "y" ]]; then
    echo "[personalize] Aborted."
    exit 0
  fi
fi

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

# Literal string replacement via python3 — values passed as argv, no shell escaping needed.
# Idempotent: if `old` is not in the file, exits 0 (no-op).
_py_replace() {
  local path="$1" old="$2" new="$3"
  python3 - "$path" "$old" "$new" <<'PYEOF'
import sys, pathlib
path = pathlib.Path(sys.argv[1])
old  = sys.argv[2]
new  = sys.argv[3]
try:
    content = path.read_text(encoding='utf-8')
except Exception as e:
    print(f'[personalize] WARNING: cannot read {path}: {e}', flush=True)
    sys.exit(0)
if old not in content:
    sys.exit(0)  # already replaced or not present — idempotent
path.write_text(content.replace(old, new), encoding='utf-8')
PYEOF
}

# Wrapper: dry-run just reports; apply calls _py_replace.
do_replace() {
  local file="$1" from="$2" to="$3"
  [[ -f "$file" ]] || return 0

  if [[ "$DRY_RUN" == true ]]; then
    if python3 -c "
import sys, pathlib
path=pathlib.Path(sys.argv[1])
try:
    c=path.read_text(encoding='utf-8')
except:
    sys.exit(1)
sys.exit(0 if sys.argv[2] in c else 1)
" "$file" "$from" 2>/dev/null; then
      echo "[personalize] (dry-run) $file"
      echo "[personalize]   FROM: $from"
      echo "[personalize]     TO: $to"
    fi
  else
    _py_replace "$file" "$from" "$to"
    echo "[personalize] updated: $file"
  fi
}

remove_file() {
  local target="$1"
  if [[ -e "$target" ]]; then
    if [[ "$DRY_RUN" == true ]]; then
      echo "[personalize] (dry-run) would remove: $target"
    else
      rm -f -- "$target"
      echo "[personalize] removed: $target"
    fi
  fi
}

# --------------------------------------------------------------------------- #
# Tier 1 — identity replacements
# --------------------------------------------------------------------------- #
echo "[personalize] --- Tier 1: identity ---"

TEMPLATE_DESC="Single source of truth for a REST API contract: TypeSpec -> openapi.yml, linted, mocked, breaking-change gated."

for f in \
    "README.md" \
    ".env.example" \
    ".claude/rules/versioning.md" \
    ".claude/skills/contract-versioning/SKILL.md" \
    "scripts/sandbox.sh" \
  ; do
  do_replace "$f" "$TEMPLATE_OWNER_SLUG" "$NEW_OWNER_SLUG"
done

# README H1 — only the exact heading (not prose mentions of the concept name)
do_replace "README.md" "# claude-api-contract" "# ${TITLE}"

# package.json — name and description
do_replace "package.json" '"name": "claude-api-contract"' "\"name\": \"${SLUG}\""
do_replace "package.json" "\"description\": \"${TEMPLATE_DESC}\"" "\"description\": \"${DESCRIPTION}\""

# package-lock.json — name appears twice (root entry and first packages entry)
do_replace "package-lock.json" '"name": "claude-api-contract"' "\"name\": \"${SLUG}\""

# --------------------------------------------------------------------------- #
# Tier 2 — reset / normalize
# --------------------------------------------------------------------------- #
echo ""
echo "[personalize] --- Tier 2: reset ---"

# Reset version to 0.0.0 (new project, no release yet)
do_replace "package.json" '"version": "0.2.0"' '"version": "0.0.0"'

# Delete template-internal audit docs (irrelevant in derived projects)
for f in docs/AUDIT-*.md; do
  remove_file "$f"
done

# --------------------------------------------------------------------------- #
# Tier 3 — deep .claude/ frontmatter tag rewrite
# --------------------------------------------------------------------------- #
if [[ "$TIER3" == true ]]; then
  echo ""
  echo "[personalize] --- Tier 3: .claude/ frontmatter tags ---"
  while IFS= read -r -d '' f; do
    do_replace "$f" "[claude-api-contract]" "[${SLUG}]"
  done < <(find ".claude/commands" ".claude/agents" ".claude/skills" \
               -name "*.md" -print0 2>/dev/null)
fi

# --------------------------------------------------------------------------- #
# Done
# --------------------------------------------------------------------------- #
echo ""
if [[ "$DRY_RUN" == true ]]; then
  echo "[personalize] Dry-run complete. No files were modified."
  echo "[personalize] Re-run without --dry-run to apply, or use --yes to skip confirmation."
else
  echo "[personalize] Done (token replacements)."
  echo ""
  echo "[personalize] Next: prose pass — run /personalize in Claude Code to rewrite"
  echo "[personalize]   README prose, CLAUDE.md consumer section, contract-first diagram."
  echo "[personalize]   Or run: npm run personalize  for token-only re-run."
fi
