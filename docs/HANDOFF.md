# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining; updated LAST at end of session.

## Status
- **Etap 1 (core scaffold) — DONE & on `main`.** `.claude/` config, scripts, gates, `CLAUDE.md`, ADRs.
- **Etap 2 (first contract slice) — DONE & MERGED.** PR #1 merged to `main` (`3d3b50d`). auth `/auth/*` (user-flow D1 + service-flow D5) + articles CRUD; envelopes; `openapi.yml` 3.1.0 (7 paths, 10 ops).
- **Etap 3 (examples, CI, mock) — DONE; in review.** Branch `feat/etap-3-examples-ci-mock`, **PR #2 OPEN**: https://github.com/VadayI/claude-api-contract/pull/2
  - `spec/auth.tsp` + `spec/articles.tsp`: `@opExample` (26 inline examples — success + 400/401/403/404/409/429) + `@extension("x-faker")` (7 fields). `openapi.yml` regenerated (drift OK).
  - `examples/**` request fixtures (auth + articles). `scripts/check_mock.sh` + `npm run mock:smoke` (11 endpoints, two-way validation, enforce-401 without bearer).
  - `.github/workflows/contract-ci.yml` — 5 gates: TypeSpec drift · Spectral lint · examples · oasdiff breaking (`--fail-on ERR`) · Prism mock smoke.
  - `docs/verify/etap-3.md` (Prism + curl checklist). `INDEX.md` + `CHANGELOG` updated.
  - `npm run validate` GREEN + `npm run mock:smoke` GREEN (sandbox + WSL2). breaking SKIP (no prior tag).

## What's next (in order)
1. **Merge PR #2**: wait for `contract-ci` green, then `gh pr merge 2 --merge --delete-branch`; `git switch main && git pull`.
2. **Wire the CI gate into branch protection** (full PUT — granular PATCH 404s until `required_status_checks` exists): set `required_status_checks.contexts=["contract-ci"]`, keep `required_pull_request_reviews.required_approving_review_count=0` (PR-only, solo). After this, merges need green CI, not `--admin`.
3. **Release `v0.1.0`** via `/release v0.1.0` from `main` (rebuild → gates → CHANGELOG via oasdiff → tag → push). Never tag a RED contract.
4. **Etap 4 (separate repos, after v0.1.0):** invert consumers `claude-django` (validate impl vs contract; pull + sync-gate; pin `CONTRACT_VERSION`) and `claude-react-mui` (Bearer + refresh-flow; `api:pull`; sync-gate).

## Decisions locked
- Envelope defaults (list `{count,next,previous,results}`; errors `{detail}`+`{errors[]}`; 429+`Retry-After`).
- Auth: Bearer/JWT, refresh in body (ADR 0003); Variant A source of truth (ADR 0002); WSL2-only (ADR 0001).
- Order: contract to v0.1.0 first, then consumers.

## Accepted deviations (v0.1.0) — see docs/api/INDEX.md
- Security scheme keys `BearerAuth`/`OAuth2Auth`; Bearer scheme without `bearerFormat`; `/auth/token` JSON body.
- `listArticles` example uses a "middle page" (`next`/`previous` URLs, not `null`) — Spectral 6.16/AJV crashes on literal `null` examples vs nullable-3.1 schemas (docs/lessons.md). Schema still types `next: url | null`.

## Environment notes (see docs/lessons.md)
- Run git/`gh` from the host/WSL2 shell (sandbox lacks gh/PAT; `.git` on 9p unsafe to mutate from sandbox — caused an `index.lock` once this session).
- Branch protection on `main` is ON; solo can't self-approve → reviews count set to 0; first PR merged via `--admin`.
- 9p file-tool NUL-padding on shrink — author via bash (heredoc/python/sed), never the Write/Edit tools on `/mnt`; verify `tr -cd '\000' < f | wc -c` == 0.
- `oasdiff` not in the sandbox — `npm run breaking` errors there; on the host (oasdiff present) and in CI it SKIPs until the first `v*` tag.
- Spectral examples gate uses `--fail-severity warn` → `spectral:oas` "all" warnings are blocking.
