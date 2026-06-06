# Вимоги до шаблону `claude-api-contract`

**Статус:** оновлено після дослідження інструментів (D1/D2/OpenAPI-версія підтверджені)
**Автор:** VadayI
**Дата:** 2026-06-06
**Тип:** Claude Code configuration template (третій у наборі)

-----

## 1. Призначення

`claude-api-contract` — це третій шаблон Claude Code config, який стає **єдиним джерелом істини (single source of truth) для REST API контракту**. Він проєктує і релізить мовно-нейтральний `openapi.yml`, від якого **паралельно і незалежно** стартують backend (`claude-django`) і frontend (`claude-react-mui`).

### Проблема, яку він вирішує

У поточній схемі контракт народжується в backend: `drf-spectacular` генерує `openapi.yml` із серіалізаторів/в’юх, а frontend його споживає (`npm run api:pull`). Наслідок — **frontend не може початися по-справжньому, доки backend не напише хоча б серіалізатори**. Контракт прив’язаний до реалізації.

`claude-api-contract` робить контракт **незалежним артефактом**: спроєктований першим, він дозволяє обом командам стартувати одночасно — frontend проти mock-сервера, backend проти контракту як специфікації.

### Модель джерела істини (варіант A)

```
                    ┌─────────────────────────┐
                    │   claude-api-contract    │
                    │   openapi.yml (canonical)│  ◄── єдине джерело істини
                    └───────────┬──────────────┘
                      git tag (semver) + raw URL
              ┌───────────────────┴───────────────────┐
              ▼                                         ▼
   ┌──────────────────┐                      ┌──────────────────┐
   │  claude-django   │                      │ claude-react-mui │
   │  СПОЖИВАЄ контракт│                      │ СПОЖИВАЄ контракт │
   │  валідує реалізацію│                     │ генерує TS-типи   │
   │  проти нього       │                     │ + mock на ранній  │
   │  (НЕ генерує сам)  │                      │   стадії          │
   └──────────────────┘                      └──────────────────┘
```

Обидва споживачі **тільки споживають** контракт. Жоден його не генерує. Зміна контракту — це свідома дія в `claude-api-contract` через Pull Request, а не побічний ефект коду в споживачі.

-----

## 2. Ключові рішення (зафіксовані)

|#|Рішення                     |Значення                                                                                        |
|-|----------------------------|------------------------------------------------------------------------------------------------|
|1|Модель джерела істини       |**Варіант A** — contract-репо canonical; backend і frontend обидва споживають                   |
|2|Авторинг контракту          |**TypeSpec** → компіляція в єдиний `openapi.yml`                                                |
|3|Розбивка вихідного файлу    |**Один** плаский `openapi.yml` (bundled, без зовнішніх `$ref`)                                  |
|4|Auth-схема                  |**Bearer / JWT** (`bearerAuth`, `type: http`, `scheme: bearer`, `bearerFormat: JWT`)            |
|5|Mock-сервер                 |**Prism (Stoplight)** — живий мок прямо з `openapi.yml`                                         |
|6|Доставка контракту          |**git tag (semver) + raw URL**, споживачі пінять `CONTRACT_VERSION`                             |
|7|Детекція breaking-changes   |**oasdiff** проти попереднього тегу (breaking = червоний CI)                                    |
|8|Філософія Claude Code config|**Зберігається повністю** (агенти / rules / skills / commands / WSL2 / PR-only / контекст у git)|
|9|Назва репо                  |`claude-api-contract`                                                                           |

### Підтверджені рішення (раніше — рекомендовані дефолти)

