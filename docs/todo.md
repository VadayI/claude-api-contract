# TODO (rolling)

## Now — close out PR #1 (feat/contract-first-slice)
- [ ] Commit `package-lock.json` to the PR (reproducible `npm ci` in CI). `git add package-lock.json && git commit -m "chore: pin dev toolchain via package-lock.json" && git push`
- [ ] Verify branch protection on `main` is enabled (PR + status checks) so PR-only holds.
- [ ] Review & merge PR #1.

## Etap 3 (next slice / PR)
- [ ] `examples/**` request/response examples + `x-faker` annotations for realistic dynamic mock.
- [ ] `.github/workflows/contract-ci.yml` — 5 gates: TypeSpec drift, Spectral lint, examples, oasdiff breaking, Prism mock smoke.
- [ ] Prism mock smoke test (mock comes up + returns valid responses).
- [ ] `docs/verify/<feature>.md` via `/verify` (Prism + curl checklist from `endpoints.json`).
- [ ] Release `v0.1.0` via `/release` (rebuild, gates green, CHANGELOG, tag, push) — only after gates are green.

## Cosmetic follow-ups (small PR, non-blocking)
- [ ] OAuth2 scope descriptions (currently empty map) — add in `spec/models/security.tsp` (`OAuth2Scope` with descriptions), not in YAML.
- [ ] Replace mock `tokenUrl` / `@server` (`http://localhost:4010`) with the real server when it exists.

## Later (separate repos, after v0.1.0)
- [ ] Invert consumer `claude-django` (validate impl vs contract; pull + sync-gate; pin `CONTRACT_VERSION`).
- [ ] Invert consumer `claude-react-mui` (Bearer + refresh-flow; `api:pull` from contract; sync-gate).
