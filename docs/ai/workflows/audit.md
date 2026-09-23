# Audit the current session and suggest the next action

Read actual Git status/HEAD, HANDOFF and the active plan; inspect available
non-secret command evidence. Compare performed work with applicable rules and
missing checks. Return concrete findings with exact paths/lines, observed command
results, gaps and the next useful local procedure. Missing command-log data means
unknown history, not success. Audit is read-only; no automatic install, mutation,
push, release or deployment. The optional family-core auditor may provide extra
capabilities; this local fallback does not claim its unavailable implementation.
