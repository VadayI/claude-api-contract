# Wrap up an authorized contract work session

1. Run `python scripts/ai/git_lifecycle.py inspect --fetch` (G0/G1,
   docs/ai/git-lifecycle.md): branch/HEAD/status, worktrees, refs, stash, locks,
   in-progress operations and the PR, with the next step. Reconcile upstream state
   without automatically resetting, stashing or rebasing foreign changes. A
   `MERGED / CLEANUP_PENDING` branch from an earlier session is cleaned (step 5).
2. Review the task diff. Run actual applicable contract commands from
   `docs/ai/rules/node-commands.md` and shared source/core drift checks. A scaffold
   has no contract artifact; report that coverage separately. Missing prerequisites
   are NOT_VERIFIED; never fabricate JSON PASS or use a different revision's CI.
3. Dispatch the local handoff procedure (session record, HANDOFF, transfer of
   durable facts from runtime-private memory; docs/ai/session-continuity.md);
   update relevant plans/README/CHANGELOG.
   Format only task-owned files explicitly before final checks. Commit with
   `git_lifecycle.py commit --path <task path> ... --message ...` (other staged
   entries stay staged); for exact hunks stage them and add `--staged`. A refused
   commit keeps everything; report it instead of blanket staging.
4. `git_lifecycle.py verify` reports the exact candidate's evidence (local runner
   result, bound to pre-push, or required PR checks). `git_lifecycle.py share
   --title ... --body-file ...` pushes the task branch without force and creates or
   updates its single PR, confirming the remote head. After the commit,
   `python scripts/ai/session_context.py --root . --check` must PASS so another
   agent or machine finds the record.
5. Report `git_lifecycle.py report`: BRANCH_SYNCED / MERGE_PENDING with checks and
   PR link. Merge requires a new explicit command naming the PR; run
   `git_lifecycle.py merge --pr N --expect-head <approved SHA>`, which re-checks
   head/base/checks. No release/deploy. After a confirmed merge,
   `git_lifecycle.py cleanup` removes only the proven-merged task branch and clean
   worktrees; unknown evidence keeps the branch and reports the pending step.

No changes means no empty commit/PR. A network failure is incomplete sharing;
inspect actual state before retrying an uncertain operation. This local procedure
works without plugins using Git/gh and the current runtime's actual tools.
