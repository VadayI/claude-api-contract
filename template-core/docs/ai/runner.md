# Shared detector and exact-candidate runner (P05 slice)

`scripts/ai/detector.py` emits a versioned local capability report. It records
platform/tool versions and explicit Git identity/status counts, but never records
environment values, reads secret files, changes trust, installs tools or contacts a
service intentionally. Missing and failed probes remain `MISSING` or
`NOT_VERIFIED`.

`scripts/ai/runner.py` requires full candidate and base commit IDs and requires
the base to be an ancestor. It uses `git archive` to export only committed files
to a temporary directory, rejecting links and unsafe archive paths. Dirty,
staged and untracked working-copy data cannot enter the executed candidate. Each
command is an argv array and runs with `shell=False` and an allowlisted child
environment.

```text
python scripts/ai/detector.py --repository . --output .ai-runtime/environment.json
python scripts/ai/runner.py --repository . \
  --candidate FULL_COMMIT_SHA --base FULL_BASE_SHA \
  --catalog templates/ai/checks/contract.json \
  --output .ai-runtime/results/full.json
```

The result binds candidate/base commits and trees, catalog/runner digests,
declared invalidation file digests, environment facts, timestamps, exact statuses,
exit codes and sanitized relative evidence paths. Evidence is credential/path
redacted, bounded to 64 KiB per stream and marks truncation explicitly. `FAIL`
returns 1. A missing mandatory prerequisite/evidence returns 2 and
`NOT_VERIFIED`; it never becomes PASS. A declared applicability miss is
`NOT_APPLICABLE`. Dependencies must name preceding checks; failed or unverified
dependencies cannot yield PASS.

The initial contract catalog intentionally invokes only current production,
adapter and owner-local core drift gates. TypeSpec, Spectral, examples, breaking,
Prism, policy, scheduled audit, React and Django commands still require the full
workflow-step inventory and environment provisioning in later P05 slices. This
slice does not yet provide network TTL policy, derived/scaffold applicability,
generated-artifact comparison, or cross-platform descendant-process-tree cleanup
after timeout. It does not claim one-source local/GitHub execution or P05
completion.
