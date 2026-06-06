#!/usr/bin/env bash
# scripts/session-start.sh
#
# SessionStart hook entrypoint — run automatically when Claude Code starts a session.
#
# Order of operations:
#   1. Clear a stale empty .git/index.lock if the project is on a /mnt path (WSL2 safety).
#   2. MANDATORY: run detect-env.mjs to write .claude/memory/env-detect.json.
#   3. SAFE: seed .env from .env.example if .env is missing.
#   4. OPT-IN: npm install if CLAUDE_CONTRACT_AUTO_INSTALL=1 and node_modules is absent.
#
# set -uo pipefail, but every step is wrapped so a failure never aborts the
# session (Claude Code must always start). Never prints secrets.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Step 1 — clear stale empty .git/index.lock on /mnt paths (WSL2 quirk) ---
(
  LOCK_FILE="$PROJECT_ROOT/.git/index.lock"
  if [[ "$PROJECT_ROOT" == /mnt/* ]] && [[ -f "$LOCK_FILE" ]] && [[ ! -s "$LOCK_FILE" ]]; then
    rm -f "$LOCK_FILE" && echo "[session-start] Removed stale empty .git/index.lock"
  fi
) || true

# --- Step 2 — MANDATORY: write .claude/memory/env-detect.json ---
(
  if command -v node >/dev/null 2>&1; then
    node "$SCRIPT_DIR/detect-env.mjs"
  else
    echo "[session-start] ERROR: 'node' not found on PATH."
    echo "[session-start] Node 20.19+ is required. Install via nvm (scripts/setup-wsl.sh) or https://nodejs.org"
    echo "[session-start] env-detect.json was NOT written — /doctor will report missing env data."
  fi
) || echo "[session-start] WARNING: detect-env.mjs failed (non-fatal)"

# --- Step 3 — SAFE: seed .env from .env.example if .env is missing ---
(
  if [[ ! -f "$PROJECT_ROOT/.env" ]] && [[ -f "$PROJECT_ROOT/.env.example" ]]; then
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo "[session-start] .env seeded from .env.example — fill in real values before running."
  fi
) || true

# --- Step 4 — OPT-IN: npm install (only if CLAUDE_CONTRACT_AUTO_INSTALL=1) ---
(
  if [[ "${CLAUDE_CONTRACT_AUTO_INSTALL:-0}" == "1" ]] && [[ ! -d "$PROJECT_ROOT/node_modules" ]]; then
    echo "[session-start] node_modules missing — running npm install (CLAUDE_CONTRACT_AUTO_INSTALL=1)"
    cd "$PROJECT_ROOT" && npm install
  fi
) || echo "[session-start] WARNING: npm install step failed (non-fatal)"

echo "[session-start] Done."
