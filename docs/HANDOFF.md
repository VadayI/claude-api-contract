# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are
- **Branch:** `main` (clean, fully in sync with `origin/main`)
- **Contract:** `openapi.yml` matches `spec/` (drift gate green) · latest tag: **`v0.2.0`**
- **Gates:** validate ✅ green · drift ✅ green · breaking ✅ classified (5 ERR path-removed, intentional, listed in `.oasdiff-ignore.txt`)
- **Shipped scope:** auth endpoints (register / login / refresh / logout / token) under `/api/v1/auth/*` + articles CRUD under `/api/v1/articles/*`. Full endpoint registry in `.claude/memory/endpoints.json`.
- **No active plans** (`docs/plans/` empty). No open PRs. Release cycle closed.

## What's next
- **Consumer update required:** both `claude-django` and `claude-react-mui` must update any hardcoded `/auth/` prefix to `/api/v1/auth/` and bump `CONTRACT_VERSION` to `v0.2.0`.
- **New resource?** Start the pipeline from `ba` (user stories + scope first, then `api-architect → tsp-author → contract-reviewer → breaking-check → mock-validator → docs-writer`).
- **Nothing is blocked.** All gates green; repo at a clean resting point.

## Open questions / risks
- None. The intentional breaking rename (ADR 0004) is documented and the oasdiff ignore is in place.

## Environment notes
- WSL2 Ubuntu on Windows. Run all commands inside WSL2 (`node`, `npm`, `git`, `gh`, `claude`).
- `oasdiff` must be on PATH (breaking-change gate). Verify: `oasdiff --version`.
- Node 20.19+ required (22 LTS recommended). Verify: `node --version`.
- `.claude/memory/env-detect.json` is rewritten by the `SessionStart` hook on every session start.
