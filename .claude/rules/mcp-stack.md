# MCP stack & docs verification

> Loaded per-agent by `api-architect`, `tsp-author`, `docs-writer`, `contract-reviewer`.

## Servers (committed baseline)

- **github** — PRs, releases, branch protection. From the official plugin `github@claude-plugins-official` (or the `.mcp.json` fallback — never both).
- **context7** — up-to-date library docs. From `context7@claude-plugins-official` (or fallback).

Manage installs with `/plugins`; secrets (`GITHUB_PERSONAL_ACCESS_TOKEN`, `CONTEXT7_API_KEY`) live in `.env` only (gitignored).

## Verify before you author (hard expectation)

The toolchain (TypeSpec emitter, Spectral rules, Prism flags, oasdiff flags, `openapi-typescript`) moves fast. Before writing TypeSpec, designing a rule, or stating a tool flag, **verify the current API/flags via context7** rather than relying on memory. A spec authored against a stale emitter API wastes a whole pipeline pass.

- `tsp-author` — verify `@typespec/*` decorators and emitter options.
- `api-architect` / `contract-reviewer` — verify OpenAPI 3.1 + Spectral rule semantics.
- `docs-writer` — verify oasdiff `changelog` flags.
