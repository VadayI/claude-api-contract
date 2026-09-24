#!/usr/bin/env bash
# Compatible legacy detector hook: no lock cleanup, env seeding or package install.
# The shared detector (scripts/ai/detector.py) serves the exact-candidate runner;
# this legacy probe stays until the P07 project-state migration. A failed probe is
# visibly unknown.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v node >/dev/null 2>&1; then
  echo '[session-start] NOT_VERIFIED: Node 20.19+ is required for the legacy detector.' >&2
  exit 1
fi
node "$SCRIPT_DIR/detect-env.mjs"
