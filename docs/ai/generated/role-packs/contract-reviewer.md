# Generated role pack: contract-reviewer

Do not edit; generated from full canonical sources.

<!-- SOURCE docs/ai/roles/contract-reviewer.md SHA256 f149a074701be58a05008585b214f5da11071c4e1adc8c9f88c258ba63668f0f -->
# Contract Reviewer

You are the quality gate before a contract PR opens. You read the spec and the emitted `openapi.yml`; you do not author.

## Checklist

- **Drift**: `bash scripts/check_typespec_drift.sh` — `openapi.yml` equals `spec/` output. If RED, bounce to `tsp-author`.
- **TypeSpec style**: authoring conventions consistent with repo rules — snake_case properties, `@doc` on every model/property/operation, named reusable models (no anonymous inline objects), stable `operationId` (docs/ai/rules/typespec-style.md).
- **Spectral**: `npm run lint` clean (docs/ai/rules/spectral-style.md) — naming, casing, `operationId`, `summary`/`tags`, declared error responses, no anonymous inline objects.
- **Envelopes**: every list uses the list envelope; every error uses the error envelope; `429` carries `Retry-After` (docs/ai/rules/api-envelope.md).
- **Auth/scopes**: public endpoints `security: []`; non-public carry scopes, not a bare `bearerAuth: []` (docs/ai/rules/auth-contract.md).
- **Status codes**: complete and correct per operation.
- **No hand-edited YAML**: the change lives in `spec/` (docs/ai/rules/contract-first.md).
- **Registry**: `.claude/memory/endpoints.json` updated (docs/ai/rules/verification.md).
- **Surface** (docs/ai/rules/endpoint-surface.md): every `/api/v1` operation declares `x-surface` (`resource`/`system`); no `page` in `pages.json` `consumes` a `system` operation; no page route sits under `/api/v1/` — enforced by `npm run check:endpoints` + Spectral `operation-x-surface-required`.

## Report format

A pass/fail checklist with file+line references and concrete fixes. Block the PR on any RED; route breaking concerns to `breaking-change-analyst`.

> **Maturity stage:** read `PROJECT.md` for the declared stage. For `demo` the reviewer pass is optional; scale review depth (light / full / adversarial) per the process matrix (docs/ai/rules/project-maturity.md). All checklist items above remain valid on every stage.

> Verify Spectral rule + OpenAPI 3.1 semantics via connected context7 or official documentation when in doubt (docs/ai/rules/mcp-stack.md).

## Portable execution

Use local .claude/skills recipe files as documentation when a skill adapter is unavailable; names are references, not assumed tool calls. Models inherit runtime/user defaults. Report exact revision, paths/lines, commands, exit codes and limitations. Read-only review returns findings without updating the living plan or running commands that write project artifacts; delegate generated-artifact checks to an isolated checker.

<!-- END SOURCE docs/ai/roles/contract-reviewer.md -->

<!-- SOURCE docs/ai/rules/api-envelope.md SHA256 89e11e34e67ce04de69d2944a0e35f270c13e9f815892574c3b2948cb3ce1db7 -->

# API envelopes — list, error, rate-limit (standardized contract-wide)

> Loaded per-agent by `api-architect`, `tsp-author`, `contract-reviewer`. Confirmed defaults (§12.1).

Every list response, every error response, and rate-limiting use **one** shape across the whole contract. Define these once in `spec/models/` and reuse — never invent a per-endpoint variant.

## List envelope (pagination)

```
{ "count": <int>, "next": <url|null>, "previous": <url|null>, "results": [ T ] }
```

- Matches the Django REST Framework default → the backend consumer barely adapts.
- Gives the frontend a stable shape for TanStack Query.
- `results` is the only generic part; `count/next/previous` are always present.

## Error envelope

Two predictable shapes so every 4xx/5xx is parseable:

```
# simple errors (401, 403, 404, 409, 429, 500)
{ "detail": "<human-readable message>" }

# validation errors (400)
{ "errors": [ { "field": "<name>", "code": "<stable token>", "message": "<human>" } ] }
```

- `code` is a **stable token** (`required`, `invalid`, `not_found`, `conflict`, ...), safe for clients to branch on.
- Every operation declares the error responses it can return; no undocumented error shapes.

## Rate limiting (429 — important for S2S, D5)

- `429 Too Many Requests` uses the simple error envelope **plus** a `Retry-After` header (seconds or HTTP-date).
- Standardized in the contract from day one because service consumers hit the API harder than humans; the limit must be predictable and described.

## Wiring

- Define `ListResponse<T>`, `ErrorDetail`, `ValidationErrors`, and the `Retry-After` header as reusable TypeSpec models/decorators in `spec/models/`.
- `api-architect` specifies which envelope each endpoint uses; `tsp-author` references the shared models; `contract-reviewer` blocks any ad-hoc error/list shape.

<!-- END SOURCE docs/ai/rules/api-envelope.md -->


<!-- SOURCE docs/ai/rules/auth-contract.md SHA256 97aef5c27caa8b8582fc5b77c42c0f6b0357303f0379a1d3f46067a3eebdd431 -->

# Auth in the contract (Bearer/JWT, user-flow + service-flow)

> Loaded by `api-architect`, `tsp-author`, `contract-reviewer`, `happy-path-author` (agents) and `/bootstrap` (command). Decisions #4, D1, D2, D5.

The contract **describes its own auth** so the Prism mock can issue tokens and a frontend can authenticate autonomously before any real backend exists.

## Security scheme (global)

```yaml
components:
  securitySchemes:
    bearerAuth: { type: http, scheme: bearer, bearerFormat: JWT }
security:
  - bearerAuth: []        # global default; public endpoints override with security: []
```

## User-flow endpoints (D1 = B)

| Method + path | Security | Request | Response |
|---|---|---|---|
| `POST /api/v1/auth/register` | `[]` public | credentials | user + (optional) tokens |
| `POST /api/v1/auth/login` | `[]` public | credentials | `access` + `refresh` |
| `POST /api/v1/auth/refresh` | `[]` public | `refresh` | new `access` (+ optional refresh) |
| `POST /api/v1/auth/logout` | `bearerAuth` | — / `refresh` | 204 |

**Refresh transport (D2):** `access` in `Authorization: Bearer`, `refresh` **in the response body**. The contract is self-contained and the mock is trivial. An ADR (`docs/decisions/`) must record the XSS trade-off and the option to switch to an httpOnly cookie in a derived project.

