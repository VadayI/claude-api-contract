# WORKLOG

> Append-only chronicle of what changed each session (newest first).

## 2026-06-07
- Migrated all auth endpoints to the `/api/v1/auth/*` prefix
  (register, login, refresh, logout, token) — PR #9. Intentional breaking change,
  recorded in ADR 0004; the 5 path renames are listed in `.oasdiff-ignore.txt`
  to keep the breaking-change gate active for everything else.
  — gates: validate green · drift green · breaking classified (5 ERR
  path-removed, intentional/ignored) — tag: v0.2.0 (MINOR, pre-1.0 breaking convention).
  Consumers: update any hardcoded `/auth/` prefix to `/api/v1/auth/` and bump
  `CONTRACT_VERSION` pin to `v0.2.0`.
