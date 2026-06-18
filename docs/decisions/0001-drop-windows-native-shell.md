# ADR 0001 — Drop Windows-native shell; require Linux/macOS/WSL2

**Status:** superseded by [0009](0009-allow-best-effort-windows-git-bash.md) (2026-06-18) · **Date:** 2026-06-06

## Context
Gate scripts and the SessionStart hook are bash + Node. PowerShell/cmd cannot run them, and PATH interop on Windows resolves `claude`/`node` to the Windows binaries, producing a mis-detected runtime.

## Decision
Support only Claude Code CLI on **Linux / macOS / WSL2 Ubuntu**. On Windows, the user installs WSL2 and runs everything inside it. `scripts/detect-env.mjs` records `platform_supported` and `wrong_runner_suspected`; `/doctor`, `/bootstrap`, `/preflight` hard-STOP on an unsupported platform.

## Consequences
- Cowork, Windows-native shells, and Claude API/SDK standalone are unsupported (no SessionStart hook → no `env-detect.json`).
- Working from `/mnt/c` or `/mnt/d` is fine (run git from the host shell to avoid bind-mount lock quirks).
