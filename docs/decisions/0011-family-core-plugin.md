# ADR 0011 — Family-core plugin for the template family

**Status:** proposed · **Date:** 2026-07-07 · **Source analysis:** `docs/AUDIT-2026-07-07.md` §6

## Context

Three sibling templates (`claude-api-contract`, `claude-django`, `claude-react-mui`) triplicate a common core: process agents (`ba`, `devil`, `auditor`, `brief-synthesizer`, `template-sync`, the generic part of `docs-writer`), process commands (`/audit`, `/doctor`, `/preflight`, `/bootstrap`, `/handoff`, `/wrap-up`, `/synthesize-brief`, `/set-language`, `/fix-ci`, `/review-pr`, `/create-pr`, `/verify`, `/plugins`, `/update-from-template`) and process rules (`workflow`, `no-stubs`, `git-operations`, `preflight`, `environment`, `mcp-stack`, `living-plan`, `verification`, `node-commands`, `project-maturity`). Every core fix currently requires 3 PRs in 3 repos, and the family owner also wants to **add commands/agents/skills to already-existing projects** — which is literally the plugin distribution model.

Hard constraint of the plugin mechanism: a plugin ships **commands / agents / skills / hooks / MCP servers — not `rules/` and not CLAUDE.md**. A plugin agent cannot `@`-import repo rules by relative path; at dispatch it receives the host project's context (CLAUDE.md import block) like any subagent.

## Decision

1. **Distribution:** new marketplace repo `github.com/VadayI/claude-family-marketplace`, plugin `plugins/family-core/` (`agents/`, `commands/`, `skills/`, `scripts/`, `hooks/`), released as semver tags. Hook scripts travel inside the plugin and are referenced via `${CLAUDE_PLUGIN_ROOT}`.
2. **Layering rule (core/domain boundary):** text identical across the 3 repos → core (plugin); text containing domain words (contract/spec/openapi · django/DRF · react/MUI) → stays in the repo. `workflow.md` never moves (pipelines differ per repo). Norms that would have been "rules" travel as plugin skills or agent bodies.
3. **Safety invariants stay in repos.** Skill triggering is not guaranteed, so contract/domain integrity invariants (gates, envelopes, drift) live ONLY in repo rules and agent bodies — never delegated to plugin skills. Plugin skills must be **self-contained**: no `.claude/rules/...` pointers (the host repo may not have them).
4. **Core agents are self-sufficient:** generic body in the plugin; domain specifics read at runtime from the host project's CLAUDE.md / PROJECT.md. Domain tails that cannot be generalized stay as repo-local agents until Phase 2 settles them per-agent (criterion: the layering rule above).
5. **Fallback = degradation, not breakage:** every repo remains functional WITHOUT the plugin; local copies are deleted only after the pilot proves parity. `/doctor` checks a minimum core version (mitigates version drift between repos).
6. **Migration:**
   - **Phase 0** — this ADR.
   - **Phase 1 (low risk)** — marketplace repo + `family-core v0.1.0`: `auditor`, `template-sync`, `/audit`, `/handoff`, `/wrap-up`, `/set-language`, `log-cmd.mjs`. Pilot in `claude-api-contract` (add to `enabledPlugins`, delete local duplicates, one week of use). Verify plugin-hook parity Cowork vs CLI here.
   - **Phase 2** — `ba`, `devil`, `brief-synthesizer`, `/synthesize-brief`, session-start/detect-env (extract generic parts; domain tails stay in repos).
   - **Phase 3** — roll out to `claude-django` + `claude-react-mui` (local copies → delete; domain deltas → their rules). `/update-from-template` + `template-sync` narrow to the domain layer; a core update = plugin tag bump.
7. **Non-goals:** CI gate scripts (`check_*.sh`) stay in repos — they must run without Claude; domain rules stay rules; CLAUDE.md stays per-repo.

## Consequences

- **+** A core fix = one plugin release instead of 3 PRs; existing projects get new core capabilities by installing/bumping the plugin.
- **+** Repo `.claude/` shrinks to the domain layer; `/update-from-template` narrows accordingly.
- **−** Version drift between repos becomes possible — mitigated by the `/doctor` min-version check (§5).
- **−** Cowork vs CLI plugin-hook behavior parity is unverified — explicit Phase 1 exit criterion.
- **−** Skills moved into the plugin lose repo-rule pointers — they must be rewritten self-contained before the move (checklist item for every Phase 1/2 candidate).
- Open (settled per-agent during Phase 2, criterion fixed here): exact split of `ba` / `devil` / `brief-synthesizer` domain tails.
