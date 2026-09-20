#!/usr/bin/env bash
# Explicit Bash wrapper. AI_PYTHON is one executable path, never a shell fragment.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${AI_PYTHON:-python}" "$SCRIPT_DIR/launch.py" "$@"
