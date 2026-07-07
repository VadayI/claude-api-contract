---
name: prism-mock
description: "[claude-api-contract] Running the Prism mock — commands for static/dynamic/proxy modes and x-faker recipes. Activate for mock smoke tests or example debugging. Invariants (two-way validation gate, Docker flags, mode semantics) live in .claude/rules/prism-mock.md."
---

# Prism Mock — recipes

> Invariants (two-way validation as the gate, static default, Docker flags, port) — `.claude/rules/prism-mock.md`; this skill is the how-to.

## Run

```bash
npm run mock                 # static (examples) on $PRISM_PORT (default 4010)
npm run mock:dynamic         # dynamic (Faker + x-faker)
npx prism mock openapi.yml -p 4010
npx prism mock openapi.yml -d -p 4010            # dynamic
npx prism proxy openapi.yml https://api...       # contract-test a live API (optional)
npx prism mock openapi.yml -h 0.0.0.0 -m false   # in Docker — both flags required (.claude/rules/deploy.md)
```

## x-faker

```yaml
properties:
  first_name:
    type: string
    x-faker: name.firstName
```

Controls dynamic generation per property.

## Smoke recipe

- Bring the mock up, hit each endpoint with the documented request; expect a 2xx valid body and the documented error codes (checklists: `docs/verify/*.md`, gate: `bash scripts/check_mock.sh`).
- Live-reloads on `openapi.yml` change — keep it running while editing examples.
