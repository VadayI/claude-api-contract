---
name: openapi-design
description: "[claude-api-contract] Generic REST/OpenAPI design heuristics + index of the repo's contract rules. Activate when designing endpoint contracts (api-architect phase)."
---

# OpenAPI / REST Design — heuristics & index

> Generic heuristics here; repo-binding specifics live in the rules indexed below — do not restate them.

## REST heuristics

- Resources are plural nouns (`/api/v1/articles`, `/api/v1/articles/{id}`); action = HTTP method, never a verb in the path.
- Status codes: 200 read/update, 201 create, 204 delete/no-body; 400 validation, 401 unauthenticated, 403 forbidden, 404 not found, 409 conflict, 429 throttled, 500 server error.
- Full JSON Schema (OpenAPI 3.1): named components & enums, no anonymous inline objects.
- Design for the consumer's branch points: stable `operationId`s, stable error `code` tokens, explicit per-operation error responses.

## Repo canon (the specifics live there)

- Envelopes — list / error / 429 + `Retry-After`: `.claude/rules/api-envelope.md`
- Auth flows (user + S2S), scopes-not-roles: `.claude/rules/auth-contract.md`
- Surface classification (`resource` / `system` / page-map): `.claude/rules/endpoint-surface.md`
- Breaking vs safe + semver policy: `.claude/rules/breaking-changes.md`, `.claude/rules/versioning.md`
- TypeSpec authoring norms: `.claude/rules/typespec-style.md`
