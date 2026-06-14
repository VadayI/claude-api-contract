# Examples (validated; feed the mock)

> Loaded by `mock-validator`, `docs-writer`, `tsp-author` (agents) and `/validate-contract`, `/fix-ci` (commands).

`examples/**` holds request/response examples that (a) feed Prism's static mock and (b) double as documentation. They must always be valid against the schema.

## Rules

- Every example validates against its schema. Inline `example`/`examples` in `openapi.yml` are checked by Spectral (`scripts/check_examples.sh`); standalone files under `examples/**` are checked by Prism's two-way validation in the mock smoke test.
- Prefer **realistic** values over `"string"` / `0`. Use `x-faker` annotations in the schema for dynamic-mode realism (@.claude/rules/prism-mock.md).
- One representative example per significant response (success + the common errors), so the mock and the docs cover the real shapes.
- An example is never a stub. If an endpoint's example is missing because the schema is incomplete, that is a `spec/` task — fix the schema, do not fake the example (@.claude/rules/no-stubs.md).

> `mock-validator` owns example completeness; `docs-writer` references examples from `docs/api/INDEX.md`.
