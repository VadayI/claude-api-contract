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
- `system` answers the core concern directly: *the frontend must not build a page for it.* The canonical example is `POST /api/v1/auth/token` (service-to-service — a browser can never hold a client secret; `.claude/rules/auth-contract.md`).
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

- **Spectral** `operation-x-surface-required` (`.spectral.yaml`): every operation must declare `x-surface ∈ {resource, system}` (`.claude/rules/spectral-style.md`). Runs in `npm run lint` — CI Gate 2 + the pre-commit hook.
- **`check_endpoints_registry.mjs`** (`npm run check:endpoints` — CI verification step + the pre-push hook): every operation's `x-surface` is present, valid, and equals its `surface` in `endpoints.json`; every `pages.json` `consumes` target exists and is not `system`; no `page` route sits under `/api/v1/`.

`contract-reviewer` still reviews surface *intent*; these gates make the mechanics non-negotiable.
