# Audit the current session and suggest the next action

First check that the work is committed and synchronized with GitHub:
`python scripts/ai/git_lifecycle.py --json inspect --fetch` (docs/ai/git-lifecycle.md).
Synchronized means: no staged, unstaged or untracked paths in `working_tree`;
`head` equals the branch's remote-tracking tip (`remote_tracking`, or
`base_refs.remote_tracking` on the base branch); no blockers; PR evidence
`VERIFIED`. Anything else (for example `LOCAL_CHANGES`, `COMMITTED_UNPUSHED`,
`BEHIND_REMOTE`, `DIVERGED`, `LOCAL_COMMITS_ON_BASE`, `PR_HEAD_MISMATCH`,
`NOT_VERIFIED`, a pending cleanup) is reported as the first finding with the
exact paths, commits and next step. Then ask the user whether to finalize first
(`/wrap-up`: commit, push, PR) or audit the current state anyway. The audit
itself never commits, pushes, pulls or cleans; the fetch only updates
remote-tracking refs. Unavailable gh or network is `NOT_VERIFIED`, never
synchronized.

Then read actual Git status/HEAD, HANDOFF and the active plan; inspect available
non-secret command evidence. Compare performed work with applicable rules and
missing checks. Return concrete findings with exact paths/lines, observed command
results, gaps and the next useful local procedure. Missing command-log data means
unknown history, not success. Audit is read-only; no automatic install, mutation,
push, release or deployment. The optional family-core auditor may provide extra
capabilities; this local fallback does not claim its unavailable implementation.
