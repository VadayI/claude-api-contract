# ADR 0007 — Changelog policy: Unreleased fragments + release stamping

**Status:** accepted · **Date:** 2026-06-13

## Context

The template gave two contradictory instructions about `CHANGELOG.md`:

- `/create-pr` and `.claude/rules/git-operations.md` required `CHANGELOG.md` to be
  **updated at PR time**.
- `/release`, `.claude/rules/versioning.md`, and `.claude/rules/breaking-changes.md`
  described the entry as **generated at release time** from
  `oasdiff changelog <prev-tag> openapi.yml`.

If both fire, a contract PR writes an entry and `/release` then prepends a second,
machine-generated one — duplicate or divergent history. The ambiguity also blocks the
planned `contract-policy` PR gate: it cannot know whether to require a changelog entry on a
PR or not.

Two repositories consume this contract (`claude-django`, `claude-react-mui`) and pin a
version. They need both *what* changed (wire shape) and *why / how to migrate* (intent).
`oasdiff changelog` produces an accurate but mechanical wire diff with no rationale; a purely
human changelog risks silently omitting a wire change. `CHANGELOG.md` already carries a
Keep-a-Changelog `## [Unreleased]` section.

## Decision

Adopt **Unreleased fragments + release stamping** (Keep a Changelog):

- **At PR time** — for a user-facing or contract change, the author adds a human-readable
  line under `## [Unreleased]` in `CHANGELOG.md` (the *why* / migration note). A non-contract
  or internal-only PR may legitimately add nothing ("n/a"). This is the single PR-side
  changelog requirement (`git-operations.md`).
- **At release time** — `/release` (via `docs-writer`):
  1. renames `## [Unreleased]` → `## [vX.Y.Z] — <date>`;
  2. runs `oasdiff changelog <prev-tag> openapi.yml` to **verify and augment** — add any wire
     change the fragments missed and flag breaking items + the required bump;
  3. opens a fresh empty `## [Unreleased]`.

`oasdiff` is the **safety net and breaking-change authority**, not the sole source; the human
fragments carry intent. `breaking-changes.md` and `versioning.md` stay valid — `oasdiff` still
folds in at release; this ADR clarifies it *verifies/augments* the accumulated fragments
rather than replacing them.

## Consequences

**Positive:**
- The changelog records both *what* (oasdiff-verified wire facts) and *why* (human fragments).
- Changes are reviewable per PR (the fragment is in the diff); releases stay deterministic.
- Unblocks the `contract-policy` gate (#2): it can require an `## [Unreleased]` fragment on
  user-facing / contract PRs while leaving release generation to `/release`.
- Matches the structure `CHANGELOG.md` already declares.

**Risk / guard:**
- Minor double-handling (author writes a line; oasdiff also runs at release). They are
  complementary: skipping the human fragment still yields an oasdiff-verified entry at release,
  so wire facts are never lost — only the rationale would be.
- Non-contract PRs must not be forced to invent a changelog line; "n/a" is valid. The future
  gate must scope the requirement to user-facing / contract changes only.
