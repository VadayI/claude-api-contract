# Shared project state and legacy migration

Shared project registries and settings live under `docs/project-state/`.
Machine-local detection and command records live under gitignored
`.ai-runtime/`. The older `.claude/memory/` path remains a read fallback for
known artifacts until a project completes migration.

## Explicit artifact map

| Legacy file | Canonical file | Ownership |
|---|---|---|
| `project.json` | `docs/project-state/project.json` | Project settings |
| `endpoints.json` | `docs/project-state/endpoints.json` | Project registry |
| `routes.json` | `docs/project-state/routes.json` | Project registry |
| `pages.json` | `docs/project-state/pages.json` | Project registry |
| `template-sync.json` | `docs/project-state/template-lineage.json` | Project lineage |
| `env-detect.json` | `.ai-runtime/env-detect.json` | Machine-local stack probe |
| `command-log.jsonl` | `.ai-runtime/command-log.jsonl` | Machine-local runtime |
| `.claude/rules/output-language.md` | `docs/ai/overrides/output-language.md` | Project language preference (see below) |

`.ai-runtime/environment.json` is reserved for the shared detector report
(`python scripts/ai/detector.py --repository . --write`, schema version 1). Stack
probes (`scripts/detect-env.mjs`, `scripts/detect-env.py`) keep their own schema
in `.ai-runtime/env-detect.json`; the two files have different producers and are
never merged or compared.

No other legacy basename is migrated automatically. The preview reports unknown
names without reading their contents. Classify those files separately before
changing them. Transcript data, credentials and arbitrary files are never part
of this migration map.

## Preview and apply

Run from the derived repository root:

```sh
python scripts/ai/project_state.py --root .
python scripts/ai/project_state.py --root . --apply
```

Preview is read-only. Apply validates known JSON/JSONL files, creates canonical
files without overwriting, then removes the legacy source only after confirming
the bytes match. Repeating apply after a successful migration makes no changes.
When both locations contain different bytes, that artifact is skipped and both
paths are reported for a human diff. Other nonconflicting artifacts can migrate.
Unknown or invalid files stay untouched, and the command exits nonzero while
any conflict, invalid artifact or unknown name remains.

## Consumers

The resolver chooses the canonical copy when only it exists and falls back to
legacy for an unmigrated project. If both copies exist with different bytes, it
raises an error; modification time is never used to select a winner. New writes
must call `writable_state_path` and are refused while a legacy copy remains.

Shell and Node consumers call the same implementation instead of copying the
rule:

```sh
python scripts/ai/project_state.py --root . --resolve endpoints.json
python scripts/ai/project_state.py --root . --writable command-log.jsonl --category runtime
```

`--resolve` prints the root-relative POSIX path the fallback rule selects (the
canonical path when neither copy exists, so a caller reports a clear missing
file). `--writable` prints the canonical path or exits 2 while a legacy copy
remains. Exit code 2 also reports a conflict or an unknown artifact name.

Runtime writers (session-start hooks, command loggers) may run
`python scripts/ai/project_state.py --root . --migrate-runtime` or call
`migrate_runtime()` before writing: it moves only `env-detect.json` and
`command-log.jsonl`, leaves project registries and unknown files untouched, and
exits 1 only for a runtime conflict or invalid record. A writer that meets a
conflict refuses to write and names both paths; it never creates a second copy
beside the legacy file. Project registries are never migrated by a writer — a
human runs `--apply` after reviewing the preview.

Session records, the handoff and the documentation map are described in
`session-continuity.md`; `scripts/ai/session_context.py` reads project settings
through the same resolver.

## Output-language preference

The shared preference `docs/ai/overrides/output-language.md` is read by Claude
and Codex through AGENTS.md; the older `.claude/rules/output-language.md` was
visible to Claude only. Review, then apply:

```sh
python scripts/ai/project_state.py --root . --language
python scripts/ai/project_state.py --root . --language --apply
```

Apply creates the shared file exclusively from the legacy bytes, verifies it,
and only then replaces the legacy file with a fixed pointer to the shared file.
A legacy CLAUDE.md import of the old path therefore keeps working and there is
exactly one writable preference. When both files hold different preferences the
command writes nothing and exits 1: reconcile from the user's current choice
through the set-language procedure, which writes that choice to the shared file
and then runs `--language --apply --keep-shared` to replace the legacy file with
the pointer. A pointer without the shared file also exits 1. Repeating a completed migration changes nothing. New preferences are written
only to the shared file. `session_context.py` prints the effective language.

## Ownership after migration

`docs/project-state/**`, `docs/ai/overrides/**` and `.ai-runtime/**` are project-owned or machine-local:
template installers and seed inventories must not deliver, overwrite or remove
them, and `.ai-runtime/` stays gitignored. Legacy `.claude/memory/**` entries in
`.gitignore` remain during the transition so an unmigrated checkout keeps its
runtime files out of Git.
