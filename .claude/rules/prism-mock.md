# Prism mock & two-way validation

> Loaded per-agent by `mock-validator`. Gates: mock smoke + example validation. Command: `/mock`.

Prism turns `openapi.yml` into a live mock server and validates requests/responses against the schema — so the frontend can develop against the contract before any backend exists.

## Modes

- **static** (default) — responses come from `examples` in the schema. Deterministic; use this for tests.
- **dynamic** (`-d`, `npm run mock:dynamic`) — Faker-generated responses. Use to check the frontend is not brittle to data variation.
- **`x-faker`** — a custom schema field that controls dynamic generation of specific properties (e.g. `x-faker: name.firstName`). Add it to `examples/**` schemas for realistic dynamic mocks.
- **proxy** (`prism proxy`) — contract-test a live API against the schema (optional, for staging parity).

## Two-way validation

Prism validates **both** the incoming request and the outgoing response against the schema. That single behavior covers the "mock smoke" gate (mock comes up and returns a valid response) and reinforces the "example validation" gate.

## Operational notes

- Default port from `PRISM_PORT` (`.env`), fallback `4010`.
- In Docker, run with `-h 0.0.0.0` or the mock is unreachable outside the container.
- Live-reloads on `openapi.yml` change.
- The richer the `examples` / ranges / validation keywords in the schema, the closer the mock is to the real API — that is `mock-validator`'s motivation to keep examples complete.

> Activate the `prism-mock` skill for command recipes.
