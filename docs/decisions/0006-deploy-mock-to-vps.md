# ADR 0006 — Deploy static Prism mock to VPS via Docker + ghcr.io

**Status:** accepted · **Date:** 2026-06-09

## Context
The contract is the single source of truth. Before any backend code exists, both consumers (`claude-django` and `claude-react-mui`) need to work against the Prism mock. Running `npm run mock` locally means each consumer brings up their own mock instance independently, with no guarantee they are testing against the same contract version. A shared, versioned VPS deployment gives both teams one stable URL pinned to the same contract tag.

## Decision
1. Package the static Prism mock into a Docker image (`node:22-alpine`, `prism-cli` installed globally), built from the `Dockerfile` at the repo root.
2. Publish to `ghcr.io/<owner>/<repo>-mock:<vX.Y.Z>` — the image tag matches the contract version tag.
3. Expose directly on `IP:PORT` (no nginx / reverse proxy). The mock is read-only, stateless, and returns only contract-defined shapes; TLS termination is not required for development/staging use.
4. VPS deployment: `docker pull ghcr.io/<owner>/<repo>-mock:<tag>` then `docker run -d --restart unless-stopped`. The deploy script (`scripts/deploy-mock.sh`) builds the image, pushes it to ghcr.io, and prints the exact VPS command — the **user** executes it on the VPS. The agent never SSH-es into remote machines.
5. `npm run deploy:mock` is the entry point; `--dry-run` previews all steps without contacting Docker or ghcr.io.

## Consequences
- Both consumers share one stable mock URL `http://IP:PORT`, pinned to a specific contract tag.
- Mock version tracks the contract git tag — consumers know exactly what schema they are testing against.
- Redeploying after a release: `npm run deploy:mock -- --ip <VPS_IP> --port <PORT>`, then run the printed `docker run` command on the VPS.
- Security note: direct `IP:PORT` is appropriate for development and staging mocks (responses contain only contract-defined shapes, no real secrets). For production-adjacent environments, add TLS termination and an auth layer in front.
- Docker and a ghcr.io write-capable `GITHUB_PERSONAL_ACCESS_TOKEN` (`packages:write`) are required on the machine running `deploy:mock`; they are not required to run the contract quality gates.
