# Reproducible adapter generation

Canonical sources remain the project's full `docs/ai/catalog.json`, rules, roles
and workflows. The shared `scripts/ai/adapters.py` renderer delivers complete role
packs with each role/rule source path, SHA-256 and end marker. It also renders
Claude/Codex role entry points and every catalog workflow except coordinator-only
`orchestrate`. Native Codex role activation remains subject to the measured runtime
limitations; generated TOML validity alone is not activation evidence.

```text
python scripts/ai/generate_adapters.py --root .
python scripts/ai/generate_adapters.py --root . --apply
python scripts/ai/generate_adapters.py --root . --check
```

The default is a read-only preview. `--check` fails on drift without repair.
`--apply` preflights all outputs before writing. Exit 1 means drift/conflicts;
exit 2 means invalid input. The manifest at
`docs/ai/generated/adapters-manifest.json` records source and generated digests.
Run one writer at a time. Writes interrupted after preflight can be repeated;
this component does not claim full transactional rollback (P13).

Fresh missing outputs are created; identical files are adopted without changing
bytes; only unchanged previously template-owned outputs update automatically.
Customized generated files and removed catalog outputs cause explicit conflicts,
with zero writes. `CLAUDE.md` has mixed ownership: existing different content is
never replaced automatically. Reconcile that root entry point explicitly while
preserving project instructions. No settings/model/trust files are generated.

For the integrated React pilot, one explicit `--import-legacy` transition can use
the old `docs/ai/delivery-manifest.json` digests to recognize unchanged template
outputs. Local edits still conflict. The old manifest's unrelated source records
are not treated as stale generated files. After migration, normal commands use
the new adapter manifest. Stack installers still own their complete delivery
manifest and must include shared core payload and generated receipt.

Role IDs and workflow IDs must be lowercase ASCII identifiers. Roles may declare
`read_only: true`; existing `reviewer` retains its compatible read-only default.
Coordinator-only rules are excluded from worker packs even when shared rules link
to them; direct inclusion fails. Sources are never shortened to fit packs.
All stack-specific procedures remain in their own canonical Markdown files.
