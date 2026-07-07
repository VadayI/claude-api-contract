---
name: contract-versioning
description: "[claude-api-contract] Step-by-step release flow and consumer pin-bump recipes. Activate for /release, version bumps, or consumer sync setup. Policy (semver table, delivery URL, pin forms, sync gate) lives in .claude/rules/versioning.md."
---

# Contract Versioning & Release — recipes

> Policy (semver table, raw-URL delivery, pin forms, consumer sync gate) — `.claude/rules/versioning.md`; this skill is the flow.

## Release flow (/release)

```bash
npm run validate         # compile + drift + lint + examples (must be green)
npm run breaking         # classify; confirm the bump
oasdiff changelog <prev-tag> openapi.yml       # docs-writer folds into CHANGELOG.md (ADR 0007)
git tag vX.Y.Z && git push origin vX.Y.Z
```

## Consumer pin bump (their side)

1. Update `CONTRACT_VERSION` and refresh the vendored `openapi.yml` from the raw URL at the new tag.
2. Recompute `sha256` in `contract.lock.json`.
3. Open the PR; their `check_contract_sync.sh` must go green.
