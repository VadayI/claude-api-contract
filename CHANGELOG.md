# Changelog

All notable contract changes are documented here. Format derived from `oasdiff changelog`.
Breaking changes are flagged and require a MAJOR version bump (@.claude/rules/breaking-changes.md).

## [v0.2.0] — 2026-06-07

> **Semver classification:** MINOR (pre-1.0 breaking convention — `0.x` breaking change bumps MINOR)
> oasdiff changelog vs `v0.1.1`: 5 error-level (api-path-removed-without-deprecation) + 5 info-level (endpoint-added) — see below.
> **Breaking changes:** yes — auth endpoint paths renamed from `/auth/*` to `/api/v1/auth/*` (see ADR 0004).

### Changed
- `POST /auth/login` removed; replaced by `POST /api/v1/auth/login` (path renamed — breaking, intentional per ADR 0004).
- `POST /auth/logout` removed; replaced by `POST /api/v1/auth/logout` (path renamed — breaking, intentional per ADR 0004).
- `POST /auth/refresh` removed; replaced by `POST /api/v1/auth/refresh` (path renamed — breaking, intentional per ADR 0004).
- `POST /auth/register` removed; replaced by `POST /api/v1/auth/register` (path renamed — breaking, intentional per ADR 0004).
- `POST /auth/token` removed; replaced by `POST /api/v1/auth/token` (path renamed — breaking, intentional per ADR 0004).

All five renames are listed in `.oasdiff-ignore.txt` to keep the breaking-change gate active for everything else. Consumer impact: update any hardcoded `/auth/` prefix to `/api/v1/auth/`.

---

## [v0.1.1] — 2026-06-07

> Semver classification: **patch** — no paths, schemas, operationIds, required fields, or response shapes changed.
> `oasdiff changelog` reports: "No changes to report, but specs are different" — diff is infrastructure-only (server URL + tokenUrl); no semantic wire-shape change.
> Breaking changes: **none**.

### Changed
- `servers`: Added production server `https://api.example.com` alongside the Prism mock (`http://localhost:4010`). Derived projects should replace this URL with the real one.
- `components.securitySchemes.OAuth2Auth.flows.clientCredentials.tokenUrl`: Updated from `http://localhost:4010/auth/token` to `https://api.example.com/auth/token`.

### Added
- `.oasdiff-ignore.txt`: Allow-list file for consciously accepted deviations (with in-file usage instructions). Keeps the breaking-change gate active for everything not explicitly listed.
- `.spectral.yaml`: Silenced `oas3-server-not-example.com` rule — `api.example.com` is an intentional placeholder for derived projects; documented with a comment in the file.

### Fixed
- `README.md`: Status section updated to reflect `v0.1.0` release and completed Etap 4 consumer inversion.
- `spec/articles.tsp`: Added STUB comment above `listArticles` last-page null example — deferred due to Spectral/AJV null-nullable-3.1 incompatibility; no wire-shape change.

---

## [0.1.0] - 2026-06-07

### Added (Etap 3 — examples, CI, mock)
- **Inline examples** for all 10 operations (`@opExample` in `spec/`) emitting into `openapi.yml` — success responses plus key error envelopes (400 validation, 401/403/404/409/429 simple).
- **`x-faker`** annotations on key schema properties for realistic dynamic mock (`User.email/name`, `Article.title/slug/body/created_at/updated_at`).
- **Request fixtures** under `examples/**` (auth + articles) feeding the mock smoke.
- **Prism mock smoke** gate — `scripts/check_mock.sh` + `npm run mock:smoke` (boots the mock, asserts documented status codes; security enforced).
- **CI** — `.github/workflows/contract-ci.yml` with 5 gates (drift, Spectral lint, examples, oasdiff breaking, mock smoke).
- **Verify handoff** — `docs/verify/etap-3.md`.

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
- Breaking-аналіз (oasdiff): N/A — перший тег, нема бази для порівняння (SKIP).
- Earlier: Scaffolding (Etap 1) — `.claude/` config (agents, rules, commands, skills), scripts, CLAUDE.md, README.
