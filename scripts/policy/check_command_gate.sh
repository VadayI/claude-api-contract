#!/usr/bin/env bash
# scripts/policy/check_command_gate.sh
#
# UserPromptExpansion hook (matcher: release|ship-contract|create-pr) — fires
# when a user-typed slash command expands, BEFORE Claude runs it. Enforces cheap,
# deterministic preconditions so a release/deploy never runs from a bad state.
#
# Policy (decided 2026-06-14):
#   /release, /ship-contract  -> BLOCK on a failed precondition (exit 2).
#   /create-pr                -> ADVISORY only (stdout notice, never blocks).
#
# I/O: reads hook JSON on stdin (command_name). For UserPromptExpansion, exit 2
# blocks the expansion and stdout is injected into Claude's context. Node parses
# the JSON (Node 20.19+ is required; jq is not assumed).
set -uo pipefail

INPUT="$(cat)"

json_field() {
  printf '%s' "$INPUT" | node -e '
    let s="";
    process.stdin.on("data",d=>s+=d).on("end",()=>{
      try{
        let v=JSON.parse(s);
        for(const k of process.argv[1].split(".")) v=(v==null?undefined:v[k]);
        process.stdout.write(v==null?"":String(v));
      }catch{ process.stdout.write(""); }
    });
  ' "$1"
}

CMD="$(json_field command_name)"
CMD="${CMD#/}"            # tolerate a leading slash
CMD="${CMD%.md}"          # tolerate a .md suffix

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
cd "$ROOT" 2>/dev/null || true

block()  { echo "[command-gate] BLOCK /$CMD: $1" >&2; exit 2; }
advise() { echo "[command-gate] advisory (/$CMD): $1"; }   # stdout -> context

case "$CMD" in
  release)
    [ -f openapi.yml ] || block "no contract — openapi.yml is missing. Build it (npm run api:compile && npm run api:bundle) before releasing."
    if [ -n "$(git status --porcelain --untracked-files=no 2>/dev/null)" ]; then
      block "working tree has uncommitted tracked changes — commit or stash first (a release tag must point at a committed state)."
    fi
    echo "[command-gate] /release preconditions OK."
    ;;
  ship-contract)
    [ -f openapi.yml ] || block "no contract — openapi.yml is missing. Build it and run 'npm run ready' before shipping the mock."
    echo "[command-gate] /ship-contract preconditions OK."
    ;;
  create-pr)
    branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
    [ "$branch" = "main" ] && advise "you are on 'main' — PRs must come from a feature branch (git-operations.md)."
    if git rev-parse --verify -q main >/dev/null 2>&1; then
      changed="$(git diff --name-only main...HEAD 2>/dev/null || true)"
      if printf '%s\n' "$changed" | grep -qE '^(spec/|openapi\.yml)'; then
        printf '%s\n' "$changed" | grep -qx 'CHANGELOG.md' || advise "contract changed but CHANGELOG.md has no new entry — add a '## [Unreleased]' fragment (ADR 0007)."
      fi
    fi
    ;;
  *)
    : ;;
esac
exit 0
