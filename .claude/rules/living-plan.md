# Living plan (execution log per feature)

Non-trivial work gets a plan file `docs/plans/NNNN-<slug>.md` that lives and breathes through the pipeline.

## Structure

- **Goal / scope** — what this change does and explicitly does not do.
- **Steps** — the pipeline stages with the files each touches.
- **Risks** — breaking-change risk, consumer impact, open questions.
- **Execution log** — append-only; each agent adds **one line** when its phase finishes.

## Rules

- The plan is created in Plan Mode and approved before any file changes.
- After finishing a phase, each agent appends a one-line confirmation to the **Execution log** via an `Edit` append — never a full-file rewrite (concurrent phases must not clobber each other):
  > `phase done: tsp-author — spec/articles.tsp + openapi.yml recompiled`
- The plan is the single place to see "where we are" mid-feature; `/wrap-up` folds it into `docs/WORKLOG.md` and refreshes `docs/HANDOFF.md`.
