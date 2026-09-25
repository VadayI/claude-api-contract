# Git lifecycle G0-G9 (P08)

`scripts/ai/git_lifecycle.py` is the shared, agent-neutral implementation of the
session finalization state machine. Claude wrap-up, Codex skills and a person at
a terminal call the same CLI; nothing depends on a plugin or on runtime memory.
Python 3.13+ standard library, Git 2.38+ (`merge-tree --write-tree`,
`--pathspec-from-file`) and, for pull requests, the `gh` CLI with the user's own
authentication.

Every state is derived from the actual repository, remote and PR at the moment
of the call. A journal in the shared Git directory
(`<git-common-dir>/ai-lifecycle/journal.jsonl`, never an untracked file) only
lists steps that started without a recorded end; it never decides a state.

```text
python scripts/ai/git_lifecycle.py inspect --fetch            # G0/G1: state and next step
python scripts/ai/git_lifecycle.py commit --path src/a.py --path docs/x.md --message "feat: ..."  # G3
python scripts/ai/git_lifecycle.py verify --mode local|github  # G4
python scripts/ai/git_lifecycle.py share --title "..." --body-file pr.md [--draft]  # G5
python scripts/ai/git_lifecycle.py merge --pr N --expect-head FULL_SHA  # G7, user command only
python scripts/ai/git_lifecycle.py cleanup [--branch B]        # G8
python scripts/ai/git_lifecycle.py report                      # G9
```

`--json` (before the subcommand) prints machine-readable output. Exit codes:

| Code | Meaning |
|---|---|
| 0 | Step completed (or nothing to do): COMMITTED/NO_CHANGES, MERGE_PENDING, merged, CLEANED, verify PASS; `inspect`/`report` always |
| 1 | Refused: a precondition failed and this step changed nothing; also verify FAIL |
| 2 | Usage or environment error |
| 3 | Incomplete or not verified: the result names the state (for example `COMMITTED_WITH_UNEXPECTED_CHANGES`, `MERGE_NOT_CONFIRMED`, `PUSH_NOT_CONFIRMED`, `BRANCH_SYNCED / PR_NOT_VERIFIED`, `MERGED / CLEANUP_PENDING`, verify PENDING/NONE/NOT_VERIFIED); some actions may have happened |

## Steps

| Step | Command | Guarantees |
|---|---|---|
| G0 inspect | `inspect` | Repository root, gitdir, common dir, branch, HEAD, base (and how it was found), staged/unstaged/untracked/partially staged paths, stash count, worktrees, locks, in-progress operations, PR evidence, merged branches still present locally or on the remote. Read-only (`GIT_OPTIONAL_LOCKS=0`). |
| G1 reconcile | `inspect --fetch` | `git fetch --prune` updates remote-tracking refs only. Divergence is reported (`DIVERGED`, `BEHIND_REMOTE`, `LOCAL_COMMITS_ON_BASE`); there is no pull, rebase or reset. |
| G2 prepare | procedure | Session record, HANDOFF and docs are written by the calling procedure (`docs/ai/session-continuity.md`); format only task-owned files. |
| G3 commit | `commit --path ...` | Literal paths (`:(literal)` pathspecs; hooks keep their own globs); a directory covers the changed files below it. Default mode commits the working-tree content of task paths that have **no staged changes** (`git commit --only` with a NUL pathspec file), so other staged entries stay staged. A task path with staged changes (hunks, mode-only change, `rm --cached`) needs `--staged`, which commits the index and refuses if it holds non-task paths. Half of a rename is refused. No commit on the base branch or with an undetermined base, no empty commit, no blanket staging. Hooks run; a failed commit unstages the new files it added. Afterwards the committed paths and a raw-byte digest snapshot of every foreign path (no Git filters) are compared: a hook that added or changed other paths yields exit 3 `COMMITTED_WITH_UNEXPECTED_CHANGES` with the paths. |
| G4 verify | `verify` | Local mode: the newest runner result whose candidate commit **and** tree equal HEAD. GitHub mode: required checks of the open PR whose head equals HEAD. PASS only when every reported required check passed; skipped, neutral or unknown results are `NOT_VERIFIED`; missing evidence is never PASS. |
| G5 share | `share` | Push without force (the remote branch must be an ancestor of HEAD), confirmed with `ls-remote`. One open same-repository PR per branch (fork PRs with the same branch name are ignored): created with `--title`/`--body-file`, updated otherwise. A branch already merged in a PR is not pushed again (no duplicate PR after a squash merge and head-branch deletion); a deleted upstream with unavailable PR evidence is not pushed either. gh failure after a successful push is `BRANCH_SYNCED / PR_NOT_VERIFIED`. |
| G6 await | report | `BRANCH_SYNCED / MERGE_PENDING`: the branch is needed by its PR and is kept. |
| G7 merge | `merge --pr N --expect-head SHA` | Only on the user's explicit command (D01). Fetches, then re-reads the PR: same repository, open, not draft, head equals the approved full SHA, expected base; checks PASS for that head (GitHub required checks, or in local mode a runner result whose base is the current merge base); merge state CLEAN, HAS_HOOKS or UNSTABLE (non-required checks only; BEHIND, BLOCKED, DIRTY and DRAFT are refused). CI mode and merge method are read from the **base branch's** `project.json`, not from the branch being merged. `gh pr merge --match-head-commit`; never `--admin`. An unconfirmed outcome is `MERGE_NOT_CONFIRMED` (exit 3); run `inspect` before retrying. |
| G8 cleanup | `cleanup` | Requires a MERGED same-repository PR and proof that its head is in the base: ancestry (merge commit, fast-forward), the PR merge commit being in the base and containing the head (squash, rebase), or `merge-tree` producing the unchanged base tree. Refused while other open PRs target the branch. A branch with commits after the PR head is kept (a local branch behind the PR head, e.g. after a GitHub update-branch, is fine). A clean current worktree switches to the base and the base is only fast-forwarded, both with `--no-overwrite-ignore`; linked worktrees are removed without `--force` and only when they have no ignored files (`.env`, local databases, runner results) and are not locked; others are reported. The local branch is deleted with `update-ref -d` at its observed tip; the remote branch only when its tip is the PR head, with `--force-with-lease` bound to that tip, so a concurrent push is never lost. Stash, other branches and locks are never touched. Already cleaned branches report `MERGED / CLEANED` again. |
| G9 report | `report` | Final state with the exact pending step, e.g. `MERGED / CLEANUP_PENDING: worktree ... kept`. `MERGED / CLEANED` only after the actions were confirmed. |

