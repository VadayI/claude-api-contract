---
name: contract-versioning
description: "[claude-api-contract] Semver-on-git-tags release flow and consumer pinning. Activate for /release, version bumps, or consumer sync setup."
---

# Contract Versioning & Release

## Semver rule
- major = breaking (oasdiff ERR forces it). minor = new endpoint/optional field. patch = docs/examples/fixes.

## Release flow (/release)
```bash
npm run validate         # compile + drift + lint + examples (must be green)
npm run breaking         # classify; confirm the bump
oasdiff changelog <prev-tag> openapi.yml >> CHANGELOG.md   # via docs-writer
git tag vX.Y.Z && git push origin vX.Y.Z
```
Never tag a RED contract.

## Consumer pinning (their side)
- `CONTRACT_REPO=https://github.com/VadayI/claude-api-contract`, `CONTRACT_VERSION=vX.Y.Z`.
- Fetch: `https://raw.githubusercontent.com/VadayI/claude-api-contract/<tag>/openapi.yml`.
- Committed `contract.lock.json` (repo + version + path + sha256) next to the vendored copy.
- Consumer `check_contract_sync.sh` diffs vendored copy vs `openapi.yml@CONTRACT_VERSION` — RED on divergence.
- Bumping the pin = deliberate PR in the consumer.
