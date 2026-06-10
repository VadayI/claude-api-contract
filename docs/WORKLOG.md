# WORKLOG

> Append-only chronicle of what changed each session (newest first).

## 2026-06-10 (session 7)
- feat: `scripts/seed.sh` + README "Quick install" — PR #32 — CI: green — tag: none
  - Added `scripts/seed.sh`: one-liner seed script (`bash <(curl -fsSL .../scripts/seed.sh)`) modelled after `claude-react-mui`
  - Shallow-clones `main` → copies all committed files (Class B artifacts absent from git, so correctly excluded) → wipes transient memory → prints next steps
  - Updated `README.md`: new "Quick install" section above step-by-step guide
  - Smoke-tested: `.spectral.yaml`, `.mcp.json`, `.env.example`, ADR 0001/0005/0006 present; `spec/`, `openapi.yml`, ADR 0002–0004 absent ✓
  - Branch `feat/seed-script` → PR #32 → squash-merged `d5f1b99` — CI green
  - No contract change; no semver bump; consumers: no action needed

## 2026-06-09 (session 6)
- chore: reset HANDOFF, WORKLOG, CHANGELOG to clean template starters — PR #31 — CI: green — tag: none
  - Audited GitHub `main` for local-project data leakage: `spec/`, `examples/`, `openapi.yml`, ADR 0002–0004 correctly absent
  - Found `docs/HANDOFF.md`, `docs/WORKLOG.md`, `CHANGELOG.md` contained claude-api-contract meta-development history (sessions 1–5, PRs, v0.1–v0.4 entries)
  - Reset all three to clean template starters (blank slate for a fresh clone)
  - Branch `docs/session-5-wrap-up` → PR #31 → squash-merged `fc13671`
  - No contract change; no semver bump; consumers: no action needed

## <YYYY-MM-DD>
- <change> — gates: <result> — tag: <if any>
