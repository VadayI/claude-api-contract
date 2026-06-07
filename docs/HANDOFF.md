# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining; updated LAST at end of session.

## Status
- **Etap 1 (core scaffold) — DONE & on `main`.** `.claude/` config, scripts, gates, `CLAUDE.md`, ADRs.
- **Etap 2 (first contract slice) — DONE & MERGED.** PR #1 merged to `main` (`3d3b50d`). auth `/auth/*` (user-flow D1 + service-flow D5) + articles CRUD; envelopes; `openapi.yml` 3.1.0 (7 paths, 10 ops).
- **Etap 3 (examples, CI, mock) — DONE & MERGED.** PR #2 merged to `main`. `@opExample` (26 inline examples), `x-faker` (7 fields), `examples/**` fixtures, `check_mock.sh`, `contract-ci.yml` (5 gates), `docs/verify/etap-3.md`.
- **Release v0.1.0 — DONE.** Tag `v0.1.0` на `main` (merge-commit `3f5504a`), PR #3 merged, GitHub Release опублікований. `oasdiff v1.18.4` встановлений у `~/.local/bin`. breaking-аналіз N/A (перший тег).

## Raw URL (споживачі пінять цю версію)

```
https://raw.githubusercontent.com/VadayI/claude-api-contract/v0.1.0/openapi.yml
```

## What's next (in order)

1. **Branch protection** (малий крок, але важливий): wire `contract-ci` до `required_status_checks` на `main` — full PUT `/branches/main/protection` (`required_status_checks.contexts=["contract-ci"]`, `required_approving_review_count=0`). Після цього CI-gate є hard-block на merge, `--admin` більше не потрібен.
2. **Etap 4 — consumer repos (після v0.1.0):**
   - `claude-django`: pin `CONTRACT_VERSION=v0.1.0`; vendor `openapi.yml`; `scripts/check_contract_sync.sh`; validate impl vs contract.
   - `claude-react-mui`: `openapi-typescript` з `v0.1.0`; Bearer + refresh-flow; sync-gate.
3. **Cosmetic follow-ups (minor PR):**
   - OAuth2 scope descriptions (empty map в `spec/models/security.tsp`).
   - Replace mock `tokenUrl`/`@server` (localhost:4010) реальним URL, коли backend з'явиться.
   - `last-page` list example (після фіксу Spectral/AJV null-example bug upstream).

## Decisions locked
- Envelope defaults (list `{count,next,previous,results}`; errors `{detail}`+`{errors[]}`; 429+`Retry-After`).
- Auth: Bearer/JWT, refresh in body (ADR 0003); Variant A source of truth (ADR 0002); WSL2-only (ADR 0001).
- Order: contract → v0.1.0 (DONE) → consumers (next).

## Accepted deviations (v0.1.0) — see docs/api/INDEX.md
- Security scheme keys `BearerAuth`/`OAuth2Auth`; Bearer scheme without `bearerFormat`; `/auth/token` JSON body.
- `listArticles` example uses "middle page" (`next`/`previous` URLs, not `null`) — Spectral 6.16/AJV crashes on literal `null` examples vs nullable-3.1 schemas (docs/lessons.md). Schema still types `next: url | null`.

## Environment notes (see docs/lessons.md)
- `oasdiff v1.18.4` встановлено у `~/.local/bin` (не `/usr/local/bin` — sudo недоступний в цій сесії). `~/.bashrc` оновлено. Для нових терміналів PATH підхопиться автоматично.
- Run git/`gh` from the host/WSL2 shell.
- Branch protection на `main` ON (solo, reviews count=0). Merge через PR + CI.
- 9p file-tool NUL-padding на shrink — автори через bash (heredoc/python/sed), verify `tr -cd '\000' < f | wc -c` == 0.
- Spectral examples gate `--fail-severity warn` → `spectral:oas` "all" warnings are blocking.
