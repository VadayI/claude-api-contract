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
5. **The contract describes its own auth** (`/auth/*`) so the mock can issue tokens and a frontend can log in autonomously before any backend endpoint exists (@.claude/rules/auth-contract.md).

## What is NOT a build output

- TS types — `claude-react-mui` generates them via `openapi-typescript`.
- Python models — `claude-django` validates its implementation against the contract; it generates nothing.

> If a task would hand-edit `openapi.yml`, STOP. The change belongs in `spec/`. The YAML is a build artifact that happens to be committed (so consumers can fetch it by raw URL at a tag).
