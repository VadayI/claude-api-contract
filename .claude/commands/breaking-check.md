---
model: sonnet
description: "[claude-api-contract] Run oasdiff vs the previous tag and classify changes; state the required semver bump."
---

Detect breaking changes against a base ref (default: latest `v*` tag) and decide the semver bump. Delegates analysis to `breaking-change-analyst`.

## Log
```bash
node scripts/log-cmd.mjs /breaking-check "$ARGUMENTS"
```

## Input
Optional `$ARGUMENTS`: a base ref (tag/branch/commit). Default: latest `v*` tag.

## Steps

0. **Runtime gate** (env-detect.json). Confirm `oasdiff` is on PATH; if missing → STOP with the install hint (`scripts/setup-wsl.sh`).

1. Run the gate:
   ```bash
   npm run breaking            # or: bash scripts/check_breaking.sh $ARGUMENTS
   ```

2. Dispatch `breaking-change-analyst` to classify each diff (@.claude/rules/breaking-changes.md) and produce:
   - the required semver bump (major/minor/patch) + the rule forcing it;
   - a per-change breaking/non-breaking table;
   - consumer-impact notes for `claude-django` / `claude-react-mui`.

3. If a breaking change is intended: propose the `.oasdiff-ignore.txt` entry + an ADR — never weaken the gate.

4. Report. If clean/non-breaking → suggest `/create-pr`. If breaking → confirm the major bump plan before `/release`.
