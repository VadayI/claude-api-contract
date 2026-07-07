# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-07-07, session 15 end — family-core v0.1.0 pilot, via Cowork)
- Branch: `main` == `origin/main` (PR #52 merged) + **uncommitted pilot changes**: `settings.json` (+`extraKnownMarketplaces`, +`family-core@claude-family-marketplace`), 6 local duplicates DELETED (agents auditor/template-sync, commands audit/handoff/wrap-up/set-language), 5 mention-files updated, ADR 0011 -> accepted, docs. Awaiting branch/PR on the host.
- **family-core v0.1.0 live:** github.com/VadayI/claude-family-marketplace (main `462d160`, tag `v0.1.0`).
- Audit 2026-07-07 queue: **A–H done; G Phase 0+1 done.** Remaining: pilot week -> Phase 2 (ba/devil/brief-synthesizer) -> Phase 3 (claude-django / claude-react-mui). Inherited: L2; AUDIT-file tracking decision.
- Counts: 10 agents · 19 commands · 21 rules · 6 skills (local) + family-core plugin.
- ⚠️ Sandbox mount: stale-cache ghosting now proven to extend to files rewritten by host git (ADR 0011 unreadable in sandbox; todo/WORKLOG/HANDOFF served stale) — that is why docs updates went through this host-run script. ALL git ops stay on host.
- Contract untouched → still **v0.4.0**.

## What was done this session
- `claude-family-marketplace` repo + `family-core v0.1.0` (11 files; manifests verified vs official docs); content generalized & self-contained.
- Pilot wiring: settings.json marketplace+plugin; 6 duplicates deleted; mentions updated; environment.md baseline doc-drift fixed (engineering out, family-core in).
- ADR 0011 accepted (Phase 1 shipped).

## What's next
1. **HOST:** branch `feat/family-core-pilot` → `git add -u` (picks up the 6 deletions) → commit → push → PR.
2. **Pilot smoke (Claude Code CLI in this repo):** `/plugin` shows family-core; `/audit` + `/handoff` present & run; `log-cmd` appends to `.claude/memory/command-log.jsonl`; `/update-from-template` resolves `template-sync` (record: bare name or scoped `family-core:template-sync`).
3. **Pilot week:** use normally; then Phase 2 (extract generic ba/devil/brief-synthesizer into the plugin) → Phase 3 (roll out to claude-django / claude-react-mui).
4. Inherited: **L2** confirm `UserPromptExpansion` on the live CLI; decide whether `docs/AUDIT-*.md` stay untracked.

## Open questions / risks
- Bare-name dispatch of plugin agents — pilot exit criterion; scoped-name fallback documented in `/update-from-template`.
- Plugin-hook parity Cowork vs CLI — v0.1.0 ships no hooks (log-cmd is command-invoked); the parity check moves to Phase 2 (session-start hook).
- Derived projects keep their local copies until they enable the plugin — degradation by design (ADR 0011 §5); `/update-from-template` will surface the 6 deletions as template deltas.
