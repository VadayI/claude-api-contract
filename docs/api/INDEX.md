# API index (human overview)

> The contract is `openapi.yml` (OpenAPI 3.1). This index is a human-readable overview that points at it; it is not the source of truth. Every API endpoint carries a **surface** (@.claude/rules/endpoint-surface.md): `resource` (frontend-facing API) or `system` (machinery the browser never calls). Frontend **pages** are a separate map (`.claude/memory/pages.json`), not API endpoints.

## API — Auth
| Method + path | Security | Surface | Purpose |
|---|---|---|---|
| POST /api/v1/auth/register | public | resource | register a user |
| POST /api/v1/auth/login | public | resource | obtain access + refresh |
| POST /api/v1/auth/refresh | public | resource | new access from refresh (transport; no page) |
| POST /api/v1/auth/logout | bearerAuth | resource | invalidate session (transport; no page) |
| POST /api/v1/auth/token | public | **system** | service client-credentials (S2S) — **no frontend page** |

## API — \<Resource\>
| Method + path | operationId | Security / scopes | Surface | Envelope | Statuses |
|---|---|---|---|---|---|
| GET /api/v1/\<r\> | list\<R\> | bearerAuth | resource | list | 200,401,403,429 |

## Pages (frontend route map)
> From `.claude/memory/pages.json`. The SPA scaffolds a page/route per row; a page never targets a `system` operation.

| Route | Page | Auth | Consumes (operationId) |
|---|---|---|---|
| /register | Register | public | registerUser |
| /login | Login | public | loginUser |
| /articles | Articles list | bearer | listArticles |
| /articles/new | New article | bearer | createArticle |
| /articles/{id} | Article detail | bearer | getArticle |
| /articles/{id}/edit | Edit article | bearer | getArticle, updateArticle, deleteArticle |
