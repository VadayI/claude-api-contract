# claude-api-contract — опис проекту (що / як / навіщо)

**Тип:** Claude Code configuration template (третій у наборі, поряд із `claude-django` і `claude-react-mui`)
**Статус:** проектування (ще до тегу `v0.1.0`)
**Джерело вимог:** `REQUIREMENTS-claude-api-contract.md`
**Дата:** 2026-06-06

---

## 1. Навіщо (проблема й мета)

### Проблема
У поточній схемі REST API контракт народжується в backend: `drf-spectacular` генерує `openapi.yml` із серіалізаторів/вʼюх, а frontend його споживає (`npm run api:pull`). Наслідок — **frontend не може стартувати по-справжньому, доки backend не напише хоча б серіалізатори**. Контракт прив'язаний до реалізації, обидві команди послідовні замість паралельних.

### Мета
`claude-api-contract` робить контракт **незалежним артефактом**: спроектований першим, він дозволяє backend і frontend стартувати **одночасно** — frontend проти mock-сервера, backend проти контракту як специфікації. Контракт стає **єдиним джерелом істини (single source of truth)**.

### Модель джерела істини (Варіант A)
```
                    ┌─────────────────────────┐
                    │   claude-api-contract    │
                    │ openapi.yml (canonical)  │  ◄── єдине джерело істини
                    └───────────┬──────────────┘
                     git tag (semver) + raw URL
             ┌───────────────────┴───────────────────┐
             ▼                                         ▼
  ┌──────────────────┐                      ┌──────────────────┐
  │  claude-django   │                      │ claude-react-mui │
  │ СПОЖИВАЄ контракт│                       │ СПОЖИВАЄ контракт│
  │ валідує реалізацію│                      │ генерує TS-типи  │
  │ проти нього       │                      │ + mock рано      │
  │ (НЕ генерує сам)  │                      │ (НЕ генерує сам) │
  └──────────────────┘                      └──────────────────┘
```
Обидва споживачі **тільки споживають** контракт. Жоден його не генерує. Зміна контракту — свідома дія в `claude-api-contract` через Pull Request, ніколи не побічний ефект коду в споживачі.

---

## 2. Що створюємо (артефакти)

Канонічний продукт — **мовно-нейтральний `openapi.yml`**. Решта — допоміжні артефакти навколо нього.

| Артефакт | Шлях | Призначення |
|---|---|---|
| Канонічний контракт | `openapi.yml` (корінь) | Єдине джерело істини, OpenAPI 3.1, bundled, Spectral-clean |
| Вихідний код контракту | `spec/**/*.tsp` | TypeSpec-джерело, з якого компілюється `openapi.yml` |
| Людський індекс ендпоінтів | `docs/api/INDEX.md` | Огляд для людини, вказує на `openapi.yml` як контракт |
| Приклади запит/відповідь | `examples/**` | Валідовані проти схеми, годують mock (static + `x-faker`) |
| Конфіг mock-сервера | `prism.config.*` / npm-скрипт | Підняття Prism із `openapi.yml` |
| Версіонований реліз | git tag `vX.Y.Z` | Пін для споживачів |
| Changelog контракту | `CHANGELOG.md` | Що змінилось, breaking-помітки (oasdiff) |

**Що НЕ є виходом:**
- TS-типи — frontend генерує локально через `openapi-typescript`.
- Python-моделі — backend валідує реалізацію проти контракту, не генерує код.
- Жодного мовно-специфічного коду в каноні.

---

## 3. Як (стек і середовище)

**Стек авторингу:**
- **TypeSpec** (`@typespec/compiler`, `@typespec/openapi3`, `@typespec/http`, `@typespec/rest`) — DSL для опису API.
- **OpenAPI 3.1** — формат канонічного виходу (повна JSON Schema; узгоджено з TypeSpec, `openapi-typescript`, `schemathesis`).
- **Spectral** (`@stoplight/spectral-cli`) — lint контракту (шаровий рулсет: `extends spectral:oas` + кастомні правила; запозичення з Zalando/DigitalOcean).
- **Prism** (`@stoplight/prism-cli`) — mock-сервер + двостороння валідація запит/відповідь.
- **oasdiff** — детекція breaking-changes між версіями.
- **Node 20.19+** — тулчейн (консистентно з `claude-react-mui`).

