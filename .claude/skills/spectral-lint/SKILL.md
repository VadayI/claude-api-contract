---
name: spectral-lint
description: "[claude-api-contract] Writing and running a layered Spectral ruleset for OpenAPI governance. Activate when crafting .spectral.yaml rules or fixing lint failures."
---

# Spectral Lint

## Layered ruleset (.spectral.yaml)
```yaml
extends: [[spectral:oas, all]]
rules:
  # property casing
  property-casing:
    description: Properties must be snake_case.
    severity: error
    given: $.components.schemas..properties.*~
    then: { function: casing, functionOptions: { type: snake } }
  # operationId present + unique handled by spectral:oas; add casing if desired
  operation-summary-required:
    given: $.paths[*][get,post,put,patch,delete]
    then: { field: summary, function: truthy }
    severity: error
```

## Crafting order (cheapest first)
1. JSON Schema in the spec (types/formats/required/enums).
2. Spectral built-ins: `truthy`, `pattern`, `casing`, `length`, `enumeration`, `xor`.
3. Custom JS functions — last resort only.

## Must-enforce (beyond minimal spectral:oas)
- property casing; `operationId` present/unique; `summary`+`description`+`tags`.
- declared error responses; no anonymous inline objects.
- example validity: `oas3-valid-schema-example`, `oas3-valid-media-type-examples`.

## Run
```bash
npm run lint                         # spectral lint openapi.yml --ruleset .spectral.yaml
npx spectral lint openapi.yml --fail-severity warn
```

## Practice
- `spectral:oas` is intentionally minimal — extend it.
- `recommended: true/false` to stage rollout in derived projects.
- Borrow rules (not whole files) from Zalando + DigitalOcean rulesets.
