# WORKLOG

> Append-only chronicle of what changed each session (newest first).

## 2026-06-06 — Etap 2 (first contract slice: auth + articles)
- Full pipeline: api-architect (design → `docs/plans/0001`) → tsp-author (`spec/` → `openapi.yml`) → contract-reviewer (READY FOR PR, 0 blockers) → docs-writer (`endpoints.json`, `INDEX.md`, `CHANGELOG`). breaking-analyst SKIP (no prior tag).
- Authored `spec/main.tsp`, `spec/auth.tsp`, `spec/articles.tsp`, `spec/models/{pagination,errors,security}.tsp`. Generated first canonical `openapi.yml` (OpenAPI 3.1.0): 7 paths, 10 operations.
- Auth: user-flow (register/login/refresh/logout, D1) + service-flow (`/auth/token`, client-credentials, D5). Articles CRUD (blog-style) with `articles:read`/`articles:write` scopes. Envelopes: `ListResponse<T>`, `ErrorDetail`, `ValidationErrors`, `Retry-After` on 429.
- Toolchain fixes (in PR): removed `@typespec/rest` (incompatible peer with compiler 1.x); added `tspconfig.yaml` (emits 3.1.0).
- Fixed an accidental personal-email leak the authoring subagent wrote into `info.contact.email` → `VadayI@users.noreply.github.com`.
- `npm run validate` GREEN locally (WSL2) and in sandbox. Branch `feat/contract-first-slice` pushed; **PR #1 open**: https://github.com/VadayI/claude-api-contract/pull/1
- Open: `package-lock.json` still untracked (recommend committing to the PR for `npm ci`).

## 2026-06-06 — Etap 1 (scaffold)
- Created the template core: repo scaffolding (`.gitignore`, `.gitattributes`, `.spectral.yaml`, `package.json`, `.mcp.json`), `.claude/settings.json`.
- Node/bash toolchain scripts: `detect-env.mjs`, `session-start.sh`, `log-cmd.mjs`, `install.sh`, `setup-wsl.sh`, gate scripts (`check_typespec_drift.sh`, `check_examples.sh`, `check_breaking.sh`, `bundle-openapi.mjs`).
- 18 rules, 11 agents, 6 skills, 17 commands, `CLAUDE.md`, `README.md`, `templates/`, ADRs.
- Pending (next Etap): `spec/` first slice (auth D1+D5 + sample resource), `examples/`, CI workflow `contract-ci.yml`, first compile → `openapi.yml`, tag `v0.1.0`.

## 2026-06-06 — Etap 1 verified; first push prepared
- Verification pass: no empty/NUL/corrupt files, frontmatter present, no orphan rules, scripts runnable.
- GitHub repo created (empty). First push prepared as a host-shell command block (sandbox lacks gh/PAT; /mnt 9p unsafe for .git). Push + branch protection pending.
