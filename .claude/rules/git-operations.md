# Git operations (PR-only, GitHub is the source of truth)

## Iron rules

1. **NEVER commit directly to `main`.** Branch → PR → review → merge. `git push origin main` and `git push --force` are denied in `.claude/settings.json`.
2. **One logical change per PR.** A contract change and its regenerated `openapi.yml` go together in the same commit (drift gate).
3. **Conventional-ish branch names:** `feat/<resource>`, `fix/<thing>`, `chore/<thing>`, `docs/<thing>`.
4. **Run git from the host shell when the repo is on `/mnt/...`** (WSL2 bind-mount quirk); the SessionStart hook clears only stale *empty* `index.lock` files.

## Commit hygiene

- Commit `spec/` and the regenerated `openapi.yml` **together**. Never one without the other.
- Output language for commit messages / PR descriptions follows `output-language.md` (if present), except code identifiers, paths, and tokens which stay English.

## Releases

- Releases are **git tags** `vX.Y.Z` (@.claude/rules/versioning.md), created via `/release` after all gates are green. Tags are pushed; `main` is moved only by merged PRs.

## PR checklist (enforced by review)

- [ ] `npm run validate` green (compile + drift + lint + examples).
- [ ] `npm run breaking` classified; semver bump stated in the PR description.
- [ ] `docs/api/INDEX.md` + `CHANGELOG.md` updated.
- [ ] No hand-edit of `openapi.yml` (it must equal `spec/` output).