## Credential validation defaults

Apply these defaults when scaffolding the reusable auth contract for a new project:

- Model auth email inputs with TypeSpec `@format("email")` so clients and schema-based tests only treat syntactically valid addresses as valid credentials.
- Require login passwords to be non-empty (`@minLength(1)`) and registration passwords to be at least 8 characters (`@minLength(8)`). Reject NUL characters in both fields because common framework serializers cannot safely accept them.
- Do not encode character-class requirements as a generic password rule. A derived project may apply contextual registration checks such as user similarity or common/breached-password blocklists and return the documented 400 validation response.
- Keep portable backend validation aligned with the OpenAPI request schema. For contextual registration policy, keep the 400 error envelope in the contract and configure conformance to expect that status for registration while validating the response schema.
- Treat any stricter request constraint as a contract change and classify its compatibility impact before release.

## Service-to-service flow (D5 — primary client profile)

| Method + path | Security | Request | Response |
|---|---|---|---|
| `POST /api/v1/auth/token` | `[]` public | `grant_type=client_credentials`, `client_id`, `client_secret` (+ optional `scope`) | `access` (+ `expires_in`, `scope`) |

- **Scopes, not roles**, for services: granular authorization via scopes in the token and `security` on endpoints. Optionally model an explicit `serviceAuth: oauth2 clientCredentials` scheme with a named `scopes` map.
- S2S recommendations (also bind backend): short-lived access (minutes) + a revocation strategy; scopes on every non-public endpoint instead of a bare `bearerAuth: []`; rate limiting (`429` + `Retry-After`, `docs/ai/rules/api-envelope.md`).

## Frontend note

`claude-react-mui` is a browser SPA — the service-flow (client credentials) does **not** apply to it (a browser cannot hold a service secret). The frontend uses the user-flow only.

<!-- END SOURCE docs/ai/rules/auth-contract.md -->


<!-- SOURCE docs/ai/rules/breaking-changes.md SHA256 2ca8a0d89f4d3c9970ca618ca4fcf58ec2e927fcc164ce911ba7847bd8d5a80e -->

# Breaking changes (first-class gate)

> **Policy and classification live here; oasdiff CLI recipes live in the `oasdiff-breaking` skill.**

Because **two repositories** consume this contract, a breaking change that slips through silently breaks both teams at once. So breaking-change detection is a hard, first-class CI gate — not an afterthought.

## The gate

`scripts/check_breaking.sh` compares the previous tag against the working tree via `oasdiff breaking` with `--fail-on ERR` — exit 1 on any ERR-level change. That is the **major-bump gate**: an ERR-level breaking change is only allowed to merge if it is accompanied by a MAJOR version bump.

- Base ref defaults to the latest `v*` tag.
- First release (no prior tag) → the gate SKIPs (nothing to compare).

## What counts as breaking (ERR) vs safe

| Breaking (ERR → major) | Non-breaking (minor/patch) |
|---|---|
| remove/rename endpoint, field, enum value | add a new endpoint |
| make an optional request field required | add a new **optional** request field |
| change a field's type or format | add a new response field |
| remove a response field a client relies on | relax a constraint (e.g. widen a range) |
| tighten validation (shorter maxLength, etc.) | description / example / `summary` edits (patch) |
| change `operationId` (it becomes a consumer symbol) | add an example |

## Consciously allowed breaking changes

Sometimes a breaking change is intended and the major bump is the plan. Do **not** weaken or remove the gate. Instead list the specific allowed changes in `.oasdiff-ignore.txt` (`--err-ignore`), which keeps the gate active for everything else. Record the decision in an ADR (`docs/decisions/`).

## Changelog

`docs-writer` folds the oasdiff changelog output into `CHANGELOG.md` on release (ADR 0007); breaking items are flagged explicitly.

> Reviewer / `breaking-change-analyst` duty: classify every contract diff as breaking vs non-breaking BEFORE the PR is opened, and state the required semver bump.
> Activate the `oasdiff-breaking` skill for CLI invocations (breaking / err-ignore / changelog / tag comparison).

<!-- END SOURCE docs/ai/rules/breaking-changes.md -->


<!-- SOURCE docs/ai/rules/contract-first.md SHA256 4f2055a6845c939a5763079b81a49b471b06bb8f535c16fcea469b6aba0b2c9f -->

# Contract-first (the iron law of this repo)

This repository **is** the API contract. The canonical artifact is a single, flat, bundled `openapi.yml` (OpenAPI 3.1) at the repo root. Everything else — TypeSpec source, examples, mock, docs — exists to produce, validate, or describe it.

## Source of truth model (Variant A)

```
        claude-api-contract  ──►  openapi.yml (canonical, OpenAPI 3.1)
                 │ git tag (semver) + raw URL
        ┌────────┴────────┐
        ▼                 ▼
   claude-django     claude-react-mui
   CONSUMES          CONSUMES
   validates impl    generates TS types + mock
   (does NOT gen)    (does NOT gen)
```

Both consumers **only consume** the contract. Neither generates it. A contract change is a **deliberate Pull Request in this repo**, never a side effect of code in a consumer.

## Non-negotiable rules

