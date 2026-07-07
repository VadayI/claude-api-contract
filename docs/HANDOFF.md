# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-07-07, end of session — duplication/plugin audit + quick wins, via Cowork)
- Branch: `main` == `origin/main` (`bb1a804`, PR #47) + **uncommitted local changes from this session**: 15 tracked files (CLAUDE.md, 13 rules, settings.json) + 4 docs (AUDIT-2026-07-07, HANDOFF, WORKLOG, todo). Awaiting branch/PR on the host.
- ⚠️ Stale `.git/index.lock` left by the sandbox — on the host run `rm -f .git/index.lock` BEFORE any git command.
- Class B artifacts untracked as designed (`spec/`, `examples/`, `openapi.yml`, `.claude/memory/`, ADR 0002–0004, `docs/AUDIT-*.md`).
- Contract untouched this session (no `spec/`/`openapi.yml` diff) → no semver movement. Latest tag: **v0.4.0**.
- Counts: **12 agents · 23 commands · 21 rules · 6 skills · 3 workflows**. Plugin baseline now: **superpowers + github + context7** (engineering removed).

## What was done this session
- **`docs/AUDIT-2026-07-07.md`** — delta audit: N1 global-context leak via inline `@`-imports (doc-verified; the "11 global + 10 scoped" design was silently defeated — ~1050 lines loaded instead of ~350); N2 plugin duplication (engineering out; up-to-3× GitHub MCP dedup); N3 six rule↔skill content-overlap pairs (plan); N4 internal process overlaps; N5 family-core plugin design + migration plan; prioritized PR plan A–H.
- **Applied (B1/B2/C):** CLAUDE.md prose `@`-mentions → backticks (13; import block intact); 27 cross-refs in 13 rules → backticks; `settings.json` minus `engineering@knowledge-work-plugins`; local `settings.local.json` minus `enabledMcpjsonServers`.
- **Verified:** both settings JSON-parse; zero non-backticked `@.claude/rules` refs outside the import block; diffs reviewed against `/tmp/audit-bak`.

## What's next
1. **HOST:** `rm -f .git/index.lock` → `git checkout -b chore/audit-2026-07-07` → `git add CLAUDE.md .claude/rules .claude/settings.json docs/AUDIT-2026-07-07.md docs/HANDOFF.md docs/WORKLOG.md docs/todo.md` → commit (uk body, per report §7) → push → PR. One PR is fine (mechanical, homogeneous); split B1/B2/C into three if preferred.
2. After merge: derived projects pick the fixes up via `/update-from-template`.
3. Queue (see `docs/todo.md`): D mcp-stack note → E agent tails → F×6 rules↔skills dedup → G family-core Phase 0–1 (ADR 0011 + marketplace repo) → H decisions.
4. Inherited: L2 confirm `UserPromptExpansion` on the live CLI; AUDIT-file tracking decision.

## Open questions / risks
- family-core: exact core/domain boundary for `ba`/`devil`/`brief-synthesizer` (domain tails) — to be settled in ADR 0011.
- Plugin-hook behavior parity Cowork vs CLI — test during family-core Phase 1 pilot.
- superpowers stays with some inert skills (TDD, worktrees…) — accepted consciously; note D adds the layer boundaries.
