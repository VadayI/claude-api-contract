---
model: sonnet
description: "[claude-api-contract] Diagnose and fix a red CI run on the contract PR."
---

Diagnose a failing CI run and fix it. Maps each failing gate to its owner agent.

## Log
```bash
node scripts/log-cmd.mjs /fix-ci "$ARGUMENTS"
```

## Steps
1. `gh run list` / `gh run view --log-failed` — identify the failing gate.
2. Map → fix:
   - **TypeSpec drift** → `tsp-author`: recompile (`npm run api:compile && npm run api:bundle`), commit both.
   - **Spectral lint** → `contract-reviewer` (@.claude/rules/spectral-style.md).
   - **Examples** → `mock-validator` (@.claude/rules/examples-validation.md).
   - **Breaking-change** → `breaking-change-analyst`: bump major or add `.oasdiff-ignore.txt` + ADR.
   - **Mock smoke** → `mock-validator`.
3. Re-run gates locally (`npm run validate`, `npm run breaking`) before pushing the fix.
4. Report what failed, the fix, and the re-run result.
