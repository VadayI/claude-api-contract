# Аудит шаблону claude-api-contract — 2026-06-14

> Повний аудит шаблону як інструмента для створення нових проєктів-контрактів.
> Перевірено: 12 агентів, 23 команди, 6 скілів, 20 правил, ~20 скриптів (+ policy),
> hooks (settings.json + husky), 3 CI-воркфлоу, package.json, шаблони.
> Метод: вивантаження вмісту + перехресна перевірка посилань + **живий прогін гейтів** +
> верифікація Claude Code-конфігу профільним агентом.

## Вердикт

Шаблон **здоровий і робочий за призначенням**: контракт компілюється, всі локально доступні
гейти зелені, перехресні посилання (скрипти, правила, агенти) в основному цілісні. Орфанів-правил
немає, мертвих посилань на скрипти немає. Знайдено **1 high**, **4 medium** і кілька low/verify —
переважно незавершена обв'язка (husky), неузгодженість двох скілів і трикутник протиріч навколо `HANDOFF.md`.

| Рівень | К-сть | Суть |
|---|---|---|
| 🔴 HIGH | 1 | husky+commitlint закомічені, але не під'єднані (немає devDeps + `prepare`) |
| 🟠 MEDIUM | 4 | 2 скіли ніким не активуються · протиріччя HANDOFF · застарілий список clean.sh · `SendMessage` |
| 🟡 LOW/VERIFY | 6 | формат `tools` · `UserPromptExpansion` · `statusMessage` · «after preflight» · SubagentStop matcher · spectral warn/error |

## Що працює (перевірено живим прогоном)

| Перевірка | Результат |
|---|---|
| `npm run validate` (compile + drift + lint + examples) | ✅ зелено |
| `npm run mock:smoke` (Prism, 11 ендпоінтів) | ✅ зелено — auth видає токени, `GET /articles` без auth → 401 |
| `npm run check:endpoints` (реєстр) | ✅ 10/10 операцій зареєстровано |
| `npm run breaking` (oasdiff vs v0.4.0) | ⚠️ у пісочниці падає (немає oasdiff); на твоїй машині oasdiff 1.18.4 присутній (env-detect) — **не дефект шаблону** |
| TypeSpec drift (`openapi.yml` == `spec/`) | ✅ збігається |
| Орфани-правила (всі 20) | ✅ кожне правило має ≥1 посилання |
| Посилання на скрипти (команди/hooks/CI/package.json) | ✅ усі резолвляться |
| Диспетч агентів у командах | ✅ усі імена існують |
| Пін версії oasdiff (CI == setup-wsl.sh == env-detect) | ✅ v1.18.4 скрізь |
| ADR-посилання (0001, 0007 …) | ✅ усі присутні (0001–0008) |
| `seed.sh`, README `## For consumers` / `## Quick start` | ✅ узгоджені з `/check-readme` |

Висновок по «чи воно працює»: **так** — основний контур (TypeSpec → openapi.yml → lint → examples → mock)
відтворюється з нуля і зелений. Проблеми нижче — це обв'язка та узгодженість, а не зламаний контракт.

---

## 🔴 HIGH

### H1. husky + commitlint закомічені, але не під'єднані

**Доказ.** `.husky/commit-msg`, `pre-commit`, `pre-push` і `commitlint.config.mjs` присутні й закомічені
(додані сьогодні, 17:17). Але:

- `package.json` (останній правлений 16:50) **не містить** `husky`, `@commitlint/cli`,
  `@commitlint/config-conventional` у `devDependencies` — і їх немає ні в `node_modules/`, ні в `package-lock.json`.
- **Немає скрипта `prepare`** (`"prepare": "husky"`), тож `npm ci`/`npm install` ніколи не виставляє
  `core.hooksPath=.husky` → git **не викликає** ці hooks на свіжому клоні.
- `.husky/commit-msg` запускає `npx --no-install commitlint` — з `--no-install` він **впаде**, бо commitlint не встановлено.
- Коментар у `.husky/pre-commit` радить «installing husky + commitlint (devDeps) and running `npm run prepare`» —
  але `npm run prepare` дає `Missing script: prepare`.

