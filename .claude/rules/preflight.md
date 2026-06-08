# Project-kickoff preflight (hard gate)

Before any contract work on a new project, verify the inputs and access exist. Spec consumed by `/preflight` and the `ba` kickoff gate.

## Runtime gate (FIRST, hard STOP)

Read `.claude/memory/env-detect.json` (written ONLY by the Claude Code CLI SessionStart hook).

- **Missing** → `NO_ENV_DETECT`: STOP. The runtime is unverified — this template is supported only in **Claude Code CLI on Linux / macOS / WSL2**. Run `node scripts/detect-env.mjs` once manually; if that fails, install Node 20.19+. Never hand-write the file.
- **`platform_supported == false`** → `UNSUPPORTED_PLATFORM`: hard STOP. Install WSL2 Ubuntu and relaunch `claude` inside it.
- **`node_supported == false`** → STOP. Install Node 20.19+ (`scripts/setup-wsl.sh`).

## Build-input gate (CRITICAL items)

| Item | Check | Missing → |
|---|---|---|
| Maturity stage | `PROJECT.md` records `demo / prototype / PoC / MVP / production` | `ba` asks the user; do NOT assume a stage |
| Definition of Done | `PROJECT.md` §7 has standard gates checked off AND project-specific criteria stated (not blank) | `ba` / `brief-synthesizer` must surface this for explicit team agreement before work starts |
| Project brief | `PROJECT.md` / `docs/**` describe the API's purpose & resources | `ba` returns questions; do NOT invent resources |
| Toolchain | `node`, `npm`, TypeSpec/Spectral/Prism installed | `bash scripts/install.sh` |
| oasdiff | on PATH (breaking gate) | install per `scripts/setup-wsl.sh` |
| GitHub access | `gh auth status` ok; repo reachable | fix auth; never print secrets |
| context7 | reachable for doc lookups | `/plugins` |

If a CRITICAL item is missing, STOP — do not start the feature pipeline. Report a checklist; fix access or ask the user. Never print secret values.
