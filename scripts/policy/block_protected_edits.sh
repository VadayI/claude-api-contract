#!/usr/bin/env bash
# scripts/policy/block_protected_edits.sh
#
# PreToolUse hook (matcher: Write|Edit|MultiEdit) — runs in Claude Code CLI on
# the user's machine. Hard-blocks any direct Edit/Write to the canonical
# openapi.yml.
#
# Contract-first invariant (contract-first.md / no-stubs.md): openapi.yml is a
# build artifact GENERATED from spec/**/*.tsp. It is never hand-edited — the only
# legitimate way it changes is `npm run api:compile && npm run api:bundle`.
#
# I/O: reads the hook payload as JSON on stdin (tool_name, tool_input.file_path).
# Exit 2 + stderr blocks the tool call (message shown to Claude); exit 0 allows.
# Node parses the JSON (Node 20.19+ is a hard project requirement; jq is not).
set -uo pipefail

INPUT="$(cat)"

# Read a dotted field from the stdin JSON via Node (empty string if absent).
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

TOOL_NAME="$(json_field tool_name)"
FILE_PATH="$(json_field tool_input.file_path)"

# Only edit-family tools are relevant (the matcher already scopes this).
case "$TOOL_NAME" in
  Edit|Write|MultiEdit|NotebookEdit) ;;
  *) exit 0 ;;
esac

[ -n "$FILE_PATH" ] || exit 0

if [ "$(basename "$FILE_PATH")" = "openapi.yml" ]; then
  {
    echo "[protected-edits] BLOCKED direct edit of: $FILE_PATH"
    echo "openapi.yml is GENERATED from spec/ — never hand-edited (contract-first.md)."
    echo "To change the contract: edit spec/**/*.tsp, then run:"
    echo "    npm run api:compile && npm run api:bundle"
  } >&2
  exit 2
fi

exit 0