**Середовище (як у двох інших шаблонів):**
- WSL2 Ubuntu на Windows (обов'язково) / Linux / macOS.
- Claude Code CLI (термінальний `claude`), GitHub як джерело істини, bash-only gate-скрипти й хуки.
- **НЕ підтримується:** Cowork, Windows-native shells, Claude API/SDK standalone.
- Зберігається повна філософія Claude Code config: агенти / rules / skills / commands / WSL2 / PR-only / контекст у git.

---

## 4. Auth у контракті

Контракт **сам описує auth-ендпоінти**, щоб mock віддавав токени і frontend міг логінитись автономно ще до першого ендпоінта backend.

**Security scheme:** Bearer/JWT — `bearerAuth` (`type: http`, `scheme: bearer`, `bearerFormat: JWT`), глобально, з `security: []` на публічних ендпоінтах.

**User-flow (D1 = B):**

| Метод + шлях | Security | Запит | Відповідь |
|---|---|---|---|
| `POST /auth/register` | `[]` публічний | credentials | user + (опц.) токени |
| `POST /auth/login` | `[]` публічний | credentials | `access` + `refresh` |
| `POST /auth/refresh` | `[]` публічний | `refresh` | новий `access` (+ опц. refresh) |
| `POST /auth/logout` | `bearerAuth` | — / `refresh` | 204 |

> **Транспорт refresh (D2):** access у `Authorization: Bearer`, refresh — **у тілі відповіді**. Контракт самодостатній, mock тривіальний. ADR фіксує XSS-вартість і опцію перемкнутись на cookie.

**Service-to-service (D5 — основний профіль клієнтів):**

| Метод + шлях | Security | Запит | Відповідь |
|---|---|---|---|
| `POST /auth/token` | `[]` публічний | `grant_type=client_credentials`, `client_id`, `client_secret` (+ опц. `scope`) | `access` (+ `expires_in`, `scope`) |

- **Scopes замість ролей** для сервісів: гранульована авторизація через scopes у токені та `security` на ендпоінтах (опц. явний `serviceAuth: oauth2 clientCredentials`).
- Рекомендації S2S: короткий access (хвилини) + revocation-стратегія; scopes на всіх не-публічних ендпоінтах; rate limiting на рівні контракту (`429` + `Retry-After`).

---

## 5. Pipeline і агенти

```
Feature (новий ресурс/ендпоінт):
  ba → api-architect (проектує контракт) → tsp-author (пише TypeSpec)
     → [contract-reviewer | breaking-change-analyst]
     → mock-validator → docs-writer (INDEX.md + CHANGELOG)
```

| Агент | Призначення | Модель |
|---|---|---|
| `ba` | Бізнес-аналіз, user stories, scope ендпоінтів | opus |
| `api-architect` | REST-контракт: ресурси, коди, permissions, версіонування | opus |
| `tsp-author` | Реалізація контракту в TypeSpec | sonnet |
| `contract-reviewer` | Рев'ю контракту перед PR (консистентність, naming, коди) | opus |
| `breaking-change-analyst` | Аналіз oasdiff, класифікація breaking vs non-breaking | opus |
| `mock-validator` | Перевірка прикладів і поведінки mock проти схеми | sonnet |
| `docs-writer` | `docs/api/INDEX.md`, `CHANGELOG.md`, опис PR | sonnet |

Опціональні (як у попередніх шаблонів): `devil`, `integration-architect`, `auditor`, `brief-synthesizer`.

---

## 6. CI Gates (hard, червоні)

| Gate | Інструмент | Падає коли |
|---|---|---|
| **TypeSpec drift** | `tsp compile` + diff | рекомпіляція `.tsp` ≠ закоміченому `openapi.yml` |
| **Spectral lint** | `spectral lint` | контракт порушує style-rules (naming, описи, коди) |
| **Валідація прикладів** | Prism / схема-валідатор | приклад у `examples/**` не валідний проти схеми |
| **Breaking-change** | `oasdiff breaking --fail-on ERR` | breaking-зміна vs попередній тег без major-bump |
| **Mock smoke-тест** | Prism + запит | mock не піднімається або не віддає валідну відповідь |

> **Ключова відмінність від двох інших шаблонів:** breaking-change gate — first-class. Контракт споживають ДВА репо, тож ламка зміна має падати в CI **до релізу**, інакше тихо розламає обидві команди одночасно.

---

## 7. Версіонування і доставка

**Версіонування:** semver на git-тегах (`vX.Y.Z`).
- **major** — breaking-зміна (oasdiff gate змушує).
- **minor** — новий ендпоінт / поле, зворотно сумісне.
- **patch** — описи, приклади, виправлення без зміни форми.

**Доставка в споживачі:** git tag + raw URL, пін на версію.
- Споживач тримає `CONTRACT_VERSION=vX.Y.Z`.
- Тягне саме цей тег: `https://raw.githubusercontent.com/VadayI/claude-api-contract/<tag>/openapi.yml`.
- Підняття піна = свідомий PR у споживачі, ніколи не авто-drift.

**Посилання на контракт у споживачі (звірка цілісності).** Кожен споживач тримає у **закоміченому** конфізі (щоб мандрувало в git і було видиме CI) посилання на джерело контракту, а не лише номер версії:
- `CONTRACT_REPO=https://github.com/VadayI/claude-api-contract` — GitHub-посилання на репо контракту.
- `CONTRACT_VERSION=vX.Y.Z` — пінований тег.
- Похідний raw-URL: `https://raw.githubusercontent.com/VadayI/claude-api-contract/<CONTRACT_VERSION>/openapi.yml`.

Рекомендована форма піна — закомічений `contract.lock.json` (repo + version + path + sha256 вендореної копії) поряд із вендореним `openapi.yml`. `.env` лишається лише для локальних оверайдів; джерело істини піна — закомічений файл, бо `.env` gitignored.

**Sync-gate (consumer-side, «чи нічого не змінилось»).** Кожен споживач має gate-скрипт, що тягне `openapi.yml@CONTRACT_VERSION` із `CONTRACT_REPO` і **звіряє** його з вендореною копією (diff / sha256) — **червоніє**, якщо щось розійшлося (вендорену копію відредагували руками, або тег зрушили). Це окремий рівень поверх наявних gate'ів: повний ланцюг цілісності — `контракт@тег → вендорена openapi.yml → згенеровані типи/реалізація`.

```
claude-react-mui: npm run api:pull  → openapi.yml@CONTRACT_VERSION
                  npm run api:types → openapi-typescript → schema.d.ts
claude-django:    scripts/pull_contract.sh → openapi.yml@CONTRACT_VERSION
                  валідація реалізації (schemathesis + drf-openapi-tester)
```

---

## 8. Структура репо (орієнтовна)

```
claude-api-contract/
├── .claude/
│   ├── agents/      # ba, api-architect, tsp-author, contract-reviewer,
│   │                #   breaking-change-analyst, mock-validator, docs-writer
│   ├── commands/    # /bootstrap, /doctor, /preflight, /audit, /wrap-up,
│   │                #   /create-pr, /review-pr, /fix-ci, /release,
│   │                #   /validate-contract, /breaking-check, /mock
│   ├── rules/       # contract-first, typespec-style, versioning,
│   │                #   breaking-changes, git-operations, environment, ...
│   ├── skills/      # typespec-authoring, openapi-design, spectral-lint,
│   │                #   prism-mock, oasdiff-breaking, ...
│   ├── memory/      # env-detect.json, command-log.jsonl
│   └── settings.json
├── spec/            # TypeSpec-джерело (*.tsp)
│   ├── main.tsp     # точка входу (service-декоратор + роутинг)
│   ├── auth.tsp
│   └── models/      # спільні моделі + envelope (list / error)
├── examples/        # приклади (валідовані; x-faker де доречно)
├── docs/
│   ├── api/INDEX.md
│   ├── decisions/   # ADR
│   └── WORKLOG.md
├── scripts/         # detect-env.mjs, gate-скрипти (check_*.sh), log-cmd.mjs
├── templates/       # scaffold-входи для /bootstrap
├── openapi.yml      # ◄ КАНОНІЧНИЙ ВИХІД (bundled, OpenAPI 3.1)
├── .spectral.yaml   # шаровий рулсет
├── .github/workflows/ # contract-ci.yml (5 gate'ів)
├── CHANGELOG.md
├── CLAUDE.md
└── README.md
```

---

## 9. Slash-команди (специфічні)

Поверх стандартного набору (`/bootstrap`, `/doctor`, `/preflight`, `/audit`, `/wrap-up`, `/create-pr`, `/review-pr`, `/fix-ci`, `/synthesize-brief`, `/set-language`, `/handoff`):

| Команда | Дія |
|---|---|
| `/validate-contract` | Spectral lint + валідація прикладів + TypeSpec drift локально |
| `/breaking-check [ref]` | oasdiff проти попереднього тегу, класифікація змін |
| `/mock [port]` | Підняти Prism mock із поточного `openapi.yml` |
| `/release [version]` | Зібрати `openapi.yml`, оновити CHANGELOG, поставити тег, push |

---

## 10. Вплив на споживачів (окремі PR-и, після тегу `v0.1.0`)

### `claude-django` (backend)
- Прибрати генерацію `openapi.yml` через `drf-spectacular` як джерело істини.
- Інвертувати drift-gate: «реалізація проти зовнішнього контракту, розбіжність = червоний» (schemathesis + drf-openapi-tester).
- Додати `scripts/pull_contract.sh` + пін `CONTRACT_VERSION` + `CONTRACT_REPO` + sync-gate (`scripts/check_contract_sync.sh`), що звіряє вендорену `docs/api/openapi.yml` з `openapi.yml@CONTRACT_VERSION` на GitHub; `drf-spectacular` лишити лише для Swagger UI/Redoc.
- Auth під S2S: user-flow (D1) + service-flow `/auth/token` (D5); scope-based permissions; короткий access + revocation; rate limiting `429` + `Retry-After`.

### `claude-react-mui` (frontend)
- Auth-інверсія: `api-client` на Bearer + refresh-flow замість session/CSRF (узгодити ADR).
- `npm run api:pull` тягне з `claude-api-contract` (`CONTRACT_REPO` + `CONTRACT_VERSION`), не з backend; sync-gate (`scripts/check_contract_sync.sh`) звіряє вендорену `src/lib/api/openapi.yml` з пінованим тегом на GitHub.
- На ранній стадії `VITE_API_BASE_URL` → Prism mock, потім staging backend.
- Обробка `429` + `Retry-After` у транспортному шарі.
- (Деталізований план: `claude-react-mui/docs/plans/0003-api-contract-inversion.md`.)
- Примітка: service-flow (client credentials) frontend **не стосується** — браузер не тримає секрет сервіса.

### Спільне
- Пін `CONTRACT_VERSION` на конкретний тег; підняття = свідомий PR.
- **Закомічене посилання на контракт** (`CONTRACT_REPO` GitHub URL + `CONTRACT_VERSION`, напр. у `contract.lock.json`) — щоб репо/CI знали, з чим звірятися.
- **Sync-gate**: тягне `openapi.yml@CONTRACT_VERSION` із GitHub і звіряє з вендореною копією (diff/sha256) — червоніє при будь-якій розбіжності.
- `/doctor` (або окрема `/contract-check`) репортить джерело контракту + чи пінований тег ще збігається з вендореною копією.
- Жоден споживач **не генерує** контракт — лише споживає.
- CI споживача червоніє, якщо реалізація/типи розходяться з пінненою версією.

---

## 11. Ключові рішення (зафіксовані)

| # | Рішення | Значення |
|---|---|---|
| 1 | Модель джерела істини | **Варіант A** — contract-репо canonical; backend і frontend обидва споживають |
| 2 | Авторинг контракту | **TypeSpec** → компіляція в єдиний `openapi.yml` |
| 3 | Розбивка вихідного файлу | **Один** плаский `openapi.yml` (bundled, без зовнішніх `$ref`) |
| 4 | Auth-схема | **Bearer / JWT** |
| 5 | Mock-сервер | **Prism (Stoplight)** |
| 6 | Доставка контракту | **git tag (semver) + raw URL**, пін `CONTRACT_VERSION` |
| 7 | Детекція breaking | **oasdiff** проти попереднього тегу (breaking = червоний CI) |
| D1 | Набір auth-ендпоінтів | **B** — login + refresh + logout + register |
| D2 | Транспорт refresh | **refresh у тілі відповіді** (ADR фіксує XSS-вартість + опцію cookie) |
| D3 | Семвер-правило | breaking = **major** bump (oasdiff `--fail-on ERR`) |
| D4 | Версія OpenAPI | **OpenAPI 3.1** |
| D5 | Профіль клієнтів | **Service-to-service** — підсилює Bearer/JWT, додає service-flow + scopes |

---

## 12. Відкриті питання

**Закриті:** D1 (B з register), D2 (тіло відповіді), OpenAPI 3.1.

**Лишаються на підтвердження:**
1. **Пагінація / помилки (envelope)** — стандартизувати на рівні контракту, до написання `spec/models/`:
   - list: `{ count, next, previous, results: T[] }` (збігається з дефолтом DRF);
   - errors: `{ detail }` для простих + `{ errors: [{ field, code, message }] }` для валідаційних;
   - `429` + `Retry-After` як частина error-envelope (важливо для S2S).
2. **Порядок впровадження** — спершу довести `claude-api-contract` до `v0.1.0`, потім правити двох споживачів окремими PR-ами.

---

## 13. Найцінніші доповнення (поверх первинних вимог)

1. Шаровий Spectral із запозиченням правил із Zalando/DigitalOcean.
2. `x-faker` у `examples/` для реалістичного dynamic-mock.
3. `oasdiff changelog` для авто-`CHANGELOG.md` (через `docs-writer`).
4. `--err-ignore` config для свідомо дозволених breaking без зняття gate.
5. `drf-openapi-tester` як другий рівень backend-валідації поряд зі `schemathesis`.
6. Пін версії `schemathesis` як частина залежностей backend.

---

## 14. Наступні кроки

1. Підтвердити envelope (§12.1) і порядок впровадження (§12.2).
2. `/bootstrap` шаблону: скелет `.claude/` (агенти, rules, skills, commands), `spec/`, gate-скрипти, `contract-ci.yml`.
3. Спроектувати й написати перший зріз контракту (auth + приклад ресурсу) у TypeSpec → скомпілювати `openapi.yml`.
4. Налаштувати 5 CI-gate'ів і Prism mock.
5. Реліз тегу `v0.1.0`.
6. Окремими PR-ами інвертувати `claude-django` і `claude-react-mui`.
