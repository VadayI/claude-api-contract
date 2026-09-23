# claude-api-contract

Derived projects select `local` or `github` CI before their first push with
`python scripts/ai/ci_mode.py --target . --mode local --apply` (or `github`).
Local mode creates manual-only workflows; GitHub mode activates the same exact
runner catalog on automatic events. See `docs/ai/workflows/bootstrap.md` for
the ownership-safe switch and repository setup order.

**Single source of truth for a REST API contract.** TypeSpec в†’ a canonical, bundled `openapi.yml` (OpenAPI 3.1), linted (Spectral), mocked (Prism), and breaking-change gated (oasdiff). Two repositories consume it in parallel вЂ” `claude-django` (backend, validates its implementation against the contract) and `claude-react-mui` (frontend, generates TS types + a mock). Neither generates the contract; both pin a version.

This is the third Claude Code configuration template in the set, alongside [`claude-django`](https://github.com/VadayI/claude-django) and [`claude-react-mui`](https://github.com/VadayI/claude-react-mui). It keeps their philosophy: agents / rules / skills / commands, WSL2, PR-only, context in git.

## Why

In the old flow the contract was born in the backend (`drf-spectacular` generated `openapi.yml` from serializers), so the frontend could not truly start until the backend wrote serializers. Here the contract is an **independent artifact, designed first** вЂ” so backend and frontend start at the same time: the frontend against a Prism mock, the backend against the contract as a specification.

## Where this runs

Shared Python tooling and launcher version probes are verified on native Windows;
Bash scripts use explicit Git Bash (`C:/Program Files/Git/bin/bash.exe`) from
PowerShell. Linux Python 3.13 is the control platform. This does not establish
sandbox isolation or complete derived TypeSpec/Prism acceptance. See
[measured compatibility](docs/ai/runtime-compatibility.md).

## Requirements

- **Python 3.13+** вЂ” standard-library family tooling; no application dependency.

The contract repository delivers its shared runtime from its own `template-core/`
using a content digest, without recording a future commit SHA. Run
`npm run ai:core:check` for a read-only source/delivery comparison and
`npm run ai:core:sync` to preview ownership conflicts and apply safe updates.
`scripts/install.sh` performs this delivery before dependency installation.
Committed runtime files are also included by fresh seed. Local customizations
conflict rather than being overwritten; project notes and settings are untouched.
After editing canonical source, run `python template-core/scripts/ai/generate_core.py`
before syncing. Never hand-edit delivered files listed in `docs/ai/core-source.json`;
`production.py` is this repository's stack-specific delivery source.

`npm run ai:claude -- --probe` and `npm run ai:codex -- --probe` use the
portable launchers. PowerShell can invoke `scripts/ai/launch.ps1`; Git Bash can
invoke `scripts/ai/launch.sh`. See [launcher configuration](docs/ai/launchers.md).
These entry points do not establish that every legacy contract role/procedure
has been migrated to Codex; that migration remains in progress.

- **Node.js 20.19+** (22 LTS recommended) вЂ” runs the hook, TypeSpec, Spectral, Prism
- **git** вЂ” version control
- **GitHub CLI (`gh`)** вЂ” PR/release automation
- **oasdiff** вЂ” breaking-change gate (Go binary, not an npm package)
- **Claude Code CLI** вЂ” `npm install -g @anthropic-ai/claude-code`

## Fresh seed and ownership-aware update

Use Python 3.13+, Git and Bash (explicit Git Bash on native Windows):

```bash
bash scripts/seed.sh "../my contract" --ref main
```

The script clones a selected ref into a printed temporary directory and delivers
only its reviewed manifest. It does not create a remote, push, run npm, seed env,
activate workflows or delete existing project data. `--url <fork>` selects another
reviewed source; legacy `--force` cannot bypass ownership conflicts. The temporary
source is retained for review/recovery.

For an already available reviewed checkout, preview and apply directly:

```bash
python scripts/ai/production.py --target "../my contract"
python scripts/ai/production.py --target "../my contract" --apply
```

Source drift/customized template files stop all writes. Project notes are seed-once
and are not recreated after intentional deletion once a receipt exists;
custom instructions/MCP/settings require a reviewable reconciliation. Active
workflows are omitted from fresh seed until the user's CI choice is resolved and
workflows are reviewed/materialized (P06 pending). Existing workflows are retained.
Do not create a GitHub template-derived remote or push copied workflows before
that choice. Install/update never removes `.git`, stash or foreign files.

In the target, use `python scripts/ai/launch.py claude` or `codex`, then the local
`doctor` and `bootstrap` procedures. Install contract dependencies explicitly with
`bash scripts/install.sh` when needed. Supply credentials through the runtime's
normal credential mechanism; template setup never reads/copies your real env.
Native custom-role activation remains subject to the measured compatibility
limits; full role packs and local procedure files work as explicit prompts.

[Production structure and migration](docs/ai/production-structure.md) describe the
21 canonical rules, selected roles, preserved legacy functions and pending P12
transfer. `npm run ai:check` checks a pristine template source; in a customized
project, use `npm run ai:adapters:check` plus `npm run ai:core:check`. Project notes
are not template drift. Bootstrap personalizes only reviewed project-owned fields,
not generated adapters or core provenance. Full atomic rollback remains pending.

## Try it in a throwaway sandbox

Clone the template into a temporary directory and install all dependencies in one command:

```bash
bash scripts/sandbox.sh                  # clone into /tmp/cac-sandbox.XXXXXX + install
bash scripts/sandbox.sh /my/path         # clone into a specific path
bash scripts/sandbox.sh --ref v0.2.1     # pin a specific tag or branch
```

Or via npm: `npm run sandbox`

The sandbox is a full git clone (tags included), so all quality gates work. To remove it: `rm -rf <printed-path>`.

## Clean up

Remove build and session artifacts when you want a clean slate:

```bash
bash scripts/clean.sh                   # Class A вЂ” safe, always regenerable
bash scripts/clean.sh --dry-run         # preview what would be deleted
bash scripts/clean.sh --reset-to-clone  # Class A + B вЂ” resets to fresh-clone state (confirms)
```

Or via npm: `npm run clean`

| Class | What | When to use |
|---|---|---|
| **A** (default) | `node_modules/`, `tsp-output/`, `.tsp/`, session memory files | Any time вЂ” fully regenerable |
| **B** (`--reset-to-clone`) | `spec/`, `examples/`, `openapi.yml`, `LOCAL/`, local ADRs, `.env` | To bring this copy to the state of a fresh clone; **irreversible** |

> Full inventory of both classes вЂ” `docs/AUDIT-2026-06-08.md`.

## Quick start (in Claude Code CLI)

```
/doctor          # audit the environment, recommends /bootstrap
/bootstrap        # scaffold + personalize identity (Mode A) or resume (Mode B)
/personalize      # (standalone) re-run token + prose identity rewrite
/synthesize-brief # (optional) build PROJECT.md from docs/** вЂ” records maturity stage (demo/prototype/PoC/MVP/production)
/happy-paths      # (optional) generate business happy-path journeys вЂ” re-runnable after /preflight once endpoints exist
/preflight        # build-input gate
/check-readme     # audit + fix README freshness
/ship-contract    # package mock в†’ push to ghcr.io в†’ print VPS deploy command
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
ba в†’ api-architect в†’ tsp-author в†’ [contract-reviewer | breaking-change-analyst]
   в†’ mock-validator в†’ docs-writer
```

## CI gates (hard, red)

| Gate | Tool | Fails when |
|---|---|---|
| TypeSpec drift | `tsp compile` + diff | recompiled `spec/` в‰  committed `openapi.yml` |
| Spectral lint | `spectral lint` | style/naming/codes/envelope violations |
| Example validation | Spectral / Prism | an example is invalid against schema |
| Breaking-change | `oasdiff breaking --fail-on ERR` | breaking change without a major bump |
| Mock smoke | Prism | mock does not come up / returns invalid response |

> These 5 are the canonical contract-integrity gates (always on, every maturity stage). Two more layers complement them:
>
> - **Process gates** вЂ” `contract-policy.yml` (PR-scoped, diff-aware): no bare TODO/FIXME in contract artifacts (a documented `STUB:` is allowed), an ADR alongside any `.oasdiff-ignore.txt` change, a CHANGELOG `[Unreleased]` fragment on contract changes, and README в†” `package.json` version coherence. Plus a supplementary **endpoints-registry coverage** check in `contract-ci.yml` вЂ” every `openapi.yml` path is recorded in `.claude/memory/endpoints.json` (`npm run check:endpoints`).
> - **Local Claude Code hooks** вЂ” `.claude/settings.json` (run in the CLI, not CI): hard-block direct edits to the generated `openapi.yml`, gate `/release` + `/ship-contract` on cheap preconditions (`/create-pr` is advisory), and nudge the living-plan execution log. A weekly **`scheduled-audit`** workflow reports STUB/TODO inventory, version drift, and gate health.

## Local git hooks (optional)

For commits made **outside** Claude Code, opt into Husky + commitlint to mirror the gates locally:

```bash
npm i -D husky@^9 @commitlint/cli@^19 @commitlint/config-conventional@^19
npm pkg set scripts.prepare="husky" && npm run prepare
```

`pre-commit` (no hand-edited `openapi.yml`, no bare TODO in contract files, Spectral), `commit-msg` (Conventional Commits вЂ” English type prefix; Ukrainian subject/body allowed), `pre-push` (validate + breaking + mock). commitlint is pinned to **v19**: v21 requires Node в‰Ґ 22.12 while this template targets Node в‰Ґ 20.19.

## Delivery & versioning

Releases are **git tags** `vX.Y.Z`. Consumers pin `CONTRACT_VERSION` and fetch:
`https://raw.githubusercontent.com/VadayI/claude-api-contract/<tag>/openapi.yml`. Bumping a pin is a deliberate PR in the consumer. See `.claude/rules/versioning.md`.

## For consumers

Once the contract is tagged and the mock is deployed (via `/ship-contract`), both consumer teams can start parallel work against the same shared mock:

| Consumer | Role | How to use |
|---|---|---|
| **`claude-django`** (backend) | Validates its implementation against the contract | Vendor `openapi.yml@<tag>` в†’ run `scripts/check_contract_sync.sh` in CI |
| **`claude-react-mui`** (frontend) | Generates TS types + develops against the live mock | `openapi-typescript openapi.yml@<tag>` в†’ point app at `http://<IP>:<PORT>` |

**Pin the contract version** (in each consumer repo, committed вЂ” not just an env var):
```
CONTRACT_REPO=https://github.com/VadayI/claude-api-contract
CONTRACT_VERSION=vX.Y.Z
```
Bumping the pin is a **deliberate PR in the consumer**. See `.claude/rules/versioning.md`.

**Live mock** (deployed with `/ship-contract`):
```
http://<IP>:<PORT>
```
> Run `/ship-contract <IP> <PORT>` to build, push, and deploy the mock вЂ” then replace `<IP>:<PORT>` with the real address above.

**Backend** (`claude-django`): vendor `openapi.yml`, run your `check_contract_sync.sh` gate in CI, write a `contract.lock.json` (`repo` + `version` + `sha256`).

**Frontend** (`claude-react-mui`): generate TS types with `openapi-typescript`, develop against `http://<IP>:<PORT>` (the Prism static mock returns deterministic contract-compliant responses). Scaffold pages **only** for the `page` routes in `.claude/memory/pages.json` вЂ” never for `system` endpoints like `/api/v1/auth/token` (@.claude/rules/endpoint-surface.md).

## Structure

```
.claude/         agents В· commands В· rules В· skills В· settings.json
spec/            TypeSpec source (main.tsp, auth.tsp, models/)
examples/        request/response examples (feed the Prism mock)
docs/            api/INDEX.md В· decisions/ (ADR) В· WORKLOG.md
scripts/         detect-env.mjs В· session-start.sh В· gate scripts
openapi.yml      в—„ CANONICAL OUTPUT (bundled, OpenAPI 3.1)
.spectral.yaml   layered ruleset
```

> Status: **v0.4.0 released** вЂ” full contract slice (auth + articles CRUD), 5 CI gates + process gates + local Claude Code policy hooks, Prism mock (reference + derived-aware). Docker packaging + VPS deploy (`/ship-contract`). `/check-readme` freshness command. See `docs/HANDOFF.md` for current state.

## Uninstall

### Remove only regenerable artifacts (safe вЂ” keeps your contract source)

```bash
bash scripts/clean.sh        # removes node_modules/, tsp-output/, session memory files
```

Regenerate them at any time with `npm ci` and `npm run api:compile`.

### Remove the entire project folder

If the project is in its own dedicated folder, just delete that folder:

```bash
# Linux / macOS / WSL2 вЂ” replace <path> with your actual project folder
rm -rf /path/to/your/contract

# Example (WSL2 path for D:\Dev\My\VMT\contract):
rm -rf /mnt/d/Dev/My/VMT/contract
```

> This deletes everything вЂ” source files, git history, dependencies. Make sure you have pushed
> your work to GitHub (or have a backup) before running this.

## Shared-core readiness draft

`template-core/` contains the independent P09 maturity/readiness resolver for
Python 3.13+ (standard library only). See [its README](template-core/README.md)
and [migration report](template-core/docs/ai/maturity-migration.md). It does not
change contract application behavior or declare production family integration.
