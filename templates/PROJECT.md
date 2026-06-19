# <Project> — API contract brief

**Type:** claude-api-contract (single source of truth for the REST API)
**Status:** <design | v0.1.0 | ...>
**Date:** <YYYY-MM-DD>
**Maturity stage:** <demo | prototype | PoC | MVP | production | other> <!-- scales pipeline depth; see .claude/rules/project-maturity.md -->

## 1. Purpose
<Why this API exists; who consumes it (services / browser SPA / mobile).>

## 2. Resources & surfaces
<List the resources and their endpoints (method + path + purpose + auth/scopes + surface: `resource` | `system` — @.claude/rules/endpoint-surface.md).>
<Frontend pages: the SPA routes (page-map in `.claude/memory/pages.json`) and which operations each consumes. `system` endpoints (e.g. S2S `/api/v1/auth/token`) get no page.>

## 3. Auth profile
- User-flow (D1): register / login / refresh / logout — Bearer/JWT, refresh in body (D2).
- Service-flow (D5): `POST /api/v1/auth/token` client-credentials + scopes (if S2S).

## 4. Envelopes
- list: `{ count, next, previous, results: T[] }`
- errors: `{ detail }` + `{ errors: [{ field, code, message }] }`
- 429 + `Retry-After`

## 5. Versioning & consumers
- semver on git tags; consumers pin `CONTRACT_VERSION`.
- Consumers: <claude-django (validates) · claude-react-mui (generates types)>.

## 6. Open questions
<Gaps — never invented; resolved before authoring spec/models.>

## 7. Definition of Done — ready contract

**Agreed on:** <YYYY-MM-DD>

### Standard gates (always required)
- [ ] `npm run validate` green (TypeSpec drift · Spectral lint · example validation)
- [ ] `npm run breaking` classified; semver bump stated in the PR description
- [ ] Prism mock smoke passes (`npm run mock`)
- [ ] `.claude/memory/endpoints.json` complete and up-to-date
- [ ] `docs/api/INDEX.md` reflects all new/changed endpoints
- [ ] PR open, contract-reviewer passed, no hand-edited `openapi.yml`

### Project-specific criteria
<Add conditions agreed with the team — e.g. "all auth endpoints + Article CRUD done", "v1.0.0 tagged and pushed", "frontend mock deployed to staging", etc. Never leave this blank — if there are no extra criteria, write "none beyond standard gates".>

## 8. Happy paths
Primary success journeys (full detail in `docs/api/HAPPY-PATHS.md` — generate with `/happy-paths`):
- <Journey name> — <one line, plain language>.
