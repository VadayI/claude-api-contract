# ADR 0005 — Project maturity stage: guidance-only process scaler

**Status:** accepted · **Date:** 2026-06-08

## Context

The template's agents and pipeline previously ran at full production-grade rigour regardless
of whether the project was a throwaway demo or a live API serving two real consumer
repositories. This created friction for early-stage work (forcing full `devil` + adversarial
review on a PoC that will be discarded) while providing no explicit signal to tighten
things up when the contract is actually being shipped to production.

The contract's five CI gates (TypeSpec drift, Spectral lint, example validation,
breaking-change analysis, Prism mock smoke) are non-negotiable: they protect the integrity
of the contract and the consumers that pin it. But the *depth* of the design process —
how many pipeline stages run, whether `devil` is invoked, how complete the examples must
be — can be profitably scaled to match where in its lifecycle the project sits.

## Decision

Introduce a **project maturity stage** (`demo / prototype / PoC / MVP / production / other`)
as an explicit, recorded field in `PROJECT.md`. The stage acts as a **process scaler**:

- It modulates pipeline depth, `devil` invocation, review rigour, and expected example
  completeness (the process matrix lives in `.claude/rules/project-maturity.md`).
- It does **not** disable or weaken any CI gate, any `@doc` requirement, any no-stubs rule,
  or any contract-first invariant. Those apply on every stage without exception.
- `other` is treated as MVP until the user clarifies.
- The stage is collected at `/synthesize-brief` time; enforced as a CRITICAL build-input
  at `/preflight`. If absent in docs, `ba` / `brief-synthesizer` emits an Open Question;
  the orchestrator asks the user via `AskUserQuestion`. Never assume.

The rule is wired globally (import block in `CLAUDE.md`) because it governs the
orchestrator's dispatch decisions (pipeline depth, `devil` invocation).

## Consequences

**Positive:**
- Early-stage projects move faster without ceremony; production projects get full rigour
  by default.
- The stage is explicitly auditable in `PROJECT.md` — no implicit "we decided to skip devil
  because it felt like a demo."
- Consumers are protected: the CI gates that guard the wire shape are never relaxed.

**Risk / guard:**
- The stage must not become a rationalisation for weakening contract integrity. The invariant
  section of `project-maturity.md` states this explicitly. Any request to skip a CI gate
  on the grounds of "it's just a demo" is refused — the gate runs; only the process depth
  scales.
- `other` defaults to MVP strictness to err on the safe side when the intent is unclear.
