---
model: sonnet
description: "[claude-api-contract] End-of-session wrap-up — persist WORKLOG, refresh HANDOFF, fold the living plan."
---

Persist session context to git so work history stays in sync across machines (@.claude/rules/living-plan.md).

## Log
```bash
node scripts/log-cmd.mjs /wrap-up "$ARGUMENTS"
```

## Steps
1. Append a dated entry to `docs/WORKLOG.md` (what changed, gates, tag if any).
2. Fold the active `docs/plans/NNNN-*.md` Execution log into the worklog.
3. Regenerate `docs/HANDOFF.md` (the rolling "where we are / what's next" snapshot — read FIRST on joining, updated LAST). Note it is local-only/gitignored unless your project commits it.
4. Update `.claude/memory/endpoints.json` if endpoints changed; update ADRs/`docs/todo.md`/`docs/lessons.md` as needed.
5. Report what was persisted.
