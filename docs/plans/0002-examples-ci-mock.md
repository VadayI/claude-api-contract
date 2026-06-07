# Plan 0002 — Etap 3: examples, CI, mock

## Goal / scope
Add validated request/response examples + `x-faker` to the contract, a 5-gate CI workflow, a Prism mock smoke test, and a verification handoff. Does NOT change endpoint shapes (no breaking changes). One PR.

## Steps (files)
- api-architect — example/x-faker matrix (design only).
- tsp-author + mock-validator (subagent) — `spec/auth.tsp`, `spec/articles.tsp` (`@opExample` + `@extension x-faker`) → `openapi.yml`; `examples/**`; `scripts/check_mock.sh` + `package.json` (`mock:smoke`).
- CI — `.github/workflows/contract-ci.yml` (drift, lint, examples, oasdiff breaking, mock smoke).
- docs-writer — `docs/verify/etap-3.md`, `docs/api/INDEX.md`, `CHANGELOG.md`, `docs/lessons.md`.

## Risks
- Examples gate strictness (`--fail-severity warn`). → authored to 0 warnings.
- Spectral/AJV null-example crash → list example uses URLs, not null.
- oasdiff absent in sandbox → breaking verified in CI/host; first release SKIPs.

## Execution log
- phase done: api-architect — example/x-faker matrix designed (10 ops).
- phase done: tsp-author+mock-validator — spec/ examples + x-faker, openapi.yml recompiled, check_mock.sh, gates green.
- phase done: docs-writer — verify/etap-3.md, INDEX.md, CHANGELOG, lessons.md.
- phase done: contract-reviewer — validate + mock:smoke re-run GREEN independently; no stubs; tsp-output gitignored.
