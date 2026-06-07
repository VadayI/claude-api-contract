# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining; updated LAST at end of session.

## Status
- **Etap 1 (core scaffold) — DONE & on `main`.** `.claude/` config, scripts, gates, `CLAUDE.md`, ADRs.
- **Etap 2 (first contract slice) — DONE; in review.** Branch `feat/contract-first-slice`, **PR #1 OPEN**: https://github.com/VadayI/claude-api-contract/pull/1
  - `spec/` (TypeSpec) → first canonical `openapi.yml` (OpenAPI **3.1.0**): 7 paths, 10 operations.
  - Auth `/auth/*`: `registerUser, loginUser, refreshToken, logoutUser` (user-flow D1) + `issueServiceToken` (service-flow D5, client-credentials).
  - Articles `/api/v1/articles`: full CRUD (blog-style), scopes `articles:read` / `articles:write`.
  - Envelopes: `ListResponse<T>`, `ErrorDetail`, `ValidationErrors`, `Retry-After` (429). Schemes: `BearerAuth` + `OAuth2Auth`.
  - `npm run validate` GREEN (compile + drift + spectral + examples, 0 warnings). breaking gate SKIP (no prior tag).
  - Registry `.claude/memory/endpoints.json` (10), `docs/api/INDEX.md`, `CHANGELOG`, plan `docs/plans/0001` all updated.

## What's next (in order)
1. **Close PR #1**: commit `package-lock.json` to the branch (`npm ci` reproducibility); confirm `main` branch protection; review & merge. (See `docs/todo.md`.)
2. **Etap 3 (next PR):** `examples/**` + `x-faker`; `.github/workflows/contract-ci.yml` (5 gates: drift, spectral, examples, oasdiff breaking, Prism mock smoke); Prism mock smoke; `docs/verify/*` via `/verify`.
3. **Release `v0.1.0`** via `/release` once Etap 3 gates are green.
4. Later (separate PRs): invert consumers `claude-django` and `claude-react-mui`.

## Decisions locked
- Envelope defaults (list `{count,next,previous,results}`; errors `{detail}`+`{errors[]}`; 429+`Retry-After`).
- Auth: Bearer/JWT, refresh in body (ADR 0003); Variant A source of truth (ADR 0002); WSL2-only (ADR 0001).
- Order: contract to v0.1.0 first, then consumers.

## Accepted deviations (v0.1.0) — see docs/api/INDEX.md
- Security scheme keys `BearerAuth`/`OAuth2Auth` (emitter defaults, stable consumer symbols).
- Bearer scheme emits `scheme: Bearer` without `bearerFormat: JWT` (TypeSpec http limitation; canon not hand-edited).
- `/auth/token` body is JSON (not form-urlencoded) for a self-contained contract + trivial mock.

## Environment notes (see docs/lessons.md)
- Run git/`gh` from the host/WSL2 shell (sandbox lacks gh/PAT; `.git` on 9p unsafe to mutate from sandbox).
- 9p file-tool NUL-padding on shrink — write via bash or author in ext4 sandbox then `cp`.
- `@typespec/rest` dropped (incompatible with compiler 1.x); OpenAPI 3.1 set via `tspconfig.yaml`.
- Spectral examples gate uses `--fail-severity warn` → `spectral:oas` "all" warnings are effectively blocking.
