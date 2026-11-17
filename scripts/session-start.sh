#!/usr/bin/env bash
# SessionStart: jawna detekcja środowiska bez sprzątania locków, seedowania env
# ani instalacji pakietów. Wspólny detektor (scripts/ai/detector.py) zapisuje
# .ai-runtime/environment.json; legacy probe Node (scripts/detect-env.mjs) zapisuje
# stack-specyficzny .ai-runtime/env-detect.json. Na końcu scripts/ai/session_context.py
# drukuje kontekst sesji (Git, ustawienia, mapa dokumentacji, ostatni rekord sesji)
# bez czytania .ai-runtime. Nieudana sonda jest widoczna jako NOT_VERIFIED, nigdy
# jako zielona sesja.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
status=0

# Wspólny detektor: Python 3.13+ (AI_PYTHON, inaczej python3, potem python z PATH — D18); brak = NOT_VERIFIED.
python_ok=0
for PYTHON in ${AI_PYTHON:+"$AI_PYTHON"} python3 python; do
  if command -v "$PYTHON" >/dev/null 2>&1 \
    && "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else 2)' >/dev/null 2>&1; then
    python_ok=1
    break
  fi
  [ -n "${AI_PYTHON:-}" ] && break   # jawny AI_PYTHON nie jest zastępowany niczym innym
done
if [ "$python_ok" = 1 ]; then
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

# Kontekst sesji dla każdego agenta; ustalenia ciągłości nie blokują startu (exit 0).
if [ "$python_ok" = 1 ]; then
  if ! "$PYTHON" "$ROOT/scripts/ai/session_context.py" --root "$ROOT"; then
    echo '[session-start] NOT_VERIFIED: session context unavailable (invalid documentation map or settings).' >&2
    status=1
  fi
fi
exit "$status"
