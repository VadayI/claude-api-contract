# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-06-09)
- Branch: `main` — clean, HEAD = `6b1d116` (PR #22, v0.3.0 release)
- Contract: `openapi.yml` matches `spec/` ✓ · latest tag: **`v0.3.0`**
- Gates: all green (`npm run validate` ✓ — drift · lint · examples)
- Template: 11 agents · **22 commands** (new: `check-readme`, `ship-contract`) · **20 rules** (new: `deploy.md`) · 6 skills · 5 CI gates
- 3 PRs open, none merged yet — all are infrastructure/template additions (no contract change)

## What was done this session
- **PR #23** (`feat/contract-packaging`) — Docker + VPS deploy infrastructure (Slice A)
  - `Dockerfile` (node:22-alpine, prism-cli@5.12.0, USER node, `-h 0.0.0.0`, static mock)
  - `.dockerignore` (minimal context — only `openapi.yml`)
  - `scripts/check_ready.sh` — readiness gate composing all 5 existing gates + auth presence check
  - `scripts/deploy-mock.sh` — build + push to `ghcr.io/<owner>/<repo>-mock:<tag>` + print VPS command; `--dry-run`
  - `package.json`: `ready`, `deploy:mock` scripts
  - `docs/decisions/0006-deploy-mock-to-vps.md` — ADR
- **PR #24** (`feat/check-readme-command`) — README audit command (Slice B)
  - `.claude/commands/check-readme.md` — `/check-readme`: audits version, counts, `## For consumers`, links
  - `.claude/agents/docs-writer.md` — scope += README freshness
  - `README.md` — `## For consumers` section added, status `v0.1.0` → `v0.3.0`, Quick start updated
- **PR #25** (`feat/ship-contract-command`) — ship command (Slice C)
  - `.claude/rules/deploy.md` — deploy model rule (loaded per-command by `/ship-contract`)
  - `.claude/commands/ship-contract.md` — `/ship-contract <IP> <PORT>`: readiness gate → build/push → README update → report

## What's next
- **Merge order:** PR #23 → #24 → #25 (A → B → C; B's README section needs A's scripts to exist; C references A+B)
  - All three can actually merge independently (no code conflicts), but semantic order matters
- **After merge:** run `/release` minor bump → **`v0.4.0`** (new commands + deploy infrastructure = minor addition)
- **Test `/ship-contract` end-to-end:** provide a real VPS IP + port, run `bash scripts/deploy-mock.sh --ip <IP> --port 4010`, confirm `http://IP:4010/api/v1/auth/login` returns 200
- **Test `/check-readme`:** run it, confirm it reports the current README as up-to-date (after PR #24 merges)
- Consumer repos (`claude-django`, `claude-react-mui`) are on `v0.1.0` — contract shape unchanged, no pin bump needed yet; bump after v0.4.0 tag if consumers want the deploy infra

## Open questions / risks
- `GITHUB_PERSONAL_ACCESS_TOKEN` needs `write:packages` scope for `docker push` to `ghcr.io` (noted in `deploy.md` + `deploy-mock.sh`); verify the PAT has this scope before running `/ship-contract`
- ghcr.io package visibility: if the repo is public, the package will be public by default; if private, VPS needs `docker login ghcr.io` before pull (documented in `deploy-mock.sh` output)
- `.env.example` has unstaged local changes (not committed — dev-only secrets placeholder edit)
- `docs/decisions/0002–0004`, `examples/`, `spec/`, `openapi.yml` are untracked on this working copy
  (Class B items — template-internal working state, excluded from commits intentionally)

## Environment notes
- WSL2 Ubuntu, Node v24.16.0, oasdiff on PATH, Docker available
- Repo at `/mnt/d/Dev/My/claude-api-contract` (Windows drive via WSL2)
- `.claude/memory/env-detect.json` current (SessionStart hook)
