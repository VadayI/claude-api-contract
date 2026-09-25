# Project-kickoff preflight (hard gate)

Before any contract work on a new project, verify the inputs and access exist. Spec consumed by `/preflight` and the `ba` kickoff gate.

## Runtime gate (FIRST, hard STOP)

Read `.ai-runtime/env-detect.json` (produced by an explicit `node scripts/detect-env.mjs` run or the SessionStart hook `scripts/session-start.sh`; the shared detector report `.ai-runtime/environment.json` is refreshed alongside).

- **Missing** → `NO_ENV_DETECT`: STOP. The runtime is unverified. Run `node scripts/detect-env.mjs` once manually; if that fails, install Node 20.19+. Never hand-write the file.
- **`platform_tier == "unsupported"`** → `UNSUPPORTED_PLATFORM`: hard STOP. Native Windows without a POSIX `bash`/`git` on PATH, or a runner we cannot execute the bash gates on. Install Git for Windows (Git Bash) or WSL2 Ubuntu, then relaunch.
- **`platform_tier == "best-effort"`** (native Windows + Git Bash) → WARN, do not STOP. Gate scripts run through Git Bash; there is **no OS-level Bash-tool sandbox** (`sandbox_available == false`) and this path is less tested than Linux/macOS/WSL2. Recommend WSL2 for sandbox/Docker parity. The legacy boolean `platform_supported` stays `true` here.
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
| Documentation access | context7 when connected, otherwise official documentation | Report unavailable reference access for the affected task |

If a CRITICAL item is missing, STOP — do not start the feature pipeline. Report a checklist; fix access or ask the user. Never print secret values.

## P04 runtime transition

Python 3.13+ stdlib tooling and both Claude/Codex launchers are delivered locally. Optional plugins/MCP are not prerequisites for local procedures: gh/Git provide repository operations and official documentation is the library-reference fallback. Do not grant trust or install plugins automatically. Run detector explicitly and check current tools; stale legacy JSON is not operational evidence. The shared detector and exact-candidate runner (`scripts/ai/detector.py`, `scripts/ai/runner.py`) and the CI choice (`scripts/ai/ci_mode.py`) are delivered; the stack `detect-env` probe writes `.ai-runtime/env-detect.json` beside the shared detector report and is not gate evidence by itself. Native Windows uses PowerShell orchestration and explicit C:/Program Files/Git/bin/bash.exe for Bash commands; platform labels above do not establish sandbox isolation.
