# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-06-10)
- Branch: `main` — clean, HEAD = `d5f1b99` (PR #32, seed.sh one-liner)
- Contract: `openapi.yml` absent (Class B — local working copy only) · `spec/` absent · latest tag: **`v0.4.0`**
- Gates: n/a (`spec/` absent — CI gates skip cleanly; PR #32 CI green)
- Template: 11 agents · 22 commands · 21 rules · 6 skills · 5 CI gates · `scripts/seed.sh` added

## What was done this session (session 7)
- **PR #32** (`feat/seed-script`) — squash-merged `d5f1b99`
  - Added `scripts/seed.sh`: one-liner seed script (`bash <(curl -fsSL .../scripts/seed.sh)`)
    - Shallow-clones `main` → copies committed files → wipes transient memory → prints next steps
    - Supports `--ref`, `--url` (fork), `--force` options
    - Class B artifacts (`spec/`, `examples/`, `openapi.yml`) correctly excluded (not in committed `main`)
  - Updated `README.md`: "Quick install" section above step-by-step guide
  - Smoke-tested in temp dir: all expected files present, Class B absent ✓

## What's next
- **Verify one-liner on clean machine:** `bash <(curl -fsSL https://raw.githubusercontent.com/VadayI/claude-api-contract/main/scripts/seed.sh)` from an empty folder
- **Test fresh clone:** `git clone https://github.com/VadayI/claude-api-contract /tmp/test-clone` → confirm `HANDOFF.md` shows generic starter, `WORKLOG.md` clean
- **Test `/ship-contract` end-to-end:** provide a real VPS IP + port → `bash scripts/deploy-mock.sh --ip <IP> --port 4010` → confirm `http://IP:4010/api/v1/auth/login` returns 200
- **Next contract work:** when a new resource is needed → `ba` → full pipeline → `/release` with semantic bump

## Open questions / risks
- `GITHUB_PERSONAL_ACCESS_TOKEN` needs `write:packages` scope for `docker push` to `ghcr.io` — verify before running `/ship-contract`
- ghcr.io package visibility: if repo is public, package is public by default; if private, VPS needs `docker login ghcr.io` before pull

## Environment notes
- WSL2 Ubuntu, Node v24.16.0, oasdiff 1.18.4 on PATH, Docker 29.5.2 available
- Repo at `/mnt/d/Dev/My/claude-api-contract` (Windows drive via WSL2)
- `.env.example` has local edits (not committed — dev-only; user decision)