|# |Питання                 |**Підтверджено**                                                       |Примітка                                                                                  |
|--|------------------------|-----------------------------------------------------------------------|------------------------------------------------------------------------------------------|
|D1|Набір auth-ендпоінтів   |**B** — `login` + `refresh` + `logout` + `register`                    |`register` легше прибрати в похідному проєкті, ніж додати; дає автономний цикл проти mock |
|D2|Транспорт refresh-токена|**refresh у тілі відповіді**                                           |Контракт самодостатній, mock тривіальний. ADR має зафіксувати XSS-вартість і опцію cookie|
|D3|Семвер-правило          |breaking = **major** bump                                              |Примусово через oasdiff `--fail-on ERR`                                                   |
|D4|Версія OpenAPI          |**OpenAPI 3.1**                                                        |Повна JSON Schema; узгоджено з TypeSpec, `openapi-typescript`, `schemathesis` (див. §14)  |
|D5|Основний профіль клієнтів|**Service-to-service (S2S)** — API споживають інші сервіси            |Підсилює вибір Bearer/JWT. Auth має передбачати service-flow, не лише user-flow (див. §5) |

> **D5 — наслідки для auth.** Оскільки більшість похідних API споживатимуть інші сервіси (server-to-server, mobile, сторонні клієнти), Bearer/JWT — однозначно правильний дефолт: cookie/CSRF прив’язані до браузера й тут не підходять. Це знімає актуальність порад «access у пам’яті» та httpOnly-cookie (вони для браузерного SPA проти XSS). Натомість контракт має передбачати **service-flow** (client credentials + scopes) поряд із user-flow (D1). Для S2S XSS-ризик D2 відсутній — refresh у тілі лишається чистим рішенням.

> **D2 — обов’язкова примітка в ADR.** Refresh у тілі означає, що frontend зберігає його на клієнті (memory/localStorage), що слабше проти XSS, ніж httpOnly-cookie. Для стартового шаблону + автономного mock це прийнятний trade-off, але похідний проєкт має могти свідомо перемкнутись на cookie — це фіксується в ADR auth-mode.

-----

## 3. Стек і середовище

**Стек авторингу:**

- **TypeSpec** (`@typespec/compiler`, `@typespec/openapi3`, `@typespec/http`, `@typespec/rest`) — DSL для опису API
- **OpenAPI 3.1** — формат канонічного виходу
- **Spectral** (`@stoplight/spectral-cli`) — lint контракту (шаровий рулсет, див. §13)
- **Prism** (`@stoplight/prism-cli`) — mock-сервер + валідація запитів/відповідей
- **oasdiff** — детекція breaking-changes між версіями
- **Node 20.19+** — тулчейн (консистентно з `claude-react-mui`; `openapi-typescript` рекомендує Node 20.x+)

**Середовище (як у двох інших шаблонів):**

- WSL2 Ubuntu на Windows (обов’язково) / Linux / macOS
- Claude Code CLI (термінальний `claude`)
- GitHub як джерело істини
- bash-only (gate-скрипти й хуки — bash)
- **НЕ підтримується:** Cowork, Windows-native shells, Claude API/SDK standalone (як у попередніх шаблонів — через відсутність SessionStart-хука)

-----

## 4. Виходи шаблону (артефакти)

Канонічний продукт — **мовно-нейтральний `openapi.yml`**. Решта — допоміжні артефакти навколо нього.

|Артефакт                   |Шлях                         |Призначення                                               |
|---------------------------|-----------------------------|----------------------------------------------------------|
|Канонічний контракт        |`openapi.yml` (корінь)       |Єдине джерело істини, OpenAPI 3.1, bundled, Spectral-clean|
|Вихідний код контракту     |`spec/**/*.tsp`              |TypeSpec-джерело, з якого компілюється `openapi.yml`      |
|Людський індекс ендпоінтів |`docs/api/INDEX.md`          |Огляд для людини, вказує на `openapi.yml` як контракт     |
|Приклади запитів/відповідей|`examples/**`                |Валідовані проти схеми, годують mock (static + `x-faker`) |
|Конфіг mock-сервера        |`prism.config.*` / npm-скрипт|Підняття Prism із `openapi.yml`                           |
|Версіонований реліз        |git tag `vX.Y.Z`             |Пін для споживачів                                        |
|Changelog контракту        |`CHANGELOG.md`               |Що змінилось між версіями, breaking-помітки (oasdiff)     |

