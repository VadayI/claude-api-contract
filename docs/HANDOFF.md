# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining; updated LAST at end of session.

## Status

- **Etap 1 (core scaffold) — DONE & on `main`.** `.claude/` config, scripts, gates, `CLAUDE.md`, ADRs.
- **Etap 2 (first contract slice) — DONE & MERGED.** PR #1. auth `/auth/*` (D1+D5) + articles CRUD; envelopes; `openapi.yml` 3.1.0 (7 paths, 10 ops).
- **Etap 3 (examples, CI, mock) — DONE & MERGED.** PR #2. `@opExample` (26), `x-faker` (7 fields), `contract-ci.yml` (5 gates).
- **Release v0.1.0 — DONE.** Tag `v0.1.0` → `3f5504a`. Raw URL: `https://raw.githubusercontent.com/VadayI/claude-api-contract/v0.1.0/openapi.yml`
- **Etap 4 (інверсія консумерів) — DONE ✅:**
  - **claude-django**: PR #12–#16 MERGED ✅; branch protection ON ✅; інверсія повна (ADR 0017–0020, pull_contract.sh, conformance-gate, HasScope, contract envelope).
  - **claude-react-mui PR #10** (contract-source + sync-gate + articles): MERGED ✅; CI GREEN.
  - **claude-react-mui PR #12** (Bearer + refresh, ADR 0021): MERGED ✅ (CI: Quality Gates SUCCESS; E2E failure — флапаючий тест у consumer, не контракт).

## What's next (follow-ups, без жорсткого дедлайну)

- **react-mui PR3**: 429 + Retry-After backoff у `client.ts` транспорті.
- **react-mui PR4**: `npm run mock` — Prism проти vendored `openapi.yml` (localhost:4010).
- **django**: власний CI воркфлоу + required status check на `main`.
- **django**: `contract.lock.json`/sha256 (наразі лише tag-pin у `.env.example`).
- **contract-repo cosmetic PR**: OAuth2 scope descriptions; реальний `@server`/`tokenUrl`; `last-page` list example.

## Decisions locked

- Envelope: `{count,next,previous,results}` / `{detail}` / `{errors:[{field,code,message}]}` / 429+`Retry-After`.
- Auth: Bearer/JWT, refresh in body (D2); Variant A source of truth; WSL2-only.
- Консумери тільки споживають контракт (react-mui ADR 0020, django ADR 0017).
- Bearer/JWT default у react-mui (ADR 0021 supersedes 0018).

## Accepted deviations (v0.1.0)

- `BearerAuth`/`OAuth2Auth` scheme keys; Bearer без `bearerFormat`; `/auth/token` JSON body.
- `listArticles` example — «middle page» (Spectral/AJV null-nullable crash, docs/lessons.md).

## Environment notes (see docs/lessons.md)

- `oasdiff v1.18.4` у `~/.local/bin`; `~/.bashrc` оновлено.
- git/`gh` — тільки з host/WSL2 shell.
- contract-repo `main`: branch protection ON (`contract-ci` required, reviews=0).
- claude-django `main`: branch protection ON (PR-only, без CI, reviews=0).
- claude-react-mui `main`: branch protection відсутній (follow-up, non-blocking).
- 9p NUL-padding: файли на `/mnt` писати через bash heredoc → `tr -cd '\000' < f | wc -c` == 0.
- Spectral `--fail-severity warn` → всі warnings блокують.
- **Stacked PRs + squash-merge**: squash+delete base → GitHub auto-close stacked PR. Після merge робити `git rebase origin/main` + `push --force-with-lease` + перестворити PR (docs/lessons.md).
