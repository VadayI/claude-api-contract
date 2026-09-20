# Maturity migration report — 2026-09-20

Source tables were read in full from Django and API-contract
`.claude/rules/project-maturity.md`; their exact normalized contents are retained
in `legacy/` and hashed in the core manifest. React had no stage table there.
This report proposes migration metadata; it does not silently modify a project's
declared maturity or CI requirements.

| Legacy | New | Retained historical minimum |
| --- | --- | --- |
| demo | prototype | Django BA/API/test/implementation/docs, reviewer, happy path + 401; contract BA/API/author/mock/docs and one happy example per endpoint |
| prototype | prototype | Django security reviewer, key 400/403 cases; contract reviewer and happy + 1–2 key error examples |
| PoC | poc | Full pipeline, full applicable review, typical errors/examples, medium compatibility attention |
| MVP | mvp | Full quality gate, all declared Django response codes, success/typical contract errors and enforced compatibility/semver; risk review recommended |
| production | production | Full pipeline with mandatory risk/adversarial review, exhaustive response examples/tests, strict compatibility and ADR for breaking changes |
| other | mvp | The prior MVP floor remains until clarified |
| unknown/missing | unresolved | Cannot produce a passing profile; no silent default |

The resolver unions new-stage requirements with the mapped historical floor and
adds a mandatory `legacy_<stack>_<old-stage>` proof referring to this table and
the complete archived rules. Removing or editing those migration requirements
is rejected. A project cannot lower its inherited process by changing only the
new stage. A deliberate requirement change needs a separate reviewed migration.

All historical gates remain enabled: Django ruff, stub ledger, conformance,
README, file size, pytest and endpoint permissions; contract TypeSpec drift,
Spectral, examples, breaking-change, Prism smoke and documentation annotations.
`full_profile` and `contract_integrity` are never dropped for an early maturity.

This draft has 12 unit fixtures, including all 24 stage/target combinations.
One regression was observed and fixed: evidence with an old catalog digest had
incorrectly yielded READY; it now yields NOT_VERIFIED. Artifact/config/phase and
entire-profile digests, TTL, mandatory N/A, duplicate records and secret paths
are covered. These are resolver proofs, not 24 deployments or hosted CI proof.
