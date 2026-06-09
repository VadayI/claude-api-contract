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

- **Node.js 20.19+** (22 LTS recommended) — runs the hook, TypeSpec, Spectral, Prism
- **git** — version control
- **GitHub CLI (`gh`)** — PR/release automation
- **oasdiff** — breaking-change gate (Go binary, not an npm package)
- **Claude Code CLI** — `npm install -g @anthropic-ai/claude-code`

## Installation (step by step)

Follow these steps once on a fresh machine. Every command is meant to run in a **bash shell**
(Linux / macOS / WSL2 Ubuntu). Windows users: complete Step 0 first.

### Step 0 — Windows only: install WSL2

Open **PowerShell as Administrator** and run:

```powershell
wsl --install -d Ubuntu    # installs WSL2 + Ubuntu; reboot when prompted
```

After reboot, open the **Ubuntu** app — every subsequent step runs **inside Ubuntu**, not PowerShell.

### Step 1 — Go to your project folder

Navigate to the folder where you want the contract to live. Two common scenarios:

**A) Create a new folder:**

```bash
mkdir -p ~/projects/my-contract   # create the folder
cd ~/projects/my-contract         # enter it
```

**B) Use an existing folder** (e.g. you are already in `D:\Dev\My\VMT\contract` via WSL2):

```bash
cd /mnt/d/Dev/My/VMT/contract     # navigate to it (WSL2 path for D:\Dev\My\VMT\contract)
```

> The next step clones the template **into the current directory**, so make sure it is the exact
> folder you want the project files to end up in.

### Step 2 — Clone the template into the current folder

```bash
git clone https://github.com/VadayI/claude-api-contract.git .
```

The trailing **`.`** (dot) tells git to clone into the **current directory** instead of creating a
subfolder named `claude-api-contract`. The directory must be empty (or contain only a `.git` folder).

Or using the GitHub CLI:

```bash
gh repo clone VadayI/claude-api-contract .
```

> **Without the dot** (`git clone <url>`) git creates a subfolder named `claude-api-contract` inside
> the current directory. Use that form only if you deliberately want a subfolder.

### Step 3 — Disconnect from the template and link your own repo

After cloning, `.git` still points to the original template repository. Replace it with a fresh
git history connected to **your** GitHub repo.

**3a — Remove the template's git history and start fresh:**

```bash
rm -rf .git                # delete the template's .git (history, remotes, branches)
git init                   # start a clean repository
git add -A
git commit -m "init: bootstrap from claude-api-contract template"
```

**3b — Create your GitHub repo and link it:**

```bash
gh repo create my-contract --private --source=. --push
```

This creates a private repo named `my-contract` on GitHub, sets it as `origin`, and pushes the
initial commit in one command. Replace `my-contract` with your desired repo name.
Use `--public` instead of `--private` if you want a public repo.

> **Alternative** — if you already created the GitHub repo manually:
> ```bash
> git remote add origin https://github.com/YOUR_USERNAME/my-contract.git
> git push -u origin main
> ```

### Step 4 — Install system toolchain

```bash
bash scripts/setup-wsl.sh  # nvm + Node LTS + Claude Code CLI + checks gh/oasdiff (idempotent)
```

This script installs: **nvm**, **Node LTS**, **Claude Code CLI** (`@anthropic-ai/claude-code`).
It also checks that `gh` and `oasdiff` are on PATH and prints install hints if they are missing.
Safe to re-run at any time.

> After running, reload your shell (`source ~/.bashrc` or open a new terminal) so `node`, `npm`,
> and `claude` are on your PATH.

### Step 5 — Install project dependencies

```bash
bash scripts/install.sh    # npm ci (TypeSpec, Spectral, Prism) + oasdiff presence check
```

Installs the npm dev-dependencies declared in `package.json`:
`@typespec/compiler`, `@typespec/http`, `@typespec/openapi3`, `@stoplight/spectral-cli`,
`@stoplight/prism-cli`. Creates `node_modules/`.

### Step 6 — Configure secrets

```bash
cp .env.example .env       # create your local .env from the template
```

Open `.env` and fill in the values (GitHub PAT, `CONTEXT7_API_KEY`, etc.).
The `SessionStart` hook seeds `.env` automatically on the first `claude` launch if the file is
missing, but filling in real values before working is recommended.

### Step 7 — Launch Claude Code

```bash
claude                     # start the Claude Code CLI from the repo root
```

Inside Claude Code, run:

