---
model: sonnet
description: "[claude-api-contract] Workflow audit — suggest the next command from the command log + live state."
---

Audit the workflow and recommend the next command. Delegates to `auditor`.

## Log
```bash
node scripts/log-cmd.mjs /audit "$ARGUMENTS"
```

## Steps
1. Dispatch `auditor`: read `.claude/memory/command-log.jsonl` + live state (branch, drift, last gate results, pending tag).
2. Report "where we are" + the single best next command with a one-line reason + any blocking issue.
