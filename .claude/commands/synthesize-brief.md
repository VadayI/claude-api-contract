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
1. Dispatch `brief-synthesizer`: fold `docs/**`, ADRs, and the conversation into `PROJECT.md` — purpose, resources, auth profile (D1/D5), envelopes, versioning policy, consumers, open questions.
2. Gaps become **Open Questions** (do not invent requirements).
3. Report the brief; suggest `/preflight`.
