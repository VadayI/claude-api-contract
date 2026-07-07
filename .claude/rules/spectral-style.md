# Spectral linting (layered ruleset, enforced)

> Loaded by `contract-reviewer` (agent) and `/validate-contract`, `/review-pr`, `/fix-ci` (commands). Gate: `npm run lint`.

`.spectral.yaml` is a **layered** ruleset — not a copy of someone else's. It `extends: [[spectral:oas, all]]` and adds custom rules for this repo's naming / codes / envelope.

## Crafting order (cheapest first)

1. Lean on **JSON Schema** in the spec itself (types, formats, required, enums).
2. Then **Spectral's built-in functions** (`truthy`, `pattern`, `casing`, `length`, `enumeration`, ...).
3. Only then **custom JS functions** — last resort, hardest to maintain.

## What the layer must enforce (beyond the minimal `spectral:oas`)

- **Property casing** — snake_case (or the chosen repo convention), consistently.
- **`operationId` present, unique, and casing-consistent** (it becomes a consumer symbol).
- **`summary` + `description` + at least one `tag`** on every operation.
- **`x-surface` on every operation** — `resource` or `system`; the frontend page-vs-system separation, gate `operation-x-surface-required` (`.claude/rules/endpoint-surface.md`).
- **Error responses declared** — every operation lists the error envelope responses it can return (`.claude/rules/api-envelope.md`).
- **No anonymous inline objects** in schemas — named components only.
- **`example`/`examples` validate against schema** (built-in `oas3-valid-schema-example`, `oas3-valid-media-type-examples`) — this is also the examples gate (`scripts/check_examples.sh`).

## Practices

- `spectral:oas` is intentionally minimal — extending it is mandatory, not optional.
- Use `recommended: true/false` on custom rules to stage a gradual rollout in derived projects.
- Borrow concrete rules from **Zalando** (versioning, naming, request/response shape) and **DigitalOcean** (`operationId` naming, `$ref` discipline) rulesets — copy the *rule*, not the whole file.

> Activate the `spectral-lint` skill for rule syntax and examples.