```
/doctor      # audits the environment and reports any missing tools
/bootstrap   # scaffolds spec/ and examples/ AND personalizes identity (Mode A)
/personalize # (optional) re-run identity rewrite or prose pass at any time
```

Then follow the prompts. See **Quick start** below for the full command sequence.

> **Template identity is rewritten automatically by `/bootstrap`** — it replaces
> `VadayI/claude-api-contract` URLs, README title, `package.json` name/version with
> your owner/repo. Run `/personalize` standalone if you need to re-run or add
> the prose pass (README description, consumer names).

---

> **Just want to try it without a permanent install?** See *Try it in a throwaway sandbox* below —
> one command clones and installs everything into a temp directory.

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
bash scripts/clean.sh                   # Class A — safe, always regenerable
bash scripts/clean.sh --dry-run         # preview what would be deleted
bash scripts/clean.sh --reset-to-clone  # Class A + B — resets to fresh-clone state (confirms)
```

Or via npm: `npm run clean`

| Class | What | When to use |
|---|---|---|
| **A** (default) | `node_modules/`, `tsp-output/`, `.tsp/`, session memory files | Any time — fully regenerable |
| **B** (`--reset-to-clone`) | `spec/`, `examples/`, `openapi.yml`, `LOCAL/`, local ADRs, `.env` | To bring this copy to the state of a fresh clone; **irreversible** |

> Full inventory of both classes — `docs/AUDIT-2026-06-08.md`.

## Quick start (in Claude Code CLI)

```
/doctor          # audit the environment, recommends /bootstrap
/bootstrap        # scaffold + personalize identity (Mode A) or resume (Mode B)
/personalize      # (standalone) re-run token + prose identity rewrite
/synthesize-brief # (optional) build PROJECT.md from docs/** — records maturity stage (demo/prototype/PoC/MVP/production)
/preflight        # build-input gate
/check-readme     # audit + fix README freshness
/ship-contract    # package mock → push to ghcr.io → print VPS deploy command
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

## For consumers

Once the contract is tagged and the mock is deployed (via `/ship-contract`), both consumer teams can start parallel work against the same shared mock:

| Consumer | Role | How to use |
|---|---|---|
| **`claude-django`** (backend) | Validates its implementation against the contract | Vendor `openapi.yml@<tag>` → run `scripts/check_contract_sync.sh` in CI |
| **`claude-react-mui`** (frontend) | Generates TS types + develops against the live mock | `openapi-typescript openapi.yml@<tag>` → point app at `http://<IP>:<PORT>` |

**Pin the contract version** (in each consumer repo, committed — not just an env var):
```
CONTRACT_REPO=https://github.com/VadayI/claude-api-contract
CONTRACT_VERSION=vX.Y.Z
```
Bumping the pin is a **deliberate PR in the consumer**. See `.claude/rules/versioning.md`.

**Live mock** (deployed with `/ship-contract`):
```
http://<IP>:<PORT>
```
> Run `/ship-contract <IP> <PORT>` to build, push, and deploy the mock — then replace `<IP>:<PORT>` with the real address above.

**Backend** (`claude-django`): vendor `openapi.yml`, run your `check_contract_sync.sh` gate in CI, write a `contract.lock.json` (`repo` + `version` + `sha256`).

**Frontend** (`claude-react-mui`): generate TS types with `openapi-typescript`, develop against `http://<IP>:<PORT>` (the Prism static mock returns deterministic contract-compliant responses).

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

> Status: **v0.3.0 released** — full contract slice (auth + articles CRUD), 5 CI gates, Prism mock. Docker packaging + VPS deploy (`/ship-contract`). `/check-readme` freshness command. See `docs/HANDOFF.md` for current state.

## Uninstall

### Remove only regenerable artifacts (safe — keeps your contract source)

```bash
bash scripts/clean.sh        # removes node_modules/, tsp-output/, session memory files
```

Regenerate them at any time with `npm ci` and `npm run api:compile`.

### Remove the entire project folder

If the project is in its own dedicated folder, just delete that folder:

```bash
# Linux / macOS / WSL2 — replace <path> with your actual project folder
rm -rf /path/to/your/contract

# Example (WSL2 path for D:\Dev\My\VMT\contract):
rm -rf /mnt/d/Dev/My/VMT/contract
```

> This deletes everything — source files, git history, dependencies. Make sure you have pushed
> your work to GitHub (or have a backup) before running this.
