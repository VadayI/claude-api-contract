---
model: sonnet
description: "[claude-api-contract] Package the Prism mock into Docker, push to ghcr.io, print the VPS deploy command — and update README ## For consumers with the live URL."
---

Package the static Prism mock into a versioned Docker image, push to `ghcr.io`, and print the exact VPS command. Updates `README.md ## For consumers` with the real `http://IP:PORT` once live. @.claude/rules/deploy.md

## Log
```bash
node scripts/log-cmd.mjs /ship-contract "$ARGUMENTS"
```

## Input

`$ARGUMENTS` = `<IP> <PORT>` (space-separated). If either is missing, ask via `AskUserQuestion`:
- IP: the VPS public IP address
- PORT: port to expose (default: 4010)

## Steps

0. **Runtime gate.** Read `.claude/memory/env-detect.json`. If missing → `NO_ENV_DETECT`. If `platform_supported == false` → STOP. If `node_supported == false` → STOP.

1. **Readiness gate.**
   ```bash
   bash scripts/check_ready.sh
   ```
   RED → identify which check failed and route to the right agent:
   - compile/drift/lint → `tsp-author` or `contract-reviewer`
   - examples → `mock-validator`
   - mock smoke → `mock-validator`
   - missing auth endpoints → `api-architect`
   
   Do NOT continue if the contract is not ready.

2. **Package + push.**
   ```bash
   bash scripts/deploy-mock.sh --ip $IP --port $PORT
   ```
   This builds the Docker image, pushes to `ghcr.io/<owner>/<repo>-mock:<tag>`, and prints the VPS `docker run` command. **The user must run that VPS command manually** — this step only builds and pushes. Print the VPS command prominently.

3. **Update README.** Delegate to `docs-writer`: replace the `http://<IP>:<PORT>` placeholder in `README.md ## For consumers` with the real `http://$IP:$PORT`. Also note the image ref `ghcr.io/<owner>/<repo>-mock:<tag>`. Commit the README change.

4. **Report:**
   - Base URL: `http://$IP:$PORT`
   - Image: `ghcr.io/<owner>/<repo>-mock:<tag>`
   - VPS command: (repeat the docker run command from step 2)
   - Next step: `/release` if HEAD is not yet tagged (so consumers have a `CONTRACT_VERSION` to pin), or `/wrap-up` to persist the session.
