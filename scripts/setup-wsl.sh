#!/usr/bin/env bash
# scripts/setup-wsl.sh
#
# One-shot WSL2/Linux bootstrap for the contract toolchain (idempotent):
#   nvm + Node LTS + Claude Code CLI (WSL2-native) + gh + oasdiff.
#
# Safe to re-run. Never prints secrets. Designed for a fresh Ubuntu WSL2 shell.
set -uo pipefail

echo "[setup] 1/4 — nvm + Node LTS"
if ! command -v nvm >/dev/null 2>&1 && [[ ! -s "$HOME/.nvm/nvm.sh" ]]; then
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
fi
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm install --lts >/dev/null 2>&1 || true
hash -r
echo "[setup]   node: $(command -v node) ($(node --version 2>/dev/null))"

echo "[setup] 2/4 — Claude Code CLI (WSL2-native)"
npm install -g @anthropic-ai/claude-code >/dev/null 2>&1 || true
hash -r
echo "[setup]   claude: $(command -v claude || echo 'NOT on PATH')"

echo "[setup] 3/4 — GitHub CLI (gh)"
if ! command -v gh >/dev/null 2>&1; then
  echo "[setup]   gh missing. Install: https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
else
  echo "[setup]   gh: $(gh --version 2>/dev/null | head -n1)"
fi

echo "[setup] 4/4 — oasdiff (breaking-change gate)"
if ! command -v oasdiff >/dev/null 2>&1; then
  echo "[setup]   oasdiff missing. Install (one of):"
  echo "[setup]     go install github.com/oasdiff/oasdiff@v1.18.4"
  echo "[setup]     brew tap oasdiff/homebrew-oasdiff && brew install oasdiff"
else
  echo "[setup]   oasdiff: $(oasdiff --version 2>/dev/null | head -n1)"
fi

echo "[setup] Done. Next: bash scripts/install.sh  (npm deps) then  npm run validate"
