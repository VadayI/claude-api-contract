# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-06-09)
- Branch: `main` — clean, HEAD = `45ba061` (PR #29, Prism Docker fix)
- Contract: `openapi.yml` matches `spec/` ✓ · latest tag: **`v0.4.0`**
- Gates: all green (`npm run validate` ✓ — drift · lint · examples)
- Template: 11 agents · 22 commands · **21 rules** (deploy.md updated with `-m false` invariant) · 6 skills · 5 CI gates

## What was done this session (session 5)
- **PR #29** (`fix/prism-docker-multiprocess`) — squash-merged
  - Root cause: `stoplight/prism:5` default multiprocess mode reads `cluster.isPrimary` → `undefined` inside Docker → immediate startup crash
  - Fix: `-m false` added to `Dockerfile` CMD (single-process mode); local `npm run mock` unaffected
  - `.claude/rules/deploy.md` Invariants: new bullet documents the `-m false` requirement for Docker deploys
  - `docs/lessons.md`: first real gotcha entry (symptom / cause / fix / note)
  - Docker smoke-test verified: container starts cleanly, `Prism is listening on http://0.0.0.0:4010`
- `/audit` + `/doctor`: environment healthy (WSL2, Node v24.16.0, all tools present, all scopes green)

## What's next
- **Test `/ship-contract` end-to-end:** provide a real VPS IP + port, run `bash scripts/deploy-mock.sh --ip <IP> --port 4010`, confirm `http://IP:4010/api/v1/auth/login` returns 200. The Prism crash fix means the container will now start correctly.
- **Consumer repos** (`claude-django`, `claude-react-mui`) are on `v0.1.0` — contract shape unchanged, no pin bump needed yet; bump after a real contract change
- **Next contract work:** when a new resource is needed, start with `ba` → full pipeline → `/release` with semantic bump

## Open questions / risks
- `GITHUB_PERSONAL_ACCESS_TOKEN` needs `write:packages` scope for `docker push` to `ghcr.io` — verify before running `/ship-contract`
- ghcr.io package visibility: if repo is public, package is public by default; if private, VPS needs `docker login ghcr.io` before pull (documented in `deploy-mock.sh` output)
- `.env.example` has unstaged local changes (not committed — dev-only secrets placeholder edit; user decision to leave as-is)
- `docs/decisions/0002–0004`, `examples/`, `spec/`, `openapi.yml` are untracked on this working copy (Class B items — template-internal working state, excluded from commits intentionally)

## Environment notes
- WSL2 Ubuntu, Node v24.16.0, oasdiff 1.18.4 on PATH, Docker 29.5.2 available
- Repo at `/mnt/d/Dev/My/claude-api-contract` (Windows drive via WSL2)
- `.claude/memory/env-detect.json` current (SessionStart hook)
