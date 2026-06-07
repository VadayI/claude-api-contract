# TODO (rolling)

## Now — close out PR #2 (feat/etap-3-examples-ci-mock)
- [ ] Wait for `contract-ci` green on PR #2 (`gh pr checks 2 --watch`).
- [ ] Merge PR #2 (`gh pr merge 2 --merge --delete-branch`); `git switch main && git pull`.
- [ ] Enable required status check `contract-ci` on `main` via full PUT to `.../branches/main/protection` (keep reviews count 0).

## Next — release v0.1.0
- [ ] `/release v0.1.0` from `main` (rebuild, gates green, CHANGELOG via oasdiff changelog, tag `v0.1.0`, push tag). First tag → breaking gate baseline established.
- [ ] Confirm raw URL resolves: `https://raw.githubusercontent.com/VadayI/claude-api-contract/v0.1.0/openapi.yml`.

## Etap 4 — invert consumers (separate repos, after v0.1.0)
- [ ] `claude-django`: validate impl vs contract; pull + `scripts/check_contract_sync.sh`; pin `CONTRACT_VERSION=v0.1.0` (+ `contract.lock.json`).
- [ ] `claude-react-mui`: Bearer + refresh-flow; `api:pull` (`openapi-typescript`) from contract@v0.1.0; sync-gate.

## Cosmetic follow-ups (small PR, non-blocking)
- [ ] OAuth2 scope descriptions (empty map) — add in `spec/models/security.tsp`, not in YAML.
- [ ] Replace mock `tokenUrl` / `@server` (`http://localhost:4010`) with the real server when it exists.
- [ ] Optional: a `last-page` list example once Spectral/AJV null-example bug is fixed upstream (track version).
