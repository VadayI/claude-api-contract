---
model: sonnet
description: "[claude-api-contract] Project-kickoff preflight — hard gate verifying brief/toolchain/access before contract work."
---

Run the **project kickoff preflight** — a hard gate verifying agents have the inputs and access to build the contract correctly. Spec: `@.claude/rules/preflight.md`.

## Log
```bash
node scripts/log-cmd.mjs /preflight "$ARGUMENTS"
```

## Contract
If a CRITICAL item is missing, STOP — do not start the feature pipeline. Report a checklist; fix access or ask the user. Never print secrets.

## Input
Optional `$ARGUMENTS`: a scope — `brief`, `toolchain`, `access`. Default: all.

## Steps
0. **Runtime gate (hard STOP).** Read `.claude/memory/env-detect.json`. Missing → `NO_ENV_DETECT` (see `/doctor`). `platform_supported == false` → `UNSUPPORTED_PLATFORM`.
1. **Brief** — `PROJECT.md`/`docs/**` describe the API purpose and resources, record a maturity stage (`demo / prototype / PoC / MVP / production`), and contain a completed Definition of Done (§7 — standard gates + project-specific criteria, not blank). Missing stage or missing/blank DoD → dispatch `ba` to surface these for explicit team agreement; do NOT invent resources or assume a stage (@.claude/rules/project-maturity.md).
2. **Toolchain** — node/npm + TypeSpec/Spectral/Prism installed (`bash scripts/install.sh`), `oasdiff` on PATH.
3. **Access** — `gh auth status` ok, repo reachable, context7 reachable.
4. Report a CRITICAL/OK checklist. All-green → proceed to the first resource via the pipeline.
