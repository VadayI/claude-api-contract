# Breaking changes (first-class gate)

> **Policy and classification live here; oasdiff CLI recipes live in the `oasdiff-breaking` skill.**

Because **two repositories** consume this contract, a breaking change that slips through silently breaks both teams at once. So breaking-change detection is a hard, first-class CI gate — not an afterthought.

## The gate

`scripts/check_breaking.sh` compares the previous tag against the working tree via `oasdiff breaking` with `--fail-on ERR` — exit 1 on any ERR-level change. That is the **major-bump gate**: an ERR-level breaking change is only allowed to merge if it is accompanied by a MAJOR version bump.

- Base ref defaults to the latest `v*` tag.
- First release (no prior tag) → the gate SKIPs (nothing to compare).

## What counts as breaking (ERR) vs safe

| Breaking (ERR → major) | Non-breaking (minor/patch) |
|---|---|
| remove/rename endpoint, field, enum value | add a new endpoint |
| make an optional request field required | add a new **optional** request field |
| change a field's type or format | add a new response field |
| remove a response field a client relies on | relax a constraint (e.g. widen a range) |
| tighten validation (shorter maxLength, etc.) | description / example / `summary` edits (patch) |
| change `operationId` (it becomes a consumer symbol) | add an example |

## Consciously allowed breaking changes

Sometimes a breaking change is intended and the major bump is the plan. Do **not** weaken or remove the gate. Instead list the specific allowed changes in `.oasdiff-ignore.txt` (`--err-ignore`), which keeps the gate active for everything else. Record the decision in an ADR (`docs/decisions/`).

## Changelog

`docs-writer` folds the oasdiff changelog output into `CHANGELOG.md` on release (ADR 0007); breaking items are flagged explicitly.

> Reviewer / `breaking-change-analyst` duty: classify every contract diff as breaking vs non-breaking BEFORE the PR is opened, and state the required semver bump.
> Activate the `oasdiff-breaking` skill for CLI invocations (breaking / err-ignore / changelog / tag comparison).
