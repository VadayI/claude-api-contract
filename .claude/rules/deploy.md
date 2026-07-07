# Deploy model (Prism mock → Docker → VPS)

> Loaded per-command by `/ship-contract` (`.claude/rules/deploy.md`).

The contract is delivered as a **static Prism mock** packaged into a Docker image and deployed directly on a VPS at `http://IP:PORT` (no nginx, no TLS). This is appropriate for development/staging mocks — the mock is stateless, read-only, and returns only contract-defined shapes.

## Architecture

```
[local machine]                   [ghcr.io]                [VPS]
openapi.yml + Dockerfile ──build──► image ──push──► pull ──► docker run
  (static Prism mock)           ghcr.io/<owner>/          -p PORT:PORT
                                <repo>-mock:<vX.Y.Z>      -h 0.0.0.0
                                                           │
                          backend + frontend ◄── http://IP:PORT
```

## Invariants

- **Agent never SSH-es.** The script builds and pushes locally; the user runs the VPS command.
- **Image tag = contract tag.** `ghcr.io/<owner>/<repo>-mock:<vX.Y.Z>` tracks the version; consumers know exactly what schema they're hitting.
- **Static mode only.** Deterministic responses from `examples` in the schema. No `-d` flag.
- **`-h 0.0.0.0` is required** in the Prism CMD — without it the mock is unreachable from outside the container.
- **`-m false` (single-process) is required** in the Prism CMD inside Docker — prism 5's default multiprocess mode reads `cluster.isPrimary`, which is `undefined` in a container, crashing at startup with `Cannot read properties of undefined (reading 'isPrimary')`. Local `npm run mock` is unaffected (it runs Prism directly via Node, not multiprocess).
- **`GITHUB_PERSONAL_ACCESS_TOKEN`** must have `write:packages` scope for `docker push` to `ghcr.io`. Never print or log the token.

## Readiness gate

`bash scripts/check_ready.sh` must pass before packaging. It verifies: compile + drift + lint + examples + endpoints registry + Prism smoke + breaking + artifact presence + auth endpoints. A contract that fails this gate is not ready for consumers.

## Security notes

- Direct `IP:PORT` is appropriate for dev/staging mocks (no auth required — contracts describe only shape, not secrets).
- If the ghcr.io package is private, the VPS needs `docker login ghcr.io` before `docker pull`.
- For production-adjacent environments: add TLS termination and IP allowlisting.
