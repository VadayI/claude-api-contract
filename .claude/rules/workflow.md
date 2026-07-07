# Workflow & agent pipeline

The orchestrator is a **dispatcher**: classify the request, delegate to agents, synthesize their reports. It does not author TypeSpec or edit `openapi.yml` itself.

## Default pipeline (new resource / endpoint)

```
ba → api-architect (designs the contract) → tsp-author (writes TypeSpec)
   → [contract-reviewer | breaking-change-analyst]
   → mock-validator → docs-writer (INDEX.md + CHANGELOG)
```

| Stage | Agent | Output |
|---|---|---|
| Requirements | `ba` | user stories, scope, endpoint draft |
| Contract design | `api-architect` | resources, methods, status codes, permissions, envelope choice |
| Authoring | `tsp-author` | `spec/**/*.tsp` → recompiled `openapi.yml` |
| Review | `contract-reviewer` | consistency, naming, codes, Spectral-clean |
| Breaking analysis | `breaking-change-analyst` | oasdiff classification + required semver bump |
| Mock & examples | `mock-validator` | Prism comes up, examples valid |
| Docs | `docs-writer` | `docs/api/INDEX.md`, `CHANGELOG.md`, PR description |

## Triggers

- "design/add an endpoint", "new resource", "API contract" → full pipeline from `ba`.
- "is this change breaking?" → `breaking-change-analyst` directly.
- "lint/clean the contract" → `contract-reviewer`.
- "mock not returning X" → `mock-validator`.

## Rules of engagement

1. **First action on any task: classify and delegate.** Do not open `spec/` files until an agent runs. Ambiguous request → one round of clarification first (`AskUserQuestion`).
2. **Plan first for non-trivial work.** Stay in Plan Mode; present scope, sub-tasks, files, risks; change nothing until the user approves.
3. **PRs only** — never commit to `main` (`.claude/rules/git-operations.md`).
4. **Contract-first** — every change flows `spec/ → openapi.yml`, never the reverse (`.claude/rules/contract-first.md`).
5. If a task touches more than ~3 files, split it and run each slice through the pipeline.

## Optional agents

`devil` (challenge the design), `auditor` (`/audit` — next-command suggestion from the command log), `brief-synthesizer` (`/synthesize-brief`), `happy-path-author` (`/happy-paths` — business user journeys from the brief, re-runnable after the contract is designed), `template-sync` (sync a derived project to a newer template version).
