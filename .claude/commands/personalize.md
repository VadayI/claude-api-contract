---
model: sonnet
description: "[claude-api-contract] Rewrite template identity (URLs, package name, .claude tags, prose) to match this project. Run once after cloning from the template."
---

Personalize a `claude-api-contract`-derived project by replacing all template identity strings with this project's owner/repo/title. Two phases: a deterministic script for token replacements, then a `docs-writer` prose pass for natural-language descriptions.

## Log
```bash
node scripts/log-cmd.mjs /personalize "$ARGUMENTS"
```

## Input
Optional `$ARGUMENTS`: flags forwarded to `scripts/personalize.sh` — `--name <slug>`, `--owner <owner>`, `--title <title>`, `--description <desc>`, `--no-tier3`, `--force`. If `--name`/`--owner` are not provided, resolved from the git remote origin.

## Steps

### 1. Resolve identity
Run `scripts/personalize.sh --dry-run` (forwarding any `$ARGUMENTS` flags). Show the proposed values and the list of files that would change. Present to the user for review.

If the owner or slug cannot be resolved (no git remote set yet, no flags given), ask via `AskUserQuestion`:
- header `Project identity` — options based on detected slug, `basename $(pwd)`, or freeform.

### 2. Apply token replacements
Run `scripts/personalize.sh --yes [flags from $ARGUMENTS]`. This covers:
- **Tier 1** — `VadayI/claude-api-contract` URLs in README, `.env.example`, `versioning.md`, `contract-versioning/SKILL.md`, `sandbox.sh`; `package.json` name + description; `package-lock.json` name; README H1.
- **Tier 2** — `package.json` version reset to `0.0.0`; delete `docs/AUDIT-*.md` (template artifacts).
- **Tier 3** — `[claude-api-contract]` → `[{slug}]` in all `.claude/commands/`, `.claude/agents/`, `.claude/skills/` frontmatter.

### 3. Prose pass (`docs-writer`)
Dispatch `docs-writer` to rewrite natural-language identity that the script cannot safely touch:
- `README.md` — self-description paragraph (L3–L5), consumer list, status line. Replace with a project-appropriate description; if `PROJECT.md` exists, use its Purpose section. Reset status to `bootstrapping — no contract released yet`.
- `CLAUDE.md` — consumer section (the paragraph mentioning `claude-django`/`claude-react-mui`). Generalize to backend/frontend consumer roles, or use real names from `PROJECT.md` if provided.
- `.claude/rules/contract-first.md` — the ASCII source-of-truth diagram. Replace `claude-django` / `claude-react-mui` with generic `backend-consumer` / `frontend-consumer` (or project-specific names from `PROJECT.md`).
- (Optional) Reset `CHANGELOG.md`, `docs/HANDOFF.md`, `docs/WORKLOG.md` to fresh stubs — ask the user first.

Input to `docs-writer`: the resolved `OWNER/SLUG/TITLE` values + `PROJECT.md` content (if it exists).

### 4. PR
Create branch `chore/personalize`, stage all changes, open a PR. Never commit to `main`.
Commit message: `chore: personalize from template (owner/repo)`.
