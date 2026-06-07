# API index (human overview)

> The contract is `openapi.yml` (OpenAPI 3.1) at the repo root — the single source of truth, generated from `spec/**/*.tsp`. This index is a human-readable overview that points at it. Maintained by `docs-writer`.

**Version:** 0.1.0 (unreleased) · **Servers:** `http://localhost:4010` (Prism mock)

## Security schemes

| Scheme (key) | Type | Used by |
|---|---|---|
| `BearerAuth` | http bearer (JWT) | global default; user-flow; logout; articles (human clients) |
| `OAuth2Auth` | oauth2 client-credentials (`tokenUrl: /auth/token`, scopes `articles:read`, `articles:write`) | service-flow (S2S, D5); articles (service clients) |

Articles endpoints accept **either** a user bearer token **or** a service token carrying the required scope (`security: [{BearerAuth}, {OAuth2Auth:[scope]}]` — OR semantics).

## Auth — `/auth/*` (tag `auth`)

| Method | Path | operationId | Auth | Responses |
|---|---|---|---|---|
| POST | `/auth/register` | `registerUser` | public | 201 · 400 · 409 |
| POST | `/auth/login` | `loginUser` | public | 200 · 400 · 401 |
| POST | `/auth/refresh` | `refreshToken` | public | 200 · 400 · 401 |
| POST | `/auth/logout` | `logoutUser` | BearerAuth | 204 · 401 |
| POST | `/auth/token` | `issueServiceToken` | public (S2S) | 200 · 400 · 401 |

Refresh transport (D2): `access` via `Authorization: Bearer`, `refresh` in the response body.

## Articles — `/api/v1/articles` (tag `articles`)

| Method | Path | operationId | Scope | Envelope | Responses |
|---|---|---|---|---|---|
| GET | `/api/v1/articles` | `listArticles` | `articles:read` | list | 200 · 401 · 403 · 429 |
| POST | `/api/v1/articles` | `createArticle` | `articles:write` | single | 201 · 400 · 401 · 403 · 409 · 429 |
| GET | `/api/v1/articles/{id}` | `getArticle` | `articles:read` | single | 200 · 401 · 403 · 404 · 429 |
| PATCH | `/api/v1/articles/{id}` | `updateArticle` | `articles:write` | single | 200 · 400 · 401 · 403 · 404 · 409 · 429 |
| DELETE | `/api/v1/articles/{id}` | `deleteArticle` | `articles:write` | none | 204 · 401 · 403 · 404 · 429 |

List query params: `page` (int32), `page_size` (int32), `status` (`draft`/`published`/`archived`), `search` (string).

## Envelopes (@.claude/rules/api-envelope.md)

- **List:** `ListResponse<T>` → `{ count, next, previous, results }` (e.g. `ArticleList`).
- **Error (simple):** `{ detail }` — 401/403/404/409/429.
- **Error (validation):** `{ errors: [ { field, code, message } ] }` — 400.
- **429:** simple error body **+ `Retry-After`** header (int32 seconds).

## Accepted deviations (v0.1.0)

- Security scheme keys are `BearerAuth` / `OAuth2Auth` (emitter defaults), not lowercase `bearerAuth` / `serviceAuth`. Stable consumer symbols; renaming later would be breaking.
- Bearer scheme emits `scheme: Bearer` without `bearerFormat: JWT` — a TypeSpec `@typespec/http` limitation (built-in `BearerAuth` has no `bearerFormat` field). Canon is generated, never hand-edited.
- `/auth/token` request body is JSON (not `application/x-www-form-urlencoded`) for a self-contained contract and a trivial mock.

## Follow-ups (next small PR / slice)

- Populate OAuth2 scope descriptions (currently empty in the scopes map).
- Replace the mock `tokenUrl` / `@server` with the real server when it exists.
- `examples/**` + `x-faker`, CI workflow (5 gates), Prism mock smoke (Etap 3) → then tag `v0.1.0`.
