#!/usr/bin/env bash
# scripts/policy/check_plan_execution_log.sh
#
# SubagentStop hook (advisory) — fires when a subagent finishes. Reminds (never
# blocks) that a core pipeline agent should append a one-line execution-log entry
# to the active living plan (living-plan.md).
#
# Policy (decided 2026-06-14): ADVISORY only — print a notice, always exit 0.
# Self-limiting: silent unless a living plan exists AND it has no 'phase done:'
# line yet, so it never nags once the log has started. Scoping to core agents is
# done by the settings.json matcher.
#
# I/O: reads (and discards) hook JSON on stdin. Always exits 0.
set -uo pipefail

cat >/dev/null 2>&1 || true        # drain stdin

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
cd "$ROOT" 2>/dev/null || exit 0

PLAN="$(ls -t docs/plans/[0-9]*-*.md 2>/dev/null | head -n1 || true)"
[ -n "$PLAN" ] || exit 0           # no living plan → nothing to advise

grep -qiE 'phase done:' "$PLAN" 2>/dev/null && exit 0   # log already started → silent

{
  echo "[plan-log] advisory: ${PLAN} has no 'phase done:' execution-log line yet."
  echo "[plan-log] each core agent should append one line per finished phase (living-plan.md)."
} >&2
exit 0
