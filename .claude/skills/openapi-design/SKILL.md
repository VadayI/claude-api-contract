---
name: openapi-design
description: "[claude-api-contract] REST/OpenAPI design principles — resources, methods, status codes, envelopes, scopes, versioning. Activate when designing endpoint contracts."
---

# OpenAPI / REST Design

## Resources
- Plural nouns: `/api/v1/articles`, `/api/v1/articles/{id}`.
- Action = HTTP method (GET/POST/PATCH/PUT/DELETE), never a verb in the path.

## Status codes
- 200 OK, 201 Created, 204 No Content.
- 400 validation, 401 unauthenticated, 403 forbidden, 404 not found, 409 conflict, 429 throttled, 500 server error.

## Envelopes (repo-wide, one shape)
- List: `{ count, next, previous, results: T[] }`.
- Error (simple): `{ detail }`. Error (validation, 400): `{ errors: [{ field, code, message }] }`.
- 429: simple error + `Retry-After` header.

## Auth & scopes
- Global `bearerAuth` (JWT). Public endpoints `security: []`.
- Service endpoints: scopes (`orders:read`), not roles. `/auth/token` client-credentials for S2S.

## Versioning
- Backward-incompatible change → new MAJOR (git tag). Never change the contract silently.
- Stable `operationId` — renaming is breaking.

## OpenAPI 3.1
- Full JSON Schema; named components & enums; no anonymous inline objects.
