# Update from a reviewed template revision

Select an explicit template commit/ref and obtain a separate source checkout.
Inspect its revision and changelog. Run its
`python scripts/ai/production.py --target <project>` to preview the full ownership
plan. A failed source drift check must be resolved in that source, not bypassed.
Review the pending paths/conflicts. Apply the already-authorized update with
`--apply` only when there are no conflicts; custom/mixed instructions/config need
an explicit reviewable reconciliation. `seed.sh --force` cannot bypass ownership.
Never recursively copy `.claude`, `.codex`, scripts or docs over the project.

Repeat the preview and verify installed core/adapters; run applicable project
checks for the exact updated candidate. Preserve project docs, CI/maturity choice,
registries, overrides, language, spec/examples/OpenAPI, LOCAL and private config.
No secrets are part of the manifest. Removed managed files are retained until an
explicit reviewed migration. The receipt is written last; interrupted writes are
retryable when already-identical. Full atomic rollback is not yet implemented;
review backups/diff before a larger update and report this P13 limitation.

Use this local procedure when the optional template-sync plugin is unavailable.
Worker implements; coordinator reads only reported evidence paths. Return the
source revision, changed files, conflicts, checks and next step; never claim full
family/P12 adoption from component delivery alone.
