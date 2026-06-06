---
model: sonnet
description: "[claude-api-contract] Set or change the output language rule."
---

Set the project output language (explanations, PR/commit messages, comments — code identifiers/paths stay English).

## Log
```bash
node scripts/log-cmd.mjs /set-language "$ARGUMENTS"
```

## Steps
1. Ask via `AskUserQuestion` (header `Language`): `English` (Recommended), `Українська`, `Polski` (harness adds "Other").
2. **English** → remove `.claude/rules/output-language.md` if present and drop its `@`-import from `CLAUDE.md`.
3. **Other** → copy `templates/output-language.md` → `.claude/rules/output-language.md` replacing both `{LANGUAGE_NATIVE}` tokens; append `@.claude/rules/output-language.md` to the `CLAUDE.md` import block (after `@.claude/rules/preflight.md`) if not already present.
4. Confirm and respond in the chosen language from now on.
