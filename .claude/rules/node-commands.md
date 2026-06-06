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
npm run validate            # compile + drift gate + spectral lint + examples gate
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
