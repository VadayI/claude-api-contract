# Session continuity

A new session of any agent (Claude, Codex or another runtime), on any machine,
must find the project's purpose, architecture, current decisions, branch and
revision, the results and limits of the last checks, and the next step, without
the previous chat and without `.ai-runtime/`. The information lives in three
places:

- execution rules and procedures: `docs/ai/`;
- versioned project notes and data: the documents named by the `documentation`
  map, plus `docs/project-state/`;
- machine-local state: gitignored `.ai-runtime/`. Nothing in this procedure
  needs it.

## Documentation map

`docs/project-state/project.json` → `documentation` maps roles to actual
root-relative paths. An explicit entry is authoritative, even when its file is
missing, so a gap is reported rather than hidden. Without an entry, the first
existing default is used. Do not create duplicate PROJECT, NOTES or ARCHITECTURE
files when README, a brief or a rule already has that role. Point the map at
the existing document instead.

| Role | Defaults (first existing) | Holds |
|---|---|---|
| `readme` | `README.md` | Purpose and how to run |
| `project` | `docs/PROJECT.md`, `PROJECT.md` | Project brief |
| `architecture` | `docs/ARCHITECTURE.md`, `docs/ai/rules/architecture.md`, `docs/ai/rules/contract-first.md` | Architecture |
| `decisions` | `docs/decisions` | ADRs |
| `handoff` | `docs/HANDOFF.md` | Rolling "where we are / what's next" |
| `sessions` | `docs/sessions` | One record per finished session |
| `backlog` | `docs/todo.md` | Backlog |
| `lessons` | `docs/lessons.md` | Lessons learned |
| `worklog` | `docs/WORKLOG.md` | History from before session records existed |

Entries may name document files (`.md`, `.markdown`, `.txt`, `.rst`, `.adoc`)
or directories. Paths cannot traverse links, leave the project, contain hidden
components (`.git`, `.ai-runtime`, `.env*`, `.npmrc`, …), mention secrets or
credentials, or name configuration/data files: an agent following the map
should only ever open notes. Projects may add roles such as `runbook`; the
start context lists them.

## Start of a session

```sh
python scripts/ai/session_context.py --root .
```

The command prints, in a bounded form:

- Git branch, HEAD, the number of changed paths and upstream ahead/behind. It
  does not fetch, so the upstream numbers reflect the last fetch.
- The project settings summary and the persisted output language
  (`docs/ai/overrides/output-language.md`, or the Claude-only legacy file with
  its migration command).
- The resolved documentation map.
- The newest session record present in the working tree (by its UTC
  identifier, whichever branch it was written on — merged records belong to
  this history), with its checks, limitations and next step.
- A snapshot comparison.
- Continuity findings.

Git runs with `GIT_OPTIONAL_LOCKS=0`, so the index is never refreshed or locked.
After this, read the handoff and the active plan.

The snapshot comparison lists the paths changed by commits after the commit
that last changed the record, excluding continuity files. Such paths are a
finding: that work is not described yet, so inspect the diff before relying on
the notes; it does not mean the handoff is false. The recorded revision is
also compared with HEAD. A revision missing from this clone (after a squash or
rebase merge, in a shallow or single-branch clone, or never pushed) is only
reported, because the record's own commit anchors the comparison.

## During the work

Record verified facts and decisions together with their source: a command, a
file, an ADR or the user's explicit choice. Put durable settings and registries
in `docs/project-state/` (see `project-state-migration.md`).

## End of a session

This is part of wrap-up or handoff, not of every intermediate answer.

1. Create a record:
   `python scripts/ai/session_context.py --root . --new-record --agent claude`
   (use `codex` or another lowercase runtime name as appropriate). The file
   `<sessions>/<UTC>-<agent>-<random>.md` is created exclusively. It carries the
   branch and the known HEAD as `revision`, never the SHA of a future commit.
2. Fill every section: Task, Changes, Decisions, Checks, Limitations and Next
   step. Give actual commands with PASS/FAIL/NOT_VERIFIED, candidate and base.
   Write "none" instead of leaving a section empty. Never paste transcripts, env
   values, tokens or raw logs.
