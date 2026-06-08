# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-06-08)
- Branch: `main` — clean, HEAD = `6e642fb` (PR #20 squash-merged)
- Contract: `openapi.yml` matches `spec/` ✓ · latest tag: `v0.2.0`
- Gates: all green (`npm run validate` ✓ — drift · lint · examples)
- Template: 11 agents · 20 commands · **19 rules** (new: `project-maturity.md`) · 6 skills · 5 CI gates

## What was done this session
- **PR #20** — project maturity stage + Definition of Done (`feat/maturity-stage-and-dod`)
  - New global rule `.claude/rules/project-maturity.md`: 5-stage taxonomy + process matrix + CI-gate invariant
  - `templates/PROJECT.md` §7 DoD: standard checklist + project-specific criteria (explicit agreement required)
  - Preflight gate: 2 new CRITICAL rows (stage + DoD) → hard STOP if missing
  - `CLAUDE.md`: import + dispatcher note
  - 7 agents + 2 commands updated with maturity-aware guidance
  - ADR 0005 recorded

## What's next
- `/release` minor bump → **`v0.3.0`**: session 2 (`/personalize`) + session 3 (maturity+DoD) both minor additions;
  run `npm run validate && npm run breaking` first.
- Test `/personalize` prose pass (docs-writer step 3) against a real derived project clone.
- Consider adding `/synthesize-brief` flow test: verify `AskUserQuestion` fires for missing stage + missing DoD.
- Consumer repos (`claude-django`, `claude-react-mui`) are on `v0.1.0` — contract shape unchanged, no pin bump needed.

## Open questions / risks
- `scripts/personalize.sh` prose pass (docs-writer step 3) not yet end-to-end tested against a derived project.
- `.env.example` has unstaged local changes (not committed — likely dev-only secrets placeholder edit).
- `docs/decisions/0002–0004`, `examples/`, `spec/`, `openapi.yml` are untracked on this working copy
  (Class B items — present only on the template's own working copy, not committed to git).
  These belong to the template-internal working state and are excluded from commits intentionally.

## Environment notes
- WSL2 Ubuntu, Node v24.16.0, oasdiff on PATH
- Repo at `/mnt/d/Dev/My/claude-api-contract` (Windows drive via WSL2)
- `.claude/memory/env-detect.json` current (SessionStart hook)
