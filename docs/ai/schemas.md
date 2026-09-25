# Shared machine contracts

Python 3.13+ with the standard library validates the shipped, deliberately small
JSON Schema vocabulary. No pip package, marketplace, agent CLI or network access
is required. Schema references are never fetched. This is not a general-purpose
JSON Schema implementation: unsupported keywords, including nested ones, fail.

```text
python scripts/ai/schema.py project docs/project-state/project.json --root .
python scripts/ai/schema.py catalog docs/ai/catalog.json --root .
```

In the source repository use `template-core/scripts/ai/schema.py` instead.
Exit 0 means structural and relationship validation passed; exit 2 means invalid
input, schema or filesystem access. Neither command repairs files or proves that
declared capabilities or checks have actually run. The caller selects a reviewed,
non-secret input; the validator does not discover or read real env/credential files.

## Project configuration

`templates/ai/schemas/project.schema.json` requires explicit template kind/scaffold,
CI choice, user-command merge policy (with an optional `git.merge_method`: `merge`,
`squash` or `rebase`, used by the P08 Git lifecycle), reported-file coordinator policy, maturity,
contract provenance, documentation map, capabilities and saved deployment map.
There is no default CI selection. Unknown policy keys and enum values fail.
Project extensions belong in `extensions`; they never grant runtime permissions.

Contract sources require an HTTP(S) URL, sha256 digest, repository-relative artifact
path and, for `repo_pin`, an explicit pin. URLs cannot contain credentials, query
parameters or fragments. A digest is a declared identity until the integrity runner
verifies it. This schema does not fetch URLs or certify reachability. Artifact and
documentation paths may refer to future files, but cannot traverse outside the
project or through links. The artifact is a file; documentation entries may also
name directories (ADRs, session records). The documentation roles and their
defaults are defined in `session-continuity.md`. P06 materializes an explicit CI choice in project
settings. P07 migrates legacy settings and registries with the procedures in
`project-state-migration.md`; installing these schemas does not create or
overwrite project settings.

Legacy maturity data is checked against the existing P09 resolver's historical
floors. Saved deployment profiles use that resolver and must match the project's
kind, stage, capabilities and legacy provenance. Empty deployment maps are allowed
before selecting a deployment target; they are not readiness evidence.

## Instruction catalog

`templates/ai/schemas/catalog.schema.json` accepts the integrated React pilot
catalog without rewriting its full sources. In addition to shape validation,
the CLI checks unique rule IDs, real contained source files, role/consumer IDs
and dependency closure. A dependency pointing to a coordinator-only rule does
not make that rule mandatory for a worker (D02). Cyclic worker references are
allowed only when all referenced worker rules are delivered. Legacy inventory
and hidden-rule metadata remain available for the broader P12 migration.

The supported vocabulary is `type`, `const`, `enum`, `required`, `properties`,
`additionalProperties`, `items`, `minItems`, `uniqueItems`, `minLength`, `pattern`
and `minimum`, with `$schema`, `title` and `description` annotations. Only JSON
object/array/string/integer/boolean/null types are supported. Duplicate keys,
NaN/Infinity, booleans used as integers, and keywords on incompatible types fail.

Check/runner result schemas, launcher integration and downstream delivery are
integrated (P04/P05/P06); the P07 project-state migration below is in progress.
These contracts alone do not complete family acceptance (P13).