**Що НЕ є виходом:**

- TS-типи — frontend генерує локально через `openapi-typescript` (як зараз)
- Python-моделі — backend не потребує згенерованого коду, валідує реалізацію проти контракту
- Жодного мовно-специфічного коду в каноні

-----

## 5. Auth у контракті

Контракт **сам описує auth-ендпоінти**, щоб mock віддавав токени і frontend міг логінитись автономно ще до першого ендпоінта backend.

### Security scheme

```yaml
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
security:
  - bearerAuth: []   # глобально, з security: [] на публічних ендпоінтах
```

### Auth-ендпоінти (D1 = B, підтверджено)

|Метод + шлях         |Security        |Запит        |Відповідь                      |
|---------------------|----------------|-------------|-------------------------------|
|`POST /auth/register`|`[]` (публічний)|credentials  |user + (опц.) токени           |
|`POST /auth/login`   |`[]` (публічний)|credentials  |`access` + `refresh`           |
|`POST /auth/refresh` |`[]` (публічний)|`refresh`    |новий `access` (+ опц. refresh)|
|`POST /auth/logout`  |`bearerAuth`    |— / `refresh`|204                            |

> **Транспорт refresh (D2, підтверджено):** access у `Authorization: Bearer`, refresh — **у тілі відповіді**. Контракт повністю самодостатній, mock тривіальний.

### Service-to-service auth (D5)

Оскільки основний профіль клієнтів — інші сервіси, контракт має передбачати **machine-to-machine** автентифікацію поряд із user-flow. Сервіс автентифікується не логіном/паролем користувача, а власними обліковими даними (`client_id` / `client_secret`).

|Метод + шлях         |Security        |Запит                          |Відповідь                         |
|---------------------|----------------|-------------------------------|----------------------------------|
|`POST /auth/token`   |`[]` (публічний)|`grant_type=client_credentials`, `client_id`, `client_secret` (+ опц. `scope`)|`access` (+ `expires_in`, `scope`)|

**Scopes замість простих ролей.** Для сервісів важлива гранульована авторизація (який сервіс що може), а не людська ролі-модель. Виражається через scopes у токені та `security` на ендпоінтах:

```yaml
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
    # опційно — повний OAuth2 client-credentials, якщо потрібен явний scope-контракт
    serviceAuth:
      type: oauth2
      flows:
        clientCredentials:
          tokenUrl: /auth/token
          scopes:
            "orders:read": Читання замовлень
            "orders:write": Створення/зміна замовлень
security:
  - bearerAuth: []
# приклад scope-обмеженого ендпоінта:
#   security: [{ serviceAuth: ["orders:write"] }]
```

> **Рекомендації для S2S-профілю** (фіксуються в `rules` контракту й вимогах до backend):
> - **короткий access** (хвилини) + чітка revocation-стратегія — витік секрета сервіса інакше дає ширший доступ;
> - **scopes** в усіх не-публічних ендпоінтах замість єдиного `bearerAuth: []`;
> - **rate limiting** на рівні контракту — сервіси б’ють API інтенсивніше за людей (див. `429` в envelope помилок, §12).

-----

## 6. Pipeline і агенти

Зберігаємо агентний флоу, адаптований під contract-first.

```
Feature (новий ресурс/ендпоінт):
  ba → api-architect (проєктує контракт) → tsp-author (пише TypeSpec)
     → [contract-reviewer | breaking-change-analyst]
     → mock-validator → docs-writer (INDEX.md + CHANGELOG)
```

### Орієнтовний склад агентів

