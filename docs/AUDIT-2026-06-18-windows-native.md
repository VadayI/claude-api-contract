# Аудит шаблону `claude-api-contract` — платформенна вісь: чи потрібен WSL2?

> Дата: 2026-06-18 · Скоуп: платформенне рішення (WSL2 vs нативний Windows) у
> `docs/decisions/0001-drop-windows-native-shell.md`, `scripts/detect-env.mjs`,
> `.claude/rules/environment.md`, `.claude/rules/preflight.md`, `scripts/*.sh`, hooks.
> Метод: веб-research поточного стану Claude Code (червень 2026) + читання першоджерел
> у репозиторії + grep bash-шару на WSL/Linux-залежні ідіоми.
>
> Контекст: попередній аудит `AUDIT-2026-06-16-config-deep-audit.md` покрив **внутрішню
> когерентність** (биті посилання, orphan-правила, hooks, гейти) і навмисно НЕ чіпав
> платформенне рішення. Цей звіт закриває саме його.

## Підсумковий вердикт (пряма відповідь)

**Так — агенти Claude можуть працювати безпосередньо на Windows, без WSL2.** Відколи в
кінці 2025 з'явилася нативна Windows-версія Claude Code, WSL2 більше **не є обов'язковим**.
Жорстка вимога шаблону «тільки Linux/macOS/WSL2» тепер **сильніша, ніж того вимагає поточна
реальність Claude Code**. Це стало **рішенням про скоуп підтримки**, а не технічною
неможливістю — і його варто переформулювати.

Нюанс: «нативний Windows» у Claude Code = запуск із PowerShell/CMD, але **Bash-tool і hooks
виконуються через Git Bash** (Git for Windows — єдина тверда вимога). Тобто `.sh`-скрипти
шаблону мають де виконуватися й на Windows — просто не в PowerShell, а в Git Bash.

---

## 1. Що змінилося в Claude Code (станом на 2026-06)

- **Нативний Windows-інсталятор** (без Node, автооновлення) — офіційно рекомендований спосіб;
  встановлення `irm https://claude.ai/install.ps1 | iex` у PowerShell. WSL **не потрібен**.
- **Git for Windows обов'язковий**: Claude Code використовує **Git Bash** усередині для Bash-tool,
  навіть якщо запущений із PowerShell/CMD. Саме тут виконуватимуться `.sh`-скрипти проекту.
- **WSL2 тепер опційний**, доречний лише коли потрібні: OS-рівневий **sandboxing Bash-tool**
  (доступний ТІЛЬКИ macOS/Linux/WSL2), Docker-інтеграція, або вже наявне Linux-оточення.

Джерела — у кінці звіту.

---

## 2. Де шаблон активно блокує нативний Windows

| Місце | Механіка | Наслідок |
|---|---|---|
| `scripts/detect-env.mjs:54` | `platformSupported = (linux \|\| darwin)` → для `win32` дає `false` | `platform_supported:false` записується у `env-detect.json` |
| `.claude/rules/preflight.md` (Runtime gate) | `platform_supported == false` → `UNSUPPORTED_PLATFORM`, **hard STOP** | `/preflight` зупиняє будь-яку роботу на Windows |
| `CLAUDE.md` (env-detect параграф) | «On Windows-native (no WSL2) — STOP and instruct to install WSL2» | оркестратор відмовляє Windows-користувачу |
| `docs/decisions/0001-...md` | ADR: «Support only Linux/macOS/WSL2» | політика-першоджерело |
| `.claude/rules/environment.md` | «Windows-native PowerShell/cmd is NOT supported» | дублює політику |

Тобто навіть якби скрипти прекрасно бігали в Git Bash, **штучний платформенний гейт усе одно
завертає Windows на вході**.

---

## 3. Розбір аргументів ADR 0001 (їх два — обидва вже неточні)

**Аргумент А — «Gate scripts and the SessionStart hook are bash+Node; PowerShell/cmd cannot run them.»**
Технічно правда, що PowerShell/cmd їх не виконають — але **нерелевантно**: нативний Claude Code
на Windows і не використовує PowerShell/cmd для Bash-tool, він використовує **Git Bash**. Усі hooks
у `settings.json` мають форму `bash scripts/...` — Git Bash їх виконує. Премиса вірна, висновок
(«отже потрібен WSL2») — ні.

**Аргумент Б — «PATH interop on Windows resolves claude/node to the Windows binaries → mis-detected runtime.»**
Це **специфічний failure-mode саме WSL2**, а не нативного Windows. Сам репозиторій це підтверджує:
евристика `wrong_runner_suspected` у `detect-env.mjs:57-64` ловить рівно випадок «користувач WSL2
випадково запустив Windows-ський `node.exe` через PATH-interop». На нативному Windows
`os.platform()==='win32'` — однозначний; визначення runtime там **надійніше**, ніж у WSL2.
Тобто крихким є якраз WSL2-шлях, а не Windows.

**Висновок:** обидва аргументи ADR описують реальні речі, але **не доводять** потребу WSL2 для
нативного Windows. ADR радше фіксує «ми тестуємо лише на одному shell-оточенні», ніж «Windows не може».

---

