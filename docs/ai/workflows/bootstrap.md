# Bootstrap — portable contract procedure

Read AGENTS.md. Coordinators delegate; an assigned worker executes within its scope. Runtime tool names are examples; preserve all substantive steps using available capabilities.

Bootstrap a `claude-api-contract` project from this template config. An explicitly coordinating session delegates implementation steps; an assigned worker implements the requested scaffold within its role. Scaffolding/setup tasks use their documented shell. Two modes:

- **A. Fresh** — `.claude/`, `CLAUDE.md`, `templates/` copied (Quick start done) but no `.git/` and no `spec/`.
- **B. Resume** — existing git+GitHub repo with a partial scaffold.

## Log
```bash
# Optional legacy log: pass actual arguments as separate argv; never evaluate them.
```

## Input
Optional `<procedure arguments>`: `--dry-run` and/or a project slug. If slug empty, ask via `the current runtime's user-input capability`.

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
- `MODE_AMBIGUOUS` → STOP, ask via `the current runtime's user-input capability`. If `spec/main.tsp` exists but no `.git/` → STOP (`SPEC_WITHOUT_GIT`).
- `NO_ENV_DETECT` → STOP (runtime unverified; see `/doctor`). Never fabricate the file.

## Hard preflight (refuse if any blocker)
Read `env-detect.json`: `platform_tier`, `node_supported`, `gh.authenticated`. Hard STOP only on `platform_tier == "unsupported"` or `node_supported == false`. `best-effort` (native Windows + Git Bash) proceeds with a warning — recommend WSL2 for sandbox/Docker parity. Tested path: Linux/macOS/WSL2.

## Mode A flow
1. `bash scripts/install.sh` (npm deps + oasdiff check).
2. **Personalize identity** — rewrite all template identity strings before the first commit:
   - Extract slug from `<procedure arguments>` if provided (e.g. `/bootstrap my-api` → slug = `my-api`); otherwise ask via `the current runtime's user-input capability` (header `Project slug`).
   - Try `gh repo view --json nameWithOwner` to resolve the GitHub owner. If unavailable, also ask.
   - Run `bash scripts/personalize.sh --name {slug} --owner {owner} --dry-run`.
   - Dispatch `docs-writer` for the prose pass: README self-description, project documentation and overrides (preserve AGENTS/CLAUDE generated entry points), `contract-first.md` diagram (see `/personalize` step 3 for full spec).
   - Apply reviewed identity changes only to project-owned package/README/CODEOWNERS and project overrides. Do not rewrite generated adapters, canonical template rules, core provenance or remove audit notes; full personalization migration remains P12.
3. Author the contract skeleton via `tsp-author`. These files exist in the scaffold already — **no copying needed**: `.spectral.yaml`, `docs/api/INDEX.md`, `CHANGELOG.md`. Active workflows are intentionally absent from a fresh seed until CI choice/materialization (P06); existing project workflows remain untouched. The following must be authored fresh:
   - `spec/main.tsp` — `@service`, `@server`, global `bearerAuth` security scheme, imports of the other spec files.
   - `spec/models/` — `ListResponse<T>`, `ErrorDetail`, `ValidationErrors`, `Retry-After` header model (docs/ai/rules/api-envelope.md).
   - `spec/auth.tsp` — all user-flow + S2S auth endpoints (docs/ai/rules/auth-contract.md).
   - `examples/auth/` — representative request/response examples for the auth endpoints.
   The first domain resource is designed later via the full pipeline (`ba → api-architect → tsp-author`).
4. `npm run api:compile && npm run api:bundle` → first `openapi.yml`.
5. `npm run validate` green; `npm run mock` smoke via `mock-validator`.
6. Before any first push, ask for CI execution mode: `local` (recommended) or `github`. A non-interactive bootstrap without an explicit answer stops. Run `python scripts/ai/ci_mode.py --target . --mode local --apply` or `--mode github`. The preview without `--apply` reports exact writes and conflicts. The choice is saved in project-owned `docs/project-state/project.json`; the active `contract-checks.yml` and `contract-audit.yml` are created from inert templates with a checked ownership receipt. Local mode has only manual `workflow_dispatch` events and installs no local schedule; GitHub mode adds pull request, push, merge group and scheduled events. Both use `scripts/ai/runner.py` with `templates/ai/checks/contract.json`; unavailable exact base or prerequisite fails honestly. Preserve foreign workflows and existing branch rules. Do not create a remote from the GitHub template before this local step, since the upstream repository's active maintenance workflows are copied by that route. Prepare an explicit initial file list, review the active workflows and choice, then follow the PR policy. Never push directly to main.

## Mode B flow
PR the missing pieces only; re-run `npm run validate`; reconcile `endpoints.json` with `openapi.yml`.

## After
Suggest `/synthesize-brief` (if no `PROJECT.md`) → `/preflight` → first resource via the pipeline.
