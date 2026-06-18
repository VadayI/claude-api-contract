# ADR 0009 — Allow best-effort native Windows via Git Bash

**Status:** accepted · **Date:** 2026-06-18 · **Supersedes:** the hard exclusion in [0001](0001-drop-windows-native-shell.md)

## Context
ADR 0001 (2026-06-06) hard-excluded native Windows and required WSL2. Two of its premises no longer hold:

- **"PowerShell/cmd cannot run the bash + Node gates."** True, but irrelevant. Since late 2025 Claude Code ships a **native Windows** build that runs the Bash tool through **Git Bash** (Git for Windows is a hard requirement). The `.sh` gate scripts and `bash scripts/*` hooks execute there — they never needed PowerShell/cmd.
- **"PATH interop mis-detects the runtime."** That is specifically the *WSL2* failure mode — already caught by `wrong_runner_suspected` in `scripts/detect-env.mjs`. On native Windows `os.platform() === 'win32'` is unambiguous, so detection is actually *more* reliable than under WSL2.

A grep of `scripts/**` confirms the bash layer is ~95% portable to Git Bash; the only hard Linux-only pieces are `scripts/setup-wsl.sh` (a convenience bootstrap) and one `python3` call in `scripts/personalize.sh` (now replaced with `node`). Full analysis: `docs/AUDIT-2026-06-18-windows-native.md`.

## Decision
Replace the binary supported/unsupported platform check with **three tiers**:

| Tier | Platforms | Gate behavior |
|---|---|---|
| `supported` | Linux / macOS / WSL2 | proceed; OS-level Bash-tool sandbox available |
| `best-effort` | native Windows **with** `bash` + `git` on PATH (Git Bash) | proceed with a **warning**; no sandbox; less tested |
| `unsupported` | native Windows **without** `bash`/`git`; any runner we cannot execute the bash gates on | hard STOP |

`scripts/detect-env.mjs` records `platform_tier` and `sandbox_available`, and keeps the legacy boolean `platform_supported` as a derived alias (`tier !== 'unsupported'`) for backward compatibility. `/doctor`, `/bootstrap`, `/preflight` hard-STOP only on `unsupported`; on `best-effort` they emit a warning recommending WSL2 for sandbox / Docker parity.

## Consequences
- WSL2 / Linux / macOS remain the **tested, recommended** path — nothing about that weakens.
- Native Windows users can run the template through Git Bash without WSL2, accepting: no OS-level Bash-tool sandbox, and a less-tested shell (Git Bash MSYS2 coreutils differ from GNU in edge cases).
- Windows-native **PowerShell/cmd** remain unsupported — they cannot run the bash gates.
- Before relying on the best-effort path in a derived project, run one empirical pass on Windows/Git Bash: `npm run validate` + a pipeline pass + confirm the SessionStart hook fires.
