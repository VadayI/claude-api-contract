# Contract production instruction structure (P04)

The canonical 21 rules live in `docs/ai/rules`. Their full text is retained;
explicit changes remove inherited coordinator scope from workers, obsolete
confirmation/three-file restrictions, plugin hard requirements and automatic Git
lock deletion. The historic root instructions are preserved as non-normative
`docs/ai/legacy/instructions-before-p04.md`. `migration-inventory.json` records the
original 10 agents, 19 commands, six skills and 21 rules with baseline hashes.
Unselected roles/skills/commands remain delivered unchanged and explicitly await
P12 semantic migration. This checkpoint does not claim their Codex runtime parity.

`tsp-author` and read-only `contract-reviewer` receive all 20 non-coordinator rules
as complete generated packs. `catalog.json` declares dependencies; the shared
renderer rejects omitted dependencies and coordinator leakage. Legacy rule paths
are generated pointers to full sources, so remaining consumers can follow them.
Selected bootstrap/doctor/verify workflows retain their substantive steps with
portable arguments/tools and explicit ownership limits. Local handoff, wrap-up,
audit, language and template-sync procedures replace the mandatory marketplace
dependency for these functions; they do not claim an unavailable plugin's exact
implementation or successful operational checks.

## Generation and safe delivery

```
python scripts/ai/production.py --check
python scripts/ai/production.py --apply
python scripts/ai/production.py --target "../my contract"       # preview
python scripts/ai/production.py --target "../my contract" --apply
```

`templates/ai/production-inputs.json` explicitly lists public delivery files.
`docs/ai/production-manifest.json` records their content hashes/ownership;
`docs/ai/generated/adapters-manifest.json` records canonical source digests.
`scripts/seed.sh` clones the selected ref then calls the same Python preflight.
Native Windows uses `C:/Program Files/Git/bin/bash.exe` explicitly. `--force` only
retains CLI compatibility: it cannot override a conflict. Source drift fails
before any write. Project notes are seed-once and never read during update;
mixed settings/config require review when customized. Exact recorded legacy
template hashes permit the known migration; all other local edits conflict.
No secret path is eligible; `.env.example` is the sole public env exception.

Fresh seed omits active `.github/workflows`; existing project workflows are not
modified. The CI choice is recorded and the owned workflow materialized only by
`scripts/ai/ci_mode.py --mode local|github --apply`, which must run before the
first push. Seed creates no remote, does not stage/push or run
npm, does not seed private env, and does not clear runtime/project memory.
The temporary clone is retained with its exact path for review, not blindly
removed. All supplied files operate without a sibling clone or network plugin.

Repeated install is empty. Once a receipt exists, project-owned files are never
reseeded, including after intentional deletion. The receipt is written last, so
already-written identical files can be retried after interruption. Full
transactional backup and rollback remain P13; no reset/clean/stash is used.
Removed files are retained rather than deleted. Existing custom
AGENTS/CLAUDE/MCP/settings are not replaced.
Project overrides, language, registry and Class B derived artifacts remain owned
by the project. Personalization must target reviewed project identity fields;
legacy broad personalization/reset-to-clone scripts are not update mechanisms.

## Runtime evidence and remaining scope

The generated Codex layout follows the current official
[custom agent format](https://learn.chatgpt.com/docs/agent-configuration/subagents)
and [repository skills layout](https://learn.chatgpt.com/docs/build-skills), read
2026-09-20. Generated role files inherit model settings; reviewer declares read-only.
No project trust or global settings are changed. Existing measured CLI behavior
and limitations remain in `runtime-compatibility.md`; file parsing/discovery is
not proof of a completed role session. Local prompts/role packs are the fallback
when native custom-role activation is unavailable.

Source Claude settings no longer pin a model, auto-register optional marketplaces
or run a Stop formatter. The compatible SessionStart runs the shared detector,
the stack probe and prints the session context; it cannot remove index.lock,
create env or install packages. Shared detector/runner (P05) and runtime
hooks/CI (P06) are delivered; P07 adds the project-state resolver/migration and
session continuity (project-state-migration.md, session-continuity.md). P08 adds the
Git lifecycle CLI (git-lifecycle.md) used by wrap-up; its Windows and real-GitHub
acceptance, all-role transfer (P12) and end-to-end derived acceptance (P13) remain
separate criteria. Registries resolve `docs/project-state/` first and fall back
to legacy `.claude/memory/` until `project_state.py --apply` migrates them.
