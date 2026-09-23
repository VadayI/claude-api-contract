# Shared detector and exact-candidate runner (P05 slice)

`scripts/ai/detector.py` emits a versioned local capability report. It records
platform/tool versions and explicit Git identity/status counts, but never records
environment values, reads secret files, changes trust, installs tools or contacts a
service intentionally. Missing and failed probes remain `MISSING` or
`NOT_VERIFIED`.

`scripts/ai/runner.py` requires full candidate and base commit IDs and requires
the base to be an ancestor. It uses `git archive` to create a separate pristine
export for every check, rejecting links and unsafe archive paths. Dirty, staged,
untracked, or earlier-check mutations cannot enter a later check. Each command is
an argv array and runs with `shell=False` and an allowlisted child environment.
Archive extraction preserves only Git's regular-file executable bit; snapshots
bind both file content and executable state, so chmod-only mutation is visible.

```text
python scripts/ai/detector.py --repository . --output .ai-runtime/environment.json
python scripts/ai/runner.py --repository . \
  --candidate FULL_COMMIT_SHA --base FULL_BASE_SHA \
  --catalog templates/ai/checks/contract.json \
  --output .ai-runtime/results/full.json
```

Results must be new files below the repository's `.ai-runtime`; linked ancestors,
existing output paths and escaping locations are rejected before checks run.
Evidence directories are run-unique and created beside the reserved no-follow
staging file. Complete JSON is flushed and synced before an exclusive atomic
same-filesystem link claims the final path. Any failure after reservation removes
that run's matching staging/final inode and evidence so the same output can retry.

The result binds candidate/base commits and trees, catalog, runner, detector and
schema digests, declared configuration/lockfile digests, environment facts,
timestamps, exact statuses, exit metadata and sanitized relative evidence paths.
Evidence redacts prefixed credential assignments, authorization headers,
credential-bearing URLs and host paths; each stored stream is bounded to 64 KiB
and marks truncation explicitly. Expected artifacts must be newly created or
changed contained regular files; their content digests are recorded, while stale
files, links and missing artifacts fail. Candidate mutations are compared with a
before/after snapshot and must be explicitly allowed.

The closed schema enumerates every emitted result field and exact SHA/digest
syntax. Runtime semantic validation additionally requires complete execution
metadata for PASS/FAIL, mutually exclusive nonzero-exit versus timeout evidence,
complete identities for available tools/repositories, exact effective runner
inputs, and presence-aware invalidation digests. Empty effective digest maps and
partial executed results cannot be finalized.

`FAIL` returns 1. A missing mandatory prerequisite/evidence returns 2 and
`NOT_VERIFIED`; it never becomes PASS. Mandatory `NOT_APPLICABLE` also prevents
PASS unless the catalog explicitly enables that policy. Current implementation
paths use `NOT_VERIFIED` when absent. Dependencies must name preceding checks;
failed, unverified, or skipped dependencies cannot yield PASS.

The initial contract catalog intentionally invokes only current production,
adapter and owner-local core drift gates. TypeSpec, Spectral, examples, breaking,
Prism, policy, scheduled audit, React and Django commands still require the full
workflow-step inventory and environment provisioning in later P05 slices. This
slice does not yet provide network TTL policy, derived/scaffold applicability,
cross-repository generated-artifact comparison, streaming capture limits before
sanitization, or cross-platform descendant-process-tree cleanup after timeout.
It does not claim one-source local/GitHub execution or P05 completion.
