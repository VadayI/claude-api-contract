# TODO

> Queue after the 2026-07-07 audit (details: `docs/AUDIT-2026-07-07.md` §7).

- [ ] **D (P3)** `mcp-stack.md`: note on superpowers layers (brainstorming/writing-plans vs `living-plan.md`; verification-before-completion vs `verification.md`; devil vs brainstorming phases)
- [ ] **E (P3)** agent tails from the 06-16 audit: `ba` -> read-only tools; SubagentStop matcher += `happy-path-author`; verify `template-sync` tools
- [ ] **F (P2)** rules<->skills content dedup, one PR per pair: typespec, spectral, prism, oasdiff, versioning, openapi-design (rule = norms, skill = recipes)
- [ ] **G (P2)** family-core plugin: ADR 0011 (core/domain boundary) -> `claude-family-marketplace` repo -> v0.1.0 pilot in this repo -> roll out to claude-django / claude-react-mui
- [ ] **H (P4)** decide: Spectral `warn`->`error` (snake_case, schema-description); make `npm run validate` include `check:endpoints`
- [ ] Inherited: **L2** confirm `UserPromptExpansion` fires on the live CLI; decide whether `docs/AUDIT-*.md` stay untracked
