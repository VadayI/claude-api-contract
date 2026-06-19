# ADR 0010 — Endpoint surface classification (page vs resource vs system)

**Status:** accepted · **Date:** 2026-06-19

## Context
The contract is consumed by two repos (Variant A): `claude-django` implements the backend; `claude-react-mui` builds the browser SPA and generates a typed client. Nothing in the contract told the frontend **which endpoints deserve a UI page and which are pure machinery**. A naive code generator would scaffold a page for every operation — including service-to-service endpoints like `POST /api/v1/auth/token`, which a browser must never call (it cannot hold a client secret; @.claude/rules/auth-contract.md). The request: at the contract stage, separate "frontend page" endpoints from "backend" endpoints.

Two complications surfaced during design:

- A single resource is often **both** a page and a data endpoint (a "products" page AND a products data API). A single dual-valued flag cannot express that cleanly.
- A browser route (`/products`) is **not** an HTTP API operation. Modeling it as one in `openapi.yml` `paths:` would pollute the REST tooling — Prism would mock it, oasdiff would score it as an API change, Spectral would lint it as an operation.

## Decision
Introduce a first-class **`x-surface`** dimension with three values, disambiguated by **path convention**:

| Value | Path | Meaning |
|---|---|---|
| `resource` | `/api/v1/...` | frontend-facing data/API endpoint (SPA calls it; may be surfaced by a page) |
| `system` | `/api/v1/...` | machinery NOT surfaced to the browser (S2S, internal/ops, webhooks) — never gets a page |
| `page` | not under `/api/v1/` | a frontend page/route of the SPA itself |

- **"Both" is modeled as a pair, not a dual flag**: data `GET /api/v1/products` (`resource`) + page `/products` (`page`, `consumes: ["listProducts"]`). Many-to-many between pages and operations.
- **The page-map lives separately from `paths:`** (page-map-separate, chosen over in-`paths` operations and over a flag-only model). `resource` / `system` operations carry `@extension("x-surface", ...)` and a `surface` field in `.claude/memory/endpoints.json`; `page` entries live in a new committed `.claude/memory/pages.json`, referencing operations by `operationId`. REST tooling continues to see only `/api/v1/*`.
- Full rule: @.claude/rules/endpoint-surface.md.

Rollout is **staged**. This slice ships the model: the rule, the registries, the agent duties, the docs, and a worked example in the demo contract. The **enforcement gates** (a Spectral rule requiring `x-surface` on every operation, introduced as `recommended: true`; a `check_endpoints_registry.mjs` cross-check of surface ↔ `x-surface` and `consumes` integrity) are a deliberate follow-up so derived projects are not turned RED before they adopt the field. Until then `contract-reviewer` enforces by reading.

## Alternatives considered
- **Binary `x-surface: ui | system`** — rejected: cannot express a resource that is both data and a page, and conflates "no page" with "not frontend-facing".
- **`x-audience: browser | service`** — rejected: maps poorly onto transport-only endpoints (`refresh` is browser-called but has no page).
- **Pages as real operations under a non-`/api/v1` prefix in `paths:`** — rejected: pollutes Prism / oasdiff / Spectral; a browser route is semantically not an HTTP operation.

## Consequences
- The contract now states intent: `claude-react-mui` scaffolds pages **only** from `pages.json`; `claude-django` implements `resource` + `system`. A page is never generated for a `system` endpoint.
- Two committed registries instead of one (`endpoints.json` + `pages.json`); both are session-permanent template methodology (kept on derive, like ADRs 0005–0009 — not the demo-contract ADRs 0002–0004).
- `endpoints.json` gains a `surface` field; the existing `check_endpoints_registry.mjs` is unaffected (it keys on `METHOD path`), so adding the field is non-breaking.
- Adopting projects must classify each endpoint and declare pages; the staged gates make this a warning, then an error, on the project's own timeline.

## Update — 2026-06-19 (enforcement enabled)
The staged gates from the Decision are now **active**:
- Spectral rule `operation-x-surface-required` (`.spectral.yaml`, severity error, `recommended: true`) — `x-surface ∈ {resource, system}` on every operation.
- `check_endpoints_registry.mjs` extended to cross-check `x-surface` presence/validity, registry `surface` ↔ `x-surface` consistency, and page-map integrity (`consumes` resolves and is not `system`; no `page` route under `/api/v1/`).

Both run in CI (`npm run lint` Gate 2 + the `check:endpoints` verification step) and locally via the husky pre-commit / pre-push hooks. A derived project may stage adoption by setting the Spectral rule `recommended: false`.
