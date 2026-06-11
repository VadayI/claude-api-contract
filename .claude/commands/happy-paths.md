---
model: sonnet
description: "[claude-api-contract] Generate (or refresh) business-level happy-path user journeys from the project brief and endpoint registry."
---

Generate plain-language business user journeys for this API contract. Delegates to `happy-path-author`. Re-runnable: story-level right after the brief; endpoint-annotated once the contract exists.

## Log
```bash
node scripts/log-cmd.mjs /happy-paths "$ARGUMENTS"
```

## Input
Optional `$ARGUMENTS`: a resource or feature name to scope the journeys (e.g. `articles`). Default: all resources from `PROJECT.md`.

## Contract
Happy paths are derived strictly from the brief — never invented. Gaps become Open Questions. No hand-editing of `openapi.yml` or `spec/` (@.claude/rules/no-stubs.md, @.claude/rules/contract-first.md).

## Steps
1. Read `PROJECT.md` (§1–§3), `.claude/memory/endpoints.json`, and `openapi.yml` (if present) to determine which mode applies — story-level (registry empty/absent) or endpoint-annotated (registry populated).
2. Dispatch `happy-path-author` to:
   - Write `docs/api/HAPPY-PATHS.md` — one journey per primary actor × goal pair, plain-language step table, Open Questions section if any gaps remain.
   - Add/replace §8 in `PROJECT.md` — short bulleted list referencing the doc, one line per journey.
3. Report the path to `docs/api/HAPPY-PATHS.md`, note the mode used (story-level / endpoint-annotated), list the journeys generated, and surface any Open Questions.
   - If the contract does not yet exist: suggest `/preflight` as the next step.
   - If the contract already exists: suggest `/verify` to confirm endpoint coverage aligns with the journeys.
