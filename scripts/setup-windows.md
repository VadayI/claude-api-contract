# Native Windows setup (best-effort) — Git Bash, no WSL2

> Counterpart to `scripts/setup-wsl.sh` for running the template on **native Windows** via
> Claude Code's Windows build. This is the **best-effort** tier (ADR 0009): the bash gate
> scripts run through **Git Bash**, but there is no OS-level Bash-tool sandbox and the shell
> is less tested than Linux/macOS/WSL2. Prefer WSL2 (`scripts/setup-wsl.sh`) when you need
> sandboxing or Docker parity.

## 1. Prerequisites — install once (PowerShell)

`winget` ships with Windows 11 and recent Windows 10.

```powershell
winget install --id Git.Git           -e --source winget   # Git for Windows → Git Bash (REQUIRED)
winget install --id OpenJS.NodeJS.LTS  -e --source winget   # Node 20.19+ (22 LTS recommended)
winget install --id GitHub.cli         -e --source winget   # gh — PRs / releases
```

`oasdiff` (the breaking-change gate) has no winget package — install via Go or grab a release binary and put it on PATH:

```powershell
go install github.com/oasdiff/oasdiff@v1.18.4               # if Go is installed
# or download from https://github.com/oasdiff/oasdiff/releases and add the .exe to PATH
```

Install Claude Code (native Windows build):

```powershell
irm https://claude.ai/install.ps1 | iex
```

## 2. Build the toolchain — from **Git Bash** in the repo root

Git Bash is the shell Claude Code uses for the Bash tool, so run the gates there:

```bash
bash scripts/install.sh     # npm deps (TypeSpec, Spectral, Prism) + oasdiff check
npm run validate            # compile + drift + lint + examples + endpoints registry
```

## 3. Verify the runtime tier

```bash
node scripts/detect-env.mjs
```

Expect `platform=windows ... BEST-EFFORT` and, in `.claude/memory/env-detect.json`,
`"platform_tier": "best-effort"` with `"sandbox_available": false`. If it reports
`unsupported`, then `bash` or `git` is not on PATH — reinstall Git for Windows and reopen Git Bash.

## Known limitations (best-effort tier)

- No OS-level Bash-tool sandbox (macOS / Linux / WSL2 only).
- Git Bash (MSYS2) coreutils differ from GNU in edge cases; the gate scripts are ~95% portable but less exercised here.
- `scripts/setup-wsl.sh` is Linux-only — use this guide instead.
- Run git from Git Bash (or any single shell) consistently to avoid index-lock quirks.
