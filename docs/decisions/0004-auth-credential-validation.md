# ADR 0004 — Auth credential validation defaults

**Status:** accepted · **Date:** 2026-09-24

## Context

The reusable auth request schemas accepted any string for email and password. Backend serializers commonly reject malformed email values, empty login passwords, and registration passwords shorter than 8 characters. Schema-based conformance tools can generate such requests when the contract leaves them valid, producing false conformance failures and exposing defaults that are unsuitable for a new project template.

## Decision

- Mark auth email request properties as `format: email`.
- Require login passwords to have at least one character.
- Require registration passwords to have at least 8 characters.
- Keep these as template defaults; derived projects may define a stricter registration rule from their own security requirements.

## Consequences

- TypeSpec remains the source of truth and the OpenAPI output must be regenerated.
- This tightens request validation and is a breaking contract change. A release that includes it requires a MAJOR version bump.
- Backends consuming the updated contract must implement compatible serializer validation.

## Amendment — v2.0.0 NUL handling and contextual validators

The first hosted Django conformance run on v1.0.0 found that Schemathesis generated a login password containing a NUL character, which Django rejected although the schema allowed it. The v2.0.0 schema prohibits NUL in login and registration passwords. Registration keeps its reusable minimum of 8 characters; contextual checks such as blocklists and user similarity may still reject a schema-shaped value with the documented 400 validation response. The Django conformance runner allows that response for registration while continuing to validate its error schema.
