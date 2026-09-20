# ADR 0001: portable family core and explicit rule delivery

Status: accepted for implementation, 2026-09-20. Downstream integration pending.

## Evidence

The React P03 pilot is recorded at `claude-react-mui` commit
`d0b9f59152a5ce06af78ae651376bda95d137b45`, including sanitized per-run hashes.
K1/K2 passed S1 after independent accessibility and seed corrections, S2 contract
policy/drift, S3 owned commit/local push, S4 stale Git handoff, and coordinator
reported-file scope. A separate Codex reviewer launcher read all 27 sources and
left its canary unchanged under the read-only sandbox. Native Codex custom-role
selection and trusted hooks remain unverified. Windows Git push required reviewed
escalation. The one-off user-authorized approval flag is never a launcher default.

K1's initial file-list run omitted rules; its full-pack retry read every source.
K2 read both formats but needed independent review in either case. Different
inherited Claude models and unavailable Codex prices prevent an adapter-only
quality/cost comparison. No token savings are claimed.

## Decision

1. Keep editable Markdown rules/contracts/workflows with JSON metadata. Generate
   wrappers and complete role packs, including source paths, SHA-256 and end
   markers. Prefer packs by default; preserve explicit file-list delivery.
   Reviewers remain read-only, workers may implement, and coordinator restrictions
   apply only to explicitly coordinating sessions.
2. Store versioned common tooling in this API-contract repository's
   `template-core/`, independently of the API version. Use Python 3.13+ and only
   its standard library. Stack rules remain sources in their stack repositories.
3. Vendor ordinary files into downstream projects, using an exact source commit,
   source content digest and per-file ownership manifest. Runtime needs neither
   an adjacent repository nor a marketplace plugin. A development pin is labelled
   explicitly. Final acceptance requires a remotely available integrated commit;
   after squash integration, replace the development pin and recheck its digest.
4. Generate local contract delivery from local core content without embedding the
   current commit's own SHA. Downstream pins are written only after the source
   commit exists. Read-only checks fail on drift and do not repair it.
5. Preserve project notes, settings, registries, overrides and secrets. Update
   unchanged template-owned files only. Mixed/customized files produce a complete
   conflict preview with zero writes. Do not delete obsolete files implicitly.
6. Launchers inherit models and trust. Unsupported native roles use explicit
   separate sessions with artifact reports. Optional MCP/plugin capabilities are
   reported separately; they cannot block ordinary reading/editing/local checks.
   Never grant project trust, install plugins or widen global permissions.

## Migration and acceptance boundaries

The P09 readiness resolver is the first independent core component. P04 adds
pinning, schemas, reproducible delivery and launchers; P05 adds exact-candidate
runner evidence; P06 adds explicit CI selection; P07 migrates memory; P08 adds
the Git state machine; P10/P11/P12 complete adoption/readiness/stack delivery.
Each component needs executable acceptance before its status becomes complete.
Existing personal configuration and historical untracked contract Class B files
are excluded. Merge, release tags and deployment remain separately authorized.
