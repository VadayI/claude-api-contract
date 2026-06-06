---
name: typespec-authoring
description: "[claude-api-contract] Authoring API contracts in TypeSpec — file layout, decorators, shared models/envelopes, emitting OpenAPI 3.1. Activate when writing or editing spec/**/*.tsp."
---

# TypeSpec Authoring

## Layout
- `spec/main.tsp` — entry: `@service`, `@server`, global `security`, `import`s.
- `spec/models/` — shared models + envelopes (`ListResponse<T>`, `ErrorDetail`, `ValidationErrors`).
- One file per resource; `import "./articles.tsp";` from `main.tsp`.

## Core decorators
- `@service({ title: "..." })`, `@server("https://api.example.com", "...")`.
- `@route("/api/v1/articles")`, `@get`/`@post`/`@patch`/`@delete`.
- `@operationId("createArticle")` — stable, unique (consumer symbol).
- `@doc("...")` on every model/property/operation; `@summary("...")` + `@tag("articles")`.
- `@useAuth(BearerAuth)` globally; per-op `@useAuth` / scopes for service endpoints.
- Optional vs required: `name?: string` (optional) vs `name: string` (required).

## Shared envelope pattern
```tsp
model ListResponse<T> {
  count: int32;
  next: url | null;
  previous: url | null;
  results: T[];
}
```
Reference `ListResponse<Article>` in list operations; never inline.

## Emit OpenAPI 3.1
```bash
npm run api:compile        # tsp compile spec --emit @typespec/openapi3
npm run api:bundle         # emitter output -> ./openapi.yml
npm run format             # tsp format spec/**/*.tsp
```
TypeSpec emits 3.1-style nullability (`type: [T, "null"]`) — consumed cleanly by openapi-typescript.

## Discipline
- Never hand-edit `openapi.yml`; edit `spec/` and recompile.
- Commit `spec/` + `openapi.yml` together (drift gate).
- Verify current `@typespec/*` APIs via context7 before authoring.