|Агент                    |Призначення                                             |Модель|
|-------------------------|--------------------------------------------------------|------|
|`ba`                     |Бізнес-аналіз, user stories, scope ендпоінтів           |opus  |
|`api-architect`          |REST-контракт: ресурси, коди, permissions, версіонування|opus  |
|`tsp-author`             |Реалізація контракту в TypeSpec                         |sonnet|
|`contract-reviewer`      |Рев’ю контракту перед PR (консистентність, naming, коди)|opus  |
|`breaking-change-analyst`|Аналіз oasdiff, класифікація breaking vs non-breaking   |opus  |
|`mock-validator`         |Перевірка прикладів і поведінки mock проти схеми        |sonnet|
|`docs-writer`            |`docs/api/INDEX.md`, `CHANGELOG.md`, опис PR            |sonnet|

*(Опціональні агенти — `devil`, `integration-architect`, `auditor`, `brief-synthesizer` — як у попередніх шаблонів.)*

-----

## 7. CI Gates (hard, червоні)

|Gate                   |Інструмент             |Падає коли                                          |
|-----------------------|-----------------------|----------------------------------------------------|
|**TypeSpec drift**     |`tsp compile` + diff   |рекомпіляція `.tsp` ≠ закоміченому `openapi.yml`    |
|**Spectral lint**      |`spectral lint`        |контракт порушує style-rules (naming, описи, коди)  |
|**Валідація прикладів**|Prism / схема-валідатор|приклад у `examples/**` не валідний проти схеми     |
|**Breaking-change**    |`oasdiff breaking --fail-on ERR`|breaking-зміна vs попередній тег без major-bump |
|**Mock smoke-тест**    |Prism + запит          |mock не піднімається або не віддає валідну відповідь|

> **Ключова відмінність від двох інших шаблонів:** breaking-change gate — first-class. Оскільки контракт споживають ДВА репо, ламка зміна має падати в CI **до релізу**, інакше тихо розламає обидві команди одночасно.

-----

## 8. Версіонування і доставка

**Версіонування:** semver на git-тегах (`vX.Y.Z`).

- **major** — breaking-зміна (oasdiff gate змушує)
- **minor** — новий ендпоінт / поле, зворотно сумісне
- **patch** — описи, приклади, виправлення без зміни форми

**Доставка в споживачі:** git tag + raw URL, пін на версію.

- Споживач тримає `CONTRACT_VERSION=vX.Y.Z` (env / config)
- Тягне саме цей тег: `https://raw.githubusercontent.com/VadayI/claude-api-contract/<tag>/openapi.yml`
- Підняття піна = свідомий PR у споживачі, ніколи не автоматичний drift

```
claude-react-mui:  npm run api:pull   →  тягне openapi.yml@CONTRACT_VERSION
                   npm run api:types  →  openapi-typescript → schema.d.ts
claude-django:     scripts/pull_contract.sh → openapi.yml@CONTRACT_VERSION
                   валідація реалізації проти нього (schemathesis + drf-openapi-tester)
```

-----

## 9. Зміни в існуючих споживачах (важливо)

Варіант A інвертує існуючу логіку. Це окремі правки в двох інших репо, без них схема не запрацює. Нижче — **обов’язкові вимоги** до кожного похідного шаблону як чеклісти. Порядок: спершу `claude-api-contract` до тегу `v0.1.0`, потім кожне репо — **окремим PR**.

### `claude-django` (backend) — вимоги

**Контракт як джерело істини (інверсія):**
- [ ] **Прибрати** генерацію `openapi.yml` через `drf-spectacular` як джерело істини.
- [ ] **Інвертувати drift-gate:** замість «код → схема, diff = червоний» — «реалізація **проти зовнішнього контракту**, розбіжність = червоний». Два рівні валідації (див. §13):
  - **schemathesis** — property-based, ганяє згенеровані запити проти запущеного backend, ловить 500/schema violations/response conformance (пін версії, 3.1);
  - **drf-openapi-tester** (`SchemaTester` / `OpenAPIClient`) — точкова валідація DRF-відповідей проти зовнішнього `openapi.yml` у pytest.
