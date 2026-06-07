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

## oasdiff installation (WSL2)

- **`scripts/setup-wsl.sh` показує інструкції, але не встановлює oasdiff автоматично** — підказує `go install` або `brew`, але `go` зазвичай відсутній у WSL2. Практичний шлях: завантажити бінарник напряму з GitHub Releases.
- **Правильний формат імені архіву:** `oasdiff_{VERSION}_linux_amd64.tar.gz` (не `oasdiff_Linux_x86_64.tar.gz`). Перевіряти актуальні назви через `gh api repos/oasdiff/oasdiff/releases/latest`.
- **sudo недоступний без TTY** (тобто з Bash-tool в Claude Code) — встановлювати у `~/.local/bin` (без sudo), дописати `export PATH="$HOME/.local/bin:$PATH"` у `~/.bashrc`. В нових сесіях PATH підхопиться автоматично; в поточній — потрібен `export PATH=...` перед запуском.
- **`scripts/check_breaking.sh` вимагає oasdiff ще до SKIP-гілки** — навіть коли нема попереднього тегу, скрипт падає на `command -v oasdiff` з exit 1. Тому oasdiff — hard-req для будь-якого реліз-процесу, не лише для v0.2.0+.

## Examples & TypeSpec @opExample (Etap 3)
- **`@opExample` форми залежать від типу відповіді.** Для відповідей-прямих-типів (`TokenPair`, `Article`, `ListResponse<Article>`) приклад подається плоско. Для відповідей із явним `@statusCode`/`@body` (201 і ВСІ помилки 400/401/403/404/409/429) `@opExample` вимагає повної форми конверта `#{ statusCode: N, body: #{...} }`, інакше компілятор кидає `unassignable`. Кілька `@opExample` на операції розкладаються по статус-кодах за формою типу. Request-приклад — через `parameters: #{ body: #{...} }` (+ `id` для операцій із path-параметром).
- **Spectral 6.16/AJV падає на `null` у прикладах проти nullable-3.1-схем.** Будь-яке значення `null` у `example` проти `type: [T, "null"]` / `anyOf [..., {type: "null"}]` (навіть із `format: uri`) валить лінтер крешем `Cannot read properties of null (reading 'enum')` — це падіння процесу, а не lint-finding, тож examples-гейт червоніє «нізащо». Обхід: не клади літеральний `null` у приклади nullable-полів. Для list-envelope приклад роби «середньою сторінкою» пагінації (`next`/`previous` — URL, не null) — він валідний проти схеми і не фейковий. Поведінку самих полів `null` усе одно описує схема (`next: url | null`).

## TypeSpec 1.x — OAuth2 scope descriptions недоступні

- **`OAuth2Scope.description` не заповнюється з `.tsp`-джерела** у TypeSpec 1.x `@typespec/http`. Компілятор (`decorators.js`) мапить кожен scope-рядок `x` лише до `{ value: x }` — поле `description` ніколи не встановлюється.
- Будь-яка спроба додати `scopes: [{ value: "…"; description: "…" }]` у flow-літерал або порушує generic `Scopes extends string[]` (неправильна форма), або змішує flow-level scopes з per-operation `ServiceOAuth2<["…"]>` — в результаті оператор отримує обидва scopes на всіх операціях замість per-operation.
- **Обхід:** чекати поки TypeSpec HTTP розкриє цей API, або відстежити issue upstream. Поточний стан у контракті: `articles:read: ''` / `articles:write: ''` — правильно за схемою, але без описів. Залишено у `docs/todo.md`.

## Stacked PRs + squash-merge (consumer repos)

- **`gh pr merge --squash --delete-branch` на base-гілці auto-CLOSE всі stacked PR**, що мають цю гілку як base. GitHub не перебазовує стек — він просто закриває залежні PR.
- **Безпечні варіанти:**
  1. Squash-merge intermediate PR **без `--delete-branch`**, потім вручну rebase стек, потім delete старі гілки.
  2. Після squash-merge intermediate PR зробити `git rebase origin/main` на наступній гілці → `push --force-with-lease` → перестворити PR з `--base main`.
- **Варіант 2** (rebase + перестворення PR) — чистіший, бо в результаті PR містить лише власні зміни відносно main.
