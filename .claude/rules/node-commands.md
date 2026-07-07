# Node / toolchain commands

> **Shell:** bash (Linux / macOS / WSL2 Ubuntu). Windows-native PowerShell/cmd is NOT supported — see `docs/decisions/0001-drop-windows-native-shell.md`. Working from a Windows drive (`/mnt/c`/`/mnt/d`) is fully supported; only caveat is slightly slower file watching, and git is best run from the host shell.
>
> **Node 20.19+ is a hard requirement.** It runs the SessionStart env-detection hook, the gate helpers, and the TypeSpec / Spectral / Prism CLIs. Install via `nvm` if missing (`scripts/setup-wsl.sh`). The hook writes `.claude/memory/env-detect.json` with the active shell + node version.

## Setup

```bash
bash scripts/setup-wsl.sh   # nvm + Node LTS + claude CLI + gh + oasdiff (idempotent)
bash scripts/install.sh     # npm deps (TypeSpec, Spectral, Prism) + oasdiff check
```

## Authoring loop

```bash
npm run api:compile         # tsp compile spec --emit @typespec/openapi3  → tsp-output/
npm run api:bundle          # copy emitter output → ./openapi.yml (canonical)
npm run format              # tsp format spec/**/*.tsp
```

## Quality gates (run before pushing)

```bash
npm run validate            # compile + drift gate + spectral lint + examples gate + endpoints registry
npm run lint                # spectral lint openapi.yml
bash scripts/check_typespec_drift.sh   # openapi.yml == spec/ output
bash scripts/check_examples.sh         # examples validate against schema
npm run breaking            # oasdiff breaking vs latest tag (--fail-on ERR)
```

## Mock

```bash
npm run mock                # Prism static mock (examples) on $PRISM_PORT (default 4010)
npm run mock:dynamic        # Prism dynamic mock (Faker + x-faker)
```

## Release

```bash
# via /release — rebuilds openapi.yml, runs gates, updates CHANGELOG (oasdiff changelog),
# tags vX.Y.Z, pushes the tag. Never tag a RED contract.
```

## Personalize (new project from template)

```bash
npm run personalize                         # resolve from git remote + confirm interactively
bash scripts/personalize.sh --dry-run       # preview all token replacements, no writes
bash scripts/personalize.sh --yes           # apply without confirmation prompt
bash scripts/personalize.sh --name my-api --owner acme --yes  # explicit values
bash scripts/personalize.sh --no-tier3      # skip .claude/ frontmatter tag rewrite
```

Tier 1: `VadayI/claude-api-contract` URLs, `package.json` name/desc, README H1.
Tier 2: `package.json` version reset → `0.0.0`, delete `docs/AUDIT-*.md`.
Tier 3: `[claude-api-contract]` → `[{slug}]` in all `.claude/` frontmatter.
Prose (requires Claude Code `/personalize`): README self-description, CLAUDE.md consumer section, `contract-first.md` diagram.

## Sandbox & cleanup

```bash
npm run sandbox                          # git clone from GitHub into a temp dir + npm install
bash scripts/sandbox.sh --ref v0.2.1    # pin a specific tag/branch
bash scripts/sandbox.sh /my/path        # clone into a specific path

npm run clean                            # remove regenerable build/session artifacts (Class A)
bash scripts/clean.sh --dry-run         # preview what would be deleted, no changes
bash scripts/clean.sh --reset-to-clone  # also remove Class B items (destructive, prompts)
bash scripts/clean.sh --reset-to-clone --yes  # skip confirmation (CI / scripting)
```

Class A (safe to delete any time — fully regenerable): `node_modules/`, `tsp-output/`, `.tsp/`,
`.claude/memory/env-detect.json`, `.claude/memory/command-log.jsonl`.

Class B (only present on the template's own working copy — absent on a fresh clone): `LOCAL/`,
`spec/`, `examples/`, `openapi.yml`, `docs/decisions/0002–0004` (demo-contract ADRs — 0005–0008 are template infra, kept), `.env`, `.claude/memory/endpoints.json`,
`.claude/settings.local.json`. See `docs/AUDIT-2026-06-08.md` for the full inventory.
