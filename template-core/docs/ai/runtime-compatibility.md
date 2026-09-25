# Runtime and optional capability compatibility

Observed 2026-09-20. Inventory is configuration evidence, not a connection test.
Versions are measured versions, not a claim that every older/newer CLI is supported.

| Surface | Claude Code 2.1.216 | Codex 0.155.0-alpha.9.2 | Evidence / limit |
| --- | --- | --- | --- |
| Shared Python launcher | Version probe passed | Version probe passed | Native Windows; PowerShell 7.6.6 and explicit Git Bash, both runtimes through both wrappers |
| Standard-library process/env boundary | Shared | Shared | Windows Python 3.14 and Linux Python 3.13 child-process fixtures: literal argv/stdin, unchanged parent env, no dotenv execution, exit-code preservation |
| Explicit role/rule reads | P03 passed | P03 passed | React `docs/ai/pilot-report.md`; fresh generic launcher model sessions not rerun |
| Native custom role selection | P03 reviewer passed | NOT_VERIFIED | Use measured separate role launcher fallback; filenames do not prove role activation |
| Reviewer restrictions | Read/Glob/Grep only | Native read-only sandbox | P03 behavioral canary/read probes; restrictions are not equivalent OS isolation |
| Hooks | Reviewed invocation hook passed P03 | Trusted hook NOT_VERIFIED | No global trust or approval bypass granted |
| Session continuity (`session_context.py`) | SessionStart prints context (hook trust as above) | AGENTS.md start step | Linux Python 3.13 fixtures: Claude→Codex→Claude records, clone without `.ai-runtime`, parallel records; real session sequence NOT_VERIFIED |
| Nested instructions | Runtime-specific | Root vs nested cwd differs | Preserve explicit rule delivery; do not equate Claude paths with Codex nesting |
| MCP connections below | NOT_VERIFIED in this change | NOT_VERIFIED in this change | No server installation, download or credential read performed |
| macOS / WSL launchers | NOT_VERIFIED | NOT_VERIFIED | Linux unit fixtures do not establish those platforms |

## Capability inventory and migration

Sources: integrated React `.mcp.json`, `.claude/settings.json`,
`docs/ai/rules/mcp-stack.md`; contract and Django `.mcp.json`,
`.claude/settings.json`, `.claude/rules/mcp-stack.md`. Existing config remains
project-owned/mixed: the core installer does not replace it.

| Capability | Consumers | Existing Claude setup | Codex mapping | Prerequisites / credentials | Fallback |
| --- | --- | --- | --- | --- | --- |
| GitHub PR reads/create, repository data | docs-writer, reviewer, contract-reviewer, finalization | github plugin or Docker stdio in `.mcp.json`, never both | Optional stdio template using the same Docker command; no marketplace-ID translation | GitHub authorization; Docker/image if stdio chosen; user-supplied `GITHUB_PERSONAL_ACCESS_TOKEN` via explicit environment forwarding | `gh pr`, `gh api`; comments/reviews still need communication authorization |
| Actions logs/status | reviewer, finalization, fix-ci | GitHub capability or gh | Same CLI fallback | gh auth and network; optional `GH_TOKEN` passed by name | `gh run`, `gh pr checks`; missing access is NOT_VERIFIED |
| Current library documentation | architects, developers/authors, reviewers, docs-writer | context7 plugin or `npx @upstash/context7-mcp` | Optional unauthenticated stdio template from official Codex docs; credentials need a separately reviewed server configuration | Node/npx, reviewed server version/network; legacy authenticated path names `CONTEXT7_API_KEY` | Official library documentation; no invented current flags |
| Browser/reference inspection | UI architect, reviewer, tester | Django lists playwright plugin; React routes to available browser tools | Use actual available authorized browser capability | Browser/runtime installation and access to target; no generic token assumed | Available browser automation; inaccessible inspection stays NOT_VERIFIED |
| Application E2E | tester, readiness | Project test runner | Same project runner | Stack dependencies and browser binaries | No MCP substitution for unexecuted E2E |
| Process techniques | design/implementation/review roles | Legacy superpowers plugin (different marketplace IDs in Django/contract) | No literal ID translation; canonical local workflows | Optional external plugin must be separately reviewed/authorized | Versioned planning/TDD/debugging/verification procedures; full migration mapping remains P12 |
| Handoff, wrap-up, template update, auditor | finalization, auditor, template-sync | Contract family-core plugin | Local family core/workflow entry points | Python 3.13+; local versioned procedures | Shared delivery exists; complete plugin-function parity remains P08/P12, not yet claimed |
| Session continuity (start context, session records) | every session; wrap-up/handoff | SessionStart hook prints `session_context.py`; wrap-up creates a record | AGENTS.md start step and wrap-up/handoff skills run the same CLI | Python 3.13+, Git; no `.ai-runtime` needed | Mechanical fixtures (Claude→Codex→Claude, clone without `.ai-runtime`, parallel records) pass; a real cross-runtime session sequence is NOT_VERIFIED |

## Optional adapters

`templates/ai/mcp/codex.optional.toml` is an inert example, not an installed
configuration. Both servers are disabled and non-required. Review/pin server
versions before deliberately enabling them; existing upstream configs used mutable
image/package references, which are inventory facts rather than vetted versions.
Never copy this file wholesale over `.codex/config.toml` or enable duplicate
plugin/stdio providers. Do not copy Claude `${VAR}` interpolation into Codex argv.
Codex's `env_vars` names forward selected environment values to stdio servers.
See the [official MCP configuration reference](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

For Claude, retain and reconcile the existing `.mcp.json` server definitions and
user selection; no new plugin enablement is needed for base file/check workflows.
Legacy Context7 passes its API key in process argv; this core does not execute or
republish a secret value through that path. Prefer official docs until the chosen
server's credential transport/version is reviewed. Credentials belong to the
user's runtime store or explicitly selected process environment, never shared JSON.

Project config cannot grant trust to itself. Doctor integration must distinguish
missing required executable, missing optional plugin, disconnected MCP, untrusted
project config and unsupported capability. This document does not implement P05
doctor probes or mark unknown connections healthy. A runtime with a separately
configured required server may fail startup; the launcher preserves that failure.
