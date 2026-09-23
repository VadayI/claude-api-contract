# Family core — development source

This directory is the planned shared-core source in the API-contract repository.
The P09 resolver was developed independently of runtime pilot P03. The measured
pilot is now accepted with documented runtime limitations. The delivery decision
is [ADR 0001](docs/ai/decisions/0001-portable-family-core.md). P04 contract
structure is reviewable, while the P05 exact runner and source-capability capsule
are documented in [runner.md](docs/ai/runner.md). The complete 55-step inventory
is machine-mapped; entries without reviewed shared implementations remain
explicitly `NOT_VERIFIED_PENDING`, so P05 and downstream integration are not yet
claimed complete.

Project configuration and instruction catalog schemas now have an offline
standard-library validator; see [machine contracts](docs/ai/schemas.md) for its
supported vocabulary, policy checks and CLI. This does not create project settings
or claim operational evidence. Shared [launchers](docs/ai/launchers.md) now provide
explicit environment initialization and PowerShell/Bash wrappers; existing stack
entry-point migration remains pending. The [runtime compatibility matrix](docs/ai/runtime-compatibility.md)
records measured support, optional MCP mappings and unverified capabilities.
The [shared adapter generator](docs/ai/adapter-generation.md) preserves full source
rules and checks ownership before updating outputs, including explicit legacy
pilot migration. Stack installer integration remains a separate acceptance step.

Python 3.13+ is required; only its standard library is used. This adds no runtime
dependency to a React, Django or contract application.

```text
python -m unittest discover -s template-core/tests -p "test_*.py"
python template-core/scripts/ai/detector.py --repository .
python template-core/scripts/ai/runner.py --repository . --candidate FULL_SHA --base FULL_SHA --catalog template-core/templates/ai/checks/contract.json --output .ai-runtime/results/full.json
python template-core/scripts/ai/readiness.py profile.json
python template-core/scripts/ai/readiness.py profile.json --evidence evidence.json
```

The first CLI form prints a deterministic checklist, not a readiness verdict.
The evidence form returns 0 for READY/READY_WITH_LIMITATIONS, 1 for NOT_READY,
and 2 for NOT_VERIFIED or invalid configuration. Neither form deploys or starts
services. Inputs and referenced proof paths must be non-secret.

## Profile

```json
{
  "stage": "poc",
  "target": "vps_smoke",
  "kind": "react",
  "exposure": "private",
  "data": "synthetic",
  "features": [],
  "phase": "pre_deploy",
  "artifact": "sha256:actual-artifact-digest",
  "config": "sha256:non-secret-target-configuration-digest"
}
```

Stages: experiment, poc, prototype, mvp, beta, production. Targets: vps_smoke,
demo, staging, live. Exposure: local/private/public. Data: synthetic/real/sensitive.
Features must explicitly list verified persistence/workers/auth/schema/frontend/
integrations capabilities. Contract profiles also select `contract_mode` artifact
or mock; artifact readiness never proves a backend. Adopted stacks need an
explicit mapping of their inherited checks. Unknown/missing settings fail closed.

## Evidence and verdicts

Each record has `id`, `status`, `artifact`, `config`, `phase`, `profile_digest`,
`catalog_digest`, Unix `observed_at`, and a sanitized relative `evidence` path.
The resolver binds records to the entire profile and catalog, rejects duplicate
IDs and unsafe paths, and expires evidence according to each rule's TTL. Records
from another target, artifact, config or phase cannot satisfy this run.

The resolver checks structure/binding, not the truth of self-reported proof. P05
runner artifacts and P11 reviewed manual evidence must provide that provenance.
A valid JSON saying PASS by itself is not operational evidence. Mandatory FAIL
wins over missing proof; missing/expired evidence and mandatory NOT_APPLICABLE
mean NOT_VERIFIED. Only optional deficiencies become READY_WITH_LIMITATIONS.

Pre-deploy health means a demonstrated artifact startup, not deployment to the
destination. Post-deploy additionally requires an actual target smoke of the same
artifact/config. An inaccessible host cannot be declared verified from a build.

## Historical floors

`migrate_stage` maps demo/prototype to prototype, PoC to poc, MVP to mvp,
production to production, and explicit other to mvp. Unknown values stay
unresolved. The migration retains original value, stack, mapped floor and
mandatory historical check IDs. Resolution unions the new profile with that
floor, and rejects an altered/stripped legacy record. See the migration report.

Every profile retains applicable full-stack gates, contract integrity and
secret/permission checks. Public exposure or real persistent data adds access,
TLS and restore requirements even for a PoC. A private synthetic experiment
does not inherit production load/restore infrastructure without an applicable
condition. The JSON catalog is the reviewable source for these predicates.

## Draft delivery

Generate/check ownership with `python template-core/scripts/ai/generate_core.py`
and `--check`. Preview an isolated delivery using
`python template-core/scripts/ai/install_core.py --target "../core scratch"`;
add `--apply` to write after a conflict-free preflight. Repeated delivery is empty;
customized files are preserved through explicit conflicts. This standalone draft
includes its own README/tests; production project integration and downstream pins
remain pending P04. No stale file deletion or overwrite-on-conflict is performed.

Validation: Windows Python 3.14 and Linux Python 3.13 passed all 13 fixtures,
including the 24-profile matrix. Fresh/repeat Unicode-path delivery also passed.

## Exact-commit development delivery

`core_sync.py` reads committed Git blobs, verifies the source manifest, and
previews the complete update before writing. Dirty source files do not affect
the selected revision. It delivers only `scripts/ai`, `templates/ai` and `docs/ai`
payloads, excluding source-only `generate_core.py` and `install_core.py`; it never
replaces the project's README, tests, notes or settings. Runtime delivery uses
`core_sync.py` with `core_paths.py`, not the standalone source-draft installer.

```text
python template-core/scripts/ai/core_sync.py --source . --commit FULL_SOURCE_SHA --target "../derived project" --development-pin
python template-core/scripts/ai/core_sync.py --source . --commit FULL_SOURCE_SHA --target "../derived project" --development-pin --apply
python ../derived-project/scripts/ai/core_sync.py --target ../derived-project --check
```

The source commit must already contain the generated manifest and `core.json`.
Preview/apply requires an explicit development or integrated label. Installed checks need no
source checkout or network. A check with `--source` also compares the installed
payload and pin to that exact source. Customized files cause conflicts and zero
writes; removed source files remain in the project and require reconciliation.
Interrupted writes can be retried. There is no automatic deletion or rollback.

Use `--integrated-pin` after the source PR is merged: it reads remote `main`
with `git ls-remote` and requires the selected commit to be its ancestor using
locally available Git objects. A missing remote/object or unintegrated commit
fails; it never falls back to a development pin, fetches, or merges. After a
squash merge, select the actual integrated commit and verify its content digest.
This check uses normal Git authentication and does not change trust/config.
React has an integrated pin to the merged core source. Per-file hashes
establish drift, not authenticity or successful stack validation.

## Owning repository delivery

The contract owner uses `python template-core/scripts/ai/core_sync.py --local-source`
to preview its local source delivery; add `--apply` to write or `--check` to
compare without repairs. Source is always `TARGET/template-core`, and cannot be
combined with a commit or another source. First regenerate the source manifest.
The receipt records `source_kind: local`, the manifest digest and per-file hashes,
without a future SHA. The same ownership preflight preserves customized files.
Source README/tests and source-only installers never overwrite project files.
An installed `core_sync.py --check` validates payload drift autonomously;
`--local-source --check` additionally checks canonical source and receipt drift.
Downstream React/Django delivery continues to use exact committed source pins.
