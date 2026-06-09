# WORKLOG

> Append-only chronicle of what changed each session (newest first).

## 2026-06-09 (session 5)
- fix: Prism Docker multiprocess crash — PR #29 — CI: green — tag: none (patch, no contract change)
  - **PR #29** (`fix/prism-docker-multiprocess`) — squash-merged
    - `Dockerfile` CMD: added `-m false` + explanatory comment (prism 5 reads `cluster.isPrimary` → `undefined` in Docker → crash; single-process mode bypasses the broken code path)
    - `.claude/rules/deploy.md` Invariants: new bullet documenting `-m false` requirement
    - `docs/lessons.md`: first real gotcha entry (symptom → cause → fix → note about local mock unaffected)
  - Docker smoke-test passed: `Prism is listening on http://0.0.0.0:4010` — no isPrimary crash
  - `/audit` + `/doctor` run: environment healthy across all 4 scopes; no env fixes applied (user decision)

## 2026-06-09 (session 4b — continuation)
- chore: merge PRs #23–#25 + #26 (wrap-up) + #27 (release) — CI: green — tag: **v0.4.0**
  - All 4 PRs merged to `main` in order #23→#24→#25→#26→#27
  - `CHANGELOG.md` — v0.4.0 entry prepended by `docs-writer`
  - `git tag v0.4.0` pushed; GitHub release created
  - Bump: **MINOR** — new commands + deploy infrastructure, zero contract shape change; consumers: no pin bump needed

## 2026-06-09 (session 4)
- feat: Docker packaging + VPS deploy infrastructure + `/check-readme` + `/ship-contract` — 3 PRs open → merged — tag: v0.4.0
  - **PR #23** (`feat/contract-packaging`) — Slice A: deploy infrastructure
    - `Dockerfile` — `node:22-alpine`, `prism-cli@5.12.0` global, static mock, `-h 0.0.0.0`, `USER node`, `npm cache clean`
    - `.dockerignore` — minimal build context (only `openapi.yml` reaches the image)
    - `scripts/check_ready.sh` — readiness gate: `npm run validate` + mock smoke + breaking + artifact/auth checks; WARN if HEAD not on a v* tag
    - `scripts/deploy-mock.sh` — build image, push to `ghcr.io/<owner>/<repo>-mock:<tag>`, print VPS `docker run` command; `--dry-run` support; early token/docker checks; `docker rm` on redeploy
    - `package.json`: `ready` + `deploy:mock` scripts added
    - `docs/decisions/0006-deploy-mock-to-vps.md` — ADR: static Prism mock, Docker, ghcr.io, direct IP:PORT
  - **PR #24** (`feat/check-readme-command`) — Slice B: README audit command
    - `.claude/commands/check-readme.md` — new `/check-readme` command: delegates to `docs-writer`, audits version/counts/consumer section/links, confirm-before-apply
    - `.claude/agents/docs-writer.md` — scope expanded: `README.md` freshness added to "What you produce"
    - `README.md` — new `## For consumers` section (backend/frontend parallel-work table, pin-version, live mock placeholder); status updated `v0.1.0` → `v0.3.0`; `/check-readme` + `/ship-contract` in Quick start
  - **PR #25** (`feat/ship-contract-command`) — Slice C: ship command
    - `.claude/rules/deploy.md` — new rule: deploy model (ghcr.io + VPS pull, static mock, no nginx, invariants, security notes)
    - `.claude/commands/ship-contract.md` — new `/ship-contract <IP> <PORT>` command: readiness gate → deploy-mock.sh → docs-writer updates README → report VPS command
  - No contract change (`spec/`/`openapi.yml` untouched); no tag needed this session

## 2026-06-08 (session 3)
- feat: project maturity stage + Definition of Done (#20) — CI: green — tag: none
  - New global rule `.claude/rules/project-maturity.md`: 5-stage taxonomy (demo/prototype/PoC/MVP/production/other),
    process matrix (pipeline depth · `devil` · review rigour · example completeness per stage),
    invariant block (5 CI gates + `@doc` always ON, never relaxed by stage)
  - ADR `docs/decisions/0005-project-maturity-stage.md`: guidance-only, no gate skipping
  - `templates/PROJECT.md`: new `**Maturity stage:**` header field + §7 Definition of Done
    (standard gates checklist + project-specific criteria — never left as placeholder)
  - `.claude/rules/preflight.md`: 2 new CRITICAL build-input rows (stage + DoD)
  - `CLAUDE.md`: import + dispatcher note (read stage before dispatch, ask if missing)
  - Agents updated: `ba`, `brief-synthesizer`, `api-architect`, `contract-reviewer`,
    `mock-validator`, `devil` — all maturity-aware; `devil` now has "When to run" section
  - Commands updated: `/preflight`, `/synthesize-brief`

## 2026-06-08 (session 2)
- feat: `/personalize` command + `scripts/personalize.sh` (#18) — CI: green (18s) — tag: none
  - Tier 1: `VadayI/claude-api-contract` URLs, `package.json` name/desc, `README.md` H1
  - Tier 2: `package.json` version → `0.0.0`, delete `docs/AUDIT-*.md`
  - Tier 3: `[claude-api-contract]` → `[{slug}]` in all `.claude/` frontmatter (~40 files)
  - Guard: refuses without `--force` on `VadayI/claude-api-contract` origin
  - `/bootstrap` Mode A: new step 2 personalizes identity before `spec/` authoring + `git init`
  - `npm run personalize` script added; README Step 7 + Quick start updated

## 2026-06-08 (session 1)
- docs: explicit step-by-step installation guide in README (#15) — CI: green — tag: none
  - Added Steps 0–7 (WSL2 → folder → clone → toolchain → deps → secrets → claude)
- fix: git clone destination with trailing `.` + Uninstall section (#16) — CI: green — tag: none
- fix: Step 3 — disconnect template `.git` + link own repo with `gh repo create` (#17) — CI: green — tag: none
- feat: `sandbox.sh` (clone → temp dir + install) + `clean.sh` (Class A/B removal) (#14) — CI: green — tag: none
- fix: CI spec/-guard — gates skip when `spec/` absent; bootstrap Mode A step 2 via `tsp-author` (#13) — CI: green — tag: none

## <YYYY-MM-DD>
- <change> — gates: <result> — tag: <if any>
