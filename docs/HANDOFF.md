# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-06-14)
- Branch: `main` — HEAD = `37c477e` (PR #38, contract-policy gate)
- Open branch (pushed, **not merged**): `chore/codeowners` `b94ac8c` (PR #39 — CODEOWNERS + personalize owner-token). Merge on host.
- **Working tree carries prepared, tested-but-uncommitted changes** for audit items 4.1–4.7 (see "Prepared this session" + PR plan below).
- Contract: `openapi.yml` absent on main (Class B — local working copy only) · `spec/` absent on main · latest tag: **`v0.4.0`**
- Template (on main): **12 agents** · **23 commands** · **20 rules** · 6 skills · 2 workflows. After the prepared PRs merge: **+1 workflow** (`scheduled-audit`) and new `scripts/policy/` + `scripts/check_endpoints_registry.mjs`.

## What was done this session (session 9 — template self-audit follow-ups)
> Source: `docs/AUDIT-2026-06-14-followups.md`. Merged PR numbers confirmed against `git log main`.
- **Merged:** #34 `1bd3276` (fail-closed spec-guard + pin oasdiff), #35 `efb0c16` (version coherence v0.4.0 + personalize reset), #36 `b51355b` (PR template), #37 `80e0629` (changelog ADR 0007), #38 `37c477e` (contract-policy gate).
- **Open:** #39 `chore/codeowners` — CODEOWNERS + personalize owner-token (not merged).
- **Prepared (uncommitted, working tree)** — audit items 4.1–4.7, each verified locally (YAML/JSON parse, `bash -n`, synthetic-stdin tests, live Prism smoke). See PR plan.

## Prepared this session — PR plan (commit on host; ≤3 files/PR where practical)
> Delivery: chosen to land as **one consolidated PR** `feat/session-9-audit-followups` (2026-06-14); the list below records the logical grouping. `chore/codeowners` (#39) is merged separately.
1. **docs wrap-up (session 9)** — `docs/WORKLOG.md`, `docs/HANDOFF.md`. Branch `docs/session-9-wrap-up`.
2. **4.2 endpoints-registry gate** — `scripts/check_endpoints_registry.mjs`, `package.json` (`check:endpoints`), `.github/workflows/contract-ci.yml` (supplementary Verify step — NOT a 6th canonical gate; "5 CI gates" wording preserved). Branch `feat/endpoints-registry-gate`.
3. **4.1a policy-hook scripts** — `scripts/policy/block_protected_edits.sh` (PreToolUse, hard-block direct `openapi.yml` edit), `scripts/policy/check_command_gate.sh` (UserPromptExpansion; /release+/ship BLOCK, /create-pr ADVISORY), `scripts/policy/check_plan_execution_log.sh` (SubagentStop, ADVISORY). Branch `feat/policy-hook-scripts`.
4. **4.1b policy-hook wiring** — `.claude/settings.json` (PreToolUse + UserPromptExpansion + SubagentStop). Branch `feat/policy-hook-wiring` (after 4.1a). NB: split by layer (scripts vs wiring) to avoid `settings.json` overlap and keep ≤3 files; the followups' by-hook split also works.
5. **4.6 README-freshness gate** — `.github/workflows/contract-policy.yml` (blocking: README status == package.json version; advisory: vs latest tag). Branch `feat/readme-freshness-gate`.
6. **4.3 ADR 0008** — `docs/decisions/0008-breaking-change-tooling-cli-not-action.md` (decline oasdiff-action: PR comments are Pro/paid; keep pinned CLI). Branch `docs/adr-0008-oasdiff`.
7. **4.4 mock derived-compat** — `scripts/check_mock.sh` (generic readiness + reference/derived auto-detect; template behaviour unchanged, derived no longer false-fails). Branch `fix/mock-smoke-derived-compat`.
8. **4.5 Husky + commitlint (optional)** — `.husky/{pre-commit,commit-msg,pre-push}`, `commitlint.config.mjs`. devDeps NOT added in working tree (commitlint@21 needs Node >=22.12; pin @19). On host: `npm i -D husky@^9 @commitlint/cli@^19 @commitlint/config-conventional@^19`, add `"prepare":"husky"`, run `npm run prepare`. Branch `feat/husky-commitlint`.
9. **4.7 scheduled-audit** — `.github/workflows/scheduled-audit.yml` (weekly STUB/TODO inventory + version-drift + gate-health). Branch `feat/scheduled-audit`.
10. **docs: README refresh** — `README.md` (guardrails landscape: process gates + endpoints check + local Claude Code hooks; optional Husky section; refreshed Status line). Merge **after** the feature PRs it documents. Branch `docs/readme-refresh`.

## Open questions / risks
- **CLEANUP (host):** a misplaced empty `WORKLOG.md` exists at the **repo root** (a path slip; sandbox `rm` is blocked). Delete it on host: `rm WORKLOG.md`. The real file is `docs/WORKLOG.md`. Do NOT `git add` the root one.
- **`.env.example`** shows a local uncommitted edit (pre-existing, dev-only) — not part of these PRs; leave as the user decided.
- **Hook event/matcher caveat (4.1):** `PreToolUse`/`UserPromptExpansion`/`SubagentStop` + their semantics (tool_name / command_name / exit-2-blocks) confirmed via official docs (2× WebSearch + followups first-source). `SubagentStop` matcher-by-agent-type is the least-certain bit; the script self-limits regardless, so a matcher mismatch only widens advisory scope, never blocks.
- `GITHUB_PERSONAL_ACCESS_TOKEN` needs `write:packages` for `docker push` to `ghcr.io` — verify before `/ship-contract`.

## Environment notes
- WSL2 Ubuntu, Node v24.16.0 (host) / v22 (sandbox), oasdiff 1.18.4 on PATH (host only — absent in the Cowork sandbox, so `npm run breaking` "FAIL: oasdiff not installed" in-sandbox is expected, not a real failure), Docker available.
- Repo at `/mnt/d/Dev/My/claude-api-contract` (Windows drive via WSL2).
- **Cowork sandbox quirks:** `Edit`/`Write` truncate on this mount — write via `bash` heredoc / `python3` in-place; `rm`/`mv`/`sed -i` blocked (`Operation not permitted`); `gh` absent (git ops on host); sandbox `git` shows a phantom empty `chore` branch — read real history with `git log main`. **Lesson:** write to full paths (`docs/WORKLOG.md`, not `WORKLOG.md`) — a relative slip silently creates a root-level file.
- `.env.example` has local edits (not committed — dev-only; user decision).
