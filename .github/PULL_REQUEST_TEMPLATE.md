<!--
PR-шаблон. Заповни релевантні секції; нерелевантні — познач "n/a".
Iron rule: PR-only, ніколи прямо в `main` (.claude/rules/git-operations.md).
Контракт змінюється ТІЛЬКИ через `spec/` → `openapi.yml` (.claude/rules/contract-first.md).
-->

## Що і навіщо
<!-- Короткий опис зміни та мотивація. -->

## Тип зміни
- [ ] Контракт (`spec/**` → `openapi.yml`)
- [ ] Процес / тулінг (`.claude/**`, `.github/**`, `scripts/**`)
- [ ] Документація
- [ ] Chore / інше

## План
- [ ] Є `docs/plans/NNNN-<topic>.md` (для нетривіальної роботи)
- [ ] План погоджено до редагування файлів
- [ ] Зміна торкається ≤ 3 файлів (інакше — розбито на менші PR)

## Зміна контракту — якщо стосується
- [ ] Редагувався `spec/**`; `openapi.yml` згенеровано повторно (`npm run api:compile && npm run api:bundle`), НЕ редаговано вручну
- [ ] `spec/` і `openapi.yml` закомічено разом (drift-гейт)
- [ ] Semver bump: `major` / `minor` / `patch`
- [ ] Обґрунтування bump:
- [ ] `.claude/memory/endpoints.json` оновлено (registry на кожен ендпоінт)

## Гейти (мають бути зелені)
- [ ] `npm run validate` — compile + TypeSpec drift + Spectral lint + examples
- [ ] `npm run breaking` — класифіковано (ERR-level ⇒ MAJOR)
- [ ] `npm run mock:smoke` — Prism піднявся, відповіді валідні

## Документація
- [ ] `docs/api/INDEX.md` оновлено (якщо змінились ендпоінти)
- [ ] `CHANGELOG.md` / release-note fragment додано
- [ ] `docs/verify/<feature>.md` оновлено (якщо стосується)
- [ ] README freshness перевірено (`/check-readme`)

## Відхилення
- [ ] Немає `TODO`; будь-який `STUB:` має `owner` + `follow-up` (.claude/rules/no-stubs.md)
- [ ] Зміна `.oasdiff-ignore.txt` супроводжується ADR у `docs/decisions/`
- [ ] Свідоме відхилення внесено в living plan

## Вплив на консюмерів (пінять `CONTRACT_VERSION`)
<!-- Що зробити споживачам контракту після мерджу/тегу. "no action needed" — теж валідна відповідь. -->
- Backend (`claude-django`):
- Frontend (`claude-react-mui`):