3. Update the handoff with a normal content edit that preserves other people's
   notes. Update the backlog, lessons and an ADR when they change.
4. Move durable facts from runtime-private memory (Claude auto memory, Codex
   memories, personal notes) into the mapped documents with their source. Such
   memory is not shared context, and another agent cannot read it.
5. Commit the record with the task's documentation. Then run
   `python scripts/ai/session_context.py --root . --check`. It must PASS; an
   uncommitted record is not visible to another machine.

A session without repository changes still records its checks and next step
when it is wrapped up, but it never creates an empty commit or PR.

## Parallel sessions and merges

Each session writes its own record file with a unique name, so two agents or
machines never edit the same record, and Git merges records without conflicts.
The handoff is merged by ordinary content. `merge=union` is not used for any
continuity path; `--check` reports it, because union merges silently interleave
the lines of competing edits. Existing `WORKLOG` files remain history. New
per-session entries go into records instead of concurrent appends.

## Record format

```markdown
---
session: 20260925T071200Z-codex-a1b2c3
agent: codex
recorded: 2026-09-25T07:12:00Z
branch: feat/example
revision: <full commit id at recording time, or "unborn">
---

# Session 20260925T071200Z-codex-a1b2c3

## Task
## Changes
## Decisions
## Checks
## Limitations
## Next step
```

Every section except Decisions must be filled, and no section may keep a
`{TODO` placeholder: write "none" instead. Records may use CRLF line endings
and a UTF-8 BOM; `## ` lines inside fenced code blocks do not start sections.
Every record in the directory is validated, not only the newest one.

## Commands and exit codes

| Command | Result |
|---|---|
| `session_context.py --root .` | Prints the start context; exit 0 even with findings |
| `--check` | 0 PASS; 1 continuity findings |
| `--json` | Machine-readable report (combine with `--check` for its exit code) |
| `--new-record --agent NAME` | Creates one record and prints its path; exit 0 |
| any | 2 for unsafe map paths, conflicting settings copies, invalid JSON or I/O errors |

`--check` finds these problems:

- no purpose document;
- a missing or empty architecture, decisions or handoff entry;
- no session record;
- an incomplete record (any record), an uncommitted newest record, or
  uncommitted edits to it;
- commits after the newest record that change relevant paths;
- `merge=union` on a continuity path;
- a conflict between the shared and the legacy language preference;
- Git being unavailable.

## Evidence boundary

`--check` passing in a fresh clone without `.ai-runtime` is the mechanical form
of the plan's continuity criterion. A real Claude → Codex → Claude sequence on
another machine is a runtime acceptance run. It is recorded separately and
stays NOT_VERIFIED until it has actually been executed.

## Runtime acceptance run

Use a disposable branch of a template or derived project whose `--check`
passes. Do not paste chat history into later sessions: each session starts
without the previous chat.

1. **Claude, machine A.** Start through the launcher. Ask for a small
   documented change, for example a line in a feature README, then wrap-up.
   Expect a record with `agent: claude`, a commit and `--check` PASS.
2. **Codex, machine B**, a fresh clone without `.ai-runtime`, first prompt
   "continue the project". Without further hints, the session states:
   - the purpose (from the mapped README or brief);
   - the architecture document;
   - one current ADR;
   - the branch and the revision of the latest record;
   - its Checks and Limitations;
   - its Next step;
   - the persisted output language.

   Codex then does that next step and wraps up with an `agent: codex` record.
3. **Claude again, machine A**, after `git pull`. Expect the same facts, now
   from the Codex record, and the snapshot shows no unrecorded commits.
4. **Parallel sessions.** Two sessions on different branches each commit a
   record, then merge. Expect two record files, no conflict in them, and the
   handoff merged by content.

Record in `runtime-compatibility.md`:

- runtime versions and OS;
- which of the listed facts each session produced unprompted;
- the record paths and commits;
- the `--check` results.

Record only observed behaviour; no transcripts or secrets. Any fact the agent
needed a hint for is a failure of that item, not a PASS.
