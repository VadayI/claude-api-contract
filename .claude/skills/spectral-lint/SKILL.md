---
name: spectral-lint
description: "[claude-api-contract] Crafting and running the layered Spectral ruleset — rule syntax, built-in functions, staged rollout, borrowed rules. Activate when editing .spectral.yaml or fixing lint failures. The enforcement list (what MUST be linted) lives in .claude/rules/spectral-style.md."
---

# Spectral Lint — recipes

> What must be enforced (casing, operationId, x-surface, envelopes, examples) — `.claude/rules/spectral-style.md`; this skill is the how-to.

## Rule syntax (live examples from `.spectral.yaml`)

```yaml
extends: [[spectral:oas, all]]
rules:
  schema-property-snake-case:
    description: Schema properties must be snake_case.
    severity: warn            # staged; tightening to error is decision H
    recommended: true
    given: $.components.schemas..properties.*~
    then:
      function: casing
      functionOptions: { type: snake, disallowDigits: false }

  operation-x-surface-required:
    description: Every operation must declare x-surface (resource|system).
    severity: error
    recommended: true         # derived projects may set false to stage rollout
    given: $.paths[*][get,post,put,patch,delete]
    then:
      - { field: x-surface, function: truthy }
      - { field: x-surface, function: enumeration, functionOptions: { values: [resource, system] } }
```

## Crafting order (cheapest first)

1. JSON Schema in the spec (types/formats/required/enums).
2. Spectral built-ins: `truthy`, `pattern`, `casing`, `length`, `enumeration`, `xor`.
3. Custom JS functions — last resort only.

## Run

```bash
npm run lint                         # spectral lint openapi.yml --ruleset .spectral.yaml
npx spectral lint openapi.yml --fail-severity warn
```

## Practice

- Disable a built-in that misfires deliberately (e.g. `oas3-server-not-example.com: off` while the template ships a placeholder server).
- Borrow rules (not whole files) from Zalando + DigitalOcean rulesets.
