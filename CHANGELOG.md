# Changelog

All notable contract changes are documented here. Format derived from `oasdiff changelog`.
Breaking changes are flagged and require a MAJOR version bump.

## [Unreleased]
- <pending changes>

## [v0.4.0] — 2026-06-09

**Contract:** no changes vs v0.3.0 (spec/ and openapi.yml unchanged — no pin bump needed for consumers).

**Template additions (minor):**

- `Dockerfile` + `.dockerignore` — node:22-alpine image, prism-cli@5.12.0, non-root USER, static mock entrypoint (PR #23).
- `scripts/check_ready.sh` — readiness gate: compile + drift + lint + examples + Prism smoke + breaking + artifact/auth checks (PR #23).
- `scripts/deploy-mock.sh` — build image, push to `ghcr.io/<owner>/<repo>-mock:<tag>`, print VPS `docker run` command; `--dry-run` flag (PR #23).
- `package.json`: `ready` + `deploy:mock` npm scripts (PR #23).
- ADR 0006: deploy-mock-to-vps decision (PR #23).
- `.claude/commands/check-readme.md` — new `/check-readme` slash command; `docs-writer` agent scope extended to README freshness (PR #24).
- `README.md` — `## For consumers` section added; status updated to v0.3.0; Quick start updated (PR #24).
- `.claude/rules/deploy.md` — deploy model rule (Prism mock → Docker → VPS) (PR #25).
- `.claude/commands/ship-contract.md` — new `/ship-contract <IP> <PORT>` slash command (PR #25).

## [v0.3.0] — 2026-06-08

**Contract:** no changes vs v0.2.0 (same wire shape — no pin bump needed for consumers).

**Template additions (minor):**

- `/personalize` command + `scripts/personalize.sh` — 3-tier token rewrite (owner/repo URLs, package.json, `.claude/` frontmatter) + optional prose pass (PR #18).
- `project-maturity.md` rule — 5-stage taxonomy (demo/prototype/PoC/MVP/production), process matrix, CI-gate invariants always ON (PR #20).
- `templates/PROJECT.md` §7 Definition of Done — standard checklist + project-specific criteria; `ba` / `brief-synthesizer` must surface before work starts.
- Preflight gate: 2 new CRITICAL rows (maturity stage + DoD).
- ADR 0005: project maturity doctrine.
