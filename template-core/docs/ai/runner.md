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
  --event pull_request --network disabled \
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

The closed standalone schema enumerates every emitted result field and exact
SHA/digest syntax. Its versioned `oneOf`/`not`/`if`/`then` contracts independently reject
partial PASS/FAIL/executed-NV evidence, PASS with a nonzero exit, ambiguous FAIL
exit/timeout states, execution evidence on unexecuted NA/NV, incomplete AVAILABLE tool or
repository identities, and inconsistent present/absent digest records. The
bundled offline schema validator implements those draft-2020-12 constructs plus
nonempty digest-map and exact evidence-cardinality constraints. Runtime semantic
validation repeats the critical relations before finalization, so schema-only
acceptance is not mistaken for a weaker validation tier.

`FAIL` returns 1. A missing mandatory prerequisite/evidence returns 2 and
`NOT_VERIFIED`; it never becomes PASS. Mandatory `NOT_APPLICABLE` also prevents
PASS unless the catalog explicitly enables that policy. Current implementation
paths use `NOT_VERIFIED` when absent. Dependencies must name preceding checks;
failed, unverified, or skipped dependencies cannot yield PASS.

The versioned run context binds the explicit event, candidate/base commits and
trees, a sorted exact Git diff, its digest, and the network policy. An absent or
unavailable base remains an input error; push/manual execution never invents
`HEAD~1`. Typed predicates are fail closed. In particular, missing `spec/` is
`NOT_APPLICABLE` only for the identified upstream `claude-api-contract` scaffold;
it is `NOT_VERIFIED` for a derived package.

Node gates provision with `npm ci --ignore-scripts` in each check's own pristine
candidate export. `node_modules` is never reused. A runtime npm content cache may
seed a private per-check cache only when its key binds the exact lock digest,
Node/npm versions, reviewed registry, empty user/global npm configuration,
operating system and architecture. Freshness requires `0 <= age <= TTL`; linked,
future-dated, expired or malformed entries are
ignored. The result records that key, reuse decision, offline/allowed policy,
TTL/created-at/age, argv, duration and outcome. Offline is the CLI default.
On Windows the literal Node `--use-system-ca` mode validates system and enterprise
certificate chains without inheriting caller-controlled Node options; the selected
CA mode is bound into the npm cache identity and result evidence.
`--network` governs provisioning and commands declaring `external`; disabled
external commands are not started. `none` and `loopback` are reviewed command
declarations, not an operating-system packet sandbox, and results say so. A
registry/tool/cache/service miss is `NOT_VERIFIED`, never PASS. Reviewed exit 75
lets a started wrapper report unavailable infrastructure without converting an
assertion failure into NOT_VERIFIED.

`{run_context}` and `{base_export}` are separate argv-token placeholders. They
expose canonical exact context and a pristine exact-base export without Git refs,
environment fallbacks or shell interpolation. Both are snapshotted; mutation
fails the check. Catalog v2 binds the exact 55-row inventory digest and count and
rejects any pending inventory disposition.

`contract.json` executes the existing three source drift checks plus TypeSpec
generated-byte drift, Spectral, examples, exact-base oasdiff, supervised Prism,
endpoint registry, TODO/ADR/CHANGELOG and README-version policies. `react.json`
maps all quality/build/E2E workflow gates through the reviewed React wrapper.
TypeSpec output is compared to candidate `openapi.yml`; missing, linked, or
different output fails. Every command runs without shell concatenation, and an
owned Windows Job Object or POSIX process group is terminated after every check,
including when the leader exits first. Output is captured to bounded temporary
files, so descendant-held pipes cannot cause unbounded `communicate()` waits.

`workflow-inventory.json` machine-maps all 55 observed workflow steps. Runnable
source gates point to stable catalog IDs. Provisioning, trigger and reporting
steps retain explicit orchestration/context/reporting classifications. No row is
pending or omitted. Django rows bind the reviewed PR #41 IDs, and React rows bind
the reviewed full catalog IDs. Missing environment-specific external tooling,
browser or network remains explicit NOT_VERIFIED evidence rather than a false
PASS. GitHub workflow adoption can consume the same catalogs without changing
their local machine contract.
