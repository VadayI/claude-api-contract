---
model: sonnet
description: "[claude-api-contract] Refresh docs/HANDOFF.md alone (lighter than /wrap-up)."
---

Refresh the rolling handoff snapshot without the full wrap-up.

## Log
```bash
node scripts/log-cmd.mjs /handoff "$ARGUMENTS"
```

## Steps
1. Probe live state: branch, `git status -sb`, last gate results, whether `openapi.yml` matches `spec/`, latest tag, pending PR.
2. Regenerate `docs/HANDOFF.md`: where we are, what's next, any RED gate or open question. Keep it short and current.
3. Report the snapshot.
