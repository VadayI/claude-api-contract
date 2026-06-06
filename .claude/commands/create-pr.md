---
model: sonnet
description: "[claude-api-contract] Open a PR for the current contract change with gates green and the semver bump stated."
---

Open a Pull Request for the current branch. PRs only — never push to `main` (@.claude/rules/git-operations.md).

## Log
```bash
node scripts/log-cmd.mjs /create-pr "$ARGUMENTS"
```

## Steps
0. **Runtime + branch gate.** On a feature branch, not `main`. Working tree has only intended changes.
1. **Gates green (hard):** `npm run validate` (drift + lint + examples) and `npm run breaking` classified. RED → STOP and fix.
2. **Docs:** `docs/api/INDEX.md` + `CHANGELOG.md` updated (dispatch `docs-writer` if not).
3. **Commit** `spec/` + regenerated `openapi.yml` together. Push the branch.
4. **Open PR** via `gh pr create` with a description from `docs-writer`: what changed, **semver bump**, consumer impact, gate results, verification doc link.
5. Report the PR URL. Suggest `/review-pr`.
