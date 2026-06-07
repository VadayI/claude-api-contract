# Lessons (gotchas worth keeping)

## Toolchain / TypeSpec
- **`@typespec/rest` is incompatible with TypeSpec 1.x** (its peer is `@typespec/compiler ~0.65`). For this contract it is **not needed** — everything comes from `@typespec/http` (`@route`, `@get/@post/...`, `@useAuth`, `@server`, `BearerAuth`, `OAuth2Auth`, `NoAuth`) + `@typespec/compiler` (`@service`) + `@typespec/openapi` (`@info`, `@tagMetadata`).
- **OpenAPI 3.1 is NOT the emitter default** (it emits 3.0.0). Set it in `tspconfig.yaml`: `@typespec/openapi3.openapi-versions: ["3.1.0"]`.
- **`@info` has no `description` field** — put the API description via `@doc` on the service namespace; it lands in `info.description`.
- **Built-in `BearerAuth` emits `scheme: Bearer` and no `bearerFormat`** — the TypeSpec http auth model has no `bearerFormat` field. Accepted as-is (canon is generated, never hand-edited).
- **`@friendlyName("{name}List", T)`** turns a generic `ListResponse<T>` into a named, reusable component (e.g. `ArticleList`) instead of an inline anonymous object.

## Spectral gate is stricter than it looks
- `scripts/check_examples.sh` runs `spectral lint --fail-severity warn`, so with `extends: [[spectral:oas, all]]` **every warning is effectively blocking**: `info.description/contact(+email)/license(+url)`, non-empty top-level `tags`, snake_case properties, schema descriptions. Author the spec to satisfy all of them.
- `contact-properties` requires `email` — use a non-personal address (e.g. GitHub no-reply), never a personal one, since the contract is committed and fetched by consumers.

## Environment (sandbox vs host)
- **9p mount NUL-padding:** the Read/Write/Edit file tools, when they SHORTEN a file on the `/mnt` 9p mount, pad the remainder with NUL bytes. Do file writes via bash (`cp`/heredoc), or author in an ext4 sandbox copy and `cp` the result onto the mount. Always check `tr -cd '\000' < f | wc -c` == 0.
- Git/`gh` must run from the host/WSL2 shell (sandbox lacks `gh`/PAT; `.git` on 9p is unsafe to mutate from the sandbox). Prepare a command block instead.

## Examples & TypeSpec @opExample (Etap 3)
- **`@opExample` форми залежать від типу відповіді.** Для відповідей-прямих-типів (`TokenPair`, `Article`, `ListResponse<Article>`) приклад подається плоско. Для відповідей із явним `@statusCode`/`@body` (201 і ВСІ помилки 400/401/403/404/409/429) `@opExample` вимагає повної форми конверта `#{ statusCode: N, body: #{...} }`, інакше компілятор кидає `unassignable`. Кілька `@opExample` на операції розкладаються по статус-кодах за формою типу. Request-приклад — через `parameters: #{ body: #{...} }` (+ `id` для операцій із path-параметром).
- **Spectral 6.16/AJV падає на `null` у прикладах проти nullable-3.1-схем.** Будь-яке значення `null` у `example` проти `type: [T, "null"]` / `anyOf [..., {type: "null"}]` (навіть із `format: uri`) валить лінтер крешем `Cannot read properties of null (reading 'enum')` — це падіння процесу, а не lint-finding, тож examples-гейт червоніє «нізащо». Обхід: не клади літеральний `null` у приклади nullable-полів. Для list-envelope приклад роби «середньою сторінкою» пагінації (`next`/`previous` — URL, не null) — він валідний проти схеми і не фейковий. Поведінку самих полів `null` усе одно описує схема (`next: url | null`).
