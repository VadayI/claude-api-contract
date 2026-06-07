# API index (human overview)

> The contract is `openapi.yml` (OpenAPI 3.1). This index is a human-readable overview that points at it; it is not the source of truth.

## Auth
| Method + path | Security | Purpose |
|---|---|---|
| POST /api/v1/auth/register | public | register a user |
| POST /api/v1/auth/login | public | obtain access + refresh |
| POST /api/v1/auth/refresh | public | new access from refresh |
| POST /api/v1/auth/logout | bearerAuth | invalidate session |
| POST /api/v1/auth/token | public | service client-credentials (S2S) |

## <Resource>
| Method + path | operationId | Security / scopes | Envelope | Statuses |
|---|---|---|---|---|
| GET /api/v1/<r> | list<R> | bearerAuth | list | 200,401,403,429 |
