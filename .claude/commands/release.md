---
model: sonnet
description: "[claude-api-contract] Cut a release — rebuild openapi.yml, run all gates, update CHANGELOG, tag vX.Y.Z, push the tag."
---

Cut a versioned contract release. A tag is the delivery unit consumers pin (@.claude/rules/versioning.md). **Never tag a RED contract.**

## Log
```bash
node scripts/log-cmd.mjs /release "$ARGUMENTS"
```

## Input
Optional `$ARGUMENTS`: the target version `vX.Y.Z`. If empty, derive it from the breaking-change classification (major/minor/patch off the latest tag) and confirm via `AskUserQuestion`.

## Steps

0. **Runtime gate** (env-detect.json) + **branch gate**: release tags are cut from a clean, merged `main`; confirm working tree clean and on the intended ref. Never `git push origin main`.

1. **Rebuild + validate (hard gate).**
   ```bash
   npm run api:compile && npm run api:bundle
   npm run validate          # drift + lint + examples
   ```
   Any RED → STOP.

2. **Breaking classification.** `npm run breaking`; dispatch `breaking-change-analyst`. Confirm the version bump matches (breaking ⇒ major).

3. **Changelog.** Dispatch `docs-writer`: `oasdiff changelog <prev-tag> openapi.yml` → prepend a `CHANGELOG.md` entry (flag breaking items + bump). Update `docs/api/INDEX.md` if endpoints changed.

4. **Tag + push the tag** (not main):
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
   Optionally `gh release create vX.Y.Z --notes-file <changelog-excerpt>`.

5. Report the tag, the raw URL consumers will pin, and the bump rationale.
