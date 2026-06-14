# ADR 0008 — Breaking-change tooling: pinned oasdiff CLI, not oasdiff-action

**Status:** accepted · **Date:** 2026-06-14

## Context
The template self-audit suggested adopting `oasdiff/oasdiff-action` for nicer
PR-level breaking-change reporting (inline annotations and grouped PR comments).

Today the contract detects breaking changes with the **oasdiff CLI pinned to
`v1.18.4`** (`contract-ci.yml` runs `go install github.com/oasdiff/oasdiff@v1.18.4`),
driven by `scripts/check_breaking.sh`: it compares the working-tree `openapi.yml`
against the **latest `v*` tag** with `--fail-on ERR` and an optional
`.oasdiff-ignore.txt` (`--err-ignore`) for consciously-allowed breaks. The same
command runs locally via `npm run breaking` (@.claude/rules/breaking-changes.md,
@.claude/rules/node-commands.md).

## Decision
Keep the pinned-CLI approach. **Do not adopt `oasdiff-action`.**

Rationale:
1. The valuable part of the action — grouped PR comments and the approval
   workflow — requires **oasdiff Pro (paid)**. The free `breaking` sub-action
   only emits inline annotations and fails the job, which `check_breaking.sh`
   already does deterministically.
2. `check_breaking.sh` encodes this project's exact base-ref semantics — base =
   the latest **semver tag**, not the PR base branch — plus the
   `.oasdiff-ignore.txt` + ADR flow for allowed breaks. Reproducing that in the
   action's base/revision model would be more configuration for less control.
3. Determinism and local/CI parity: the CLI is pinned to `v1.18.4` and the
   identical command runs locally and in CI, so a maintainer can reproduce a CI
   breaking result exactly. Pinning the action would add a second version axis.
4. Fewer third-party actions in the CI supply chain.

## Consequences
- **Positive:** deterministic, locally reproducible, precisely tuned to the
  contract's versioning model, and free of a paid dependency.
- **Trade-off:** no inline per-line PR annotations or grouped PR comments. The
  breaking summary appears in the CI job log (`[breaking] FAIL: ERR-level
  breaking change vs <tag>`); the PR template and `breaking-change-analyst`
  surface the classification and required semver bump at review time.
- **Revisit if:** oasdiff ships free PR-comment output, or the team adopts
  oasdiff Pro — at which point add `oasdiff/oasdiff-action/breaking@<pinned-tag>`
  as an *additional* reporter, keeping `check_breaking.sh` as the authoritative
  gate.