- [ ] Додати `scripts/pull_contract.sh` + пін `CONTRACT_VERSION`.
- [ ] `drf-spectacular` лишити лише для Swagger UI / Redoc, **не як канон**.
- [ ] Оновити `.claude/rules/api-docs.md`: контракт зовнішній, не генерований.

**Auth під S2S-профіль (D5) — backend має реалізувати:**
- [ ] **User-flow** (D1): `register` / `login` / `refresh` / `logout`, Bearer/JWT, refresh у тілі (D2).
- [ ] **Service-flow** (D5): `POST /auth/token` з `grant_type=client_credentials` (`client_id`/`client_secret`); модель/сторедж клієнтських облікових даних сервісів.
- [ ] **Scope-based permissions:** DRF permission-класи перевіряють scopes токена, а не лише ролі користувача (узгоджено зі `security` в контракті).
- [ ] **Короткий access + revocation-стратегія** (blacklist/rotation) — політика на рівні налаштувань.
- [ ] **Rate limiting** (DRF throttling) з відповіддю `429` + `Retry-After`, форма — за envelope контракту (§12).

### `claude-react-mui` (frontend) — вимоги

- [ ] **Auth ADR розходиться:** поточний «default session/CSRF auth mode» суперечить рішенню №4 (Bearer/JWT). `api-client` перевести на **Bearer + refresh-flow** замість cookie/CSRF.
- [ ] На ранній стадії `VITE_API_BASE_URL` → **Prism mock**, потім staging backend.
- [ ] `npm run api:pull` тягне з `claude-api-contract`, а не з backend-репо.
- [ ] Обробка `429` + `Retry-After` у транспортному шарі (retry/backoff).
- [ ] Оновити ADR (auth mode) + `.claude/rules/api-client.md`.

> **Примітка про релевантність S2S для frontend.** `claude-react-mui` — браузерний SPA, тож service-flow (client credentials) його **не стосується** — секрет сервіса не можна тримати у браузері. Frontend користується лише user-flow. Service-flow — суто backend + сервіси-споживачі поза цими двома шаблонами.

### Спільні вимоги до обох споживачів

- [ ] Пін `CONTRACT_VERSION` на конкретний тег; підняття піна — свідомий PR, ніколи не авто-drift.
- [ ] Жоден споживач **не генерує** контракт — лише споживає.
- [ ] CI споживача червоніє, якщо реалізація/типи розходяться з пінненою версією контракту.

-----

## 10. Структура репо (орієнтовна)

```
claude-api-contract/
├── .claude/
│   ├── agents/         # ba, api-architect, tsp-author, contract-reviewer,
│   │                   #   breaking-change-analyst, mock-validator, docs-writer
│   ├── commands/       # /bootstrap, /doctor, /preflight, /audit, /wrap-up,
│   │                   #   /create-pr, /review-pr, /fix-ci, /release,
│   │                   #   /validate-contract, /breaking-check, /mock
│   ├── rules/          # contract-first, typespec-style, versioning,
│   │                   #   breaking-changes, git-operations, environment, ...
│   ├── skills/         # typespec-authoring, openapi-design, spectral-lint,
│   │                   #   prism-mock, oasdiff-breaking, ...
│   ├── memory/         # env-detect.json, command-log.jsonl (gitignored де треба)
│   └── settings.json
├── spec/               # TypeSpec-джерело (*.tsp)
│   ├── main.tsp        # точка входу (service-декоратор + роутинг), аналог index.ts
│   ├── auth.tsp
│   └── models/         # спільні моделі + envelope (list / error)
├── examples/           # приклади запитів/відповідей (валідовані; x-faker де доречно)
├── docs/
│   ├── api/INDEX.md    # людський індекс ендпоінтів
│   ├── decisions/      # ADR
│   └── WORKLOG.md
├── scripts/            # detect-env.mjs, gate-скрипти (check_*.sh), log-cmd.mjs
├── templates/          # scaffold-входи для /bootstrap
├── openapi.yml         # ◄ КАНОНІЧНИЙ ВИХІД (bundled, OpenAPI 3.1)
├── .spectral.yaml      # шаровий рулсет (extends spectral:oas + кастомні правила)
├── .github/workflows/  # contract-ci.yml (5 gate'ів)
├── CHANGELOG.md
├── CLAUDE.md
└── README.md
```

