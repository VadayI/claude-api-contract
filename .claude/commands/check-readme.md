---
model: sonnet
description: "[claude-api-contract] Audit README.md against live state and apply fixes — version, counts, consumer section, links."
---

Audit `README.md` for staleness against the live repository state and update it via `docs-writer`. @.claude/rules/contract-first.md

## Log
```bash
node scripts/log-cmd.mjs /check-readme "$ARGUMENTS"
```

## Input

`$ARGUMENTS` is currently unused (the command takes no arguments). Reserved for a future `--dry-run` flag.

## Steps

1. **Dispatch `docs-writer`** to audit README.md against live state:
   - **Version drift:** compare the status line in README (the `> Status:` blockquote near the bottom) against `git tag --list 'v*' --sort=-version:refname | head -n1`. If they differ, flag as stale.
   - **Command/agent/rule counts:** compare README claims against actual directory counts (derive the live numbers from the globs below — never trust a frozen example):
     - `ls .claude/commands/*.md | wc -l` for commands
     - `ls .claude/agents/*.md | wc -l` for agents
     - `ls .claude/rules/*.md | wc -l` for rules
     - `ls .claude/skills/*/SKILL.md | wc -l` for skills
   - **`## For consumers` section:** three states:
     - Section **missing entirely** → informational note only: "will be created by `/ship-contract`" (expected on a fresh project before first ship — not an error).
     - Section **present with `<IP>:<PORT>` placeholder** → flag as stale: "run `/ship-contract` to fill in the live URL".
     - Section **present with a real IP** → OK, report as current.
   - **`## Quick start` section:** verify `/check-readme` and `/ship-contract` are listed.
   - **Broken internal links:** check that every `@.claude/rules/*.md` reference in README exists on disk.

2. **Report drift** — a checklist of what is stale vs current. Ask for confirmation before applying any changes.

3. **Apply fixes** (after confirmation) — `docs-writer` edits README.md:
   - Update the status line to the current tag.
   - Update any stale command/agent/rule/skill counts.
   - Add `/check-readme` and `/ship-contract` to `## Quick start` if missing.
   - Fix broken links.
   - Do NOT touch the `## For consumers` URL placeholder (that is `/ship-contract`'s job).

4. **Report** — list every change applied. Suggest `/ship-contract <IP> <PORT>` to fill in the consumer mock URL, or `/wrap-up` to persist the session.