**Наслідок для нового проєкту з шаблону:** husky-шар повністю інертний (git його не бачить) і **не під'єднується**
задокументованим шляхом. CI-гейти і Claude Code PreToolUse-hook дублюють захист, тож репозиторій не «голий», але
закомічена непрацездатна конфігурація вводить в оману. Це найчіткіша «мертва/зламана» знахідка.

**Виправлення A (під'єднати — рекомендовано, якщо husky потрібен):**
```bash
# 1) devDeps + prepare у package.json (через jq, без обрізання файлу)
cd "$(git rev-parse --show-toplevel)"
node -e '
  const fs=require("fs"); const p=JSON.parse(fs.readFileSync("package.json","utf8"));
  p.scripts=p.scripts||{}; p.scripts.prepare="husky";
  p.devDependencies=p.devDependencies||{};
  p.devDependencies["husky"]="^9.1.7";
  p.devDependencies["@commitlint/cli"]="^19.6.1";
  p.devDependencies["@commitlint/config-conventional"]="^19.6.0";
  fs.writeFileSync("package.json", JSON.stringify(p,null,2)+"\n");
'
npm install            # підтягне husky+commitlint і виконає prepare → виставить hooksPath
```

**Виправлення B (прибрати — якщо вистачає CI + Claude Code hooks):**
```bash
cd "$(git rev-parse --show-toplevel)"
git rm -r .husky commitlint.config.mjs
# + прибрати рядок про husky/commitlint з документації, де він згадується
```

---

## 🟠 MEDIUM

### M1. Скіли `oasdiff-breaking` і `contract-versioning` ніким не активуються

**Доказ.** 4 з 6 скілів мають явний гачок активації:
`openapi-design` (← api-architect), `typespec-authoring` (← tsp-author + typespec-style.md),
`prism-mock` (← mock-validator), `spectral-lint` (← spectral-style.md).
А `oasdiff-breaking` і `contract-versioning` — **жодного «Activate the … skill»**. `contract-versioning`
згадано лише як файл для перейменування URL у `personalize.md`, `oasdiff-breaking` — ніде.

**Наслідок.** Технічно не мертві (Skill-механізм може спрацювати за описом), але обв'язка
неузгоджена: агент `breaking-change-analyst` і команда `/release`, які мали б їх вмикати, на них не вказують.
Знижує відкривність і ламає власну конвенцію шаблону.

**Виправлення (heredoc-аппенд гачків):**
```bash
cd "$(git rev-parse --show-toplevel)"
# breaking-change-analyst → oasdiff-breaking
cat >> .claude/agents/breaking-change-analyst.md <<'EOF'

> Activate the `oasdiff-breaking` skill for oasdiff flags + changelog recipes.
EOF
# versioning.md → contract-versioning (правило вантажиться у /release-контексті)
cat >> .claude/rules/versioning.md <<'EOF'

> Activate the `contract-versioning` skill for the release + consumer-pinning recipe.
EOF
```

### M2. Протиріччя навколо `HANDOFF.md` (тривекторне)

**Доказ.**
- `docs/HANDOFF.md` **відстежується** git (`git ls-files` його показує) — це збігається з CLAUDE.md, принцип #6 «Context in Git».
- `.gitignore:25` має `/HANDOFF.md` (+ коментар «local only, not tracked») — але це ігнорує **кореневий** `HANDOFF.md`,
  якого не існує; реальний файл — `docs/HANDOFF.md`, і він **не** під це правило не підпадає.
- `wrap-up.md` крок 3: «Note it is local-only/gitignored unless your project commits it» — **суперечить** і фактичному
  стану (відстежується), і CLAUDE.md.

**Наслідок.** Незрозуміло, чи HANDOFF спільний між машинами. Правило в `.gitignore` мертве (хибний шлях).

**Виправлення (зробити HANDOFF відстежуваним — як у CLAUDE.md):**
```bash
cd "$(git rev-parse --show-toplevel)"
# 1) прибрати мертве/хибне правило з .gitignore (рядок /HANDOFF.md + його коментар)
node -e '
  const fs=require("fs"); let s=fs.readFileSync(".gitignore","utf8");
  s=s.replace(/# Session handoff[^\n]*\n\/HANDOFF\.md\n/,"");
  fs.writeFileSync(".gitignore",s);
'
# 2) у wrap-up.md замінити фразу про gitignored на «tracked» — застосуй вручну heredoc-ом:
#    було:  "Note it is local-only/gitignored unless your project commits it."
#    стало: "It is tracked in git (Context-in-Git, CLAUDE.md #6)."
```

### M3. Застарілий список скидання `decisions/0002–0004` у clean.sh + node-commands.md

**Доказ.** `scripts/clean.sh` (Class B / `--reset-to-clone`) хардкодить видалення лише
`docs/decisions/0002-…`, `0003-…`, `0004-…`. Та сама фраза «`docs/decisions/0002–0004`» — у `node-commands.md`.
Але зараз існують `0005`–`0008` (project-maturity, deploy, changelog-policy, breaking-tooling). Список заморожений
на момент, коли ADR було лише три.

**Наслідок.** `--reset-to-clone` не доводить робочу копію до стану свіжого клону (лишає 0005–0008),
а документація вводить в оману. Або список неповний, або (якщо 0005–0008 мали лишатися) — формулювання хибне.

**Виправлення.** Визначитися з наміром і синхронізувати обидва місця. Якщо 0005–0008 теж «template-dev», додати їх
до `remove` у `clean.sh` і оновити коментарі та `node-commands.md`. Якщо мали лишатися — прибрати згадку діапазону взагалі.

### M4. `SendMessage` у tools усіх 12 агентів — імовірно інертний у звичайному CLI

**Доказ (верифікація claude-code-guide + цитовані ішюї).** `SendMessage` гейтиться за експериментальним
прапором `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` (вимкнений за замовчуванням) — issues anthropics/claude-code
#42737, #35240. Усі 12 агентів мають його у `tools`.

**Наслідок.** Диспетч-флоу шаблону це **не ламає**: під-агент і так повертає фінальний звіт через сам Agent-механізм,
а CLAUDE.md-оркестратор «синтезує звіти» саме так. Тобто грант `SendMessage` — радше зайвий/оманливий, ніж критичний.

**Виправлення.** Перевірити у своїй версії CLI; якщо agent-teams вимкнено — прибрати `SendMessage` з `tools` (косметика, знімає шум). Деталі формату `tools` — у L1.

---

## 🟡 LOW / VERIFY

Ці пункти стосуються внутрішніх деталей Claude Code, які швидко змінюються. Я **не зміг повністю підтвердити**
їх із документації в межах сесії — це **рекомендації перевірити на твоїй версії CLI**, а не доведені дефекти.
(Сам шаблон у `mcp-stack.md` радить «verify current API/flags» — тут діє той самий принцип.)

| ID | Пункт | Ризик якщо припущення вірне | Дія |
|---|---|---|---|
| L1 | `tools: [Read, …]` як YAML-масив | Документований формат — comma-separated string `"Read, Glob, …"`. Якщо масив ігнорується — агент дістає **всі** інструменти (розширення прав) | Перевести на рядок для надійності |
| L2 | hook-подія `UserPromptExpansion` (gate `/release`,`/ship-contract`) | Якщо подія невалідна — `check_command_gate.sh` **не фаєрить**. Але команди мають власні in-body runtime/branch-гейти, тож це defense-in-depth, не єдиний захист | Підтвердити, що hook реально спрацьовує (лог-рядок) |
| L3 | поле `statusMessage` у hook-записах | Недокументоване; найімовірніше мовчки ігнорується | Косметика; прибрати, якщо чистити |
| L4 | «append … after `@.claude/rules/preflight.md`» (CLAUDE.md #0, set-language.md) | Останній рядок import-блоку зараз `project-maturity.md`, не `preflight.md` — вказівка трохи застаріла | Замінити на «в кінець import-блоку» |
| L5 | `SubagentStop` matcher за іменами агентів | Якщо твій CLI ігнорує matcher — `check_plan_execution_log.sh` біжить на **кожному** під-агенті. Але він advisory + self-limiting → нешкідливо | Лишити як є або підтвердити matcher |
| L6 | `.spectral.yaml`: snake_case/description = `warn` | spectral-style.md подає casing як «must enforce», але skill дозволяє стадійність через `recommended` | За бажанням підняти до `error` |

**L4 — швидке виправлення формулювання:**
```bash
cd "$(git rev-parse --show-toplevel)"
# у CLAUDE.md (IMPORTANT #0) і .claude/commands/set-language.md замінити вручну heredoc-ом:
#   "after @.claude/rules/preflight.md"
# → "at the end of the import block (currently after @.claude/rules/project-maturity.md)"
```

**L1 — приклад приведення `tools` до рядкового формату (один агент):**
```bash
# було:  tools: [Read, Glob, Grep, Write, Edit, SendMessage]
# стало: tools: Read, Glob, Grep, Write, Edit        # (+ прибрати SendMessage — див. M4)
```

---

## Охоплення аудиту

- **Агенти (12):** frontmatter, посилання на правила (всі резолвляться), диспетч-узгодженість з workflow.md/CLAUDE.md. Структурно чисто; питання лише по `tools`/`SendMessage` (L1/M4).
- **Команди (23):** усі мають `## Log` → `log-cmd.mjs`; усі посилання на скрипти/агентів/правила резолвляться; in-body runtime/branch-гейти присутні де треба.
- **Скіли (6):** 4 коректно активуються, 2 — ні (M1). Frontmatter консистентний (`[claude-api-contract]`-тег, який personalize.sh Tier-3 переписує).
- **Правила (20):** 11 в import-блоці CLAUDE.md + 9 per-agent/command = 20, **сиріт немає**. Взаємних протиріч у змісті не знайдено (envelopes/auth/versioning узгоджені між правилами і openapi-design skill).
- **Скрипти (~20 + policy/3):** усі, на які посилаються команди/hooks/CI/package.json, існують. «Неіснуючі» імена з первинного grep (`build.sh`, `pack.mjs`, `pull_contract.sh`, `check_contract_sync.sh`…) — це або consumer-side приклади в прозі, або сміття з `LOCAL/`/`node_modules`, не справжні розриви.
- **Hooks:** Claude Code (settings.json) — PreToolUse/Stop/SessionStart валідні; UserPromptExpansion/SubagentStop matcher/statusMessage → L2/L5/L3. husky → H1.
- **CI (3 воркфлоу):** contract-ci (5 гейтів + endpoints), contract-policy (diff-scoped process-гейти), scheduled-audit. Логіка узгоджена; oasdiff пін v1.18.4 збігається з локальним. `go install` без `setup-go` — ок на ubuntu-latest (Go передвстановлений).
- **package.json / templates / ADR / .mcp.json / .gitignore:** перевірено; єдине протиріччя — HANDOFF (M2).

## Рекомендований порядок виправлень

1. **H1** — вирішити долю husky (під'єднати A або прибрати B). Найбільший «обман очікувань» у шаблоні.
2. **M2** — звести HANDOFF до одного наративу (відстежується), прибрати мертвий `.gitignore`-рядок, переписати wrap-up.md.
3. **M1** — додати 2 гачки активації скілів (2 heredoc-аппенди).
4. **M3** — синхронізувати список `decisions/*` у clean.sh + node-commands.md.
5. **M4/L1** — за рішенням по agent-teams: прибрати `SendMessage` і перевести `tools` на рядок (одним проходом по 12 агентах).
6. **L2–L6** — перевірити на своїй версії CLI; правки косметичні.

> Усі гейти контракту лишаються зеленими — жодна знахідка не блокує роботу frontend/backend проти мока вже зараз.

---

## Статус впровадження (session 10, 2026-06-15)

| Знахідка | Статус |
|---|---|
| H1 husky+commitlint | ✅ під'єднано (commit `2bab66e`); commitlint після фіксу — **v19** (v21 ламав Node-floor) |
| M1 активація скілів | ✅ внесено |
| M2 HANDOFF | ✅ внесено |
| M3 ADR-список clean.sh | ✅ уточнено |
| M4/L1 SendMessage + tools | ✅ внесено (12 агентів) |
| L4 орієнтир import-блоку | ✅ внесено |
| L2 UserPromptExpansion | ⏳ verify на CLI |
| L3 statusMessage | ⏳ опціонально (косметика) |
| L5 SubagentStop matcher | ⏳ verify (нешкідливо) |
| L6 spectral warn→error | ⏳ опціонально (посилення) |

**Внесено 7/11** (усі HIGH/MEDIUM + L1, L4). Коміт `2bab66e` (21 файл) на гілці `chore/audit-2026-06-14-doc-drift`; re-pin commitlint v19 — uncommitted, чекає на коміт із хост-шелу. 4 low/verify свідомо відкладені.
