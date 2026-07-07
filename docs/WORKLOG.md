# WORKLOG

> Append-only chronicle of what changed each session (newest first).

## 2026-07-07 (duplication & plugin audit + context hygiene, via Cowork)
- docs: `docs/AUDIT-2026-07-07.md` (delta over 06-14/06-16 audits) + applied quick wins — PR: pending (host) — gates: n/a (no contract change) — tag: none
  - N1 (key finding): inline `@`-mentions leaked globally (doc-verified: imports at launch, recursive <=4 hops, code spans skipped) -> backticked: CLAUDE.md 13 repl., 13 rules 27 repl.; import block untouched
  - N2: removed `engineering@knowledge-work-plugins` from enabledPlugins (skills shadow contract-reviewer/api-architect/docs-writer + bundles a 2nd GitHub MCP); local-only: dropped `enabledMcpjsonServers` from settings.local.json (was double MCP)
  - Decisions locked: rules<->skills dedup as "norms vs recipes" (6 pairs, plan F); family-core plugin design + migration (report section 6, plan G)
  - Prior-audit statuses re-verified: P1 endpoints-gate DONE (except `validate` scope), P2 merge_group DONE, P3 agent tails still open
  - Note: sessions between #33 and #47 were not logged here — see git log

## 2026-06-15 (session 10 — template self-audit + fixes, via Cowork)

> Full audit of every agent/command/skill/rule/script/hook/CI workflow + applied fixes. Audit doc: `docs/AUDIT-2026-06-14-template.md` (untracked; `personalize.sh` Tier 2 strips `docs/AUDIT-*.md` on derive). 1 HIGH · 4 MEDIUM · 6 low/verify.

