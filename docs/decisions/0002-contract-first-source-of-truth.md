# ADR 0002 — Contract-first source of truth (Variant A)

**Status:** accepted · **Date:** 2026-06-06

## Context
Previously the contract was generated in the backend (`drf-spectacular`), coupling the contract to the implementation and serializing the two teams.

## Decision
`claude-api-contract` owns the canonical, language-neutral `openapi.yml` (OpenAPI 3.1), authored in TypeSpec and emitted to one flat bundled file. `claude-django` and `claude-react-mui` **consume** it; neither generates it. A contract change is a deliberate PR here, delivered as a semver git tag; consumers pin `CONTRACT_VERSION`.

## Consequences
- Backend and frontend start in parallel (frontend against the Prism mock, backend against the spec).
- Breaking changes are a first-class CI gate (two consumers).
- Consumers add a sync-gate verifying their vendored copy matches the pinned tag.
