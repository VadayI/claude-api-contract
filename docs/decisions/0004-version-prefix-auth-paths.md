# ADR 0004 — Version-prefix the auth paths (`/auth/*` → `/api/v1/auth/*`)

**Status:** accepted · **Date:** 2026-06-07

## Context
The auth endpoints lived under `/auth/*` while the resource endpoints (e.g. articles) lived under `/api/v1/articles`. The `/api/v1` prefix is the project-wide versioning doctrine, and the two consumers (`claude-django`, `claude-react-mui`) must agree on a single, consistent path convention. A split namespace (`/auth/*` vs `/api/v1/*`) forces each consumer to special-case auth in its base-URL / SDK config.

## Decision
- Move all 5 auth endpoint paths under the versioned prefix:
  - `POST /auth/register` → `POST /api/v1/auth/register`
  - `POST /auth/login`    → `POST /api/v1/auth/login`
  - `POST /auth/refresh`  → `POST /api/v1/auth/refresh`
  - `POST /auth/logout`   → `POST /api/v1/auth/logout`
  - `POST /auth/token`    → `POST /api/v1/auth/token`
- The OAuth2 client-credentials security scheme `tokenUrl` is updated to match the new `/api/v1/auth/token` path.

## Consequences
- **Breaking change.** Both consumers must update `CONTRACT_VERSION` to `v0.2.0` and change their client base URLs / SDK config to the new auth paths. `claude-django` re-points its auth routes; `claude-react-mui` regenerates its TS client against the new paths.
- The oasdiff breaking gate goes RED against `v0.1.1` (5 × `api-path-removed-without-deprecation`). These specific changes are consciously allow-listed in `.oasdiff-ignore.txt` referencing this ADR; the gate stays active for everything else (it is never weakened or removed).
- **Version bump: `v0.2.0`.** Per the pre-1.0 convention, a backward-incompatible change in the `0.x` series bumps MINOR (a `1.0`-line project would bump MAJOR).
