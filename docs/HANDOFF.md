# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## 2026-09-25 — P07 session continuity (development core)

Branch `feat/p07-shared-memory` (draft PR #66); commit `6fb703a` on top of `0e3f4cd`. Nothing is merged (D01).

- Start every session with `python scripts/ai/session_context.py --root .` (branch/HEAD, settings, documentation map, latest record, snapshot diff; no `.ai-runtime` needed). End with `--new-record --agent <runtime>` and, after the commit, `--check` (docs/ai/session-continuity.md).
- This session: `docs/sessions/20260925T075805Z-claude-93ac65.md` (task, checks, limitations, next step).
- Next: The user runs `PUBLISH-P07-2026-09-24.ps1` (Status → Push → UpdatePrs → Checks). Merge #65 → #66 only on the user's command, then repin Django/React to the integrated core; after that, P08.

## 2026-09-24 — P07 consumer adoption (draft PR #66, development core)

Branch `feat/p07-shared-memory` on top of `fix/p06-contract-consistency` (PR #65).
The P07 core now has consumers; nothing is merged (D01).

- Core (`template-core/scripts/ai/project_state.py`): `--resolve NAME` /
  `--writable NAME [--category runtime]` print the single fallback rule for shell
  and Node callers; `--migrate-runtime` / `migrate_runtime()` move only
  `env-detect.json` + `command-log.jsonl`; `artifact_relative_paths()` serves
  changed-file gates. Runtime map changed: `env-detect.json →
  .ai-runtime/env-detect.json`; `.ai-runtime/environment.json` is reserved for the
  shared detector (`detector.py --repository . --write`).
- Contract consumers: `scripts/session-start.sh` runs the shared detector and the
  Node stack probe; `detect-env.mjs`/`log-cmd.mjs` write to `.ai-runtime/` through
  `scripts/runtime-state.mjs` (legacy runtime copies are moved, conflicts refuse);
  `check_endpoints_registry.mjs`, `check_ready.sh` and `react_gate.py` resolve
  registries via `project_state` (`docs/project-state/` first, legacy
  `.claude/memory/` until migrated, differing copies fail closed); `clean.sh`,
  `sandbox.sh`, rules/workflows/agents/commands and role packs use the new paths.
  `contract-ci.yml` now runs every `tests/test_*.py`.
- Verified on Linux Python 3.13.7 / Node 22: `generate_core`, `core_sync
  --local-source`, `production`, `generate_adapters` `--check` PASS;
  `template-core/tests` 101 OK (incl. interrupted-copy rollback); `tests/` 26 OK
  (runtime-writer fixtures move/identical/conflict + Python↔Node cross-runtime). Not run: the project-data migration of the
  untracked `.claude/memory/{endpoints,pages}.json` in the main checkout
  (preview only; `--apply` is a user decision).
- Next: merge fix PR #65, then this PR (checks run after retarget to `main`);
  Django/React repin to integrated; P08. Merge only on the user's command.

## 2026-09-24 — post-P06 consistency

Branch `fix/p06-contract-consistency` on top of `main` `9db26a0` (P06 merged via
PR #61; runner directory-digest fix #62; reusable auth-validation docs #64).
Integrated so far: P04 production structure and local-source core delivery,
P05 detector/exact-candidate runner, P06 explicit CI mode (`scripts/ai/ci_mode.py`),
Husky staged/all-ref hooks and the Claude edit-payload parser. Not delivered:
P07 shared project state (core commit `68305e3` on `feat/p07-shared-memory`,
rebase onto this branch pending), P08 Git lifecycle, P10/P11 roles, P13.

- `AGENTS.md`, `docs/ai/rules/{preflight,environment}.md`,
  `docs/ai/production-structure.md`, `docs/ai/workflows/wrap-up.md` and
  `scripts/session-start.sh` no longer describe the CI choice or the shared
  detector/runner as future P05/P06 work; role packs regenerated.
- Django and React are repinned to integrated core `9db26a0` on their own fix
  branches (`fix/p06-django-consistency`, `fix/p06-react-delivery-drift`).
- Verified on Linux Python 3.13.15: `generate_core --check`,
  `core_sync --local-source --check`, `production --check`,
  `generate_adapters --check` PASS; `tests/test_production.py` 14 OK;
  `template-core/tests` 85 OK.
- Next: rebase `feat/p07-shared-memory` here, fix the stale core docs
  (`schemas.md`, `core-manifest.json` phase) inside that core revision, deliver it
  downstream with development pins. Merge only on the user's command.

## 2026-09-20 — local core delivery continuation

Verified base: `b6d1b3d3582c4a18545050be6f475d270f53bc48` (merged core PR #56).
Task branch: `feat/local-core-delivery`, isolated checkout. This change delivers
the owner's `template-core` runtime using manifest digests, with no future commit
SHA. Canonical source and installed payload checks are read-only; ownership
conflicts preserve custom files. Installer, npm entry points and hosted checks
include delivery. No contract schema, application models or migrations changed.

Windows Python 3.14: 40 tests passed, one host symlink test skipped. Local delivery
and repeat/source checks passed. Hosted verification and Linux results must be
read from the candidate PR; this paragraph does not assert their success.
P04 remains in progress: Django delivery and legacy bootstrap migration follow;
full role migration, runner, CI choice and family acceptance are not complete.
Merge requires a new explicit user command. Earlier snapshot below is history.

## Where we are (2026-07-07, session 15 end — family-core v0.1.0 pilot, via Cowork)
- Branch: `main` == `origin/main` (PR #52 merged) + **uncommitted pilot changes**: `settings.json` (+`extraKnownMarketplaces`, +`family-core@claude-family-marketplace`), 6 local duplicates DELETED (agents auditor/template-sync, commands audit/handoff/wrap-up/set-language), 5 mention-files updated, ADR 0011 -> accepted, docs. Awaiting branch/PR on the host.
- **family-core v0.1.0 live:** github.com/VadayI/claude-family-marketplace (main `462d160`, tag `v0.1.0`).
- Audit 2026-07-07 queue: **A–H done; G Phase 0+1 done.** Remaining: pilot week -> Phase 2 (ba/devil/brief-synthesizer) -> Phase 3 (claude-django / claude-react-mui). Inherited: L2; AUDIT-file tracking decision.
- Counts: 10 agents · 19 commands · 21 rules · 6 skills (local) + family-core plugin.
- ⚠️ Sandbox mount: stale-cache ghosting now proven to extend to files rewritten by host git (ADR 0011 unreadable in sandbox; todo/WORKLOG/HANDOFF served stale) — that is why docs updates went through this host-run script. ALL git ops stay on host.
- Contract untouched → still **v0.4.0**.

## What was done this session
- `claude-family-marketplace` repo + `family-core v0.1.0` (11 files; manifests verified vs official docs); content generalized & self-contained.
- Pilot wiring: settings.json marketplace+plugin; 6 duplicates deleted; mentions updated; environment.md baseline doc-drift fixed (engineering out, family-core in).
- ADR 0011 accepted (Phase 1 shipped).

## What's next
1. **HOST:** branch `feat/family-core-pilot` → `git add -u` (picks up the 6 deletions) → commit → push → PR.
2. **Pilot smoke (Claude Code CLI in this repo):** `/plugin` shows family-core; `/audit` + `/handoff` present & run; `log-cmd` appends to `.claude/memory/command-log.jsonl`; `/update-from-template` resolves `template-sync` (record: bare name or scoped `family-core:template-sync`).
3. **Pilot week:** use normally; then Phase 2 (extract generic ba/devil/brief-synthesizer into the plugin) → Phase 3 (roll out to claude-django / claude-react-mui).
4. Inherited: **L2** confirm `UserPromptExpansion` on the live CLI; decide whether `docs/AUDIT-*.md` stay untracked.

## Open questions / risks
- Bare-name dispatch of plugin agents — pilot exit criterion; scoped-name fallback documented in `/update-from-template`.
- Plugin-hook parity Cowork vs CLI — v0.1.0 ships no hooks (log-cmd is command-invoked); the parity check moves to Phase 2 (session-start hook).
- Derived projects keep their local copies until they enable the plugin — degradation by design (ADR 0011 §5); `/update-from-template` will surface the 6 deletions as template deltas.

## 2026-09-20 — safe legacy launcher checkpoint

Shared compatibility source: contract commit 269eeadbda4b6309b14ce289d61ecbf7f0ce03ae.
Contract core tests: Windows 43 PASS + 1 symlink SKIP; Linux all 44 PASS.
Django/React development pins deliberately depend on unmerged contract PR #57;
replace them with the actual integrated commit before downstream merge.
Legacy .env is parsed as selected literal data, never executed; credentials affect
only the child, preserving blank fallback and PAT precedence. Known legacy wrappers
migrate by exact hash; custom wrappers conflict before writes. Windows PowerShell
and Git Bash version probes passed. These are not model-session acceptance.
React actual main-to-candidate upgrade/generator check passed; Django old-seed
component upgrade/repeat passed. Full bootstrap, CI-choice and P05+ remain pending.
All PRs remain unmerged; a new explicit user command is required for merge.
