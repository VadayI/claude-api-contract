# WORKLOG

> Append-only chronicle of what changed each session (newest first).

## 2026-06-06 — Etap 1 (scaffold)
- Created the template core: repo scaffolding (`.gitignore`, `.gitattributes`, `.spectral.yaml`, `package.json`, `.mcp.json`), `.claude/settings.json`.
- Node/bash toolchain scripts: `detect-env.mjs`, `session-start.sh`, `log-cmd.mjs`, `install.sh`, `setup-wsl.sh`, gate scripts (`check_typespec_drift.sh`, `check_examples.sh`, `check_breaking.sh`, `bundle-openapi.mjs`).
- 18 rules, 11 agents, 6 skills, 17 commands, `CLAUDE.md`, `README.md`, `templates/`, ADRs.
- Pending (next Etap): `spec/` first slice (auth D1+D5 + sample resource), `examples/`, CI workflow `contract-ci.yml`, first compile → `openapi.yml`, tag `v0.1.0`.

## 2026-06-06 — Etap 1 verified; first push prepared
- Verification pass: no empty/NUL/corrupt files, frontmatter present, no orphan rules, scripts runnable.
- GitHub repo created (empty). First push prepared as a host-shell command block (sandbox lacks gh/PAT; /mnt 9p unsafe for .git). Push + branch protection pending.
