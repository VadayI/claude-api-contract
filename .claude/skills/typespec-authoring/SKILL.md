---
name: typespec-authoring
description: "[claude-api-contract] TypeSpec syntax recipes — decorators, shared envelope models, emit/format commands for OpenAPI 3.1. Activate when writing or editing spec/**/*.tsp. Norms (layout, naming, casing) live in .claude/rules/typespec-style.md."
---

# TypeSpec Authoring — recipes

> Norms (layout, naming, casing, commit discipline) live in `.claude/rules/typespec-style.md`; this skill is the how-to.

## Core decorators

- `@service({ title: "..." })`, `@server("https://api.example.com", "...")`.
- `@route("/api/v1/articles")`, `@get`/`@post`/`@patch`/`@delete`.
- `@operationId("createArticle")`.
- `@doc("...")`, `@summary("...")`, `@tag("articles")`.
- `@extension("x-surface", "resource")` (or `"system"`) on every operation.
- `@useAuth(BearerAuth)` globally; per-op `@useAuth` / scopes for service endpoints.
- Optional vs required: `name?: string` (optional) vs `name: string` (required).

## Shared envelope pattern

TypeSpec incarnation of the canonical envelopes (`.claude/rules/api-envelope.md`):

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

The emitter produces 3.1-style nullability (`type: [T, "null"]`) — consumed cleanly by `openapi-typescript`.
