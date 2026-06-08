---
model: sonnet
description: "[claude-api-contract] Synthesize PROJECT.md from docs/** and the conversation."
---

Produce a single `PROJECT.md` brief. Delegates to `brief-synthesizer`.

## Log
```bash
node scripts/log-cmd.mjs /synthesize-brief "$ARGUMENTS"
```

## Steps
1. Dispatch `brief-synthesizer`: fold `docs/**`, ADRs, and the conversation into `PROJECT.md` — **maturity stage** (demo / prototype / PoC / MVP / production / other), purpose, resources, auth profile (D1/D5), envelopes, versioning policy, consumers, **Definition of Done** (§7 — standard gates + project-specific criteria agreed with the team), open questions. If the stage is absent, it becomes the first Open Question (@.claude/rules/project-maturity.md). If the DoD project-specific criteria are absent, surface them explicitly for agreement — the DoD section must never be left blank.
2. Gaps become **Open Questions** (do not invent requirements).
3. Report the brief; suggest `/preflight`.
