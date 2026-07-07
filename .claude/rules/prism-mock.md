# Prism mock & two-way validation

> Loaded per-agent by `mock-validator`. Gates: mock smoke + example validation. Command: `/mock`.
> **Invariants live here; run commands and `x-faker` recipes live in the `prism-mock` skill.**

Prism turns `openapi.yml` into a live mock server and validates requests/responses against the schema — so the frontend can develop against the contract before any backend exists.

## Invariants

- **Two-way validation is the gate.** Prism validates both the incoming request and the outgoing response against the schema; that single behavior covers the "mock smoke" gate and reinforces the "example validation" gate.
- **Static mode is the default** — deterministic responses from `examples`; use it for tests. Dynamic mode (Faker + `x-faker`) exists to check the frontend is not brittle to data variation; proxy mode contract-tests a live API (optional, staging parity).
- **In Docker, `-h 0.0.0.0` and `-m false` are both REQUIRED** — otherwise unreachable from outside the container / crash at startup (`.claude/rules/deploy.md`).
- Default port from `PRISM_PORT` (`.env`), fallback `4010`.
- The richer the `examples` / ranges / validation keywords in the schema, the closer the mock is to the real API — that is `mock-validator`'s motivation to keep examples complete (`.claude/rules/examples-validation.md`).

> Activate the `prism-mock` skill for run commands and `x-faker` recipes.