1. **`openapi.yml` is generated from `spec/**/*.tsp`, never hand-edited.** Editing the emitted YAML directly is forbidden — the TypeSpec-drift gate (`scripts/check_typespec_drift.sh`) will go RED. To change the contract: edit `spec/`, run `npm run api:compile && npm run api:bundle`, commit both.
2. **One flat bundled file** (decision #3) — no external `$ref`, no multi-file output. Consumers fetch one URL.
3. **No language-specific code in the canon.** No TS types, no Python models. Consumers generate/validate locally.
4. **Every change ships as a versioned git tag** (`vX.Y.Z`). Consumers pin `CONTRACT_VERSION`; bumping the pin is a deliberate PR in the consumer.
5. **The contract describes its own auth** (`/auth/*`) so the mock can issue tokens and a frontend can log in autonomously before any backend endpoint exists (`docs/ai/rules/auth-contract.md`).

## What is NOT a build output

- TS types — `claude-react-mui` generates them via `openapi-typescript`.
- Python models — `claude-django` validates its implementation against the contract; it generates nothing.

> If a task would hand-edit `openapi.yml`, STOP. The change belongs in `spec/`. The YAML is a build artifact that happens to be committed (so consumers can fetch it by raw URL at a tag).

<!-- END SOURCE docs/ai/rules/contract-first.md -->


<!-- SOURCE docs/ai/rules/deploy.md SHA256 4eb255d7eb46f57cbe0350e8cf090692f1a1a073d276a0ad9b2e2f727b6c82df -->

# Deploy model (Prism mock → Docker → VPS)

> Loaded per-command by `/ship-contract` (`docs/ai/rules/deploy.md`).

The contract is delivered as a **static Prism mock** packaged into a Docker image and deployed directly on a VPS at `http://IP:PORT` (no nginx, no TLS). This is appropriate for development/staging mocks — the mock is stateless, read-only, and returns only contract-defined shapes.

## Architecture

```
[local machine]                   [ghcr.io]                [VPS]
openapi.yml + Dockerfile ──build──► image ──push──► pull ──► docker run
  (static Prism mock)           ghcr.io/<owner>/          -p PORT:PORT
                                <repo>-mock:<vX.Y.Z>      -h 0.0.0.0
                                                           │
                          backend + frontend ◄── http://IP:PORT
```

## Invariants

- **Agent never SSH-es.** The script builds and pushes locally; the user runs the VPS command.
- **Image tag = contract tag.** `ghcr.io/<owner>/<repo>-mock:<vX.Y.Z>` tracks the version; consumers know exactly what schema they're hitting.
- **Static mode only.** Deterministic responses from `examples` in the schema. No `-d` flag.
- **`-h 0.0.0.0` is required** in the Prism CMD — without it the mock is unreachable from outside the container.
- **`-m false` (single-process) is required** in the Prism CMD inside Docker — prism 5's default multiprocess mode reads `cluster.isPrimary`, which is `undefined` in a container, crashing at startup with `Cannot read properties of undefined (reading 'isPrimary')`. Local `npm run mock` is unaffected (it runs Prism directly via Node, not multiprocess).
- **`GITHUB_PERSONAL_ACCESS_TOKEN`** must have `write:packages` scope for `docker push` to `ghcr.io`. Never print or log the token.

## Readiness gate

`bash scripts/check_ready.sh` must pass before packaging. It verifies: compile + drift + lint + examples + endpoints registry + Prism smoke + breaking + artifact presence + auth endpoints. A contract that fails this gate is not ready for consumers.

## Security notes

- Direct `IP:PORT` is appropriate for dev/staging mocks (no auth required — contracts describe only shape, not secrets).
- If the ghcr.io package is private, the VPS needs `docker login ghcr.io` before `docker pull`.
- For production-adjacent environments: add TLS termination and IP allowlisting.

<!-- END SOURCE docs/ai/rules/deploy.md -->


<!-- SOURCE docs/ai/rules/endpoint-surface.md SHA256 8f2b93e6b310cc36b740ecb40e0e0503c717fbc0a98165a190a502f27b26189a -->

# Endpoint surface — page vs resource vs system (frontend-page separation)

> Loaded per-agent by `ba`, `api-architect`, `tsp-author`, `contract-reviewer`, `docs-writer`. New dimension (ADR 0010).

The contract is consumed by two repos with **different jobs**: `claude-django` implements every backend endpoint; `claude-react-mui` builds the browser SPA. The frontend must know **which endpoints deserve a page/route and which are pure machinery** — so it never scaffolds a UI page for a service-to-service or internal endpoint (e.g. `POST /api/v1/auth/token`). Every contract entry therefore declares its **surface**.

## The dimension: `x-surface`

| Value | Meaning | Path convention | Frontend (`claude-react-mui`) | Backend (`claude-django`) |
|---|---|---|---|---|
| `resource` | Frontend-facing data/API endpoint — the SPA calls it (from a page or transport code) | under `/api/v1/...` | generates a typed client; MAY be surfaced by a page | implements it |
| `system` | Machinery NOT surfaced to the browser — S2S (client-credentials), internal/ops/health, webhooks | under `/api/v1/...` | never builds a page; never calls it from app code | implements it |
| `page` | A frontend page/route of the SPA itself | NOT under `/api/v1/` (e.g. `/products`, `/login`) | scaffolds a page/route; lists the operations it `consumes` | not its concern |

- **One `x-surface` per entry.** Every `/api/v1/...` operation declares `resource` or `system`. Every page-map entry is `page`.
- `system` answers the core concern directly: *the frontend must not build a page for it.* The canonical example is `POST /api/v1/auth/token` (service-to-service — a browser can never hold a client secret; `docs/ai/rules/auth-contract.md`).
- Judgment calls (e.g. `auth/refresh`, `auth/logout`) are frontend-facing transport, so they are `resource` with simply **no page** in the page-map — not `system`. A project may mark transport-only endpoints `system` if it prefers; document the choice.

## "Both a page and data" → a **pair**, never a dual flag

A resource usually has both a UI page and a data endpoint. Do **not** overload one operation with two surfaces. Model it as **two linked entries on two paths** (the disambiguating convention the user asked for):

- data: `GET /api/v1/products` — `x-surface: resource`, `operationId: listProducts`
- page: `/products` — `x-surface: page`, `consumes: ["listProducts"]`

Many-to-many: a page may `consume` several operations (a detail+edit page consumes `getArticle` + `updateArticle`); a resource may back several pages or none. A `system` endpoint is **never** the target of a page's `consumes`.

## Where each surface lives (page-map is separate — ADR 0010)

- `resource` / `system` endpoints live in the canonical `openapi.yml` `paths:` (as today) and carry `@extension("x-surface", "...")` in TypeSpec → emitted as `x-surface` on the operation. They are also recorded in `.claude/memory/endpoints.json` with a `surface` field.
- **`page` entries are NOT in `openapi.yml` `paths:`.** A browser route is not an HTTP API operation, so it stays out of the REST contract — Prism/oasdiff/Spectral see only `/api/v1/*`. The page-map is its own committed artifact: `.claude/memory/pages.json` (optionally surfaced for humans as an `x-pages` block in `docs/api/INDEX.md`). Each page references the API operations it consumes by `operationId`.

## Registry shapes

`.claude/memory/endpoints.json` — each entry gains `surface`:
```
{ "method": "GET", "path": "/api/v1/articles", "...": "...", "surface": "resource" }
```

`.claude/memory/pages.json` — the page-map:
```
[ { "route": "/articles/{id}", "name": "Article detail", "surface": "page",
    "consumes": ["getArticle"], "auth": "bearer", "notes": "..." } ]
```

## Agent duties

- `ba` — for each resource, state the **intended pages** (does the SPA show this? which screens?) and which endpoints are machinery.
- `api-architect` — assign `x-surface` to every `/api/v1` operation; design the page-map; record both registries. The contract is incomplete until each operation has a surface and the page-map reflects the SPA.
- `tsp-author` — emit `@extension("x-surface", "resource" | "system")` on every operation.
- `contract-reviewer` — block any `/api/v1` operation missing `x-surface`; verify no page `consumes` a `system` operation; verify page routes are not under `/api/v1/`.
- `docs-writer` — `docs/api/INDEX.md` separates **Pages** from **API (resource/system)**; mark each API row's surface.

## Enforcement (enabled — ADR 0010)

Both gates are **active** (severity error). A derived project not yet ready to classify its endpoints may set the Spectral rule `recommended: false` to stage the rollout:

- **Spectral** `operation-x-surface-required` (`.spectral.yaml`): every operation must declare `x-surface ∈ {resource, system}` (`docs/ai/rules/spectral-style.md`). Runs in `npm run lint` — CI Gate 2 + the pre-commit hook.
- **`check_endpoints_registry.mjs`** (`npm run check:endpoints` — CI verification step + the pre-push hook): every operation's `x-surface` is present, valid, and equals its `surface` in `endpoints.json`; every `pages.json` `consumes` target exists and is not `system`; no `page` route sits under `/api/v1/`.

`contract-reviewer` still reviews surface *intent*; these gates make the mechanics non-negotiable.

<!-- END SOURCE docs/ai/rules/endpoint-surface.md -->


<!-- SOURCE docs/ai/rules/environment.md SHA256 c6675ad3c80d00d00df8002a4317c4702ac73fc3b1ed8d84e367b4c05c6d70b9 -->

# Environment specification (source of truth)

Defines the **expected local environment** for a `claude-api-contract` project. `/doctor` checks the live machine against this and proposes fixes.

> Philosophy: detect → report → propose → **fix only after the user confirms**. `/doctor` reads `.claude/memory/env-detect.json`, never auto-fixes risky things, never pushes to `main`, never prints secrets.

## Scope 1 — System tools

Bash on Linux / macOS / WSL2 Ubuntu — the **tested/recommended** path. Native Windows is **best-effort**: Claude Code runs the Bash tool through **Git Bash** (Git for Windows), so the `.sh` gate scripts execute, but there is no OS-level Bash-tool sandbox and the path is less tested (`docs/decisions/0001-drop-windows-native-shell.md`, superseded by `docs/decisions/0009-allow-best-effort-windows-git-bash.md`). Windows-native **PowerShell/cmd** remain unsupported — they cannot run the bash gates. Prefer WSL2 when you need sandboxing or Docker parity.

| Requirement | Expected | Check |
|---|---|---|
| **Node.js (HARD)** | 20.19+ (22 LTS recommended) on PATH | `node --version`; runs the hook, gate helpers, TypeSpec/Spectral/Prism |
| **npm (HARD)** | bundled with Node; matching the chosen runtime | `npm --version` |
| git | present | `git --version` |
| GitHub CLI | present in the chosen host runtime | `gh --version` |
| **Claude Code CLI** | WSL2/Linux/macOS → `which claude` is `/home/...` or `/usr/...` (never `/mnt/c/...`); native Windows → Windows-native install, Git Bash on PATH | install: `npm i -g @anthropic-ai/claude-code`, or the native Windows installer |
| **oasdiff** | on PATH (breaking-change gate) | `oasdiff --version` |
| Docker (OPTIONAL) | only for containerized Prism / proxy parity | `docker info` |

`.claude/memory/env-detect.json` is the source of truth for `platform_supported` / `node_supported` / `gh.*`. It is rewritten by `scripts/detect-env.mjs` on every session. **Never hand-write it** to skip a blocker.

## Scope 2 — Claude config & access

| Requirement | Expected | Check |
|---|---|---|
| Plugins baseline | `superpowers@superpowers-marketplace`, `github@claude-plugins-official`, `context7@claude-plugins-official`, `family-core@claude-family-marketplace` (auto-enabled in `.claude/settings.json`; the family marketplace auto-registers via `extraKnownMarketplaces`) | `local CLI/official-docs fallback` vs `enabledPlugins` |
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

## P04 runtime transition

Python 3.13+ stdlib tooling and both Claude/Codex launchers are delivered locally. Optional plugins/MCP are not prerequisites for local procedures: gh/Git provide repository operations and official documentation is the library-reference fallback. Do not grant trust or install plugins automatically. Run detector explicitly and check current tools; stale legacy JSON is not operational evidence. Shared detector/candidate runner and CI choice materialization remain P05/P06. Native Windows uses PowerShell orchestration and explicit C:/Program Files/Git/bin/bash.exe for Bash commands; platform labels above do not establish sandbox isolation.

<!-- END SOURCE docs/ai/rules/environment.md -->


<!-- SOURCE docs/ai/rules/examples-validation.md SHA256 6953007dfa20ecc0cfe6f2f170a3ae9a9da6899a46a6a3d13235ccc8f81489b2 -->

# Examples (validated; feed the mock)

> Loaded by `mock-validator`, `docs-writer`, `tsp-author` (agents) and `/validate-contract`, `/fix-ci` (commands).

`examples/**` holds request/response examples that (a) feed Prism's static mock and (b) double as documentation. They must always be valid against the schema.

## Rules

- Every example validates against its schema. Inline `example`/`examples` in `openapi.yml` are checked by Spectral (`scripts/check_examples.sh`); standalone files under `examples/**` are checked by Prism's two-way validation in the mock smoke test.
- Prefer **realistic** values over `"string"` / `0`. Use `x-faker` annotations in the schema for dynamic-mode realism (`docs/ai/rules/prism-mock.md`).
- One representative example per significant response (success + the common errors), so the mock and the docs cover the real shapes.
- An example is never a stub. If an endpoint's example is missing because the schema is incomplete, that is a `spec/` task — fix the schema, do not fake the example (`docs/ai/rules/no-stubs.md`).

> `mock-validator` owns example completeness; `docs-writer` references examples from `docs/api/INDEX.md`.

<!-- END SOURCE docs/ai/rules/examples-validation.md -->


<!-- SOURCE docs/ai/rules/git-operations.md SHA256 fabab4b6eb28267d58eb66c453f9440e8789717483e167ba03448b1a7678c275 -->

# Git operations (PR-only, GitHub is the source of truth)

## Iron rules

1. **NEVER commit directly to `main`.** Branch → PR → review → merge. `git push origin main` and `git push --force` are denied in `.claude/settings.json`.
2. **One logical change per PR.** A contract change and its regenerated `openapi.yml` go together in the same commit (drift gate).
3. **Conventional-ish branch names:** `feat/<resource>`, `fix/<thing>`, `chore/<thing>`, `docs/<thing>`.
4. **Run git from the host shell when the repo is on `/mnt/...`** (WSL2 bind-mount quirk); never remove index.lock automatically, regardless of size or age.

## Commit hygiene

- Commit `spec/` and the regenerated `openapi.yml` **together**. Never one without the other.
- Output language for commit messages / PR descriptions follows `output-language.md` (if present), except code identifiers, paths, and tokens which stay English.

## Releases

- Releases are **git tags** `vX.Y.Z` (`docs/ai/rules/versioning.md`), created via `/release` after all gates are green. Tags are pushed; `main` is moved only by merged PRs.

## PR checklist (enforced by review)

- [ ] `npm run validate` green (compile + drift + lint + examples + endpoints registry).
- [ ] `npm run breaking` classified; semver bump stated in the PR description.
- [ ] `docs/api/INDEX.md` updated; for a user-facing / contract change, a `CHANGELOG.md` `## [Unreleased]` fragment added (ADR 0007).
- [ ] No hand-edit of `openapi.yml` (it must equal `spec/` output).

## Session finalization

Authorized commit/push/PR proceed with exact task-owned paths after real checks. Merge requires a new explicit user command; releases/tags/deploy remain separate. Preserve foreign staged/unstaged/untracked files, refs, stash and worktrees. No automatic stash, reset, clean or force push. Pending PR is MERGE_PENDING.

<!-- END SOURCE docs/ai/rules/git-operations.md -->


<!-- SOURCE docs/ai/rules/living-plan.md SHA256 162ed419da61246343e78b3db512bf3ca95277cb2324973280a57b9851a02ce7 -->

# Living plan (execution log per feature)

Non-trivial work gets a plan file `docs/plans/NNNN-<slug>.md` that lives and breathes through the pipeline.

## Structure

- **Goal / scope** — what this change does and explicitly does not do.
- **Steps** — the pipeline stages with the files each touches.
- **Risks** — breaking-change risk, consumer impact, open questions.
- **Execution log** — append-only; each agent adds **one line** when its phase finishes.

## Rules

- Create a reviewable plan before nontrivial changes when needed; an already-authorized plan remains authorized across sessions.
- After finishing a phase, each agent appends a one-line confirmation to the **Execution log** via an `Edit` append — never a full-file rewrite (concurrent phases must not clobber each other):
  > `phase done: tsp-author — spec/articles.tsp + openapi.yml recompiled`
- The plan is the single place to see "where we are" mid-feature; `/wrap-up` folds it into `docs/WORKLOG.md` and refreshes `docs/HANDOFF.md`.

<!-- END SOURCE docs/ai/rules/living-plan.md -->


<!-- SOURCE docs/ai/rules/mcp-stack.md SHA256 f95c283a700b2f8b1dfefc5bc357fc2e3ef0476c517029b5cfb74de7ea0c1cb3 -->

# MCP stack & docs verification

> Loaded per-agent by `api-architect`, `tsp-author`, `contract-reviewer`, `breaking-change-analyst`, `docs-writer`.

## Servers (committed baseline)

- **github** — PRs, releases, branch protection. From the official plugin `github@claude-plugins-official` (or the `.mcp.json` fallback — never both).
- **context7** — up-to-date library docs. From `context7@claude-plugins-official` (or fallback).

Manage installs with `/plugins`; secrets (`GITHUB_PERSONAL_ACCESS_TOKEN`, `CONTEXT7_API_KEY`) live in `.env` only (gitignored).

## Verify before you author (hard expectation)

The toolchain (TypeSpec emitter, Spectral rules, Prism flags, oasdiff flags, `openapi-typescript`) moves fast. Before writing TypeSpec, designing a rule, or stating a tool flag, **verify the current API/flags via available official documentation (context7 when connected)** rather than relying on memory. A spec authored against a stale emitter API wastes a whole pipeline pass.

- `tsp-author` — verify `@typespec/*` decorators and emitter options.
- `api-architect` / `contract-reviewer` — verify OpenAPI 3.1 + Spectral rule semantics.
- `docs-writer` — verify oasdiff `changelog` flags.

## Layer boundaries — superpowers plugin vs repo rules

`superpowers` ships **process technique**; repo rules own **domain invariants**. Expected active skills here: `brainstorming` (socratic probing BEFORE `ba`/`api-architect` design), `writing-plans`/`executing-plans` (planning technique — `docs/ai/rules/living-plan.md` adds the domain artifact: `docs/plans/NNNN-*.md` + append-only Execution log), `verification-before-completion` (prove-before-done discipline — complements, never replaces, `docs/ai/rules/verification.md` and its `endpoints.json`/verify docs), `dispatching-parallel-agents`, `writing-skills`.

- `devil` agent vs `brainstorming` skill: different phases — brainstorming probes before a design exists; `devil` attacks a drafted design. Keep both.
- Inert in a spec-only repo (accepted): TDD, systematic-debugging, using-git-worktrees, finishing-a-development-branch, subagent-driven-development.
- Contract-integrity invariants (gates, envelopes, drift) live only in repo rules and agent bodies — never delegated to plugin skills.

## Local fallback and credentials

Plugins are optional adapters. Use gh/Git for repository operations and official library documentation for API verification. Use local docs/ai/workflows for audit, template-sync, handoff, wrap-up and language selection. Credentials remain runtime-specific; no values in shared files. Existing .mcp.json and personal settings are preserved.

<!-- END SOURCE docs/ai/rules/mcp-stack.md -->


<!-- SOURCE docs/ai/rules/no-stubs.md SHA256 92056a5215e9bfb1bd4e50cfe82ecc080e95a9a2cd3b79d161307c9be3a39bc5 -->

# No stubs, no fakes in the contract

The contract is a promise. A stub is a broken promise that looks kept.

## Rules

- **No placeholder endpoints, fields, or schemas** "to be filled later". If a shape is unknown, it is a `ba`/`api-architect` question, not a guessed schema.
- **No fake examples.** Every example is valid against its schema and represents a real response (`docs/ai/rules/examples-validation.md`).
- **No hand-edited `openapi.yml`.** The YAML is emitted from `spec/`; editing it by hand is a stub of the source (`docs/ai/rules/contract-first.md`).
- **No empty `@doc`.** Spectral requires real descriptions; "TODO" text is a stub.

## If you must mark something incomplete

Use an explicit, greppable marker and log it, never a silent fake:

```
// STUB: <what is missing and why> — owner: <agent>, follow-up: <issue/plan ref>
```

A `STUB:` is a visible debt, surfaced in review and tracked in the living plan. A silent placeholder is forbidden.

<!-- END SOURCE docs/ai/rules/no-stubs.md -->


<!-- SOURCE docs/ai/rules/node-commands.md SHA256 f4e4e808cdfa72322f127003cbf9064144629b358d84e97b5e369ac30f193abc -->

# Node / toolchain commands

> **Shell:** use Bash for Bash gates; native Windows uses explicit Git Bash launched from PowerShell. Python tooling also runs directly in PowerShell. Historical OS support is superseded for measured tooling paths by docs/ai/runtime-compatibility.md.
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

## Derived-project ownership

Class B is an upstream-only classification: spec/examples/OpenAPI/registries/local ADRs are project-owned in derived projects. Never run reset-to-clone during install/update/bootstrap. Preview personalization; preserve project notes, generated adapters and canonical source metadata.

<!-- END SOURCE docs/ai/rules/node-commands.md -->


<!-- SOURCE docs/ai/rules/preflight.md SHA256 78c67e2cd0442b2cbab14ce8789bab6f0293abe16fbb452b00bf5b996c4b171d -->

# Project-kickoff preflight (hard gate)

Before any contract work on a new project, verify the inputs and access exist. Spec consumed by `/preflight` and the `ba` kickoff gate.

## Runtime gate (FIRST, hard STOP)

Read `.claude/memory/env-detect.json` (produced by an explicit node scripts/detect-env.mjs run or the compatible legacy hook).

- **Missing** → `NO_ENV_DETECT`: STOP. The runtime is unverified. Run `node scripts/detect-env.mjs` once manually; if that fails, install Node 20.19+. Never hand-write the file.
- **`platform_tier == "unsupported"`** → `UNSUPPORTED_PLATFORM`: hard STOP. Native Windows without a POSIX `bash`/`git` on PATH, or a runner we cannot execute the bash gates on. Install Git for Windows (Git Bash) or WSL2 Ubuntu, then relaunch.
- **`platform_tier == "best-effort"`** (native Windows + Git Bash) → WARN, do not STOP. Gate scripts run through Git Bash; there is **no OS-level Bash-tool sandbox** (`sandbox_available == false`) and this path is less tested than Linux/macOS/WSL2. Recommend WSL2 for sandbox/Docker parity. The legacy boolean `platform_supported` stays `true` here.
- **`node_supported == false`** → STOP. Install Node 20.19+ (`scripts/setup-wsl.sh`).

## Build-input gate (CRITICAL items)

| Item | Check | Missing → |
|---|---|---|
| Maturity stage | `PROJECT.md` records `demo / prototype / PoC / MVP / production` | `ba` asks the user; do NOT assume a stage |
| Definition of Done | `PROJECT.md` §7 has standard gates checked off AND project-specific criteria stated (not blank) | `ba` / `brief-synthesizer` must surface this for explicit team agreement before work starts |
| Project brief | `PROJECT.md` / `docs/**` describe the API's purpose & resources | `ba` returns questions; do NOT invent resources |
| Toolchain | `node`, `npm`, TypeSpec/Spectral/Prism installed | `bash scripts/install.sh` |
| oasdiff | on PATH (breaking gate) | install per `scripts/setup-wsl.sh` |
| GitHub access | `gh auth status` ok; repo reachable | fix auth; never print secrets |
| Documentation access | context7 when connected, otherwise official documentation | Report unavailable reference access for the affected task |

If a CRITICAL item is missing, STOP — do not start the feature pipeline. Report a checklist; fix access or ask the user. Never print secret values.

## P04 runtime transition

Python 3.13+ stdlib tooling and both Claude/Codex launchers are delivered locally. Optional plugins/MCP are not prerequisites for local procedures: gh/Git provide repository operations and official documentation is the library-reference fallback. Do not grant trust or install plugins automatically. Run detector explicitly and check current tools; stale legacy JSON is not operational evidence. Shared detector/candidate runner and CI choice materialization remain P05/P06. Native Windows uses PowerShell orchestration and explicit C:/Program Files/Git/bin/bash.exe for Bash commands; platform labels above do not establish sandbox isolation.

<!-- END SOURCE docs/ai/rules/preflight.md -->


<!-- SOURCE docs/ai/rules/prism-mock.md SHA256 9d41147b9d4bca8c56288f8e0be5b4621ef0fc28db921272974028a380b3c991 -->

# Prism mock & two-way validation

> Loaded per-agent by `mock-validator`. Gates: mock smoke + example validation. Command: `/mock`.
> **Invariants live here; run commands and `x-faker` recipes live in the `prism-mock` skill.**

Prism turns `openapi.yml` into a live mock server and validates requests/responses against the schema — so the frontend can develop against the contract before any backend exists.

## Invariants

- **Two-way validation is the gate.** Prism validates both the incoming request and the outgoing response against the schema; that single behavior covers the "mock smoke" gate and reinforces the "example validation" gate.
- **Static mode is the default** — deterministic responses from `examples`; use it for tests. Dynamic mode (Faker + `x-faker`) exists to check the frontend is not brittle to data variation; proxy mode contract-tests a live API (optional, staging parity).
- **In Docker, `-h 0.0.0.0` and `-m false` are both REQUIRED** — otherwise unreachable from outside the container / crash at startup (`docs/ai/rules/deploy.md`).
- Default port from `PRISM_PORT` (`.env`), fallback `4010`.
- The richer the `examples` / ranges / validation keywords in the schema, the closer the mock is to the real API — that is `mock-validator`'s motivation to keep examples complete (`docs/ai/rules/examples-validation.md`).

> Activate the `prism-mock` skill for run commands and `x-faker` recipes.

<!-- END SOURCE docs/ai/rules/prism-mock.md -->


<!-- SOURCE docs/ai/rules/project-maturity.md SHA256 09b66e9748308c4864f5312e6158cbdb2fb56ac6369e68dac3dd9753b4fc8eb4 -->

# Project maturity stage (process scaler)

Declare the project's maturity stage before any contract work starts. The stage scales
**process depth** — pipeline completeness, `devil` usage, review rigour, example
completeness. It does **not** gate-skip or relax contract integrity.

## Taxonomy

| Stage | One-line definition |
|---|---|
| **demo** | Throwaway show of concept; disposable after the meeting. |
| **prototype** | Exploratory shape; no real consumers, may break freely. |
| **PoC** | Validates a specific technical hypothesis; short-lived. |
| **MVP** | First real release; real consumers approaching; contract is a promise. |
| **production** | Live contract consumed by real services; every change has cost. |
| **other** | Treated as **MVP** until clarified. |

## Process matrix (CI gates always ON — see below)

| Stage | Pipeline | `devil` | `contract-reviewer` | Examples expected | Breaking-change attention | semver |
|---|---|---|---|---|---|---|
| **demo** | `ba`(light)→`api-architect`→`tsp-author`→`mock-validator`→`docs-writer` | skip | skip / optional | 1 happy-path per endpoint | low (usually pre-tag) | 0.x, fast |
| **prototype** | + `contract-reviewer` | skip | yes (light pass) | happy + 1–2 key errors | low | 0.x |
| **PoC** | full | optional | yes | happy + typical errors | medium | 0.x |
| **MVP** | full | recommended | yes (full) | success + all typical errors | high (enforced) | semver discipline |
| **production** | full, `devil` first | mandatory | full + adversarial | exhaustive (all status codes) | strict; breaking → ADR | strict semver |
| **other** | as MVP until clarified | — | — | — | — | — |

## Invariants — NEVER overridden by stage

**The 5 CI gates (TypeSpec drift · Spectral lint · example validation · breaking-change · Prism
mock smoke) and `@doc` on every model/property/operation are ALWAYS ON, regardless of stage.**
A stage modulates process depth and completeness — it does not touch contract integrity.
A missing `@doc`, a fake example, or a hand-edited `openapi.yml` is always forbidden
(`docs/ai/rules/no-stubs.md`, `docs/ai/rules/contract-first.md`).

## Where the stage lives

The stage is recorded in `PROJECT.md` (see `templates/PROJECT.md`). If `PROJECT.md` does not
state a stage, `ba` / `brief-synthesizer` must emit an **Open Question**; the orchestrator
asks via `AskUserQuestion` (options: demo / prototype / PoC / MVP / production / other).
Never assume a stage.

## How to read the matrix

- **Pipeline:** agents in the column are the minimum expected; add more if the contract
  complexity warrants it regardless of stage.
- **`devil`:** "skip" means the orchestrator may omit it by default; the user may always
  invoke it explicitly.
- **Examples:** a count here is a floor, not a ceiling — always add examples for error
  shapes that consumers would branch on (`docs/ai/rules/examples-validation.md`).
- **Breaking-change:** "low" relaxes urgency of semver precision, not the gate itself
  (`docs/ai/rules/breaking-changes.md`). ERR-level changes always require a MAJOR bump.

> First action on any task: read `PROJECT.md` for the declared stage. No stage → Open
> Question before proceeding. Scale the pipeline against the matrix; never silently skip
> an invariant (`docs/ai/rules/workflow.md`, `docs/ai/rules/preflight.md`).

<!-- END SOURCE docs/ai/rules/project-maturity.md -->


<!-- SOURCE docs/ai/rules/spectral-style.md SHA256 f0a3797168aeba3be4d40c27251572892f098cbb8bd4a39648e0981701915512 -->

# Spectral linting (layered ruleset, enforced)

> Loaded by `contract-reviewer` (agent) and `/validate-contract`, `/review-pr`, `/fix-ci` (commands). Gate: `npm run lint`.
> **Norms live here; rule-crafting recipes live in the `spectral-lint` skill.**

`.spectral.yaml` is a **layered** ruleset — not a copy of someone else's. It `extends: [[spectral:oas, all]]` — intentionally minimal, so extending it is mandatory, not optional — and adds custom rules for this repo's naming / codes / envelope. Custom rules may stage a gradual rollout in derived projects via `recommended: true/false`.

## What the layer must enforce (beyond the minimal `spectral:oas`)

- **Property casing** — snake_case (or the chosen repo convention), consistently.
- **`operationId` present, unique, and casing-consistent** (it becomes a consumer symbol).
- **`summary` + `description` + at least one `tag`** on every operation.
- **`x-surface` on every operation** — `resource` or `system`; the frontend page-vs-system separation, gate `operation-x-surface-required` (`docs/ai/rules/endpoint-surface.md`).
- **Error responses declared** — every operation lists the error envelope responses it can return (`docs/ai/rules/api-envelope.md`).
- **No anonymous inline objects** in schemas — named components only.
- **`example`/`examples` validate against schema** (built-in `oas3-valid-schema-example`, `oas3-valid-media-type-examples`) — this is also the examples gate (`scripts/check_examples.sh`).

> Activate the `spectral-lint` skill for crafting order, rule syntax, run commands, and borrowed-rule sources (Zalando / DigitalOcean).

<!-- END SOURCE docs/ai/rules/spectral-style.md -->


<!-- SOURCE docs/ai/rules/typespec-style.md SHA256 17609cd734d19f798ef3eb1add0e24c1121af832390cbf8f56fec4b7d46eecf9 -->

# TypeSpec authoring style (source of openapi.yml)

> Loaded per-agent by `tsp-author` and `contract-reviewer` (not in the global import block).
> **Norms live here; syntax recipes live in the `typespec-authoring` skill.**

`spec/**/*.tsp` is the source. `openapi.yml` is its emitted output. Author the spec well and the YAML is clean by construction.

## Layout

- `spec/main.tsp` — entry point (analogous to `index.ts`): the `@service` decorator, global `@server`, security, and `import`s of the other files. Roughly one `import` per resource file.
- `spec/auth.tsp` — auth endpoints (`docs/ai/rules/auth-contract.md`).
- `spec/models/` — shared, reusable models and the envelopes (list / error — `docs/ai/rules/api-envelope.md`). Lift anything shared to this folder (Azure approach: shared shapes live as library-level units).
- One file per resource (`spec/articles.tsp`, ...). Keep files focused; split when a file grows past ~300 lines.

## Conventions

- **OpenAPI 3.1 output** (decision D4).
- **`@route` plural nouns** under a versioned prefix: `/api/v1/articles`. Action = HTTP method, never a verb in the path.
- **Stable `operationId`** for every operation — it becomes a consumer symbol; renaming it is breaking (`docs/ai/rules/breaking-changes.md`).
- **`@doc` everywhere** — every model, property, and operation gets a description (Spectral enforces it).
- **`@summary` + tags** on operations; group by resource tag.
- **`x-surface` on every operation** (`resource` / `system`), emitted via `@extension` (`docs/ai/rules/endpoint-surface.md`).
- **camelCase OR snake_case for JSON properties — pick one repo-wide and never mix.** Default: snake_case (matches the DRF consumer's default and reduces backend adaptation).
- **Reusable models, not inline anonymous objects** — inline objects produce unusable nested types downstream. Name every shape.
- **Named enums** → map to clean TS unions.
- **Explicit status codes & error responses** on every operation (`@error`, the shared error envelope).

## Versioning in TypeSpec

TypeSpec has built-in version annotations. On a breaking reset you can rebase the spec to a base version and continue numbering — but the **delivery** version is still the git tag (`docs/ai/rules/versioning.md`). Keep TypeSpec versioning and the git-tag semver consistent.

## After editing

Recompile and bundle (commands: `docs/ai/rules/node-commands.md` or the skill), then commit `spec/` **and** the regenerated `openapi.yml` together. Never one without the other (drift gate — `docs/ai/rules/contract-first.md`).

> Activate the `typespec-authoring` skill for concrete syntax. Verify current TypeSpec/emitter APIs via context7 before writing (`docs/ai/rules/mcp-stack.md`).

<!-- END SOURCE docs/ai/rules/typespec-style.md -->


<!-- SOURCE docs/ai/rules/verification.md SHA256 74c27d1486ae8fbe7eaee96eaf4ecdbe81041987dedc440678d9f046fa0fedf0 -->

# Verification handoff (prove the contract works)

Every pipeline run ends with a verification handoff so a human can confirm the contract behaves as designed — without reading TypeSpec.

## Machine-readable endpoint registry

`api-architect` records each endpoint in `.claude/memory/endpoints.json` (committed — it is the registry, not session-local state). One object per endpoint:

```
{ "method": "POST", "path": "/api/v1/articles", "tag": "articles",
  "operationId": "createArticle", "auth": "bearerAuth",
  "scopes": ["articles:write"], "statuses": [201, 400, 401, 403, 429],
  "envelope": "single|list", "surface": "resource", "notes": "..." }
```

Append/update; never duplicate a `method+path`. Each entry also carries a `surface` (`resource`/`system`); frontend page routes live in the sibling `.claude/memory/pages.json` page-map (`docs/ai/rules/endpoint-surface.md`). The contract is incomplete until the registry entry exists.

## Verification doc

`docs-writer` generates `docs/verify/<feature>.md`: a Prism + `curl` checklist derived from `endpoints.json` + `openapi.yml`, so the user can:

1. `npm run mock` and hit each endpoint with the documented request.
2. Confirm the response matches the contract (Prism validates both directions).
3. Tick off status codes and the auth/scope behavior.

Regenerate on demand with `/verify`.

## What "verified" means here

- `npm run validate` green (compile + drift + lint + examples + endpoints registry).
- `npm run breaking` classified, semver bump stated.
- Prism mock comes up and returns valid responses for the new endpoints.
- `endpoints.json` and `docs/api/INDEX.md` reflect reality.

<!-- END SOURCE docs/ai/rules/verification.md -->


<!-- SOURCE docs/ai/rules/versioning.md SHA256 d8542372ef69b0f3654fe64bec3161517c3be644b1e1237e8cdde8bb1eef4e75 -->

# Versioning & delivery (semver on git tags)

> **Policy lives here; step-by-step release/pin recipes live in the `contract-versioning` skill.**

The contract is delivered as **git tags** (`vX.Y.Z`) plus the raw `openapi.yml` URL. Consumers pin a version; they never track a moving branch.

## Semver rules (decision #6 / D3)

| Bump | When | Gate |
|---|---|---|
| **major** (`vX+1.0.0`) | any backward-incompatible change | forced by the breaking-change gate (oasdiff `--fail-on ERR`, `docs/ai/rules/breaking-changes.md`) |
| **minor** (`vX.Y+1.0`) | new endpoint or new optional field — backward compatible | — |
| **patch** (`vX.Y.Z+1`) | descriptions, examples, fixes that do not change the wire shape | — |

## Delivery to consumers

- Canonical fetch: `https://raw.githubusercontent.com/VadayI/claude-api-contract/<tag>/openapi.yml`.
- Each consumer commits a pin so git + CI can see it (not just an env var, which is gitignored):
  - `CONTRACT_REPO=https://github.com/VadayI/claude-api-contract`
  - `CONTRACT_VERSION=vX.Y.Z`
  - recommended form: a committed `contract.lock.json` (`repo` + `version` + `path` + `sha256` of the vendored copy) next to the vendored `openapi.yml`.
- **Bumping the pin is a deliberate PR in the consumer**, never an automatic drift.

## Consumer sync-gate (their side, summarized here)

Each consumer runs a `scripts/check_contract_sync.sh` that pulls `openapi.yml@CONTRACT_VERSION` from `CONTRACT_REPO` and diffs it (or sha256) against the vendored copy — RED if they diverge (someone hand-edited the vendored file, or the tag was moved). Full chain of integrity: `contract@tag → vendored openapi.yml → generated types / validated implementation`.

## Releasing (this repo)

Use `/release [version]`: rebuild `openapi.yml`, run all gates, update `CHANGELOG.md` (oasdiff changelog), tag, push the tag. Never tag a contract that is RED on any gate.

> Activate the `contract-versioning` skill for the release + consumer-pinning recipe.

<!-- END SOURCE docs/ai/rules/versioning.md -->


<!-- END ROLE PACK contract-reviewer -->
