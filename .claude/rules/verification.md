# Verification handoff (prove the contract works)

Every pipeline run ends with a verification handoff so a human can confirm the contract behaves as designed — without reading TypeSpec.

## Machine-readable endpoint registry

`api-architect` records each endpoint in `.claude/memory/endpoints.json` (committed — it is the registry, not session-local state). One object per endpoint:

```
{ "method": "POST", "path": "/api/v1/articles", "tag": "articles",
  "operationId": "createArticle", "auth": "bearerAuth",
  "scopes": ["articles:write"], "statuses": [201, 400, 401, 403, 429],
  "envelope": "single|list", "surface": "resource", "notes": "..." }
```

Append/update; never duplicate a `method+path`. Each entry also carries a `surface` (`resource`/`system`); frontend page routes live in the sibling `.claude/memory/pages.json` page-map (`.claude/rules/endpoint-surface.md`). The contract is incomplete until the registry entry exists.

## Verification doc

`docs-writer` generates `docs/verify/<feature>.md`: a Prism + `curl` checklist derived from `endpoints.json` + `openapi.yml`, so the user can:

1. `npm run mock` and hit each endpoint with the documented request.
2. Confirm the response matches the contract (Prism validates both directions).
3. Tick off status codes and the auth/scope behavior.

Regenerate on demand with `/verify`.

## What "verified" means here

- `npm run validate` green (compile + drift + lint + examples + endpoints registry).
- `npm run breaking` classified, semver bump stated.
- Prism mock comes up and returns valid responses for the new endpoints.
- `endpoints.json` and `docs/api/INDEX.md` reflect reality.
