# Project maturity stage (process scaler)

Declare the project's maturity stage before any contract work starts. The stage scales
**process depth** — pipeline completeness, `devil` usage, review rigour, example
completeness. It does **not** gate-skip or relax contract integrity.

## Taxonomy

| Stage | One-line definition |
|---|---|
| **demo** | Throwaway show of concept; disposable after the meeting. |
| **prototype** | Exploratory shape; no real consumers, may break freely. |
| **PoC** | Validates a specific technical hypothesis; short-lived. |
| **MVP** | First real release; real consumers approaching; contract is a promise. |
| **production** | Live contract consumed by real services; every change has cost. |
| **other** | Treated as **MVP** until clarified. |

## Process matrix (CI gates always ON — see below)

| Stage | Pipeline | `devil` | `contract-reviewer` | Examples expected | Breaking-change attention | semver |
|---|---|---|---|---|---|---|
| **demo** | `ba`(light)→`api-architect`→`tsp-author`→`mock-validator`→`docs-writer` | skip | skip / optional | 1 happy-path per endpoint | low (usually pre-tag) | 0.x, fast |
| **prototype** | + `contract-reviewer` | skip | yes (light pass) | happy + 1–2 key errors | low | 0.x |
| **PoC** | full | optional | yes | happy + typical errors | medium | 0.x |
| **MVP** | full | recommended | yes (full) | success + all typical errors | high (enforced) | semver discipline |
| **production** | full, `devil` first | mandatory | full + adversarial | exhaustive (all status codes) | strict; breaking → ADR | strict semver |
| **other** | as MVP until clarified | — | — | — | — | — |

## Invariants — NEVER overridden by stage

**The 5 CI gates (TypeSpec drift · Spectral lint · example validation · breaking-change · Prism
mock smoke) and `@doc` on every model/property/operation are ALWAYS ON, regardless of stage.**
A stage modulates process depth and completeness — it does not touch contract integrity.
A missing `@doc`, a fake example, or a hand-edited `openapi.yml` is always forbidden
(`.claude/rules/no-stubs.md`, `.claude/rules/contract-first.md`).

## Where the stage lives

The stage is recorded in `PROJECT.md` (see `templates/PROJECT.md`). If `PROJECT.md` does not
state a stage, `ba` / `brief-synthesizer` must emit an **Open Question**; the orchestrator
asks via `AskUserQuestion` (options: demo / prototype / PoC / MVP / production / other).
Never assume a stage.

## How to read the matrix

- **Pipeline:** agents in the column are the minimum expected; add more if the contract
  complexity warrants it regardless of stage.
- **`devil`:** "skip" means the orchestrator may omit it by default; the user may always
  invoke it explicitly.
- **Examples:** a count here is a floor, not a ceiling — always add examples for error
  shapes that consumers would branch on (`.claude/rules/examples-validation.md`).
- **Breaking-change:** "low" relaxes urgency of semver precision, not the gate itself
  (`.claude/rules/breaking-changes.md`). ERR-level changes always require a MAJOR bump.

> First action on any task: read `PROJECT.md` for the declared stage. No stage → Open
> Question before proceeding. Scale the pipeline against the matrix; never silently skip
> an invariant (`.claude/rules/workflow.md`, `.claude/rules/preflight.md`).
