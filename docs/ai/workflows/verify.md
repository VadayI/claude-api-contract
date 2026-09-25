# Verify — portable contract procedure

Read AGENTS.md. Coordinators delegate; an assigned worker executes within its scope. Runtime tool names are examples; preserve all substantive steps using available capabilities.

Produce the human verification handoff so the user can confirm the contract behaves as designed (docs/ai/rules/verification.md).

## Log
```bash
# Optional legacy log: pass actual arguments as separate argv; never evaluate them.
```

## Input
Optional `<procedure arguments>`: a feature/resource name. Default: the most recently added endpoints.

## Steps
1. Read `docs/project-state/endpoints.json` + `openapi.yml`.
2. Dispatch `docs-writer` to generate `docs/verify/<feature>.md`: for each endpoint — the `curl` against the Prism mock (`npm run mock`), the documented request, and the expected status codes / auth-scope behavior.
3. Confirm `/api/v1/auth/*` issues usable tokens against the mock.
4. Report the path and a one-line how-to-run.
