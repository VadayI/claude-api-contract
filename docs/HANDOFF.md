# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining; updated LAST at end of session.

## Status

- **Etap 1 (core scaffold) — DONE & on `main`.** `.claude/` config, scripts, gates, `CLAUDE.md`, ADRs.
- **Etap 2 (first contract slice) — DONE & MERGED.** PR #1. auth `/auth/*` (D1+D5) + articles CRUD; envelopes; `openapi.yml` 3.1.0 (7 paths, 10 ops).
- **Etap 3 (examples, CI, mock) — DONE & MERGED.** PR #2. `@opExample` (26), `x-faker` (7 fields), `contract-ci.yml` (5 gates).
- **Release v0.1.0 — DONE.** Tag `v0.1.0` → `3f5504a`. Raw URL: `https://raw.githubusercontent.com/VadayI/claude-api-contract/v0.1.0/openapi.yml`
- **Etap 4 (інверсія консумерів) — DONE ✅:**
  - **claude-django**: PR #12–#16 MERGED ✅; branch protection ON ✅.
  - **claude-react-mui PR #10** (contract-source + sync-gate + articles): MERGED ✅.
  - **claude-react-mui PR #12** (Bearer + refresh, ADR 0021): MERGED ✅.
- **Cosmetic polish PR #6 — DONE & MERGED ✅** (2026-06-07):
  - `@server("https://api.example.com","Production")` додано поряд з Prism mock.
  - `tokenUrl` → `https://api.example.com/auth/token`.
  - `.oasdiff-ignore.txt` створено (порожній allow-list).
  - `README.md` статус виправлено.
  - `main` — єдина гілка, всі stale локальні та remote гілки видалено.

## Template vs requirements

Шаблон відповідає `REQUIREMENTS-claude-api-contract.md` на **~99%**. Два пункти заблоковані upstream-обмеженнями (не власними gap-ами):
1. OAuth2 scope descriptions — TypeSpec 1.x не підтримує `description` в `OAuth2Scope`.
2. `last-page` null example — Spectral/AJV null-nullable-3.1 crash ще присутній.

## What's next (follow-ups, без жорсткого дедлайну)

**contract-repo:**
- [ ] **`v0.1.1` тег** — PR #6 злито; всі gates зелені. Запустити `/release v0.1.1` коли зручно.
- [ ] OAuth2 scope descriptions — заблоковано TypeSpec 1.x; чекати upstream.
- [ ] `last-page` null example — заблоковано Spectral/AJV bug; STUB у `spec/articles.tsp:108`.

**react-mui:**
- [ ] PR3: 429 + Retry-After backoff у `client.ts`.
- [ ] PR4: `npm run mock` (Prism проти vendored `openapi.yml`).
- [ ] Branch protection на `main`.

**django:**
- [ ] Власний CI воркфлоу + required status check на `main`.
- [ ] `contract.lock.json`/sha256 (наразі tag-pin only).

## Decisions locked

- Envelope: `{count,next,previous,results}` / `{detail}` / `{errors:[{field,code,message}]}` / 429+`Retry-After`.
- Auth: Bearer/JWT, refresh in body (D2); Variant A source of truth; WSL2-only.
- Консумери тільки споживають контракт (react-mui ADR 0020, django ADR 0017).
- Bearer/JWT default у react-mui (ADR 0021 supersedes 0018).
- Production server placeholder: `https://api.example.com` (derived projects replace).

## Accepted deviations (v0.1.0 / v0.1.1)

- `BearerAuth`/`OAuth2Auth` scheme keys; Bearer без `bearerFormat`; `/auth/token` JSON body.
- `listArticles` example — «middle page» (Spectral/AJV null-nullable crash, docs/lessons.md).
- OAuth2 scopes в emitted YAML — порожні описи (`''`); TypeSpec 1.x не підтримує per-scope description.
- `oas3-server-not-example.com: off` у `.spectral.yaml` — intentional template placeholder.

## Environment notes (see docs/lessons.md)

- `oasdiff v1.18.4` у `~/.local/bin`; `~/.bashrc` оновлено; `PATH="$HOME/.local/bin:$PATH" npm run breaking`.
- git/`gh` — тільки з host/WSL2 shell.
- contract-repo `main`: branch protection ON (`contract-ci` required, reviews=0).
- claude-django `main`: branch protection ON (PR-only, без CI, reviews=0).
- claude-react-mui `main`: branch protection відсутній (follow-up).
- 9p NUL-padding: файли на `/mnt` писати через bash heredoc.
- Spectral `--fail-severity warn` → всі warnings блокують.
- Stacked PRs + squash-merge: squash+delete base → GitHub auto-close stacked PR (docs/lessons.md).
- TypeSpec 1.x: `OAuth2Scope.description` не підтримується у flow-літералах (docs/lessons.md).
