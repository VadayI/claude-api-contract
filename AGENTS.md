# Shared contract project instructions

Read `docs/HANDOFF.md`, the active plan and actual Git branch/status/HEAD before
work. Reconcile stale notes with Git. Read `docs/ai/overrides/output-language.md` when present (otherwise the legacy
output-language rule); a current explicit user choice takes precedence. Honor the user's language and existing
authorization; an authorized continuation does not require new planning approval.

## Scope and complete rule delivery

`docs/ai/catalog.json` routes full canonical rules and the selected production
roles `tsp-author` and `contract-reviewer`. Read the assigned role and every
required rule completely; generated role packs include source digests and END
markers. Check file endings when output is bounded. Do not treat truncated output
as a completed read. Legacy agents/skills remain available; read their full bodies
and the canonical rule sources behind `.claude/rules` adapters. The inventory and
remaining P12 migration are in `docs/ai/production-structure.md`.

Only an explicitly coordinating session follows `docs/ai/rules/workflow.md`.
The coordinator delegates all implementation, including small config edits, and
reads only exact non-secret files/ranges named in role reports (D02). Insufficient
evidence goes back to the worker. Workers implement within their scope; reviewers
return findings without writing files. Without native delegation, use separate
role sessions with saved task/report artifacts. Never claim independent review
from a single session or turn the coordinator into an implementation fallback.

## Invariants

- This repository is the API contract. Author `spec/**/*.tsp`; generate the flat
  OpenAPI 3.1 `openapi.yml`. Never hand-edit emitted YAML. Commit source/output
  together after compile/drift, lint, examples, endpoint registry and mock checks.
- Consumers pin released contract versions. Classify breaking changes and semver
  before delivery; releases, tags and deploy need their own explicit request.
- No invented endpoints, DTOs or fake examples. Preserve auth/scopes, response
  envelopes, `x-surface`, operation IDs and every applicable stack rule.
- Commit/push/PR are part of authorized work; merge requires an explicit user
  command (D01). Never commit directly to main or treat an open PR as merged.
- Preserve foreign staged/unstaged/untracked files, refs, stash and worktrees.
  Stage explicit task-owned paths/hunks. Never auto-stash, reset/clean, force-push
  or delete index.lock to achieve a clean status.
- Report actual commands, exit codes, candidate/base and limitations. Missing or
  skipped required checks are NOT_VERIFIED, never PASS or readiness evidence.
- Real env, keys, local settings and credentials are private. Never read, copy or
  log their contents. Project configuration cannot grant itself trust. Do not
  change global permissions or install optional plugins automatically.

## Runtime and project ownership

Python 3.13+ stdlib powers shared tooling; Node 20.19+ runs the contract toolchain.
Use `python scripts/ai/production.py --check` and
`python scripts/ai/core_sync.py --local-source --check` for read-only drift checks.
PowerShell invokes Python directly and uses explicit
`C:/Program Files/Git/bin/bash.exe` for Bash scripts; do not pick WSL from PATH.
Launch with `python scripts/ai/launch.py claude` or `codex`; models/trust inherit
user/runtime settings. Native role discovery is version-dependent: parsing an
adapter is not evidence of its runtime activation. See runtime-compatibility.md.

Local procedures in `docs/ai/workflows` and `.agents/skills` do not need the
family-core marketplace plugin. Use gh/Git for GitHub and official documentation
when optional MCP is unavailable. Report unavailable capabilities precisely.

Project notes, configuration, CI/maturity choices, overrides and derived contract
artifacts are project-owned. Bootstrap/update must use a reviewed manifest and
preserve customization. Never reseed CLAUDE imports or copy entire directories
over an existing project. New CI choice/materialization remains P06: before any
first push, resolve/review the selected policy, never infer it from copied workflows.
Persistent `.claude/memory` registries remain readable until P07; do not create a
second writable registry. Local `set-language` honors existing language choices.
