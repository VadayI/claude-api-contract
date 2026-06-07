---
model: sonnet
description: "[claude-api-contract] Generate/refresh the verification handoff — Prism + curl checklist for the endpoints."
---

Produce the human verification handoff so the user can confirm the contract behaves as designed (@.claude/rules/verification.md).

## Log
```bash
node scripts/log-cmd.mjs /verify "$ARGUMENTS"
```

## Input
Optional `$ARGUMENTS`: a feature/resource name. Default: the most recently added endpoints.

## Steps
1. Read `.claude/memory/endpoints.json` + `openapi.yml`.
2. Dispatch `docs-writer` to generate `docs/verify/<feature>.md`: for each endpoint — the `curl` against the Prism mock (`npm run mock`), the documented request, and the expected status codes / auth-scope behavior.
3. Confirm `/api/v1/auth/*` issues usable tokens against the mock.
4. Report the path and a one-line how-to-run.
