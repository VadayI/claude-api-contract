# TODO

> Queue after the 2026-07-07 audit (details: `docs/AUDIT-2026-07-07.md` §7).

- [x] **D (P3)** `mcp-stack.md`: note on superpowers layers — done 2026-07-07 s12 ("Layer boundaries" section)
- [x] **E (P3)** agent tails from the 06-16 audit — done 2026-07-07 s12: `ba` -> read-only tools; SubagentStop matcher += `happy-path-author`; `template-sync` tools verified (justified, no change)
- [x] **F (P2)** rules<->skills content dedup — done 2026-07-07 s13 (single PR by user decision): typespec, spectral, prism, oasdiff, versioning, openapi-design (rule = norms, skill = recipes)
- [ ] **G (P2)** family-core plugin: ADR 0011 (core/domain boundary) -> `claude-family-marketplace` repo -> v0.1.0 pilot in this repo -> roll out to claude-django / claude-react-mui
- [ ] **H (P4)** decide: Spectral `warn`->`error` (snake_case, schema-description); make `npm run validate` include `check:endpoints`
- [ ] Inherited: **L2** confirm `UserPromptExpansion` fires on the live CLI; decide whether `docs/AUDIT-*.md` stay untracked