-----

## 11. Slash-команди (нові / специфічні)

Поверх стандартного набору (`/bootstrap`, `/doctor`, `/preflight`, `/audit`, `/wrap-up`, `/create-pr`, `/review-pr`, `/fix-ci`, `/synthesize-brief`, `/set-language`, `/handoff`):

|Команда                |Дія                                                          |
|-----------------------|-------------------------------------------------------------|
|`/validate-contract`   |Spectral lint + валідація прикладів + TypeSpec drift локально|
|`/breaking-check [ref]`|oasdiff проти попереднього тегу, класифікація змін           |
|`/mock [port]`         |Підняти Prism mock із поточного `openapi.yml`                |
|`/release [version]`   |Зібрати `openapi.yml`, оновити CHANGELOG, поставити тег, push|

-----

## 12. Відкриті питання

### Закриті (цей раунд)

- ✅ **D1** — набір auth-ендпоінтів: **B** (з `register`).
- ✅ **D2** — транспорт refresh: **тіло відповіді** (з ADR-приміткою про XSS).
- ✅ **OpenAPI 3.1 vs 3.0** — **3.1** (сумісність інструментів підтверджена, див. §14).

### Лишаються на підтвердження

1. **Пагінація / помилки (envelope).** Рекомендація — стандартизувати єдиний формат одразу на рівні контракту, **до** написання `spec/models/`:
   - **list:** `{ count, next, previous, results: T[] }` — збігається з дефолтом DRF (backend майже не адаптується) і дає frontend стабільну форму для TanStack Query.
   - **errors:** єдиний envelope, напр. `{ detail }` для простих та `{ errors: [{ field, code, message }] }` для валідаційних — щоб усі 4xx мали передбачувану структуру.
   - **`429` Too Many Requests** (важливо для S2S, D5): стандартизувати в контракті як частину error-envelope разом із заголовком **`Retry-After`** — сервіси-споживачі б’ють API інтенсивніше за людей, тож rate-limit має бути передбачуваним і описаним одразу.
2. **Порядок впровадження.** Рекомендація — спершу довести `claude-api-contract` до першого тегу `v0.1.0`, потім правити двох споживачів **окремими PR** (кожна інверсія ревʼюється ізольовано).

-----

## 13. Рекомендації з реалізації (за результатами дослідження)

Конкретні практики по кожному інструменту — основа для деталізації агентів, skills і gate-скриптів.

### TypeSpec (skill `typespec-authoring`, агент `tsp-author`)

- `main.tsp` — точка входу (аналог `index.ts`); велику специфікацію розбивати на файли/папки/модулі через `import`.
- Спільні моделі та envelope тримати в `spec/models/` як перевикористовувані одиниці (підхід Azure — підіймати спільне до рівня бібліотек).
- Версійні анотації TypeSpec вбудовані; при руйнівному зломі специфікацію можна «скинути» до базової версії й продовжити нумерацію — згадати в `rules/versioning.md`.
- TypeSpec емітить nullability у 3.1-стилі (`type: [T, 'null']`) — це коректно споживається `openapi-typescript`.

### Spectral (skill `spectral-lint`, gate «Spectral lint»)

- **Шаровий рулсет, не копія чужого.** `.spectral.yaml` має `extends: spectral:oas` плюс кастомні правила під ваш naming / коди / envelope.
- Порядок крафту правил: спершу покластися на **JSON Schema**, потім опанувати **дефолтні функції Spectral**, і лише тоді — **custom-функції** (JS).
- Дефолтний `spectral:oas` навмисно мінімальний — обовʼязково розширювати (camelCase властивостей, наявність `summary`/`tags`/`operationId`, обовʼязкові error-responses).
- Прапор `recommended` на правилах — для поступового rollout у похідних проєктах.
- Готові рулсети для запозичення правил: **Zalando** (версіонування, naming, формат request/response) і **DigitalOcean** (naming `operationId`, дисципліна `$ref`).

