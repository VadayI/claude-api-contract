# ADR 0003 — Bearer/JWT auth; refresh token in the response body

**Status:** accepted · **Date:** 2026-06-06

## Context
The primary client profile is service-to-service (D5), with a browser SPA consumer too. The contract must describe its own auth so the Prism mock can issue tokens.

## Decision
- Security scheme: `bearerAuth` (`type: http`, `scheme: bearer`, `bearerFormat: JWT`), global, with `security: []` on public endpoints.
- User-flow (D1 = B): register / login / refresh / logout. Access in `Authorization: Bearer`; **refresh in the response body** (D2) — self-contained contract, trivial mock.
- Service-flow (D5): `POST /auth/token` client-credentials + scopes (not roles). Short-lived access + revocation; rate limiting (`429` + `Retry-After`).

## Consequences
- Refresh-in-body is weaker against XSS than an httpOnly cookie. Acceptable for the template + autonomous mock; a derived project can switch to a cookie auth-mode (documented trade-off).
- The browser SPA uses only the user-flow; it never holds a service secret.
