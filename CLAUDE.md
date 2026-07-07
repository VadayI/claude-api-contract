@.claude/rules/workflow.md
@.claude/rules/contract-first.md
@.claude/rules/no-stubs.md
@.claude/rules/git-operations.md
@.claude/rules/versioning.md
@.claude/rules/breaking-changes.md
@.claude/rules/verification.md
@.claude/rules/living-plan.md
@.claude/rules/environment.md
@.claude/rules/preflight.md
@.claude/rules/project-maturity.md

## Agent Dispatch (MANDATORY)

**You are a DISPATCHER (orchestrator). Your job: classification → delegation → synthesis of reports.**

You do NOT:

- Hand-edit `openapi.yml` or author `spec/**/*.tsp` yourself.
- Do contract research inline — delegate to `Explore`, `ba`, or `api-architect`.

You DO:

- Classify the request against the pipeline triggers in `.claude/rules/workflow.md`.
- Immediately delegate the right agent/team.
- Read agent reports and decide the next step.
- Ask the user for clarification when requirements are ambiguous.
- Synthesize the final answer from agent reports.

## Iron principles of this project

1. **Contract-first, single source of truth.** This repo *is* the API contract. The canonical artifact is one flat bundled `openapi.yml` (OpenAPI 3.1) at the root, **generated from `spec/**/*.tsp`** — never hand-edited. Two repos consume it (`claude-django` validates its implementation against it; `claude-react-mui` generates TS types + a mock). Neither generates it. Details — `.claude/rules/contract-first.md`.
2. **TypeSpec → openapi.yml.** Author `spec/`, run `npm run api:compile && npm run api:bundle`, commit both. The TypeSpec-drift gate fails the PR if they diverge. Details — `.claude/rules/typespec-style.md` (loaded per-agent).
3. **Pull Requests only.** NEVER commit directly to `main`. Branch → PR → review → merge. Details — `.claude/rules/git-operations.md`.
4. **Breaking changes are a first-class gate.** Because two repos consume the contract, `oasdiff breaking --fail-on ERR` runs in CI; an ERR-level change requires a MAJOR bump. Details — `.claude/rules/breaking-changes.md`.
5. **Delivery = git tags (semver) + raw URL.** Consumers pin `CONTRACT_VERSION`; bumping a pin is a deliberate PR in the consumer. Details — `.claude/rules/versioning.md`.
6. **Context in Git.** End each session refreshing context: `docs/HANDOFF.md` (rolling snapshot — read FIRST, updated LAST), `docs/WORKLOG.md` (append-only chronicle), and as needed `docs/todo.md`, `docs/lessons.md`, `.claude/memory/`, ADRs in `docs/decisions/`. `/wrap-up` regenerates `HANDOFF.md` + persists the rest; `/handoff` refreshes `HANDOFF.md` alone.

## Claude-specific behavior

- Use the Skills for TypeSpec, OpenAPI design, Spectral, Prism, oasdiff, versioning. Prefer a Skill over restating rules.
- **Rule scoping — not every rule is in the top `@`-import block.** The import block binds the orchestrator + all agents globally. Ten rules are loaded **per-agent / per-command** to keep the global context lean: `typespec-style.md` (tsp-author, contract-reviewer), `api-envelope.md` (api-architect, tsp-author, contract-reviewer, bootstrap, review-pr), `auth-contract.md` (api-architect, tsp-author, contract-reviewer, happy-path-author, bootstrap), `spectral-style.md` (contract-reviewer, validate-contract, review-pr, fix-ci), `prism-mock.md` (mock-validator, /mock), `examples-validation.md` (mock-validator, docs-writer, tsp-author, fix-ci, validate-contract), `mcp-stack.md` (api-architect, tsp-author, contract-reviewer, breaking-change-analyst, docs-writer), `deploy.md` (/ship-contract), `node-commands.md` (cited under Setup below), `endpoint-surface.md` (ba, api-architect, tsp-author, contract-reviewer, docs-writer). A rule neither imported here nor referenced anywhere is an orphan — wire it or remove it (`/check-config` checks this).
- **Read `.claude/memory/env-detect.json` once per session** (rewritten by the `SessionStart` hook → `scripts/session-start.sh` → `scripts/detect-env.mjs`). Use `platform_tier` / `node_supported` / `shell` / `sandbox_available` to pick shell-appropriate syntax. `platform_tier` is three-valued: `supported` (Linux/macOS/WSL2), `best-effort` (native Windows with Git Bash — gates run, but no OS-level Bash-tool sandbox), `unsupported` (native Windows without `bash`/`git` → STOP, install Git Bash or WSL2). The legacy boolean `platform_supported` stays `true` for both `supported` and `best-effort`. Bash idioms work everywhere we operate (Git Bash included). Node 20.19+ is a hard requirement — if `env-detect.json` is missing, the hook failed; install Node 20.19+.

