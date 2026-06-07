# Verify — Etap 3 (examples, mock, CI)

> Human verification handoff (@.claude/rules/verification.md). Confirm the contract
> behaves as designed without reading TypeSpec. Derived from
> `.claude/memory/endpoints.json` + `openapi.yml`. Regenerate with `/verify`.

## 0. Bring the mock up

```bash
npm run mock              # Prism static mock on http://localhost:4010 (examples)
# or: npm run mock:dynamic   # Faker + x-faker realistic payloads
```

Prism validates **both** request and response against the schema (two-way), and
**enforces security** — a protected endpoint without a bearer returns `401`.
Where a response has multiple status codes, select one with `Prefer: code=<N>`.

One-shot automated smoke (what CI runs):

```bash
npm run mock:smoke        # boots the mock, curls all 11 endpoints, asserts codes
```

## 1. Auth — `/auth/*` (public, except logout)

```bash
# register → 201 {user, tokens}
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:4010/auth/register \
  -H 'content-type: application/json' \
  -d @examples/auth/register.request.json                    # expect 201

# login → 200 {access, refresh}
curl -s -X POST http://localhost:4010/auth/login \
  -H 'content-type: application/json' \
  -d @examples/auth/login.request.json                       # expect 200, TokenPair

# refresh → 200 {access, refresh?}
curl -s -X POST http://localhost:4010/auth/refresh \
  -H 'content-type: application/json' \
  -d @examples/auth/refresh.request.json                     # expect 200, AccessToken

# service token (S2S, client-credentials) → 200 {access, token_type, expires_in, scope}
curl -s -X POST http://localhost:4010/auth/token \
  -H 'content-type: application/json' \
  -d @examples/auth/token.request.json                       # expect 200, ServiceTokenResponse

# logout → 204 (needs a bearer)
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:4010/auth/logout \
  -H 'authorization: Bearer testtoken'                       # expect 204
```

Confirm the mock issues usable tokens: `login` / `token` return a non-empty
`access` you can paste into `Authorization: Bearer <access>` for the articles calls.

## 2. Articles — `/api/v1/articles` (bearer OR service scope)

```bash
TOKEN=Bearer testtoken     # any bearer satisfies the mock's scheme check

# list (no auth) → 401  (security enforced)
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:4010/api/v1/articles   # expect 401

# list → 200 ListResponse<Article>
curl -s http://localhost:4010/api/v1/articles -H "authorization: $TOKEN"          # expect 200

# create → 201 Article
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:4010/api/v1/articles \
  -H "authorization: $TOKEN" -H 'content-type: application/json' \
  -d @examples/articles/create.request.json                                       # expect 201

# get one → 200 Article
curl -s http://localhost:4010/api/v1/articles/art_01HZX3K9P2QY -H "authorization: $TOKEN"  # expect 200

# update (partial) → 200 Article
curl -s -o /dev/null -w '%{http_code}\n' -X PATCH http://localhost:4010/api/v1/articles/art_01HZX3K9P2QY \
  -H "authorization: $TOKEN" -H 'content-type: application/json' \
  -d @examples/articles/update.request.json                                       # expect 200

# delete → 204
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE http://localhost:4010/api/v1/articles/art_01HZX3K9P2QY \
  -H "authorization: $TOKEN"                                                       # expect 204
```

### Exercise error envelopes (Prefer: code=N)

```bash
# 400 validation envelope {errors:[{field,code,message}]}
curl -s -X POST http://localhost:4010/api/v1/articles \
  -H "authorization: $TOKEN" -H 'content-type: application/json' \
  -H 'Prefer: code=400' -d '{}'

# 404 simple envelope {detail}
curl -s http://localhost:4010/api/v1/articles/missing \
  -H "authorization: $TOKEN" -H 'Prefer: code=404'

# 429 simple envelope + Retry-After header
curl -s -i http://localhost:4010/api/v1/articles \
  -H "authorization: $TOKEN" -H 'Prefer: code=429' | grep -i -E 'HTTP/|retry-after'
```

## 3. Checklist

- [ ] All 11 endpoints return their documented status codes (`npm run mock:smoke` green).
- [ ] `login` / `token` return a usable `access` token; protected calls accept it.
- [ ] List without a bearer → `401` (security enforced).
- [ ] `400` returns the validation envelope; `401/403/404/409/429` the simple `{detail}` envelope; `429` carries `Retry-After`.
- [ ] `npm run validate` green (compile + drift + spectral + examples).
- [ ] CI `contract-ci` green: drift · lint · examples · oasdiff breaking · mock smoke.

## CI gates (`.github/workflows/contract-ci.yml`)

| # | Gate | Command |
|---|---|---|
| 1 | TypeSpec drift | `npm run api:compile && bash scripts/check_typespec_drift.sh` |
| 2 | Spectral lint | `npm run lint` |
| 3 | Examples validation | `bash scripts/check_examples.sh` |
| 4 | Breaking changes | `npm run breaking` (oasdiff `--fail-on ERR`; SKIPs until first `v*` tag) |
| 5 | Prism mock smoke | `npm run mock:smoke` |
