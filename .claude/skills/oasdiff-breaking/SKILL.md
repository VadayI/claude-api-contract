---
name: oasdiff-breaking
description: "[claude-api-contract] Detecting breaking changes and generating a changelog with oasdiff. Activate for the breaking-change gate, /breaking-check, or release changelog."
---

# oasdiff (breaking changes + changelog)

## Breaking gate
```bash
oasdiff breaking <base.yaml> <revision.yaml> --fail-on ERR     # exit 1 on ERR = major gate
oasdiff breaking <base> <revision> --fail-on WARN              # stricter
bash scripts/check_breaking.sh [base-ref]                      # vs latest v* tag
```
Official Action: `oasdiff/oasdiff-action/breaking`.

## Consciously allowed breaking
```bash
oasdiff breaking <base> <rev> --fail-on ERR --err-ignore .oasdiff-ignore.txt
```
List specific allowed changes; keep the gate active for everything else. Record an ADR.

## Changelog (for CHANGELOG.md)
```bash
oasdiff changelog <base> <revision>            # human-readable diff
```

## Classification cheatsheet
- Breaking (ERR → major): remove/rename endpoint/field/enum, optional→required request field, type/format change, tighten validation.
- Non-breaking (minor/patch): add endpoint, add optional request field, add response field, relax constraint, description/example edits.

## Notes
- Handles renamed path params; can exclude description-only diffs; tracks `x-*` extensions.
- Compare the previous git tag's `openapi.yml` (`git show vX.Y.Z:openapi.yml`) against the working tree.
