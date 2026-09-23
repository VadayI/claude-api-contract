# API envelopes — list, error, rate-limit (standardized contract-wide)

> Loaded per-agent by `api-architect`, `tsp-author`, `contract-reviewer`. Confirmed defaults (§12.1).

Every list response, every error response, and rate-limiting use **one** shape across the whole contract. Define these once in `spec/models/` and reuse — never invent a per-endpoint variant.

## List envelope (pagination)

```
{ "count": <int>, "next": <url|null>, "previous": <url|null>, "results": [ T ] }
```

- Matches the Django REST Framework default → the backend consumer barely adapts.
- Gives the frontend a stable shape for TanStack Query.
- `results` is the only generic part; `count/next/previous` are always present.

## Error envelope

Two predictable shapes so every 4xx/5xx is parseable:

```
# simple errors (401, 403, 404, 409, 429, 500)
{ "detail": "<human-readable message>" }

# validation errors (400)
{ "errors": [ { "field": "<name>", "code": "<stable token>", "message": "<human>" } ] }
```

- `code` is a **stable token** (`required`, `invalid`, `not_found`, `conflict`, ...), safe for clients to branch on.
- Every operation declares the error responses it can return; no undocumented error shapes.

## Rate limiting (429 — important for S2S, D5)

- `429 Too Many Requests` uses the simple error envelope **plus** a `Retry-After` header (seconds or HTTP-date).
- Standardized in the contract from day one because service consumers hit the API harder than humans; the limit must be predictable and described.

## Wiring

- Define `ListResponse<T>`, `ErrorDetail`, `ValidationErrors`, and the `Retry-After` header as reusable TypeSpec models/decorators in `spec/models/`.
- `api-architect` specifies which envelope each endpoint uses; `tsp-author` references the shared models; `contract-reviewer` blocks any ad-hoc error/list shape.
