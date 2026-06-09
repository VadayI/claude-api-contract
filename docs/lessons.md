# Lessons (gotchas worth keeping)

> Append as you encounter non-obvious behaviour in TypeSpec, Spectral, Prism, oasdiff, or the CI gates.
> Format: `## <area>` → bullet per gotcha.

## Prism: multiprocess crash in Docker (prism 5)

- **Symptom:** container exits immediately at startup with
  `TypeError: Cannot read properties of undefined (reading 'isPrimary')` at `createMultiProcessPrism`.
- **Cause:** Prism 5 defaults to multiprocess mode and reads `cluster.isPrimary`, which is
  `undefined` inside a Docker container.
- **Fix:** add `-m false` to the `prism mock` command (single-process). Lives in the root
  `Dockerfile` CMD; applies to all Docker/Compose deploys.
- **Note:** local `npm run mock` is unaffected — it runs Prism directly via Node, not in Docker.
