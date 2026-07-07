# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-07-07, session 14 end — H toggles + ADR 0011 draft, via Cowork)
- Branch: `main` == `origin/main` (PR #51 F×6 dedup merged) + **uncommitted local changes from this session**: H toggles (`.spectral.yaml`, `package.json`, 9 mention-files) + NEW `docs/decisions/0011-family-core-plugin.md` (proposed) + 3 docs. Awaiting branch/PR on the host — suggested: one branch, two commits (chore(gates) H; docs(adr) 0011 + housekeeping).
- Audit 2026-07-07 queue: **A–F + H done**; **G Phase 0 drafted** (ADR 0011 proposed — awaiting user review). Remaining: G Phase 1+ (marketplace repo + pilot) after ADR acceptance; inherited L2; AUDIT-file tracking decision.
- Gates tightened: Spectral snake_case + schema-description now **error** (demo contract pre-verified clean); `npm run validate` now includes `check:endpoints` (was pre-push/CI only).
- ⚠️ Sandbox git unreliable on this mount (stale cache after host ops) — ALL git on host; sandbox = file edits + reads.
- Contract untouched → no semver movement. Latest tag: **v0.4.0**. Counts: 12 agents · 23 commands · 21 rules · 6 skills · 3 workflows.

## What was done this session
- **H1:** two Spectral rules warn→error + staging comments; skill example synced.
- **H2:** `validate` ⊇ `check:endpoints`; 9 composition mentions updated.
- **G Phase 0:** ADR 0011 (proposed) — layering rule, plugin constraints, self-contained skills, fallback, Phases 0–3, non-goals.

## What's next
1. **HOST:** branch `chore/audit-h-adr-0011` → commit 1 (chore(gates)): `.spectral.yaml` `package.json` `.claude/rules/{git-operations,node-commands,verification,deploy}.md` `.claude/skills/spectral-lint/SKILL.md` `.claude/skills/contract-versioning/SKILL.md` `.claude/commands/validate-contract.md` `scripts/check_ready.sh` `scripts/setup-windows.md`; commit 2 (docs(adr)): `docs/decisions/0011-family-core-plugin.md` `docs/{HANDOFF,WORKLOG,todo}.md` → push → PR. (`npm run validate` now ends with the endpoints gate — pre-commit hook covers it.)
2. **Review ADR 0011** — accept / amend (boundary criterion, Phase 1 scope). On accept: flip Status → accepted.
3. **G Phase 1:** create `claude-family-marketplace` (GitHub) → `family-core v0.1.0` (auditor, template-sync, /audit, /handoff, /wrap-up, /set-language, log-cmd.mjs) → pilot here; exit criteria: Cowork↔CLI hook parity + a week of use; skills rewritten self-contained before the move.
4. Inherited: **L2** confirm `UserPromptExpansion` on the live CLI; decide whether `docs/AUDIT-*.md` stay untracked.

## Open questions / risks
- ADR 0011 acceptance + Phase 1 scope confirmation — user review pending.
- `ba`/`devil`/`brief-synthesizer` domain tails — per-agent split in Phase 2 (criterion fixed in ADR).
- Plugin-hook parity Cowork vs CLI — Phase 1 exit criterion.
- `living-plan.md` wording ("each agent appends via Edit") vs read-only `ba` — fold into any nearby rules PR.
