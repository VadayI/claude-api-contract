---
model: sonnet
description: "[claude-api-contract] Manage the plugin baseline (install/verify enabled plugins)."
---

Manage the committed plugin baseline (@.claude/rules/environment.md Scope 2).

## Log
```bash
node scripts/log-cmd.mjs /plugins "$ARGUMENTS"
```

## Steps
1. Compare installed plugins vs `.claude/settings.json` `enabledPlugins`: `superpowers@superpowers-marketplace`, `engineering@knowledge-work-plugins`, `github@claude-plugins-official`, `context7@claude-plugins-official`.
2. Report missing/extra. Propose `/plugin install ...` for missing ones; apply only after the user confirms.
3. Note: do NOT enable both a plugin and the `.mcp.json` fallback for the same MCP (github/context7).
