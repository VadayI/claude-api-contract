# Versioning & delivery (semver on git tags)

The contract is delivered as **git tags** (`vX.Y.Z`) plus the raw `openapi.yml` URL. Consumers pin a version; they never track a moving branch.

## Semver rules (decision #6 / D3)

| Bump | When | Gate |
|---|---|---|
| **major** (`vX+1.0.0`) | any backward-incompatible change | forced by the breaking-change gate (oasdiff `--fail-on ERR`, @.claude/rules/breaking-changes.md) |
| **minor** (`vX.Y+1.0`) | new endpoint or new optional field — backward compatible | — |
| **patch** (`vX.Y.Z+1`) | descriptions, examples, fixes that do not change the wire shape | — |

## Delivery to consumers

- Canonical fetch: `https://raw.githubusercontent.com/VadayI/claude-api-contract/<tag>/openapi.yml`.
- Each consumer commits a pin so git + CI can see it (not just an env var, which is gitignored):
  - `CONTRACT_REPO=https://github.com/VadayI/claude-api-contract`
  - `CONTRACT_VERSION=vX.Y.Z`
  - recommended form: a committed `contract.lock.json` (`repo` + `version` + `path` + `sha256` of the vendored copy) next to the vendored `openapi.yml`.
- **Bumping the pin is a deliberate PR in the consumer**, never an automatic drift.

## Consumer sync-gate (their side, summarized here)

Each consumer runs a `scripts/check_contract_sync.sh` that pulls `openapi.yml@CONTRACT_VERSION` from `CONTRACT_REPO` and diffs it (or sha256) against the vendored copy — RED if they diverge (someone hand-edited the vendored file, or the tag was moved). Full chain of integrity: `contract@tag → vendored openapi.yml → generated types / validated implementation`.

## Releasing (this repo)

Use `/release [version]`: rebuild `openapi.yml`, run all gates, update `CHANGELOG.md` (oasdiff changelog), tag, push the tag. Never tag a contract that is RED on any gate.
