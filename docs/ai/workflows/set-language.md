# Set the project response language

Honor an explicit language already given in the current session. Otherwise read
the existing project override or legacy `.claude/rules/output-language.md`; ask
for English, Ukrainian or Polish only when no choice exists and one is needed.
For an authorized persisted change, write the chosen language into
`docs/ai/overrides/output-language.md`, creating only that project-owned file.
Do not rewrite CLAUDE/AGENTS adapters or their imports. Both runtimes read the
override from shared AGENTS. A legacy Claude-only preference moves with
`python scripts/ai/project_state.py --root . --language` (preview) and `--apply`,
which leaves a pointer at the old path. If new/legacy choices conflict, the
command writes nothing: report the difference, write the user's current choice
to the override, then run `--language --apply --keep-shared`; never choose by
mtime. Technical
identifiers remain unchanged. No translation of secrets or private transcripts.
