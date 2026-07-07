# MCP stack & docs verification

> Loaded per-agent by `api-architect`, `tsp-author`, `contract-reviewer`, `breaking-change-analyst`, `docs-writer`.

## Servers (committed baseline)

- **github** — PRs, releases, branch protection. From the official plugin `github@claude-plugins-official` (or the `.mcp.json` fallback — never both).
- **context7** — up-to-date library docs. From `context7@claude-plugins-official` (or fallback).

Manage installs with `/plugins`; secrets (`GITHUB_PERSONAL_ACCESS_TOKEN`, `CONTEXT7_API_KEY`) live in `.env` only (gitignored).

## Verify before you author (hard expectation)

The toolchain (TypeSpec emitter, Spectral rules, Prism flags, oasdiff flags, `openapi-typescript`) moves fast. Before writing TypeSpec, designing a rule, or stating a tool flag, **verify the current API/flags via context7** rather than relying on memory. A spec authored against a stale emitter API wastes a whole pipeline pass.

- `tsp-author` — verify `@typespec/*` decorators and emitter options.
- `api-architect` / `contract-reviewer` — verify OpenAPI 3.1 + Spectral rule semantics.
- `docs-writer` — verify oasdiff `changelog` flags.

## Layer boundaries — superpowers plugin vs repo rules

`superpowers` ships **process technique**; repo rules own **domain invariants**. Expected active skills here: `brainstorming` (socratic probing BEFORE `ba`/`api-architect` design), `writing-plans`/`executing-plans` (planning technique — `.claude/rules/living-plan.md` adds the domain artifact: `docs/plans/NNNN-*.md` + append-only Execution log), `verification-before-completion` (prove-before-done discipline — complements, never replaces, `.claude/rules/verification.md` and its `endpoints.json`/verify docs), `dispatching-parallel-agents`, `writing-skills`.

- `devil` agent vs `brainstorming` skill: different phases — brainstorming probes before a design exists; `devil` attacks a drafted design. Keep both.
- Inert in a spec-only repo (accepted): TDD, systematic-debugging, using-git-worktrees, finishing-a-development-branch, subagent-driven-development.
- Contract-integrity invariants (gates, envelopes, drift) live only in repo rules and agent bodies — never delegated to plugin skills.
