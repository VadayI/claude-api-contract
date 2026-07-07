# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-07-07, session 12 end — audit queue D+E, via Cowork)
- Branch: `main` == `origin/main` (`a6a5468`, PR #49) + **uncommitted local changes from this session**: 3 config files (`.claude/rules/mcp-stack.md`, `.claude/agents/ba.md`, `.claude/settings.json`) + 3 docs (HANDOFF, WORKLOG, todo). Awaiting branch/PR on the host.
- Audit 2026-07-07 (`docs/AUDIT-2026-07-07.md`, N1–N5): quick wins A/B1/B2/C **merged** (PR #48); **D+E applied this session** (uncommitted). Remaining queue: F×6 → G → H (+ inherited L2).
- ⚠️ `.git` was corrupt (config/HEAD NUL-padded, index broken tail — mount write quirk) → **repaired in-session**, `git fsck` clean. Git WRITE ops (branch/commit/push) — host only.
- Contract untouched (no `spec/`/`openapi.yml` diff) → no semver movement. Latest tag: **v0.4.0**.
- Counts: 12 agents · 23 commands · 21 rules · 6 skills · 3 workflows. Plugin baseline: superpowers + github + context7.

## What was done this session
- **D:** `mcp-stack.md` — "Layer boundaries — superpowers plugin vs repo rules": expected-active vs inert plugin skills, devil↔brainstorming phase split, invariants stay in repo rules/agent bodies.
- **E:** `ba` → `Read, Glob, Grep` (read-only; inline note — orchestrator appends its plan-log line); SubagentStop matcher += `happy-path-author`; `template-sync` tools verified (no change needed).
- **Repair:** `.git/config`, `.git/HEAD`, `.git/index` NUL-corruption fixed (`tr -d '\0'`, index rebuilt from HEAD).

## What's next
1. **HOST:** `git checkout -b chore/audit-queue-d-e` → `git add .claude/rules/mcp-stack.md .claude/agents/ba.md .claude/settings.json docs/HANDOFF.md docs/WORKLOG.md docs/todo.md` → commit (uk body) → push → PR.
2. **F×6 (P2):** rules↔skills dedup, one PR per pair (typespec, spectral, prism, oasdiff, versioning, openapi-design) — rule = norms, skill = recipes (AUDIT §4).
3. **G (P2):** family-core plugin — ADR 0011 → `claude-family-marketplace` repo → v0.1.0 pilot here → roll out to claude-django / claude-react-mui (AUDIT §6).
4. **H (P4) decisions:** Spectral `warn`→`error`; `npm run validate` ⊇ `check:endpoints`. Inherited: L2 `UserPromptExpansion` on live CLI; AUDIT-file tracking.

## Open questions / risks
- family-core: exact core/domain boundary for `ba`/`devil`/`brief-synthesizer` (domain tails) — to settle in ADR 0011.
- Plugin-hook behavior parity Cowork vs CLI — test during family-core Phase 1 pilot.
- `living-plan.md` wording ("each agent appends via Edit") vs read-only `ba` (orchestrator appends) and Bash-appending reviewers — reconcile wording within F if that pair is touched.
- Mount write quirk now proven to hit even `.git/*` — keep ALL git write ops on host; sandbox is for file edits + read-only git.
