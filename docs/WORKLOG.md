# WORKLOG

> Append-only chronicle of what changed each session (newest first).

## 2026-06-08 (session 3)
- feat: project maturity stage + Definition of Done (#20) — CI: green — tag: none
  - New global rule `.claude/rules/project-maturity.md`: 5-stage taxonomy (demo/prototype/PoC/MVP/production/other),
    process matrix (pipeline depth · `devil` · review rigour · example completeness per stage),
    invariant block (5 CI gates + `@doc` always ON, never relaxed by stage)
  - ADR `docs/decisions/0005-project-maturity-stage.md`: guidance-only, no gate skipping
  - `templates/PROJECT.md`: new `**Maturity stage:**` header field + §7 Definition of Done
    (standard gates checklist + project-specific criteria — never left as placeholder)
  - `.claude/rules/preflight.md`: 2 new CRITICAL build-input rows (stage + DoD)
  - `CLAUDE.md`: import + dispatcher note (read stage before dispatch, ask if missing)
  - Agents updated: `ba`, `brief-synthesizer`, `api-architect`, `contract-reviewer`,
    `mock-validator`, `devil` — all maturity-aware; `devil` now has "When to run" section
  - Commands updated: `/preflight`, `/synthesize-brief`

## 2026-06-08 (session 2)
- feat: `/personalize` command + `scripts/personalize.sh` (#18) — CI: green (18s) — tag: none
  - Tier 1: `VadayI/claude-api-contract` URLs, `package.json` name/desc, `README.md` H1
  - Tier 2: `package.json` version → `0.0.0`, delete `docs/AUDIT-*.md`
  - Tier 3: `[claude-api-contract]` → `[{slug}]` in all `.claude/` frontmatter (~40 files)
  - Guard: refuses without `--force` on `VadayI/claude-api-contract` origin
  - `/bootstrap` Mode A: new step 2 personalizes identity before `spec/` authoring + `git init`
  - `npm run personalize` script added; README Step 7 + Quick start updated

## 2026-06-08 (session 1)
- docs: explicit step-by-step installation guide in README (#15) — CI: green — tag: none
  - Added Steps 0–7 (WSL2 → folder → clone → toolchain → deps → secrets → claude)
- fix: git clone destination with trailing `.` + Uninstall section (#16) — CI: green — tag: none
- fix: Step 3 — disconnect template `.git` + link own repo with `gh repo create` (#17) — CI: green — tag: none
- feat: `sandbox.sh` (clone → temp dir + install) + `clean.sh` (Class A/B removal) (#14) — CI: green — tag: none
- fix: CI spec/-guard — gates skip when `spec/` absent; bootstrap Mode A step 2 via `tsp-author` (#13) — CI: green — tag: none

## <YYYY-MM-DD>
- <change> — gates: <result> — tag: <if any>