### oasdiff (skill `oasdiff-breaking`, gate «Breaking-change», команда `/breaking-check`)

- У CI: `oasdiff breaking <base> <revision> --fail-on ERR` → exit code 1 на ERR-level (це і є major-gate). `--fail-on WARN` — суворіший режим.
- Офіційний GitHub Action: `oasdiff/oasdiff-action/breaking`.
- Свідомо дозволені breaking — через config + `--err-ignore` (для WARN — `--warn-ignore`).
- `oasdiff changelog <base> <revision>` — авто-генерація для `CHANGELOG.md` (годувати з `docs-writer`).
- Обробляє перейменовані path-параметри; вміє виключати зміни лише в описах (щоб patch-описи не падали як breaking) та відстежувати `x-*` розширення.

### Prism (skill `prism-mock`, gate «Mock smoke» + «Валідація прикладів», команда `/mock`)

- Два режими: **static** (за замовчуванням, з `examples`) і **dynamic** (`-d`, через Faker.js). Рекомендація: `examples/**` годують детермінований static-mock для тестів; `-d` — для перевірки, що frontend не крихкий до варіацій даних.
- Кастомне поле **`x-faker`** у схемах керує генерацією конкретних полів у dynamic-режимі.
- Prism робить **двосторонню валідацію** (запит і відповідь проти схеми) — це закриває одразу gate «Mock smoke» і «Валідація прикладів».
- Режим **`prism proxy`** — contract testing проти живого API (опційно для staging-перевірки).
- У Docker запускати з `-h 0.0.0.0`, інакше mock недоступний поза контейнером.
- Live reload при зміні `openapi.yml`. Чим повніші `examples`/діапазони/validation-ключі у схемі — тим ближчий mock до реального API (мотивація для `mock-validator`).

### Backend-валідація (`claude-django`)

- **Два рівні** замість генерації:
  - `schemathesis` — property-based, генерує структурно валідні, але несподівані входи; з коробки перевіряє server errors, status-code/response conformance, content-type. Запінити версію (3.1 — first-class у сучасних релізах).
  - `drf-openapi-tester` (snok) / `django-contract-tester` — валідує DRF/Django Ninja відповіді проти зовнішнього `openapi.yml` (підтримка 2.0/3.0.x/3.1.x, yaml+json) через `SchemaTester` / `OpenAPIClient` у pytest.
- `drf-spectacular` лишається лише для Swagger UI/Redoc, не як канон.

### Frontend-споживання (`claude-react-mui`)

- `openapi-typescript` — повна підтримка 3.1 (включно з discriminator/поліморфізмом і nullability 3.1), runtime-free типи, Node 20+.
- MSW — inner-loop (мережевий boundary у Vitest); Prism — outer-loop/dev проти контракту.
- Головна правка — auth-інверсія (Bearer + refresh замість session/CSRF).

-----

## 14. Підтверджена сумісність версій (OpenAPI 3.1)

| Інструмент            | Стан підтримки 3.1                                                                 | Нюанс / дія                                                        |
|-----------------------|------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| TypeSpec → openapi3   | Канонічний вихід 3.1                                                                | Емітить nullability 3.1-стилю                                      |
| `openapi-typescript`  | Повна 3.1 (discriminator, поліморфізм)                                              | Рекомендує Node 20.x+                                              |
| `schemathesis`        | 3.1 first-class у сучасних версіях (раніше — експериментально; підтримує й 3.2)     | **Запінити версію** у backend, не покладатися на стару             |
| `drf-openapi-tester`  | 3.0.x / 3.1.x, yaml+json                                                            | Другий рівень валідації backend                                   |
| Prism                 | OpenAPI 3.1 / 3.0 / 2.0                                                             | Двостороння валідація + mock                                      |
| Spectral              | OpenAPI 3.1 / 3.0 / 2.0                                                             | Шаровий рулсет                                                    |
| oasdiff               | OpenAPI 3.x                                                                         | `--fail-on ERR` у CI                                              |

