# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining; updated LAST at end of session.

## Status
- **Etap 1 (ядро) — DONE.** Template core scaffolded: `.claude/` (11 agents · 19 commands · 18 rules · 6 skills · settings.json), 9 scripts (Node + bash gates), `CLAUDE.md`, `README.md`, `.spectral.yaml`, `package.json`, `.mcp.json`, `templates/`, `docs/` (WORKLOG + 3 ADRs), `.claude/memory/endpoints.json` (`[]`).
- **Git: not initialized yet in the repo.** GitHub repo created empty: https://github.com/VadayI/claude-api-contract
- **First push: PENDING** — must be run from the host/WSL2 shell (sandbox has no `gh`/PAT and `/mnt` 9p is unsafe for `.git`). Command block is in the session summary / next-session prompt.
- Verified: no empty/NUL files, frontmatter valid, no orphan rules, `detect-env.mjs` runs (Node 22, linux), `log-cmd.mjs` works.

## What's next
1. **First push** (host shell): init → branch `main` → add → commit → remote → push (one-time empty-repo seed), then enable branch protection so PR-only holds afterward.
2. **Etap 2 — spec/ first slice:** `spec/main.tsp` (@service, @server, security), `spec/models/` (ListResponse<T>, ErrorDetail, ValidationErrors + Retry-After), `spec/auth.tsp` (D1 user-flow + D5 service-flow), one sample resource (e.g. articles). Then `npm run api:compile && npm run api:bundle` → first `openapi.yml`.
3. **Etap 3 — examples/ + CI:** realistic examples (x-faker), `.github/workflows/contract-ci.yml` (5 gates), Prism mock smoke.
4. **Release `v0.1.0`** via `/release`.
5. Later (separate PRs): invert consumers `claude-django` and `claude-react-mui`.

## Decisions locked
- Envelope: recommended defaults (list `{count,next,previous,results}`; errors `{detail}`+`{errors[]}`; 429+Retry-After).
- Order: contract to v0.1.0 first, then consumers.
- Auth: Bearer/JWT, refresh in body (ADR 0003); Variant A source of truth (ADR 0002); WSL2-only (ADR 0001).

## Environment notes
- Toolchain is Node-based (.mjs scripts + bash gates), unlike the Python-based claude-django.
- Run git from the host/WSL2 shell when the repo is on `/mnt/...`.
