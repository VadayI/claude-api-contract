# <Project> — API contract brief

**Type:** claude-api-contract (single source of truth for the REST API)
**Status:** <design | v0.1.0 | ...>
**Date:** <YYYY-MM-DD>

## 1. Purpose
<Why this API exists; who consumes it (services / browser SPA / mobile).>

## 2. Resources
<List the resources and their endpoints (method + path + purpose + auth/scopes).>

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
