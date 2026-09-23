# Set the project response language

Honor an explicit language already given in the current session. Otherwise read
the existing project override or legacy `.claude/rules/output-language.md`; ask
for English, Ukrainian or Polish only when no choice exists and one is needed.
For an authorized persisted change, write the chosen language into
`docs/ai/overrides/output-language.md`, creating only that project-owned file.
Do not rewrite CLAUDE/AGENTS adapters or their imports. Both runtimes read the
override from shared AGENTS. If new/legacy choices conflict, report the difference
and reconcile from the current user instruction; never choose by mtime. Technical
identifiers remain unchanged. No translation of secrets or private transcripts.
