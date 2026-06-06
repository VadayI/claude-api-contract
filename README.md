# claude-api-contract

**Single source of truth for a REST API contract.** TypeSpec → a canonical, bundled `openapi.yml` (OpenAPI 3.1), linted (Spectral), mocked (Prism), and breaking-change gated (oasdiff). Two repositories consume it in parallel — `claude-django` (backend, validates its implementation against the contract) and `claude-react-mui` (frontend, generates TS types + a mock). Neither generates the contract; both pin a version.

This is the third Claude Code configuration template in the set, alongside [`claude-django`](https://github.com/VadayI/claude-django) and [`claude-react-mui`](https://github.com/VadayI/claude-react-mui). It keeps their philosophy: agents / rules / skills / commands, WSL2, PR-only, context in git.

## Why

In the old flow the contract was born in the backend (`drf-spectacular` generated `openapi.yml` from serializers), so the frontend could not truly start until the backend wrote serializers. Here the contract is an **independent artifact, designed first** — so backend and frontend start at the same time: the frontend against a Prism mock, the backend against the contract as a specification.

## Where this runs

- **Supported:** Claude Code CLI on **Linux / macOS / WSL2 Ubuntu**.
- **Not supported:** Cowork, Windows-native shells (PowerShell/cmd), Claude API/SDK standalone — the `SessionStart` hook (which writes `.claude/memory/env-detect.json`) does not run there. See `docs/decisions/0001-drop-windows-native-shell.md`.
- On Windows: install WSL2 Ubuntu and run every command (`node`, `npm`, `git`, `gh`, `claude`) inside it.

## Requirements

Node 20.19+ (22 LTS recommended), git, GitHub CLI (`gh`), and `oasdiff` (breaking-change gate). One-shot bootstrap:

```bash
bash scripts/setup-wsl.sh    # nvm + Node LTS + claude CLI + gh + oasdiff (idempotent)
bash scripts/install.sh      # npm deps (TypeSpec, Spectral, Prism) + oasdiff check
```

## Quick start (in Claude Code CLI)

```
/doctor          # audit the environment, recommends /bootstrap
/bootstrap        # scaffold the contract skeleton (Mode A) or resume (Mode B)
/synthesize-brief # (optional) build PROJECT.md from docs/**
/preflight        # build-input gate
# then design the first resource via the pipeline
```

## Authoring loop

```bash
npm run api:compile && npm run api:bundle   # spec/**/*.tsp -> ./openapi.yml
npm run validate                            # drift + spectral lint + examples
npm run breaking                            # oasdiff vs latest tag (--fail-on ERR)
npm run mock                                # Prism static mock (examples)
```

## Pipeline

```
ba → api-architect → tsp-author → [contract-reviewer | breaking-change-analyst]
   → mock-validator → docs-writer
```

## CI gates (hard, red)

| Gate | Tool | Fails when |
|---|---|---|
| TypeSpec drift | `tsp compile` + diff | recompiled `spec/` ≠ committed `openapi.yml` |
| Spectral lint | `spectral lint` | style/naming/codes/envelope violations |
| Example validation | Spectral / Prism | an example is invalid against schema |
| Breaking-change | `oasdiff breaking --fail-on ERR` | breaking change without a major bump |
| Mock smoke | Prism | mock does not come up / returns invalid response |

## Delivery & versioning

Releases are **git tags** `vX.Y.Z`. Consumers pin `CONTRACT_VERSION` and fetch:
`https://raw.githubusercontent.com/VadayI/claude-api-contract/<tag>/openapi.yml`. Bumping a pin is a deliberate PR in the consumer. See `.claude/rules/versioning.md`.

## Structure

```
.claude/         agents · commands · rules · skills · settings.json
spec/            TypeSpec source (main.tsp, auth.tsp, models/)
examples/        request/response examples (feed the Prism mock)
docs/            api/INDEX.md · decisions/ (ADR) · WORKLOG.md
scripts/         detect-env.mjs · session-start.sh · gate scripts
openapi.yml      ◄ CANONICAL OUTPUT (bundled, OpenAPI 3.1)
.spectral.yaml   layered ruleset
```

> Status: scaffolding (Etap 1 — `.claude/` config + scripts). Next: `spec/` first slice (auth + sample resource), CI workflow, examples, then tag `v0.1.0`.
