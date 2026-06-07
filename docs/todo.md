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
- [x] Release `v0.1.1` — tag + GitHub Release (2026-06-07). Patch: production server + tokenUrl.

## Follow-ups (non-blocking, без пріоритету)
- [x] Push CHANGELOG commit до origin/main — DONE (main = origin/main після PR #8).
- [ ] react-mui PR3: 429 + Retry-After backoff у transport.
- [ ] react-mui PR4: `npm run mock` (Prism проти vendored openapi.yml).
- [ ] claude-django: власний CI воркфлоу + required status check на `main`.
- [ ] claude-django: `contract.lock.json`/sha256 (наразі tag-pin only).
- [ ] claude-react-mui: branch protection на `main`.
- [ ] contract-repo: OAuth2 scope descriptions — заблоковано: TypeSpec 1.x `@typespec/http` не підтримує `description` на `OAuth2Scope`; відкрити issue upstream або дочекатися нової версії.
- [x] contract-repo: реальний `@server`/`tokenUrl` — DONE (PR #6, production placeholder `https://api.example.com`).
- [ ] contract-repo: `last-page` list example — заблоковано: Spectral/AJV null-nullable-3.1 bug ще присутній; STUB-коментар у `spec/articles.tsp:108`.
