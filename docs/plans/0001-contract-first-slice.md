# 0001 — Перший зріз контракту (auth + articles)

> Living plan (@.claude/rules/living-plan.md). Створено в Plan Mode, схвалено користувачем.

## Goal / scope

Перший компільований зріз контракту в TypeSpec → `openapi.yml` (OpenAPI 3.1):
спільні envelope, auth (user-flow D1 + service-flow D5), один приклад-ресурс `articles` (повний CRUD).
**Не входить:** `examples/**` + `x-faker`, CI workflow, Prism mock smoke, тег `v0.1.0` (наступні етапи).

## Рішення цього зрізу (підтверджені користувачем)

- `articles` — **blog-style** поля: `id, title, slug, body, status(enum), author_id, tags[], created_at, updated_at`.
- Scopes — **read/write split**: `articles:read` (GET), `articles:write` (POST/PATCH/DELETE).
- Доставка — файли + готовий WSL2 блок `git/PR` (пісочниця не має gh/PAT).

## Toolchain-корекції (необхідні для компіляції)

- **Прибрано `@typespec/rest@^0.65.0`** з `package.json` — несумісний peer (`~0.65.0`) з compiler 1.x; не потрібен (усе з `@typespec/http`).
- **Додано `tspconfig.yaml`** з `@typespec/openapi3.openapi-versions: ["3.1.0"]` (D4) + `output-file: openapi.yaml`.

## Структура spec/

```
spec/
├── main.tsp            # @service + @info + @server + @useAuth(BearerAuth) global; import-и
├── auth.tsp            # /auth/* (D1 user-flow + D5 service-flow)
├── articles.tsp        # /api/v1/articles CRUD
└── models/
    ├── pagination.tsp  # ListResponse<T>
    ├── errors.tsp      # ErrorDetail, FieldError, ValidationErrors + error-response моделі
    └── security.tsp    # ServiceOAuth2<Scopes> alias (clientCredentials)
```

## Спільні envelope (@.claude/rules/api-envelope.md)

- `ListResponse<T>` = `{ count: int32; next: url | null; previous: url | null; results: T[] }`.
- `ErrorDetail` = `{ detail: string }` (401/403/404/409/429/500).
- `ValidationErrors` = `{ errors: FieldError[] }`, `FieldError = { field; code; message }` (400).
- 429 — `ErrorDetail` + заголовок `Retry-After` (int32, секунди).
- Error-response моделі (`@error`, `@statusCode`): `ValidationError(400)`, `UnauthorizedError(401)`,
  `ForbiddenError(403)`, `NotFoundError(404)`, `ConflictError(409)`, `RateLimitError(429 + Retry-After)`.

## Auth (@.claude/rules/auth-contract.md)

Security schemes: `bearerAuth` (http bearer, JWT) глобально; `serviceAuth` (oauth2 clientCredentials,
tokenUrl `/auth/token`, scopes `articles:read`/`articles:write`) для S2S. Публічні — `@useAuth(NoAuth)`.

| operationId | Метод + шлях | Security | Запит | Відповіді |
|---|---|---|---|---|
| registerUser | POST /auth/register | NoAuth | RegisterRequest{email,password,name?} | 201 RegisterResponse{user,tokens?} · 400 · 409 |
| loginUser | POST /auth/login | NoAuth | LoginRequest{email,password} | 200 TokenPair{access,refresh} · 400 · 401 |
| refreshToken | POST /auth/refresh | NoAuth | RefreshRequest{refresh} | 200 AccessToken{access, refresh?} · 400 · 401 |
| logoutUser | POST /auth/logout | bearerAuth | RefreshRequest? | 204 · 401 |
| issueServiceToken | POST /auth/token | NoAuth | ServiceTokenRequest{grant_type,client_id,client_secret,scope?} | 200 ServiceTokenResponse{access,token_type,expires_in,scope} · 400 · 401 |

> Refresh transport (D2): access у `Authorization: Bearer`, refresh — у **тілі** відповіді. (ADR 0003.)
> `/auth/token` тіло — JSON (а не form-urlencoded) для самодостатності контракту й тривіальності mock; deviation від класичного OAuth2 — прийнятна для нашої екосистеми, фіксуємо нотаткою.

## Articles — /api/v1/articles, tag `articles` (@.claude/rules/typespec-style.md)

Моделі:
- `ArticleStatus` enum: `draft | published | archived`.
- `Article` (response): `id, title, slug, body, status, author_id, tags[], created_at(utcDateTime), updated_at(utcDateTime)`.
- `ArticleCreate`: `title, body` (required); `slug?, status?(=draft), tags?(=[])`.
- `ArticleUpdate`: усі поля опціональні (`title?, slug?, body?, status?, tags?`).

| operationId | Метод + шлях | Security (scope) | Відповіді |
|---|---|---|---|
| listArticles | GET /api/v1/articles?page&page_size&status&search | bearerAuth \| serviceAuth[articles:read] | 200 ListResponse\<Article\> · 401 · 403 · 429 |
| createArticle | POST /api/v1/articles | bearerAuth \| serviceAuth[articles:write] | 201 Article · 400 · 401 · 403 · 409 · 429 |
| getArticle | GET /api/v1/articles/{id} | bearerAuth \| serviceAuth[articles:read] | 200 Article · 401 · 403 · 404 · 429 |
| updateArticle | PATCH /api/v1/articles/{id} | bearerAuth \| serviceAuth[articles:write] | 200 Article · 400 · 401 · 403 · 404 · 409 · 429 |
| deleteArticle | DELETE /api/v1/articles/{id} | bearerAuth \| serviceAuth[articles:write] | 204 · 401 · 403 · 404 · 429 |

Query params list: `page` (int32, default 1), `page_size` (int32, default 20), `status` (ArticleStatus, опц.), `search` (string, опц.).

## info object (для Spectral oas:all + --fail-severity warn)

`@info`: `version: "0.1.0"`, `description`, `contact{name,url→repo}`, `license{name,url→repo}`.
Top-level `tags` наповнюються з `@tag("auth")` / `@tag("articles")` на операціях.

## Steps (pipeline)

1. api-architect — цей дизайн. ✔
2. tsp-author — написати spec/, compile+bundle, `npm run validate` зелений.
3. contract-reviewer — консистентність, naming, коди, scopes, Spectral-clean.
4. (breaking-change-analyst — SKIP: нема попереднього тегу.)
5. docs-writer — `.claude/memory/endpoints.json`, `docs/api/INDEX.md`, CHANGELOG, цей лог.
6. Фінал — validate зелений, WSL2 git/PR блок.

## Risks

- Іменування security schemes (`bearerAuth`/`serviceAuth`) — емітер може дати `BearerAuth`/`OAuth2Auth`; ключ схеми = consumer-символ, тож фіксуємо стабільні імена зараз.
- Інлайн `@example` мусять бути валідні (gate `--fail-severity warn`) — мінімум, лише де тривіально коректно.
- `/auth/token` JSON замість form — свідома deviation.

## Execution log

- phase done: api-architect — дизайн зафіксовано (docs/plans/0001), package.json/tspconfig виправлено для компіляції.
- phase done: tsp-author — spec/{main,auth,articles}.tsp + spec/models/{pagination,errors,security}.tsp; openapi.yml recompiled (3.1.0); npm run validate GREEN.
- phase done: contract-reviewer — READY FOR PR, 0 blockers; 2 cosmetic should-fix deferred (scope descriptions, mock tokenUrl).
- phase done: docs-writer — endpoints.json (10), docs/api/INDEX.md, CHANGELOG updated.
