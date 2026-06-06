---
model: sonnet
description: "[claude-api-contract] Validate the contract locally — TypeSpec drift + Spectral lint + example validation."
---

Run the full local contract validation. This is the pre-PR gate; it mirrors the CI gates so failures surface before review.

## Log
```bash
node scripts/log-cmd.mjs /validate-contract "$ARGUMENTS"
```

## Steps

0. **Runtime gate.** Read `.claude/memory/env-detect.json`. If missing → `NO_ENV_DETECT` (run `node scripts/detect-env.mjs`). If `node_supported == false` → STOP, install Node 20.19+.

1. **Recompile + drift.** Delegate to `tsp-author` or run directly:
   ```bash
   npm run api:compile && npm run api:bundle
   bash scripts/check_typespec_drift.sh
   ```
   RED → `openapi.yml` was hand-edited or not regenerated. Fix in `spec/`, recompile, commit both.

2. **Spectral lint.**
   ```bash
   npm run lint
   ```
   RED → route to `contract-reviewer` with the rule violations (@.claude/rules/spectral-style.md).

3. **Examples.**
   ```bash
   bash scripts/check_examples.sh
   ```
   RED → route to `mock-validator` (@.claude/rules/examples-validation.md).

4. **Report** a pass/fail checklist. On all-green, suggest `/breaking-check` then `/create-pr`.

> `npm run validate` runs steps 1–3 in one shot.
