# Moving a project from a Windows drive to the WSL filesystem

Decision D17/D11: the working clone lives in the WSL ext4 filesystem
(`~/src/<repo>`), not on a Windows drive seen from WSL (`/mnt/c`, `/mnt/d`). Agents
refuse to work on `/mnt` unless the user starts the session with
`ALLOW_MNT_SESSION=1` (see [session continuity](session-continuity.md#working-directory-gate-d17)).

## Why

Docker Desktop runs inside WSL2. A bind mount such as `./backend:/app` from a
Windows drive reads every file through the Windows → WSL bridge (9P/drvfs).
Measured on a real Django project:

| Operation | On `D:` (`/mnt/d`) | On ext4 (`~/src`) |
|---|---|---|
| Full pytest | 55 min | 1 min 37 s |
| Image build | 36 min | 41 s |
| pytest-xdist, 16 workers | CPU 83 % of 1600 %, stalled 12 min at start | scales |

Parallel test workers do not help on 9P: they serialize on I/O. Without
`.dockerignore` the build context also carried 386 MB of media.

## Diagnose

```bash
time ls -R /mnt/d/<path>/<repo> >/dev/null   # Windows drive
time ls -R ~/src/<repo> >/dev/null            # ext4: typically 10–50x faster
docker stats                                  # during tests: CPU far below 100 % x cores
                                              # with live processes = waiting for disk
```

## Checklist (8 steps)

1. **Stop the stack** in the old checkout: `docker compose down`.
2. **Save what Git would not carry**: push every local branch you need and note
   stashes (`git stash list`); nothing is copied implicitly.
3. **Clone into ext4**: `mkdir -p ~/src && git clone <remote-url> ~/src/<repo>`.
4. **Copy untracked local files by hand**: `.env*`, `.claude/settings.local.json`.
   Never copy `node_modules`, `.venv`, `__pycache__` or other caches.
5. **Rebuild from scratch**: keep `.dockerignore` (media, caches, `node_modules`,
   `.git`, `.env*`); `docker compose build`, `npm ci` or a fresh virtualenv.
6. **Large Windows data** (photos, datasets): mount it into the container
   separately and read-only; code, venv and caches stay on ext4.
7. **Measure**: repeat the diagnosis above, then run the full test command the
   agent gives you (agents do not run the full suite themselves, D12) and record
   the time in the session record.
8. **Switch the tools**: `cd ~/src/<repo> && code .` (VS Code Remote-WSL), start
   Claude Code or Codex there; archive the `/mnt` checkout after the first green run.

If moving is impossible right now, keep at least a test clone on ext4 for the
full test run and pre-push, with its own `COMPOSE_PROJECT_NAME` so the working
stack is not touched.
