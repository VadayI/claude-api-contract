# Spectral linting (layered ruleset, enforced)

> Loaded by `contract-reviewer` (agent) and `/validate-contract`, `/review-pr`, `/fix-ci` (commands). Gate: `npm run lint`.
> **Norms live here; rule-crafting recipes live in the `spectral-lint` skill.**

`.spectral.yaml` is a **layered** ruleset — not a copy of someone else's. It `extends: [[spectral:oas, all]]` — intentionally minimal, so extending it is mandatory, not optional — and adds custom rules for this repo's naming / codes / envelope. Custom rules may stage a gradual rollout in derived projects via `recommended: true/false`.

## What the layer must enforce (beyond the minimal `spectral:oas`)

- **Property casing** — snake_case (or the chosen repo convention), consistently.
- **`operationId` present, unique, and casing-consistent** (it becomes a consumer symbol).
- **`summary` + `description` + at least one `tag`** on every operation.
- **`x-surface` on every operation** — `resource` or `system`; the frontend page-vs-system separation, gate `operation-x-surface-required` (`.claude/rules/endpoint-surface.md`).
- **Error responses declared** — every operation lists the error envelope responses it can return (`.claude/rules/api-envelope.md`).
- **No anonymous inline objects** in schemas — named components only.
- **`example`/`examples` validate against schema** (built-in `oas3-valid-schema-example`, `oas3-valid-media-type-examples`) — this is also the examples gate (`scripts/check_examples.sh`).

> Activate the `spectral-lint` skill for crafting order, rule syntax, run commands, and borrowed-rule sources (Zalando / DigitalOcean).
