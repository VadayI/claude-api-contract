# Changelog

All notable contract changes are documented here. Format derived from `oasdiff changelog`.
Breaking changes are flagged and require a MAJOR version bump.

## [Unreleased]
- <pending changes>

## [v0.3.0] — 2026-06-08

**Contract:** no changes vs v0.2.0 (same wire shape — no pin bump needed for consumers).

**Template additions (minor):**

- `/personalize` command + `scripts/personalize.sh` — 3-tier token rewrite (owner/repo URLs, package.json, `.claude/` frontmatter) + optional prose pass (PR #18).
- `project-maturity.md` rule — 5-stage taxonomy (demo/prototype/PoC/MVP/production), process matrix, CI-gate invariants always ON (PR #20).
- `templates/PROJECT.md` §7 Definition of Done — standard checklist + project-specific criteria; `ba` / `brief-synthesizer` must surface before work starts.
- Preflight gate: 2 new CRITICAL rows (maturity stage + DoD).
- ADR 0005: project maturity doctrine.
