# Workflow & agent pipeline

Only an explicitly coordinating session is a **dispatcher**: classify the request, delegate to agents, synthesize their reports. It never implements, including configuration changes. It reads only exact non-secret files/ranges named in worker reports (D02); insufficient evidence goes back to the worker. Workers implement and are not coordinators.

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
2. **Plan first for non-trivial work.** Present scope, sub-tasks, files and risks when authorization is missing; existing user authorization persists, so continue an approved implementation without asking again.
3. **PRs only** — never commit to `main` (`docs/ai/rules/git-operations.md`).
4. **Contract-first** — every change flows `spec/ → openapi.yml`, never the reverse (`docs/ai/rules/contract-first.md`).
5. Keep logical slices reviewable; source, generated outputs, manifests and tests for one component belong together even when exceeding three files.

## Optional agents

`devil` (challenge the design), `brief-synthesizer` (`/synthesize-brief`), `happy-path-author` (`/happy-paths` — business user journeys from the brief, re-runnable after the contract is designed); from the `family-core` plugin (ADR 0011): `auditor` (`/audit` — next-command suggestion from the command log), `template-sync` (sync a derived project to a newer template version).

## Runtime-independent delegation

Use available runtime delegation. Without it, invoke separate role sessions with saved task/report artifacts; do not claim independent review from one session or let the coordinator implement as fallback. Optional plugin functions have local procedures in docs/ai/workflows.
