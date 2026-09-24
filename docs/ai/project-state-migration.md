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
| `env-detect.json` | `.ai-runtime/environment.json` | Machine-local runtime |
| `command-log.jsonl` | `.ai-runtime/command-log.jsonl` | Machine-local runtime |

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

The resolver chooses the canonical copy when only it exists and falls back to
legacy for an unmigrated project. If both copies exist with different bytes, it
raises an error; modification time is never used to select a winner. New writes
must call `writable_state_path` and are refused while a legacy copy remains.
Runtime records are moved to `.ai-runtime/`, which remains local and gitignored.
