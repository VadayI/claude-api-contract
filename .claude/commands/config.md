---
model: sonnet
description: "[claude-api-contract] Inspect/adjust template config — settings.json, rules wiring, plugin baseline."
---

Inspect and safely adjust the template configuration.

## Log
```bash
node scripts/log-cmd.mjs /config "$ARGUMENTS"
```

## Steps
1. Summarize `.claude/settings.json` (model, permissions, hooks, plugins) and the `CLAUDE.md` import block.
2. Check rule wiring: every `@.claude/rules/*` reference resolves; flag orphan rules (neither imported in `CLAUDE.md` nor referenced by any agent/command).
3. Propose changes; apply only after the user confirms. Never write secrets, never push.
