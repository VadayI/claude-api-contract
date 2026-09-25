#!/usr/bin/env bash
# SessionStart: jawna detekcja środowiska bez sprzątania locków, seedowania env
# ani instalacji pakietów. Wspólny detektor (scripts/ai/detector.py) zapisuje
# .ai-runtime/environment.json; legacy probe Node (scripts/detect-env.mjs) zapisuje
# stack-specyficzny .ai-runtime/env-detect.json. Nieudana sonda jest widoczna
# jako NOT_VERIFIED, nigdy jako zielona sesja.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
status=0

# Wspólny detektor: Python 3.13+ (AI_PYTHON lub python z PATH); brak = NOT_VERIFIED.
PYTHON="${AI_PYTHON:-python}"
if command -v "$PYTHON" >/dev/null 2>&1 \
  && "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else 2)' >/dev/null 2>&1; then
  if ! "$PYTHON" "$ROOT/scripts/ai/detector.py" --repository "$ROOT" --write; then
    echo '[session-start] NOT_VERIFIED: shared detector failed; .ai-runtime/environment.json not refreshed.' >&2
    status=1
  fi
else
  echo '[session-start] NOT_VERIFIED: Python 3.13+ (AI_PYTHON) is required for the shared detector.' >&2
  status=1
fi

# Legacy stack probe: wymaga Node; przenosi swój rekord runtime z .claude/memory sam.
if command -v node >/dev/null 2>&1; then
  node "$SCRIPT_DIR/detect-env.mjs" || status=1
else
  echo '[session-start] NOT_VERIFIED: Node 20.19+ is required for the stack probe.' >&2
  status=1
fi
exit "$status"
