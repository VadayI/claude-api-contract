# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-06-14, end of session 9)
- Branch: `main` — HEAD = `05ce21f` (PR #40, session-9 audit follow-ups). All session-9 work merged (#34–#40).
- Contract: `openapi.yml` absent on main (Class B — local working copy only) · `spec/` absent on main · latest tag: **`v0.4.0`**
- Gates: `contract-ci` skips cleanly on main (no `spec/`); `contract-policy` is PR-scoped. Post-merge `main` push CI expected green.
- Template (on main): **12 agents** · **23 commands** · **20 rules** · 6 skills · **3 workflows** (`contract-ci`, `contract-policy`, `scheduled-audit`) + `scripts/policy/` local-hook scripts.

## What was done this session (session 9 — template self-audit follow-ups, all merged)
> Source: `docs/AUDIT-2026-06-14-followups.md`. Full per-PR detail in `docs/WORKLOG.md`.
- **#34–#38** — fail-closed spec-guard + oasdiff pin, version coherence (v0.4.0), PR template, ADR 0007 changelog policy, contract-policy gate.
- **#39** `53ce953` — CODEOWNERS (zoned) + personalize owner-tokenization.
- **#40** `05ce21f` — consolidated 4.1–4.7 + README: endpoints-registry coverage (4.2), Claude Code policy hooks (4.1), README-freshness + version-coherence gate (4.6), ADR 0008 declining `oasdiff-action` (4.3), `check_mock.sh` reference/derived auto-detect (4.4), `scheduled-audit` workflow (4.7), opt-in husky+commitlint (4.5), docs + README refresh.
- No contract/wire change across the session; no semver bump; consumers: no action.

## What's next
1. **Confirm CI green** on `main` post-merge (Actions tab) — `contract-ci` should skip cleanly (no `spec/`).
2. **Optional — activate husky locally** (README "Local git hooks"): `npm i -D husky@^9 @commitlint/cli@^19 @commitlint/config-conventional@^19`, `npm pkg set scripts.prepare="husky"`, `npm run prepare`. (Adds devDeps + updates `package-lock.json` — its own small PR.)
3. **Optional — `/release`:** not required (no semver change this session); cut a tag only to mark the audit-hardening milestone.
4. **Deferred polish (nice-to-have):** fold `npm run check:endpoints` into `scripts/check_ready.sh`; per ADR 0008, revisit `oasdiff-action` only if it ships free PR comments.
5. **Next contract work:** when a new resource is needed → `ba` → full pipeline → `/release` with a semantic bump.

## Open questions / risks
- **Husky inert until activated:** `.husky/*` + `commitlint.config.mjs` are committed but do nothing until the devDeps + `prepare` are added on host (opt-in by design).
- **SubagentStop matcher caveat (4.1):** matcher-by-agent-type is the least-certain hook detail; the script self-limits (advisory, plan-based), so a mismatch only widens advisory scope, never blocks.
- `GITHUB_PERSONAL_ACCESS_TOKEN` needs `write:packages` for `docker push` to `ghcr.io` — verify before `/ship-contract`.

## Environment notes
- WSL2 Ubuntu, Node v24.16.0 (host), oasdiff 1.18.4 on PATH, Docker available. Repo at `/mnt/d/Dev/My/claude-api-contract`.
- **Cowork sandbox quirks** (if editing via Cowork again): `Edit`/`Write` truncate on this mount — write via `bash` heredoc / `python3` in-place; `rm`/`mv`/`sed -i` blocked (`Operation not permitted`); `gh` absent (git/PR run on host); sandbox `git` shows a phantom empty `chore` branch — read real state with `git fetch && git log origin/main`. **Write to full paths** (`docs/WORKLOG.md`, not `WORKLOG.md`) — a relative slip silently creates a root-level file.
