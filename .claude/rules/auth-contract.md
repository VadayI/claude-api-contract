# Auth in the contract (Bearer/JWT, user-flow + service-flow)

> Loaded by `api-architect`, `tsp-author`, `contract-reviewer`, `happy-path-author` (agents) and `/bootstrap` (command). Decisions #4, D1, D2, D5.

The contract **describes its own auth** so the Prism mock can issue tokens and a frontend can authenticate autonomously before any real backend exists.

## Security scheme (global)

```yaml
components:
  securitySchemes:
    bearerAuth: { type: http, scheme: bearer, bearerFormat: JWT }
security:
  - bearerAuth: []        # global default; public endpoints override with security: []
```

## User-flow endpoints (D1 = B)

| Method + path | Security | Request | Response |
|---|---|---|---|
| `POST /api/v1/auth/register` | `[]` public | credentials | user + (optional) tokens |
| `POST /api/v1/auth/login` | `[]` public | credentials | `access` + `refresh` |
| `POST /api/v1/auth/refresh` | `[]` public | `refresh` | new `access` (+ optional refresh) |
| `POST /api/v1/auth/logout` | `bearerAuth` | — / `refresh` | 204 |

**Refresh transport (D2):** `access` in `Authorization: Bearer`, `refresh` **in the response body**. The contract is self-contained and the mock is trivial. An ADR (`docs/decisions/`) must record the XSS trade-off and the option to switch to an httpOnly cookie in a derived project.

## Service-to-service flow (D5 — primary client profile)

| Method + path | Security | Request | Response |
|---|---|---|---|
| `POST /api/v1/auth/token` | `[]` public | `grant_type=client_credentials`, `client_id`, `client_secret` (+ optional `scope`) | `access` (+ `expires_in`, `scope`) |

- **Scopes, not roles**, for services: granular authorization via scopes in the token and `security` on endpoints. Optionally model an explicit `serviceAuth: oauth2 clientCredentials` scheme with a named `scopes` map.
- S2S recommendations (also bind backend): short-lived access (minutes) + a revocation strategy; scopes on every non-public endpoint instead of a bare `bearerAuth: []`; rate limiting (`429` + `Retry-After`, `.claude/rules/api-envelope.md`).

## Frontend note

`claude-react-mui` is a browser SPA — the service-flow (client credentials) does **not** apply to it (a browser cannot hold a service secret). The frontend uses the user-flow only.
