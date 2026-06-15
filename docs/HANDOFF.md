# HANDOFF — where we are / what's next

> Rolling snapshot. Read FIRST when joining the project; updated LAST at end of session (`/handoff` or `/wrap-up`).

## Where we are (2026-06-15, end of session 10 — template self-audit + fixes, via Cowork)
- Branch: `chore/audit-2026-06-14-doc-drift` — 2 commits ahead of `origin/main` (`4f8e8dc`): `f2178f0` (doc-drift + oasdiff pin) + `2bab66e` (session-10 audit fixes). **`2bab66e` not yet pushed** (ahead 1 of its remote); **not PR'd**.
- Uncommitted on top of `2bab66e`: `package.json` + `package-lock.json` (commitlint re-pin v21→v19 — see What's next #1).
- Contract: `openapi.yml`/`spec/`/`examples/` present locally but **untracked** on this branch (Class B) · latest tag: **`v0.4.0`**.
- Gates (run this session): `npm run validate` green · `mock:smoke` 11/11 · `check:endpoints` 10/10 · `breaking` needs `oasdiff` (host only, present there).
- Template counts unchanged: **12 agents** · **23 commands** · **20 rules** · 6 skills · 3 workflows.

## What was done this session (session 10)
> Full template audit → `docs/AUDIT-2026-06-14-template.md` (untracked; `personalize.sh` Tier 2 strips `docs/AUDIT-*.md` on derive). 1 HIGH · 4 MEDIUM · 6 low/verify.
- **Committed in `2bab66e` (21 files):**
  - **H1** husky+commitlint wired: `prepare: husky` + devDeps; `core.hooksPath=.husky/_`; commitlint tested (good passes / bad fails).
  - **M1** activated skills `oasdiff-breaking` (breaking-change-analyst) + `contract-versioning` (versioning.md).
  - **M2** HANDOFF reconciled: removed dead `/HANDOFF.md` from `.gitignore`; aligned `wrap-up.md` to CLAUDE.md (tracked).
  - **M3** clarified ADR reset list in `clean.sh` + `node-commands.md` (0002–0004 demo-contract; 0005–0008 infra, kept like 0001).
  - **M4/L1** removed `SendMessage` + `tools` array → comma-separated string across all 12 agents.
  - **L4** fixed import-block insert pointer (→ `project-maturity.md`) in CLAUDE.md + set-language.md.
- **Post-commit correction (uncommitted):** commitlint re-pinned **v21 → v19** — npm default pulled v21 (`engines.node >=22.12`, breaks the `>=20.19` floor); corrected per `docs/lessons.md`. Awaits commit.

## What's next
1. **Commit the commitlint re-pin** (`package.json` + `package-lock.json`) — amend `2bab66e` or add a fixup, on the **host shell** (git writes on `/mnt` fail from the Cowork sandbox).
2. **Push the branch + open PR → `main`** (host; `gh` absent in sandbox). The PR carries `f2178f0` + `2bab66e`. Never push `main`.
3. **Decide the low/verify items** (none blocking): **L2** confirm the `UserPromptExpansion` hook actually fires on your CLI; **L3** drop undocumented `statusMessage` (cosmetic); **L5** `SubagentStop` matcher (harmless if ignored); **L6** promote spectral snake_case/description `warn`→`error` (a tightening — affects derived projects).
4. **Decide whether to track** `docs/AUDIT-2026-06-14-template.md` (+ the older `-followups.md`) — both untracked; Tier 2 strips them on derive anyway.
5. **Next contract work:** new resource → `ba` → full pipeline → `/release` with a semantic bump.

## Open questions / risks
- **commitlint pin ↔ Node floor:** keep commitlint at **v19** while `engines.node` is `>=20.19`. Raising the floor to `>=22.12` would re-enable v21 (deliberate decision + ADR if taken).
- **L2/L5 hook details unverified in the sandbox** — confirm on the host CLI; the policy commands also self-gate in-body, so a dead hook is defense-in-depth lost, not the only guard.
- Two `docs/AUDIT-*.md` + Class B (`spec/`, `examples/`, `openapi.yml`, ADR 0002–0004, `.claude/memory/`) are untracked by design.

## Environment notes
- WSL2 Ubuntu, Node v24.16.0 (host), oasdiff 1.18.4 on PATH, Docker available. Repo at `/mnt/d/Dev/My/claude-api-contract`.
- **Cowork sandbox quirks** (if editing via Cowork again): `Edit`/`Write` truncate on this mount — write via `bash` heredoc / `node` in-place; `rm`/`mv`/`sed -i` and **all git WRITES** (`add`/`commit`) fail with `Operation not permitted` on `/mnt` — **stage/commit/push on the host shell**; `gh` absent in sandbox. SessionStart hook clears the stale empty `.git/index.lock`. **Write to full paths** (`docs/WORKLOG.md`, not `WORKLOG.md`).
