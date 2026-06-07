# TODO (rolling)

## Done ✅
- [x] Merge PR #2 (feat/etap-3-examples-ci-mock) → `main`.
- [x] Release `v0.1.0` — tag + GitHub Release. Raw URL: `https://raw.githubusercontent.com/VadayI/claude-api-contract/v0.1.0/openapi.yml`
- [x] Встановити `oasdiff` (`v1.18.4`; `~/.local/bin`).

## Now — branch protection (CI gate)
- [ ] Wire `contract-ci` до branch-protection на `main` (full PUT `required_status_checks.contexts=["contract-ci"]`, `required_approving_review_count=0`). Після цього `--admin` більше не потрібен.

## Etap 4 — invert consumers (separate repos, after v0.1.0)
- [ ] `claude-django`: validate impl vs contract; pull + `scripts/check_contract_sync.sh`; pin `CONTRACT_VERSION=v0.1.0` (+ `contract.lock.json`).
- [ ] `claude-react-mui`: Bearer + refresh-flow; `api:pull` (`openapi-typescript`) from contract@v0.1.0; sync-gate.

## Cosmetic follow-ups (small PR, non-blocking)
- [ ] OAuth2 scope descriptions (empty map) — add in `spec/models/security.tsp`, not in YAML.
- [ ] Replace mock `tokenUrl` / `@server` (`http://localhost:4010`) with the real server when it exists.
- [ ] Optional: a `last-page` list example once Spectral/AJV null-example bug is fixed upstream (track version).
