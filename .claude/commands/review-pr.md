---
model: fable
description: "[claude-api-contract] Review a contract PR — consistency, naming, codes, envelopes, breaking analysis."
---

Review a contract Pull Request before merge. Delegates to `contract-reviewer` and `breaking-change-analyst`.

## Log
```bash
node scripts/log-cmd.mjs /review-pr "$ARGUMENTS"
```

## Input
Optional `$ARGUMENTS`: a PR number/URL. Default: the PR for the current branch (`gh pr view`).

## Steps
1. Fetch the diff (`gh pr diff`).
2. Dispatch `contract-reviewer`: drift, Spectral, envelopes, auth/scopes, status codes, no hand-edited YAML, registry updated (@.claude/rules/spectral-style.md, @.claude/rules/api-envelope.md).
3. Dispatch `breaking-change-analyst`: oasdiff classification + required semver bump (@.claude/rules/breaking-changes.md).
4. Post a structured review (blocking vs non-blocking) via `gh pr review`. Block on any RED gate or un-bumped breaking change.
