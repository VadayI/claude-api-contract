---
name: prism-mock
description: "[claude-api-contract] Running the Prism mock server with two-way validation, static vs dynamic mode, and x-faker. Activate for mock smoke tests or example debugging."
---

# Prism Mock

## Run
```bash
npm run mock                 # static (examples) on $PRISM_PORT (default 4010)
npm run mock:dynamic         # dynamic (Faker + x-faker)
npx prism mock openapi.yml -p 4010
npx prism mock openapi.yml -d -p 4010        # dynamic
npx prism proxy openapi.yml https://api...   # contract-test a live API (optional)
```

## Static vs dynamic
- **static** — deterministic, from `examples`. Use for tests.
- **dynamic (-d)** — Faker-generated; checks the frontend is not brittle to variation.

## x-faker
```yaml
properties:
  first_name:
    type: string
    x-faker: name.firstName
```
Controls dynamic generation per property.

## Two-way validation
Prism validates request AND response against the schema — covers the mock-smoke and example-validation gates at once.

## Notes
- In Docker: `prism mock -h 0.0.0.0 -m false ...` — `-h 0.0.0.0` makes it reachable outside the container; `-m false` (single-process) is REQUIRED: Prism 5's default multiprocess mode reads `cluster.isPrimary` (undefined in a container) and crashes. See `deploy.md` / `Dockerfile`.
- Live-reloads on openapi.yml change.
- Smoke test: bring it up, hit each endpoint with the documented request, expect a 2xx valid body and the documented error codes.
