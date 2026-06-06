---
model: sonnet
description: "[claude-api-contract] Bring up the Prism mock from the current openapi.yml (static or dynamic)."
---

Start the Prism mock server so a frontend can develop against the contract. Delegates smoke validation to `mock-validator`.

## Log
```bash
node scripts/log-cmd.mjs /mock "$ARGUMENTS"
```

## Input
Optional `$ARGUMENTS`: a port (overrides `PRISM_PORT`, default 4010) and/or `--dynamic`.

## Steps

0. **Runtime gate** (env-detect.json). Ensure deps installed (`node_modules/`); if missing → `bash scripts/install.sh`.

1. Ensure `openapi.yml` is current: `bash scripts/check_typespec_drift.sh` (RED → recompile first).

2. Start the mock:
   ```bash
   npm run mock                 # static (examples)
   npm run mock:dynamic         # dynamic (Faker + x-faker)
   ```
   (@.claude/rules/prism-mock.md)

3. Dispatch `mock-validator` for the smoke test: hit each endpoint with the documented request, confirm two-way validation and that `/auth/*` issues usable tokens.

4. Report the base URL (`http://localhost:<port>`) and the smoke results.
