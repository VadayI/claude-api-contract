# TODO

> Queue after the 2026-07-07 audit (details: `docs/AUDIT-2026-07-07.md` §7).

- [x] **D (P3)** `mcp-stack.md`: note on superpowers layers — done 2026-07-07 s12 ("Layer boundaries" section)
- [x] **E (P3)** agent tails from the 06-16 audit — done 2026-07-07 s12: `ba` -> read-only tools; SubagentStop matcher += `happy-path-author`; `template-sync` tools verified (justified, no change)
- [x] **F (P2)** rules<->skills content dedup — done 2026-07-07 s13 (single PR by user decision): typespec, spectral, prism, oasdiff, versioning, openapi-design (rule = norms, skill = recipes)
- [ ] **G (P2)** family-core plugin — Phase 0+1 done 2026-07-07 (ADR 0011 accepted; `claude-family-marketplace` live + `v0.1.0` tagged; pilot enabled here, 6 local duplicates removed): next — a week of pilot use (exit: plugin commands run in CLI, bare-name agent dispatch works) -> Phase 2 (ba/devil/brief-synthesizer) -> Phase 3 (claude-django / claude-react-mui)
- [x] **H (P4)** — decided & applied 2026-07-07 s14: Spectral `warn`->`error` (snake_case, schema-description; staging via `recommended:false` stays); `npm run validate` now includes `check:endpoints`
- [ ] Inherited: **L2** confirm `UserPromptExpansion` fires on the live CLI; decide whether `docs/AUDIT-*.md` stay untracked
