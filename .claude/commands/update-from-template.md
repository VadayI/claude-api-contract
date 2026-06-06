---
model: sonnet
description: "[claude-api-contract] Sync a derived project's .claude config to a newer claude-api-contract version."
---

Bring a derived project's `.claude/` config up to a newer template version. Delegates to `template-sync`.

## Log
```bash
node scripts/log-cmd.mjs /update-from-template "$ARGUMENTS"
```

## Input
Optional `$ARGUMENTS`: the target template tag/ref. Default: latest `v*` tag of `claude-api-contract`.

## Steps
1. Dispatch `template-sync`: diff this project's `.claude/` (agents, rules, commands, skills) + `scripts/` against the target template ref.
2. Propose the deltas as a reviewable PR; never silently clobber project-local customizations — flag conflicts for the user.
3. Re-run `npm run validate` after applying; report what changed.
