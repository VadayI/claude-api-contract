# Handoff

Within an authorized documentation task, run
`python scripts/ai/session_context.py --root .` and inspect actual
branch/HEAD/status and the current plan. Create this session's record with
`python scripts/ai/session_context.py --root . --new-record --agent <runtime>`
(`claude`, `codex`, ...). Fill every section: task, changes, decisions, checks
(commands, results, candidate/base), limitations, next step. Update the existing
`docs/HANDOFF.md` by content with the concrete task, known revision/tree, changed
paths, actual commands/results, unresolved blockers and next step. Preserve
unrelated notes and never configure `merge=union`. The existing WORKLOG is
history; new per-session entries are records (docs/ai/session-continuity.md).
Move durable facts from runtime-private memory (Claude auto memory, Codex
memories) into the mapped documents with their source; do not copy private chat,
env values, tokens or raw logs into Git. Do not invent the SHA of the future
commit containing the handoff: the record's revision is the known HEAD. A stale
SHA requires relevant diff reconciliation, not deletion of historical notes.
After the commit, `python scripts/ai/session_context.py --root . --check` must
PASS. Report exact written paths and the evidence used. Coordinators dispatch
this writing to a worker; reviewers return findings only.
