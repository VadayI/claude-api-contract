# No stubs, no fakes in the contract

The contract is a promise. A stub is a broken promise that looks kept.

## Rules

- **No placeholder endpoints, fields, or schemas** "to be filled later". If a shape is unknown, it is a `ba`/`api-architect` question, not a guessed schema.
- **No fake examples.** Every example is valid against its schema and represents a real response (@.claude/rules/examples-validation.md).
- **No hand-edited `openapi.yml`.** The YAML is emitted from `spec/`; editing it by hand is a stub of the source (@.claude/rules/contract-first.md).
- **No empty `@doc`.** Spectral requires real descriptions; "TODO" text is a stub.

## If you must mark something incomplete

Use an explicit, greppable marker and log it, never a silent fake:

```
// STUB: <what is missing and why> — owner: <agent>, follow-up: <issue/plan ref>
```

A `STUB:` is a visible debt, surfaced in review and tracked in the living plan. A silent placeholder is forbidden.
