# TypeSpec authoring style (source of openapi.yml)

> Loaded per-agent by `tsp-author` and `contract-reviewer` (not in the global import block).

`spec/**/*.tsp` is the source. `openapi.yml` is its emitted output. Author the spec well and the YAML is clean by construction.

## Layout

- `spec/main.tsp` — entry point (analogous to `index.ts`): the `@service` decorator, global `@server`, security, and `import`s of the other files. Roughly one `import` per resource file.
- `spec/auth.tsp` — auth endpoints (`.claude/rules/auth-contract.md`).
- `spec/models/` — shared, reusable models and the envelopes (list / error — `.claude/rules/api-envelope.md`). Lift anything shared to this folder (Azure approach: shared shapes live as library-level units).
- One file per resource (`spec/articles.tsp`, ...). Keep files focused; split when a file grows past ~300 lines.

## Conventions

- **OpenAPI 3.1 output** (decision D4). TypeSpec emits 3.1-style nullability (`type: [T, "null"]`) — correct and consumed cleanly by `openapi-typescript`.
- **`@route` plural nouns** under a versioned prefix: `/api/v1/articles`. Action = HTTP method, never a verb in the path.
- **Stable `operationId`** for every operation (`@operationId` or a deterministic name) — it becomes a consumer symbol; renaming it is breaking (`.claude/rules/breaking-changes.md`).
- **`@doc` everywhere** — every model, property, and operation gets a description (Spectral enforces it).
- **`@summary` + tags** on operations; group by resource tag.
- **camelCase OR snake_case for JSON properties — pick one repo-wide and never mix.** Default: snake_case (matches the DRF consumer's default and reduces backend adaptation).
- **Reusable models, not inline anonymous objects** — inline objects produce unusable nested types downstream. Name every shape.
- **Named enums** → map to clean TS unions.
- **Explicit status codes & error responses** on every operation (`@error`, the shared error envelope).

## Versioning in TypeSpec

TypeSpec has built-in version annotations. On a breaking reset you can rebase the spec to a base version and continue numbering — but the **delivery** version is still the git tag (`.claude/rules/versioning.md`). Keep TypeSpec versioning and the git-tag semver consistent.

## After editing

Always: `npm run api:compile && npm run api:bundle`, then commit `spec/` **and** the regenerated `openapi.yml` together. Never commit one without the other (drift gate).

> Activate the `typespec-authoring` skill for concrete syntax. Verify current TypeSpec/emitter APIs via context7 before writing (`.claude/rules/mcp-stack.md`).