**Висновок:** 3.1 безпечно для всього стеку. Єдиний практичний нюанс — пін версії `schemathesis` у backend.

-----

## 15. Найцінніші доповнення до шаблону (поверх первинних вимог)

1. **Шаровий Spectral** із запозиченням правил із Zalando/DigitalOcean замість мінімального дефолту.
2. **`x-faker`** у `examples/` для реалістичного dynamic-mock.
3. **`oasdiff changelog`** для авто-`CHANGELOG.md` (через `docs-writer`).
4. **`--err-ignore` config** для свідомо дозволених breaking без зняття gate.
5. **`drf-openapi-tester` як другий рівень** backend-валідації поряд зі `schemathesis`.
6. **Пін версії `schemathesis`** як частина `scripts/pull_contract.sh` / залежностей backend.

-----

## 16. Джерела / посилання

**TypeSpec**
- Speakeasy — OpenAPI & SDK з TypeSpec: https://www.speakeasy.com/openapi/frameworks/typespec
- Azure — TypeSpec structure guidelines: https://github.com/Azure/azure-rest-api-specs/blob/main/documentation/typespec-structure-guidelines.md
- Офіційна дока openapi-ts: https://openapi-ts.dev/

**openapi-typescript**
- npm: https://www.npmjs.com/package/openapi-typescript
- Changelog (3.1 / discriminator): https://github.com/openapi-ts/openapi-typescript/blob/main/packages/openapi-typescript/CHANGELOG.md

**Spectral**
- Репозиторій: https://github.com/stoplightio/spectral
- Рулсети «in the wild» (Zalando, DigitalOcean, Azure, Box): https://github.com/stoplightio/spectral-rulesets
- Властивості правил (API Evangelist): https://apievangelist.com/2025/01/21/the-properties-of-spectral-api-governance-rules/
- Шаровий підхід (Kin Lane): https://medium.com/@kinlane/shifting-how-i-use-spectral-rules-to-govern-apis-ff8b8684e730

**oasdiff**
- Репозиторій: https://github.com/oasdiff/oasdiff
- Breaking-changes у CI: https://github.com/oasdiff/oasdiff/blob/main/docs/BREAKING-CHANGES.md
- Сайт / PR-review: https://www.oasdiff.com/
- Огляд (Nordic APIs): https://nordicapis.com/using-oasdiff-to-detect-breaking-changes-in-apis/

**Prism**
- Репозиторій: https://github.com/stoplightio/prism
- Гайд із мокінгу (static/dynamic): https://github.com/stoplightio/prism/blob/master/docs/guides/01-mocking.md
- Open-source сторінка: https://stoplight.io/open-source/prism

**schemathesis / contract testing**
- Сайт: https://schemathesis.io/
- OpenAPI.tools профіль: https://openapi.tools/tools/schemathesis
- Експериментальна 3.1 (історія): https://github.com/schemathesis/schemathesis/discussions/1822
- Гайд із OpenAPI-тестування (контракт/fuzz/CI): https://www.apideck.com/blog/openapi-testing

**Django-валідація проти зовнішнього контракту**
- `drf-openapi-tester` (snok): https://github.com/snok/drf-openapi-tester
- PyPI: https://pypi.org/project/drf-openapi-tester/
- `django-contract-tester` (форк, 3.1.x): https://github.com/maticardenas/django-contract-tester

**OpenAPI специфікація**
- OpenAPI 3.1.0: https://spec.openapis.org/oas/v3.1.0.html

-----

*Оновлено після дослідження інструментів. Наступні кроки: підтвердити envelope (§12) і порядок впровадження, після чого — деталізація окремих агентів, rules і gate-скриптів на основі §13.*
