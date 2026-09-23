# Wrap up an authorized contract work session

1. Inspect branch/HEAD/status, worktrees, refs, stash inventory and existing PR.
   Reconcile upstream state without automatically resetting, stashing or rebasing
   foreign changes. Preserve the partially staged semantics of unrelated work.
2. Review the task diff. Run actual applicable contract commands from
   `docs/ai/rules/node-commands.md` and shared source/core drift checks. A scaffold
   has no contract artifact; report that coverage separately. Missing prerequisites
   are NOT_VERIFIED; never fabricate JSON PASS or use a different revision's CI.
3. Dispatch the local handoff procedure; update relevant plans/README/CHANGELOG.
   Format only task-owned files explicitly before final checks. Stage exact files
   or hunks, inspect the staged diff and create the logical commit when separable.
4. Verify candidate/base and available hosted/local results. Push only the reviewed
   task branch without force; create or update its PR rather than duplicating one.
   Confirm actual remote head and PR state. Full automated exact-candidate runner
   and G0–G9 recovery remain P05/P08; this procedure does not claim they ran.
5. Report BRANCH_SYNCED / MERGE_PENDING with checks and PR link. Merge requires a
   new explicit command, current head/base/checks and review. No release/deploy.
   After separately authorized merge, cleanup only the proven completed task
   branch when no active worktree/additional commits depend on it. Unknown merge
   or cleanup evidence means retain the branch and report the pending step.

No changes means no empty commit/PR. A network failure is incomplete sharing;
inspect actual state before retrying an uncertain operation. This local procedure
works without plugins using Git/gh and the current runtime's actual tools.
