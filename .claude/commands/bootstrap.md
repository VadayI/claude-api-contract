---
model: sonnet
description: "[claude-api-contract] Bootstrap a contract project from this template (Mode A fresh scaffold / Mode B resume)."
---

Bootstrap a `claude-api-contract` project from this template config. You orchestrate; delegate implementation steps to agents (`devops`-style tasks run via Bash). Two modes:

- **A. Fresh** — `.claude/`, `CLAUDE.md`, `templates/` copied (Quick start done) but no `.git/` and no `spec/`.
- **B. Resume** — existing git+GitHub repo with a partial scaffold.

## Log
```bash
node scripts/log-cmd.mjs /bootstrap "$ARGUMENTS"
```

## Input
Optional `$ARGUMENTS`: `--dry-run` and/or a project slug. If slug empty, ask via `AskUserQuestion`.

## Mode detection (FIRST, before prompts)
```bash
node -e '
const fs=require("fs"); const cp=require("child_process");
if(!fs.existsSync(".claude/memory/env-detect.json")){console.log("NO_ENV_DETECT");process.exit(0)}
const hasGit=fs.existsSync(".git");
const hasSpec=fs.existsSync("spec/main.tsp");
let hasRemote=false; try{hasRemote=cp.execSync("gh repo view --json nameWithOwner",{stdio:["pipe","pipe","pipe"]}).length>0}catch{}
console.log(!hasSpec?"MODE_A":(hasGit&&hasRemote?"MODE_B":"MODE_AMBIGUOUS"));
'
```
- `MODE_A` → fresh scaffold (no `spec/` yet). GitHub repo is created by you beforehand; Mode A links to it.
- `MODE_B` → resume.
- `MODE_AMBIGUOUS` → STOP, ask via `AskUserQuestion`. If `spec/main.tsp` exists but no `.git/` → STOP (`SPEC_WITHOUT_GIT`).
- `NO_ENV_DETECT` → STOP (runtime unverified; see `/doctor`). Never fabricate the file.

## Hard preflight (refuse if any blocker)
Read `env-detect.json`: `platform_supported`, `node_supported`, `gh.authenticated`. Supported only in Claude Code CLI on Linux/macOS/WSL2.

## Mode A flow
1. `bash scripts/install.sh` (npm deps + oasdiff check).
2. Scaffold the contract skeleton from `templates/`: `.spectral.yaml`, `spec/main.tsp` + `spec/models/` (envelopes), `spec/auth.tsp` (D1+D5 endpoints), a sample resource, `examples/`, `docs/api/INDEX.md`, `.github/workflows/contract-ci.yml`, `CHANGELOG.md`.
3. `npm run api:compile && npm run api:bundle` → first `openapi.yml`.
4. `npm run validate` green; `npm run mock` smoke via `mock-validator`.
5. `git init`, link the GitHub remote, first PR (never push to `main`).

## Mode B flow
PR the missing pieces only; re-run `npm run validate`; reconcile `endpoints.json` with `openapi.yml`.

## After
Suggest `/synthesize-brief` (if no `PROJECT.md`) → `/preflight` → first resource via the pipeline.