## 4. Наскільки bash-шар реально портабельний на Git Bash

grep по `scripts/**` + `.husky/**` показав: майже все — портабельний bash + стандартні утиліти
(`git`, `npx`, `curl`, `docker`, `oasdiff`, `node`), які на Windows кладуться на PATH через
Git for Windows + нативні інсталятори. WSL/Linux-залежні місця нечисленні й переважно
**самозахищені guard'ами**:

| Місце | Залежність | Оцінка на Git Bash |
|---|---|---|
| `detect-env.mjs:49` | читання `/proc/version` | під `existsSync(...)` → безпечний no-op |
| `session-start.sh:23` | гілка `[[ $ROOT == /mnt/* ]]` (lock-cleanup) | no-op (шляхи Git Bash: `/c/…`, `/d/…`) |
| `seed.sh:64,116` | `/proc/version`, `/mnt/c/*` | guard'и; деградують м'яко |
| `setup-wsl.sh` | nvm + Linux-bootstrap | **єдиний справді Linux-only** скрипт (це convenience, не gate) |
| `personalize.sh:260` | викликає `python3` | Git Bash (MSYS2) **не несе** python3 → реальна шпилька |

**Висновок §4:** bash-шар ~95% портабельний. Жоден **гейт** (`validate`, `lint`, `breaking`,
`mock`, `examples`, `drift`) не потребує WSL2 по суті — лише bash + toolchain на PATH. Тверді
зачіпки тільки дві: `setup-wsl.sh` (Linux-only за дизайном) і `python3` у `personalize.sh`
(тривіально замінюється на `node` — він і так hard-dep).

---

## 5. Що ВСЕ Ж легітимно говорить на користь WSL2 (чесний бік)

- **Sandboxing Bash-tool** — лише macOS/Linux/WSL2. На нативному Windows OS-рівневої ізоляції
  агента немає. Для репо, що робить `git push` / `gh pr` / `docker push`, це м'який security-trade-off.
- **Одне тестоване оточення.** Підтримувати лише WSL2 Ubuntu дешевше, ніж матрицю «WSL2 + Git Bash»;
  Git Bash (MSYS2 coreutils) місцями розходиться з GNU (`sed`, `realpath`, `find -print0`, тощо).
- **Docker-паритет** для `/ship-contract` рівніший у WSL2.
- **Verification-зачіпка:** hooks викликають `bash scripts/...`; на нативному Windows це вимагає
  `bash` (Git Bash) на PATH у тому середовищі, де Claude Code запускає hook-команди. Це варто
  **перевірити емпірично** перш ніж декларувати «працює».

Тобто **рекомендувати** WSL2 як головний шлях — розумно. **Забороняти** нативний Windows
hard-STOP'ом — надмірно.

---

## 6. Рекомендації (це шаблон → рішення тиражуються в похідні проекти)

1. **Переформулювати ADR 0001** зі статусу «Windows-native unsupported (неможливо)» на
   «WSL2/Linux/macOS — *тестований і рекомендований* шлях; нативний Windows через Git Bash —
   *best-effort*». Додати superseding-нотатку з посиланням на цей звіт.
2. **Ввести 3-рівневий `platform_tier`** замість булевого `platform_supported`:
   `supported` (linux/macos/wsl2) · `best-effort` (win32 + наявний Git Bash) · `unsupported`
   (win32 без bash). Гейти `preflight`/`doctor` → hard-STOP лише на `unsupported`, на
   `best-effort` — **warning**, не STOP. Додати прапорець `sandbox_available:false` для win32.
3. **`detect-env.mjs`:** для `win32` детектувати наявність `bash`/`git` і виставляти tier
   відповідно; не повертати глухе `false`.
4. **Портабельність:** замінити `python3` у `personalize.sh:260` на `node` (вже hard-dep);
   додати `scripts/setup-windows.ps1` або doc-розділ (winget/scoop: git, gh, oasdiff, node).
5. **Доки:** оновити `environment.md`, `preflight.md`, `CLAUDE.md`, `README.md` під поточну
   реальність Claude Code (нативний Windows + Git Bash; WSL2 опційний для sandbox/Docker).
6. **Емпірична перевірка** перед перемиканням політики: реально пройти `npm run validate` +
   один прохід пайплайну в Git Bash на Windows (особливо спрацювання hooks).

> Жодної зміни шаблону цим звітом не внесено — це аудит. Імплементація — окремим PR
> (зміни лише в `docs/**`, `scripts/**`, `.claude/**`; `spec/`→`openapi.yml` не торкаємось).

---

## Джерела (research, 2026-06)

- Claude Code Docs — Advanced setup: https://code.claude.com/docs/en/setup
- Claude Code for Windows: Native Desktop App (No WSL Required): https://opencowork.chat/blog/claude-code-for-windows
- Native vs WSL2 complete guide: https://claudelab.net/en/articles/claude-code/claude-code-windows-native-wsl2-complete-guide
- Running Claude Code on Windows Without WSL: https://blog.shukebeta.com/2025/06/25/running-claude-code-on-windows-without-wsl/
- Windows install guide (2026): https://smartscope.blog/en/generative-ai/claude/claude-code-windows-native-installation/
