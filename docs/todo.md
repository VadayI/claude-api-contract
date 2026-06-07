# TODO (rolling)

## Done ✅
- [x] Merge PR #2 (feat/etap-3-examples-ci-mock) → `main`.
- [x] Release `v0.1.0` — tag + GitHub Release.
- [x] Встановити `oasdiff` (`v1.18.4`; `~/.local/bin`).
- [x] Wire `contract-ci` до branch-protection на `main` (required check).
- [x] Etap 4 claude-django: merge PR #12–#16 + branch protection ON.
- [x] Etap 4 react-mui PR1 (#10): contract-source + sync-gate + todos→articles. MERGED.
- [x] Etap 4 react-mui PR2 (#12): Bearer + refresh-flow. MERGED ✅ (CI Quality Gates GREEN).
- [x] Etap 4 повністю завершено — обидва консумери пінять v0.1.0.

## Follow-ups (non-blocking, без пріоритету)
- [ ] react-mui PR3: 429 + Retry-After backoff у transport.
- [ ] react-mui PR4: `npm run mock` (Prism проти vendored openapi.yml).
- [ ] claude-django: власний CI воркфлоу + required status check на `main`.
- [ ] claude-django: `contract.lock.json`/sha256 (наразі tag-pin only).
- [ ] claude-react-mui: branch protection на `main`.
- [ ] contract-repo: OAuth2 scope descriptions (`spec/models/security.tsp`).
- [ ] contract-repo: реальний `@server`/`tokenUrl` (коли backend з'явиться).
- [ ] contract-repo: `last-page` list example (після Spectral/AJV null-bug fix).