## States

`BLOCKED` (lock file, merge/rebase/cherry-pick/revert/bisect in progress,
conflicts), `DETACHED`, `NOT_VERIFIED` (PR evidence needed but unavailable),
`NO_CHANGES`, `LOCAL_CHANGES`, `LOCAL_CHANGES_ON_BASE`, `LOCAL_COMMITS_ON_BASE`,
`COMMITTED_UNPUSHED`, `DIVERGED`, `BEHIND_REMOTE`, `BRANCH_SYNCED / PR_MISSING`,
`BRANCH_SYNCED / PR_NOT_VERIFIED`, `BRANCH_SYNCED / MERGE_PENDING`,
`PR_HEAD_MISMATCH`, `PR_CLOSED`, `MERGED / EXTRA_COMMITS`,
`MERGED / CLEANUP_PENDING` and `MERGED / CLEANED`.

A merged PR whose branch still exists locally, or only on the remote with the
current gh user as PR author, is `MERGED / CLEANUP_PENDING` on any machine,
without a local marker; on the base branch `inspect` lists such branches under
`pending_cleanup`. Merged remote-only branches of other authors are listed under
`other_merged_remote_branches` for information and never change the state.
Branches that open PRs target (stacked or long-lived) are not listed. Without gh evidence the base branch reports
`NOT_VERIFIED` rather than `NO_CHANGES`.

## Recovery

Each command is idempotent and starts from the actual state: a repeated `share`
skips an already pushed head and never opens a second PR; a repeated `merge`
of an already merged PR with the same head reports it; a repeated `cleanup`
skips what is gone. After a network failure or timeout the command re-reads the
remote (`ls-remote`) instead of assuming success. Commands that write the index,
working tree or refs have no timeout (hooks and large checkouts may be slow);
read and network commands time out, and on POSIX they are terminated gracefully
first so Git removes its own locks (on Windows termination is immediate). A lock file is reported, never removed; known
9p/Cowork mount combinations need Git on the host.

## Configuration

The base branch is `--base`, else `refs/remotes/<remote>/HEAD`, else the remote's
default branch (`ls-remote --symref`), else a guessed `main`/`master` (reported
as a guess; `commit` then requires `--base`, and `git remote set-head <remote> --auto`
records the default once). The CI mode comes
from `--mode` or `ci.execution` on the base branch; the merge method from `--method` or the
optional `git.merge_method` (`merge`, `squash`, `rebase`; default `merge`, which
keeps stacked branches mergeable). `AI_GH` may hold a JSON argv list replacing
`gh` (used by fixtures).

## Evidence and limits

`template-core/tests/test_git_lifecycle.py` covers the section 10 fixture matrix
on disposable repositories with a local bare remote and an offline gh stand-in
(`tests/fake_gh.py`): partially staged and foreign untracked files, stash
identity, literal glob-like paths, renames, index-only changes, greedy and
failing hooks, additional commit after the PR, merge from another machine, PR
head updated remotely, squash and rebase merges (also with later conflicting
base changes and after `gc`), active dirty/clean worktrees, ignored files in
worktrees and in the base, a concurrent push during cleanup, stacked PRs, fork
PRs with the same branch name, gh offline after push, re-push after a squash
merge with a deleted head branch, rejected (diverged) push, failed, pending,
skipped and missing checks, hooks using their own glob pathspecs, foreign
file names with newlines, teammates' merged remote branches, fork PRs that
target the task branch, draft, base mismatch, local-mode evidence bound to
the merge base, new base (BEHIND), base branch states, a remote whose default
branch is not `main` without `origin/HEAD`, repeated steps, branch without
remote, locks and in-progress operations. An independent review found the
initial defects that these fixtures now pin.

Not yet verified: native Windows execution, a real GitHub lifecycle through
this CLI (gh output formats are assumed from gh's documented JSON fields), and
consumer entry points (Django/React wrap-up) — see the P08 status.
