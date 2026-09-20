# Project maturity stage (process scaler)

Declare the project's maturity stage before any feature work starts. The stage scales
**process depth** — pipeline completeness, `devil` usage, review rigour, test coverage
expectations. It does **not** gate-skip or relax TDD, security, or contract-conformance
invariants.

## Taxonomy

| Stage | One-line definition |
|---|---|
| **demo** | Throwaway proof-of-concept; disposable after the meeting. |
| **prototype** | Exploratory; no real users, may break freely. |
| **PoC** | Validates a specific technical hypothesis; short-lived. |
| **MVP** | First real release; real users approaching; the API is a promise. |
| **production** | Live API consumed by real clients; every change has cost. |
| **other** | Treated as **MVP** until clarified. |

## Process matrix (TDD + CI gates always ON)

| Stage | Pipeline depth | `devil` | Quality Gate | Tests expected | Breaking-change attention |
|---|---|---|---|---|---|
| **demo** | ba → api-architect → tester → django-developer → docs-writer | skip | reviewer only | happy path + 401 | low |
| **prototype** | + security-scanner | skip | reviewer + security | + key errors (400/403) | low |
| **PoC** | full | optional | full parallel | + typical errors | medium |
| **MVP** | full | recommended | full (max 2 cycles) | all declared codes | high |
| **production** | full, `devil` first | mandatory | full + adversarial | exhaustive (every code in contract) | strict; breaking → ADR |
| **other** | as MVP until clarified | — | — | — | — |

## Invariants — NEVER overridden by stage

**TDD (Red → Green → Refactor), the CI gates (ruff · stub ledger · contract conformance ·
app README · file-size · pytest), and `permission_classes` on every endpoint are ALWAYS ON,
regardless of stage.**

A stage modulates process depth and completeness — it does not relax:
- the failing test requirement before any production code (@.claude/rules/tdd.md),
- the no-stub rule (@.claude/rules/no-stubs.md),
- contract conformance (`scripts/check_contract_conformance.sh`),
- security checks at the Quality Gate (@.claude/rules/serializers-permissions.md).

## Where the stage lives

Recorded in `docs/PROJECT.md` (**Maturity stage** field). If `PROJECT.md` does not state a
stage, `ba` / `brief-synthesizer` emits an **Open Question**; the orchestrator asks via
`AskUserQuestion` (options: demo / prototype / PoC / MVP / production / other).
Never assume a stage — "other" is the explicit fallback, not the default silence.

## How to read the matrix

- **Pipeline depth:** agents listed are the minimum; add more if complexity warrants it.
- **`devil`:** "skip" means the orchestrator may omit it by default; the user may invoke it at any stage.
- **Tests expected:** a floor, not a ceiling — add tests for every error code the contract declares.
- **Breaking-change:** "low" relaxes urgency of semver review, not the contract conformance gate.

> First action on any feature: read `PROJECT.md` for the declared stage. No stage → Open
> Question before proceeding. Scale the pipeline against the matrix; never silently skip an
> invariant (@.claude/rules/workflow.md, @.claude/rules/preflight.md).

<!-- Last reviewed/updated: 2026-06-08 -->
