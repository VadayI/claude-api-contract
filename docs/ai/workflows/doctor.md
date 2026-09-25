# Doctor — portable contract procedure

Read AGENTS.md. Coordinators delegate; an assigned worker executes within its scope. Runtime tool names are examples; preserve all substantive steps using available capabilities.

You are the **environment configurator** for a `claude-api-contract` project. Verify the live environment against `docs/ai/rules/environment.md` and bring it up to standard. Run when connecting to the project (especially a fresh machine) or when the environment is in doubt.

## Log
```bash
# Optional legacy log: pass actual arguments as separate argv; never evaluate them.
```

## Contract
Detect → report → **propose** → fix **only after the user confirms**. NEVER auto-fix risky/irreversible things, NEVER commit or push (especially to `main`), NEVER print secret values.

## Input
Optional `<procedure arguments>`: a scope — `system`, `claude`, `project`, `git`. Default: all four.

## Steps

0. **Language:** honor the existing session choice and docs/ai/overrides/output-language.md (legacy output-language rule remains readable). Use the local set-language procedure only when needed; never rewrite CLAUDE imports.

0.5. **Runtime gate.** Read `.ai-runtime/env-detect.json` (produced by `node scripts/detect-env.mjs` or the SessionStart hook; `python scripts/ai/detector.py --repository . --write` refreshes the shared report `.ai-runtime/environment.json`). A leftover `.claude/memory/env-detect.json` is migrated by the probe itself; report a conflict between the two instead of choosing one.
   - Missing → `NO_ENV_DETECT`: run `node scripts/detect-env.mjs` once; if it fails, install Node 20.19+. Never fabricate the file.
   - `platform_tier == "unsupported"` → `UNSUPPORTED_PLATFORM` (hard STOP): native Windows without `bash`/`git`, or an unrunnable runner. Install Git for Windows (Git Bash) or WSL2, then relaunch.
   - `platform_tier == "best-effort"` → native Windows via Git Bash: proceed, but WARN that there is no OS-level sandbox (`sandbox_available == false`) and recommend WSL2 for sandbox/Docker parity.
   - `wrong_runner_suspected == true` → you launched Windows `claude.exe` from WSL2; install/launch the Linux-native CLI (`scripts/setup-wsl.sh`).
   - `node_supported == false` → install Node 20.19+.

1. **Scope 1 — system tools:** node/npm/git/gh/oasdiff present and correct versions.
2. **Scope 2 — Claude config & access:** optional plugin/MCP capability availability, with local procedures and gh/Git/official-docs fallback, `GITHUB_PERSONAL_ACCESS_TOKEN` + `CONTEXT7_API_KEY` set (never print), `gh auth status`, repo reachable.
3. **Scope 3 — project state:** `spec/`, `.spectral.yaml`, `package.json`, deps installed; `npm run validate` green. A pre-`/bootstrap` repo legitimately lacks these → report as "not set up yet" (info), not failure.
4. **Scope 4 — git hygiene:** feature branch (not `main`), branch protection, clean tree, no tracked `.env`.

## Output
A four-scope checklist with status + proposed fixes. Apply fixes only within the user's existing authorization; obtain authorization for additional external/destructive actions (remediation policy in `docs/ai/rules/environment.md`). On a fresh project, recommend `/bootstrap` next.