- chore: audit fixes — husky+commitlint wired, SendMessage removed, doc-drift — `2bab66e` (branch `chore/audit-2026-06-14-doc-drift`; not pushed/PR'd) — gates: validate green · mock:smoke 11/11 · check:endpoints 10/10 · breaking host-only — tag: none
  - **Audit:** no orphan rules; all script/agent/skill refs resolve; 4/6 skills already had activation hooks; live gates green.
  - **H1** husky+commitlint wired: `prepare: husky` + devDeps; `core.hooksPath=.husky/_`; commitlint good/bad tested.
  - **M1** activated the 2 skills that lacked a hook: `oasdiff-breaking` (breaking-change-analyst) + `contract-versioning` (versioning.md).
  - **M2** HANDOFF reconciled: removed dead `/HANDOFF.md` from `.gitignore`; aligned `wrap-up.md` to CLAUDE.md (tracked).
  - **M3** clarified ADR reset list in `clean.sh` + `node-commands.md` (0002–0004 demo-contract; 0005–0008 infra, kept like 0001).
  - **M4/L1** removed `SendMessage`; `tools` array → comma-separated string across all 12 agents.
  - **L4** import-block insert pointer → `project-maturity.md` (CLAUDE.md + set-language.md).
  - **Post-commit fix (uncommitted):** commitlint re-pinned **v21→v19** — npm default pulled v21 (`engines.node >=22.12`, breaks the `>=20.19` floor); corrected per `docs/lessons.md`. `package.json` + `package-lock.json` await commit.
  - **Deferred (low/verify):** L2 `UserPromptExpansion`, L3 `statusMessage`, L5 `SubagentStop` matcher, L6 spectral `warn`→`error`.
  - No contract/wire change; no semver bump; consumers: no action.

## 2026-06-13/14 (session 9 — template self-audit follow-ups)

> Implements `docs/AUDIT-2026-06-14-followups.md` (from the `deep-research-report.md` self-audit). Template-internal — `personalize.sh` Tier 2 strips `docs/AUDIT-*.md` on derive, so only the committed gates/rules/scripts reach derived projects.

- feat: session-9 audit follow-ups — 4.1–4.7 + README (consolidated) — PR #40 — `05ce21f` — CI: green — tag: none
  - **4.2** endpoints-registry coverage: NEW `scripts/check_endpoints_registry.mjs` + `npm run check:endpoints` + supplementary "Verify" step in `contract-ci.yml` (NOT a 6th canonical gate — "5 CI gates" wording preserved)
  - **4.1** Claude Code policy hooks: NEW `scripts/policy/{block_protected_edits,check_command_gate,check_plan_execution_log}.sh` + wired in `.claude/settings.json` (PreToolUse hard-block direct `openapi.yml` edit; UserPromptExpansion `/release`+`/ship-contract` BLOCK, `/create-pr` ADVISORY; SubagentStop ADVISORY). Hook events verified vs official docs.
  - **4.6** README-freshness + version-coherence checks added to `contract-policy.yml`
  - **4.3** ADR 0008 — declined `oasdiff-action` (PR comments require oasdiff Pro); kept the pinned CLI
  - **4.4** `check_mock.sh` — reference/derived auto-detect (template behaviour unchanged; derived no longer false-fails)
  - **4.7** NEW `.github/workflows/scheduled-audit.yml` (weekly STUB/TODO inventory + version-drift + gate-health)
  - **4.5** (opt-in) NEW `.husky/{pre-commit,commit-msg,pre-push}` + `commitlint.config.mjs` — devDeps added on host; commitlint pinned **@19** (v21 needs Node >=22.12)
  - docs: `docs/WORKLOG.md` (this block) + `docs/HANDOFF.md` + `README.md` refresh
  - 18 files; no contract change (`spec/`/`openapi.yml` untouched); no semver bump; consumers: no action needed

- chore: CODEOWNERS (zoned) + personalize owner-tokenization — PR #39 — `53ce953` — CI: green — tag: none
  - `.github/CODEOWNERS` (zoned: contract / CI / docs, owner `@VadayI`) + `scripts/personalize.sh` owner tokenization (`@VadayI` → `@${OWNER}`)
  - Audit item #4. No contract change

- chore(ci): contract-policy PR gate (lean + advisory) — PR #38 — `37c477e` — CI: green — tag: none
  - NEW `.github/workflows/contract-policy.yml` — diff-scoped PR gate complementing `contract-ci`
  - 3 blocking checks: no bare TODO/FIXME in `spec/`/`examples/`/`openapi.yml` (documented `STUB:` allowed); ADR required when `.oasdiff-ignore.txt` changes; CHANGELOG `## [Unreleased]` fragment required on contract changes (ADR 0007)
  - 1 advisory (non-blocking): suggest a living plan on `spec/` changes
  - Audit item #2. No contract change; no semver bump

- docs: changelog policy — ADR 0007 (Model A: Unreleased fragments + release stamping) — PR #37 — `80e0629` — CI: green — tag: none
  - NEW `docs/decisions/0007-changelog-policy.md` — PR adds a human line under `## [Unreleased]`; `/release` stamps `[vX.Y.Z]` and runs `oasdiff changelog` to verify/augment (oasdiff = safety net, not sole source)
  - Resolves the PR-time vs release-time changelog contradiction; unblocks the contract-policy CHANGELOG check
  - Edited `.claude/rules/git-operations.md`, `.claude/commands/release.md`, `.claude/commands/create-pr.md`
  - Audit item #8

- chore: PR template — PR #36 — `b51355b` — CI: green — tag: none
  - NEW `.github/PULL_REQUEST_TEMPLATE.md` — checklist mirroring the git-operations PR checklist (validate / breaking + semver / CHANGELOG / no hand-edit of `openapi.yml`)
  - Audit item #10. No contract change

- fix: version coherence → v0.4.0 + version-agnostic personalize reset — PR #35 — `efb0c16` — CI: green — tag: none
  - `package.json` / `package-lock.json` aligned to latest tag `v0.4.0`; `README.md` status line updated
  - `scripts/personalize.sh` Tier 2 reset made version-agnostic (resets to `0.0.0` regardless of current value)
  - Audit item: README/version drift. No contract change

- chore(ci): fail-closed spec-guard + pin oasdiff — PR #34 — `1bd3276` — CI: green — tag: none
  - `.github/workflows/contract-ci.yml` — spec-guard now fail-closed (missing `spec/` in a *derived* project → FAIL, not skip), detected via `package.json` name == `claude-api-contract`
  - Pinned `OASDIFF_VERSION: v1.18.4` (matches local; module `github.com/oasdiff/oasdiff`)
  - Audit items #1 + #5. No contract change

- Template count: **12 agents** · **23 commands** · **20 rules** · 6 skills · **3 workflows** (`contract-ci`, `contract-policy`, `scheduled-audit`) · NEW `scripts/policy/` + `scripts/check_endpoints_registry.mjs`

## 2026-06-11 (session 8)
- feat: `/happy-paths` command + `happy-path-author` agent — PR #33 — CI: green — tag: none
  - Designed and implemented a new slash command `/happy-paths` and dedicated agent `happy-path-author`
  - Command generates plain-language business user journeys (happy paths) after `/synthesize-brief`
  - **Dual-mode auto-detect:** story-level when `endpoints.json` is empty/absent (`— (to be designed)` column); endpoint-annotated when registry is populated (real `operationId` + path in table)
  - **Idempotent + re-runnable:** overwrites `docs/api/HAPPY-PATHS.md` cleanly; replaces §8 in `PROJECT.md` without duplication
  - Output: `docs/api/HAPPY-PATHS.md` (canonical journeys doc) + §8 in `PROJECT.md` (short reference list)
  - 2 new files: `.claude/agents/happy-path-author.md`, `.claude/commands/happy-paths.md`
  - 5 edited files: `synthesize-brief.md` (step 3 now suggests `/happy-paths → /preflight`), `CLAUDE.md` (Optional agents + bootstrap order), `workflow.md` (Optional agents), `templates/PROJECT.md` (§8 placeholder), `README.md` (Quick start)
  - Branch `feat/happy-paths` → PR #33 → squash-merged `b67cfeb` — CI green
  - No contract change (`spec/`/`openapi.yml` untouched); no semver bump; consumers: no action needed
  - Template count: **12 agents** · **23 commands** · 21 rules · 6 skills · 5 CI gates

## 2026-06-10 (session 7)
- feat: `scripts/seed.sh` + README "Quick install" — PR #32 — CI: green — tag: none
  - Added `scripts/seed.sh`: one-liner seed script (`bash <(curl -fsSL .../scripts/seed.sh)`) modelled after `claude-react-mui`
  - Shallow-clones `main` → copies all committed files (Class B artifacts absent from git, so correctly excluded) → wipes transient memory → prints next steps
  - Updated `README.md`: new "Quick install" section above step-by-step guide
  - Smoke-tested: `.spectral.yaml`, `.mcp.json`, `.env.example`, ADR 0001/0005/0006 present; `spec/`, `openapi.yml`, ADR 0002–0004 absent ✓
  - Branch `feat/seed-script` → PR #32 → squash-merged `d5f1b99` — CI green
  - No contract change; no semver bump; consumers: no action needed

## 2026-06-09 (session 6)
- chore: reset HANDOFF, WORKLOG, CHANGELOG to clean template starters — PR #31 — CI: green — tag: none
  - Audited GitHub `main` for local-project data leakage: `spec/`, `examples/`, `openapi.yml`, ADR 0002–0004 correctly absent
  - Found `docs/HANDOFF.md`, `docs/WORKLOG.md`, `CHANGELOG.md` contained claude-api-contract meta-development history (sessions 1–5, PRs, v0.1–v0.4 entries)
  - Reset all three to clean template starters (blank slate for a fresh clone)
  - Branch `docs/session-5-wrap-up` → PR #31 → squash-merged `fc13671`
  - No contract change; no semver bump; consumers: no action needed

## <YYYY-MM-DD>
- <change> — gates: <result> — tag: <if any>
