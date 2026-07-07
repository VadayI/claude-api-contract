# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-07-07, session 13 end — F×6 rules↔skills dedup, via Cowork)
- Branch: `main` == `origin/main` (D+E merged, branches deleted on GitHub) + **uncommitted local changes from this session**: 5 rules + 6 skills + 3 docs (14 files). Awaiting single branch/commit/PR on the host (user decision: one PR, one commit).
- Audit 2026-07-07 queue: A–E **merged**; **F×6 applied this session** (uncommitted). Remaining: G (family-core) → H (+ inherited L2).
- Dedup principle now live: **rule = norms, skill = recipes**, mutual pointers, no fact in two places. Skill examples mirror live configs (`.spectral.yaml`), not invented ones.
- ⚠️ Sandbox git remains unreliable on this mount (stale-cache showed a fake "No commits yet" state after host ops) — ALL git on host; sandbox = file edits + reads only.
- Contract untouched → no semver movement. Latest tag: **v0.4.0**. Counts: 12 agents · 23 commands · 21 rules · 6 skills · 3 workflows.

## What was done this session
- **F1–F6** (11 files): typespec, spectral, prism, oasdiff, versioning pairs split norms-vs-recipes; `openapi-design` → heuristics + rule index. Bonus fixes: `x-surface` norm+recipe added (typespec pair), oasdiff skill aligned with ADR 0008, spectral skill examples synced to live ruleset.
- Docs: WORKLOG s13, todo (F ✅), this HANDOFF.

## What's next
1. **HOST:** `git checkout -b chore/rules-skills-dedup` → add the 14 files (list in WORKLOG s13 / `git status`) → single commit → push → PR.
2. **G (P2):** family-core plugin — ADR 0011 (core/domain boundary) → `claude-family-marketplace` repo → `family-core v0.1.0` pilot here → roll out to claude-django / claude-react-mui (AUDIT §6).
3. **H (P4) decisions:** Spectral `warn`→`error` (snake_case, schema-description); `npm run validate` ⊇ `check:endpoints`. Inherited: **L2** confirm `UserPromptExpansion` on the live CLI; AUDIT-file tracking decision.

## Open questions / risks
- family-core: exact core/domain boundary for `ba`/`devil`/`brief-synthesizer` (domain tails) — ADR 0011.
- Plugin-hook behavior parity Cowork vs CLI — test during family-core Phase 1 pilot.
- `living-plan.md` wording ("each agent appends via Edit") vs read-only `ba` + Bash-appending reviewers — small wording reconcile, fold into any nearby rules PR.
- Skill descriptions now state "norms live in <rule>" — when G moves skills into a plugin, revisit those pointers (plugin skills can't assume repo rules exist).
