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

## commitlint: Node version floor (when adding Husky)

- **Symptom:** `npm i -D @commitlint/cli` pulls v21, which fails to install/run on Node 20.x.
- **Cause:** `@commitlint/cli@21` declares `engines.node >= 22.12.0`; this template targets
  Node `>=20.19`.
- **Fix:** pin commitlint to **v19** (`@commitlint/cli@^19`, `@commitlint/config-conventional@^19`)
  — `engines.node >= v18`, compatible with the project floor. Husky v9 is fine (`node >=18`).
- **Note:** `commitlint.config.mjs` disables `subject-case` + `*-max-line-length` so a Ukrainian
  subject/body passes while the English type prefix (`feat:`, `fix:`) is still enforced.
