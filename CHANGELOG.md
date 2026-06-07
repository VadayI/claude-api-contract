# Changelog

All notable contract changes are documented here. Format derived from `oasdiff changelog`.
Breaking changes are flagged and require a MAJOR version bump (@.claude/rules/breaking-changes.md).

## [Unreleased]

### Added (Etap 2 — first contract slice)
- **Auth (`/auth/*`)**: `registerUser`, `loginUser`, `refreshToken`, `logoutUser` (user-flow, D1) and `issueServiceToken` (service-flow client-credentials, D5).
- **Articles (`/api/v1/articles`)**: full CRUD — `listArticles`, `createArticle`, `getArticle`, `updateArticle`, `deleteArticle` (blog-style; `articles:read` / `articles:write` scopes).
- **Shared envelopes** (`spec/models/`): `ListResponse<T>`, `ErrorDetail`, `ValidationErrors` + `FieldError`, error-response models, `Retry-After` on 429.
- **Security schemes**: `BearerAuth` (http bearer/JWT) + `OAuth2Auth` (client-credentials, scopes `articles:read`/`articles:write`).
- First generated canonical `openapi.yml` (OpenAPI 3.1) from `spec/**/*.tsp`.

### Toolchain
- Removed `@typespec/rest` (incompatible peer with TypeSpec 1.x; not needed).
- Added `tspconfig.yaml` emitting OpenAPI **3.1.0** (D4).

### Notes
- No breaking-change analysis: first release, no prior tag (oasdiff gate SKIPs).
- Earlier: Scaffolding (Etap 1) — `.claude/` config (agents, rules, commands, skills), scripts, CLAUDE.md, README.
