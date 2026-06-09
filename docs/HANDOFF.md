# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-06-09)
- Branch: `main` — clean, HEAD = `fc13671` (PR #31, template docs reset)
- Contract: `openapi.yml` absent (Class B — local working copy only) · `spec/` absent · latest tag: **`v0.4.0`**
- Gates: n/a (`spec/` absent — CI gates skip cleanly)
- Template: 11 agents · 22 commands · 21 rules · 6 skills · 5 CI gates · all docs reset to clean starters

## What was done this session (session 6)
- **PR #31** (`docs/session-5-wrap-up`) — squash-merged
  - Audited GitHub `main`: `spec/`, `examples/`, `openapi.yml`, ADR 0002–0004 correctly absent ✓
  - Found `HANDOFF.md`, `WORKLOG.md`, `CHANGELOG.md` contained template meta-development history (sessions 1–5)
  - Reset all three to clean template starters so a fresh clone gets a blank slate

## What's next
- **Test fresh clone:** `git clone https://github.com/VadayI/claude-api-contract /tmp/test-clone` → confirm `HANDOFF.md` shows generic starter, `WORKLOG.md` has only placeholder, `CHANGELOG.md` has only `## [Unreleased]`
- **Test `/ship-contract` end-to-end:** provide a real VPS IP + port, run `bash scripts/deploy-mock.sh --ip <IP> --port 4010`, confirm `http://IP:4010/api/v1/auth/login` returns 200 (Prism `-m false` fix means container now starts correctly)
- **Consumer repos** (`claude-django`, `claude-react-mui`) — contract shape unchanged since `v0.4.0`, no pin bump needed; bump after a real contract change
- **Next contract work:** when a new resource is needed → `ba` → full pipeline → `/release` with semantic bump

## Open questions / risks
- `GITHUB_PERSONAL_ACCESS_TOKEN` needs `write:packages` scope for `docker push` to `ghcr.io` — verify before running `/ship-contract`
- ghcr.io package visibility: if repo is public, package is public by default; if private, VPS needs `docker login ghcr.io` before pull

## Environment notes
- WSL2 Ubuntu, Node v24.16.0, oasdiff 1.18.4 on PATH, Docker 29.5.2 available
- Repo at `/mnt/d/Dev/My/claude-api-contract` (Windows drive via WSL2)
- `.env.example` has local edits (not committed — dev-only; user decision)
