# Family core — independent readiness draft

This directory is the planned shared-core source in the API-contract repository.
The P09 resolver can be developed independently of runtime pilot P03. Production
generation, downstream version pins, install/update delivery and the ADR remain
P04/P12 work. Nothing here claims those integrations have happened.

Python 3.13+ is required; only its standard library is used. This adds no runtime
dependency to a React, Django or contract application.

```text
python -m unittest discover -s template-core/tests -p "test_*.py"
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

Validation: Windows Python 3.14 and Linux Python 3.13 passed all 12 fixtures,
including the 24-profile matrix. Fresh/repeat Unicode-path delivery also passed.