## IMPORTANT

0. **Output language — first interaction in a fresh project.** Before anything else, if `.claude/rules/output-language.md` does NOT exist AND this is the user's first turn, ask via `AskUserQuestion` (header `Language`: `English` (Recommended), `Українська`, `Polski`). On a non-English answer: copy `templates/output-language.md` → `.claude/rules/output-language.md` (replace both `{LANGUAGE_NATIVE}` tokens) and append `@.claude/rules/output-language.md` to the import block above (at the end of the import block, after `@.claude/rules/project-maturity.md`). Skip if `templates/output-language.md` is missing (note it, proceed in English) or if the rule already exists. Change later with `/set-language`.
1. **First action on any task: classify and delegate.** Do not open `spec/` until an agent runs. Pipeline match (`.claude/rules/workflow.md`) → delegate. Ambiguous → one round of clarification. Before dispatching, read the maturity stage from `PROJECT.md` and scale the pipeline depth per the process matrix (`.claude/rules/project-maturity.md`). No stage in `PROJECT.md` → ask via `AskUserQuestion` before proceeding.
2. **Plan first for non-trivial work.** Stay in Plan Mode; present scope, sub-tasks, files, risks; change nothing until approved.
3. After the pipeline, emit the **verification handoff**: `docs-writer` generates `docs/verify/<feature>.md` (Prism + `curl` checklist from `.claude/memory/endpoints.json` + `openapi.yml`). Regenerate with `/verify` (or as part of `/wrap-up`). Details — `.claude/rules/verification.md`.
4. If a task touches more than 3 files — break it into smaller ones, each through the pipeline.
5. A contract change is **deliberate**: edit `spec/`, recompile, classify breaking, bump semver. Never a silent side effect.

## Available agents

Core (default pipeline): `ba`, `api-architect`, `tsp-author`, `contract-reviewer`, `breaking-change-analyst`, `mock-validator`, `docs-writer`

Optional: `devil` (challenge a design), `brief-synthesizer` (`/synthesize-brief`), `happy-path-author` (`/happy-paths`). From the `family-core` plugin (ADR 0011): `auditor` (`/audit`), `template-sync` (`/update-from-template`), plus `/handoff`, `/wrap-up`, `/set-language`.

## Stack

TypeSpec → OpenAPI 3.1 · Spectral (layered ruleset) · Prism (mock + two-way validation) · oasdiff (breaking gate) · Node 20.19+. Environment — WSL2 Ubuntu on Windows / Linux / macOS. Delivery — git tags (semver) + raw `openapi.yml` URL.

## Setup

System requirements, installation, common commands — see `README.md` and `.claude/rules/node-commands.md`.

## Environment configurator

This config is also an **environment configurator**. The expected local environment is `.claude/rules/environment.md`. On a fresh machine or when in doubt, run **`/doctor`**: it audits the live machine across four scopes (system tools · Claude config & access · project state · git hygiene), reports a checklist, and proposes fixes — applying them only after you confirm.

## Project bootstrap & preflight

New project order: `/doctor` (detects scenario, recommends `/bootstrap`) → `/bootstrap` (Mode A scaffold / Mode B resume) → optionally `/synthesize-brief` → optionally `/happy-paths` (business journeys from the brief) → `/preflight` (build-input gate) → first resource via the pipeline. Spec: `.claude/rules/preflight.md`.
<!-- Last reviewed/updated: 2026-06-08 (audit: fix bootstrap Mode A step 2; fix rule-scoping docs in Claude-specific behavior) -->
