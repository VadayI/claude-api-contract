# Environment specification (source of truth)

Defines the **expected local environment** for a `claude-api-contract` project. `/doctor` checks the live machine against this and proposes fixes.

> Philosophy: detect → report → propose → **fix only after the user confirms**. `/doctor` reads `.claude/memory/env-detect.json`, never auto-fixes risky things, never pushes to `main`, never prints secrets.

## Scope 1 — System tools

Bash on Linux / macOS / WSL2 Ubuntu. Windows-native PowerShell/cmd is NOT supported (`docs/decisions/0001-drop-windows-native-shell.md`); on Windows, install WSL2 and run everything inside it.

| Requirement | Expected | Check |
|---|---|---|
| **Node.js (HARD)** | 20.19+ (22 LTS recommended) on PATH | `node --version`; runs the hook, gate helpers, TypeSpec/Spectral/Prism |
| **npm (HARD)** | bundled with Node; a Linux path, not `/mnt/c/...` | `npm --version` |
| git | present | `git --version` |
| GitHub CLI | present in WSL2 (a Windows `gh.exe` is invisible inside WSL2) | `gh --version` |
| **Claude Code CLI (WSL2-native)** | `which claude` → `/home/...` or `/usr/...`, never `/mnt/c/...` | install: `npm i -g @anthropic-ai/claude-code` |
| **oasdiff** | on PATH (breaking-change gate) | `oasdiff --version` |
| Docker (OPTIONAL) | only for containerized Prism / proxy parity | `docker info` |

`.claude/memory/env-detect.json` is the source of truth for `platform_supported` / `node_supported` / `gh.*`. It is rewritten by `scripts/detect-env.mjs` on every session. **Never hand-write it** to skip a blocker.

## Scope 2 — Claude config & access

| Requirement | Expected | Check |
|---|---|---|
| Plugins baseline | `superpowers@superpowers-marketplace`, `engineering@knowledge-work-plugins`, `github@claude-plugins-official`, `context7@claude-plugins-official` (auto-enabled in `.claude/settings.json`) | `/plugins` vs `enabledPlugins` |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | set (push/PR/release) | `[ -n "$GITHUB_PERSONAL_ACCESS_TOKEN" ]` (never print) |
| `CONTEXT7_API_KEY` | set (doc lookups) | `[ -n "$CONTEXT7_API_KEY" ]` (never print) |
| GitHub auth & repo | authenticated; repo reachable (fine-grained PAT: Contents RW, Metadata RO, Pull requests RW, Workflows RW, Administration RW) | `gh auth status`; `gh repo view <owner>/<repo>` |

## Scope 3 — Project state

| Requirement | Expected | Check |
|---|---|---|
| Skeleton | `spec/`, `examples/`, `docs/decisions/`, `.claude/` exist | `test -d` |
| Config | `CLAUDE.md`, `package.json`, `.spectral.yaml`, `.env.example` | `test -f` |
| Deps | `node_modules/` present | `test -d node_modules` / `npm ci` |
| Contract builds | `spec/` compiles and matches `openapi.yml` | `npm run validate` |

> A brand-new repo before `/bootstrap` legitimately lacks `spec/`/deps — `/doctor` reports these as "not set up yet" (info), not failures.

## Scope 4 — Git hygiene

| Requirement | Expected | Check |
|---|---|---|
| Branch | a feature branch, not `main` | `git branch --show-current` |
| Branch protection | `main` protected (PR + status checks) | `gh api repos/{owner}/{repo}/branches/main/protection` |
| Working tree | clean or only intended changes | `git status -sb` |
| No secrets tracked | `.env` ignored | `git ls-files \| grep -E '(^\|/)\.env$'` (empty = good) |

## Remediation policy

- **Propose-then-apply (after confirm):** `npm ci`, `cp .env.example .env`, create skeleton dirs, `/plugins install`, `nvm install`, install oasdiff, create a feature branch off fresh `main`.
- **Ask explicitly:** writing secrets, force ops, deleting files, enabling branch protection, pushing.
- **Forbidden in `/doctor`:** committing, `git push`, pushing to `main`, printing secrets, editing `spec/`.
