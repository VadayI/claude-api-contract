---
name: oasdiff-breaking
description: "[claude-api-contract] oasdiff CLI recipes — breaking-gate invocations, err-ignore, changelog generation, tag comparison. Activate for the breaking-change gate, /breaking-check, or release changelog. Classification policy (ERR table, major-bump rule) lives in .claude/rules/breaking-changes.md."
---

# oasdiff — recipes

> Policy (what is breaking, ERR→major, ignore→ADR) — `.claude/rules/breaking-changes.md`; this skill is the CLI how-to.

## Breaking gate

```bash
oasdiff breaking <base.yaml> <revision.yaml> --fail-on ERR     # exit 1 on ERR = major gate
oasdiff breaking <base> <revision> --fail-on WARN              # stricter, advisory runs
bash scripts/check_breaking.sh [base-ref]                      # vs latest v* tag
```

GitHub Action (`oasdiff-action`) declined — ADR 0008 (PR comments require oasdiff Pro); use the pinned CLI.

## Consciously allowed breaking

```bash
oasdiff breaking <base> <rev> --fail-on ERR --err-ignore .oasdiff-ignore.txt
```

List specific changes only; the gate stays active for everything else (ADR required — see the rule).

## Changelog

```bash
oasdiff changelog <base> <revision>            # human-readable diff for CHANGELOG.md
```

## Comparison bases

```bash
git show vX.Y.Z:openapi.yml > /tmp/base.yml    # previous tag as base
```

- Handles renamed path params; can exclude description-only diffs; tracks `x-*` extensions.
