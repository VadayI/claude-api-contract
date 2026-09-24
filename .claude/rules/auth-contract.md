# Auth in the contract (Bearer/JWT, user-flow + service-flow)

> Loaded per-agent by `api-architect` and `tsp-author`. Decisions #4, D1, D2, D5.

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
| `POST /auth/register` | `[]` public | credentials | user + (optional) tokens |
| `POST /auth/login` | `[]` public | credentials | `access` + `refresh` |
| `POST /auth/refresh` | `[]` public | `refresh` | new `access` (+ optional refresh) |
| `POST /auth/logout` | `bearerAuth` | — / `refresh` | 204 |

**Refresh transport (D2):** `access` in `Authorization: Bearer`, `refresh` **in the response body**. The contract is self-contained and the mock is trivial. An ADR (`docs/decisions/`) must record the XSS trade-off and the option to switch to an httpOnly cookie in a derived project.

### Credential validation defaults

- Model auth email inputs with TypeSpec `@format("email")` so generated clients and schema-based tests do not treat arbitrary strings as valid credentials.
- Require a non-empty password for login (`@minLength(1)`) and at least 8 characters for registration (`@minLength(8)`). Reject NUL characters in both password fields because common framework serializers do not accept them.
- A derived project may apply contextual registration checks such as user similarity or common/breached-password blocklists. Return the documented validation error for these checks; do not encode character-class requirements as a generic password rule.
- Keep the generated OpenAPI schema aligned with portable backend serializer validation. A derived backend's contextual policy may reject a schema-shaped registration request with the documented 400 response.

## Service-to-service flow (D5 — primary client profile)

| Method + path | Security | Request | Response |
|---|---|---|---|
| `POST /auth/token` | `[]` public | `grant_type=client_credentials`, `client_id`, `client_secret` (+ optional `scope`) | `access` (+ `expires_in`, `scope`) |

- **Scopes, not roles**, for services: granular authorization via scopes in the token and `security` on endpoints. Optionally model an explicit `serviceAuth: oauth2 clientCredentials` scheme with a named `scopes` map.
- S2S recommendations (also bind backend): short-lived access (minutes) + a revocation strategy; scopes on every non-public endpoint instead of a bare `bearerAuth: []`; rate limiting (`429` + `Retry-After`, @.claude/rules/api-envelope.md).

## Frontend note

`claude-react-mui` is a browser SPA — the service-flow (client credentials) does **not** apply to it (a browser cannot hold a service secret). The frontend uses the user-flow only.
