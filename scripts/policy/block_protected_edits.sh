#!/usr/bin/env bash
# Compatibility entrypoint for older Claude settings. Node parses tool JSON.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec node "$SCRIPT_DIR/claude_edit_guard.mjs"
