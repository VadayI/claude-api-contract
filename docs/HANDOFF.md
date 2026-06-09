# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-06-09)
- Branch: `main` — clean, HEAD = `484a0d0` (PR #27, CHANGELOG v0.4.0)
- Contract: `openapi.yml` matches `spec/` ✓ · latest tag: **`v0.4.0`**
- Gates: all green (`npm run validate` ✓ — drift · lint · examples)
- Template: 11 agents · **22 commands** (new: `check-readme`, `ship-contract`) · **20 rules** (new: `deploy.md`) · 6 skills · 5 CI gates

## What was done this session
- **Merged PRs #23–#25** — Docker deploy infrastructure + `/check-readme` + `/ship-contract` (all green CI, squash-merged)
  - PR #23 (`feat/contract-packaging`) — `Dockerfile`, `.dockerignore`, `scripts/check_ready.sh`, `scripts/deploy-mock.sh`, `package.json: ready + deploy:mock`, ADR 0006
  - PR #24 (`feat/check-readme-command`) — `.claude/commands/check-readme.md`, `docs-writer` scope += README, `README.md ## For consumers`
  - PR #25 (`feat/ship-contract-command`) — `.claude/rules/deploy.md`, `.claude/commands/ship-contract.md`
- **PR #26** — session 4 wrap-up (WORKLOG + HANDOFF)
- **PR #27** — `CHANGELOG.md` v0.4.0 entry + release
- **Tag `v0.4.0`** pushed; GitHub release created — MINOR bump (new commands + deploy infra, zero contract change)

## What's next
- **Test `/ship-contract` end-to-end:** provide a real VPS IP + port, run `bash scripts/deploy-mock.sh --ip <IP> --port 4010`, confirm `http://IP:4010/api/v1/auth/login` returns 200
- **Test `/check-readme`:** run it inside Claude Code CLI — should report README as up-to-date now
- **Consumer repos** (`claude-django`, `claude-react-mui`) are on `v0.1.0` — contract shape unchanged, no pin bump needed yet; bump after a real contract change
- **Next contract work:** when a new resource is needed, start with `ba` → full pipeline → `/release` with semantic bump

## Open questions / risks
- `GITHUB_PERSONAL_ACCESS_TOKEN` needs `write:packages` scope for `docker push` to `ghcr.io` — verify before running `/ship-contract`
- ghcr.io package visibility: if repo is public, package is public by default; if private, VPS needs `docker login ghcr.io` before pull (documented in `deploy-mock.sh` output)
- `.env.example` has unstaged local changes (not committed — dev-only secrets placeholder edit)
- `docs/decisions/0002–0004`, `examples/`, `spec/`, `openapi.yml` are untracked on this working copy (Class B items — template-internal working state, excluded from commits intentionally)

## Environment notes
- WSL2 Ubuntu, Node v24.16.0, oasdiff on PATH, Docker available
- Repo at `/mnt/d/Dev/My/claude-api-contract` (Windows drive via WSL2)
- `.claude/memory/env-detect.json` current (SessionStart hook)
