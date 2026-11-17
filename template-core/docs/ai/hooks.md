# Claude Code hooks: reliability standard (D18) and anchored path rules (D26)

Every template keeps its hooks by hand in `.claude/settings.json`; the core does not
generate them. `scripts/ai/hook_check.py settings` checks that file against the rules
below and `scripts/ai/hook_check.py version` reports whether the installed Claude Code
honours fail-closed hooks. `/doctor` runs both.

## Why

- Claude Code runs a command hook in the session's **current** directory, and that
  directory moves after `cd`. A hook written as `node scripts/policy/guard.mjs` then
  points at a file that does not exist.
- A hook that exits with any code other than 0 or 2 (including "command not found")
  is a **non-blocking error**: the action goes ahead. Only `"onFailure": "block"`
  (Claude Code 2.1.295+) turns such a failure into a block.
- Exit code 2 *is* a block. `python3 missing.py` exits 2, so a relative Python hook
  blocks every action after `cd`; `node missing.mjs` (exit 1) and `bash missing.sh`
  (exit 127) let every action through. Both are wrong.
- `python` is not on PATH in many WSL/Linux installations; `python3` is.

## Standard

| Rule | Form |
|---|---|
| Script path | `"$CLAUDE_PROJECT_DIR/scripts/..."` in double quotes (shell form) or `"${CLAUDE_PROJECT_DIR}/scripts/..."` as an `args` element (exec form) |
| Python | shell form only: `"${AI_PYTHON:-python3}" "$CLAUDE_PROJECT_DIR/scripts/....py"`; the default needs a shell, so never the exec form and never bare `python`/`python3`/`py` |
| Node | exec form: `"command": "node", "args": ["${CLAUDE_PROJECT_DIR}/scripts/....mjs"]` (no shell involved) |
| `onFailure` | every handler on `PreToolUse`, `UserPromptSubmit` and `UserPromptExpansion` declares it: `"block"` for a policy, `"continue"` for a log; other values are rejected |
| No false guarantees | `"onFailure": "block"` is not allowed on `Stop`, `SubagentStop`, `TaskCompleted`, `TeammateIdle` or background (`async`, `asyncRewake`) hooks, where it has no effect |
| Shell tools | a `PreToolUse` matcher that lists `Bash` also lists `PowerShell`; `MultiEdit` no longer exists and is not listed |
| Path rules (D26) | `Read(...)`/`Edit(...)` patterns in `allow`, `ask` and `deny` start with `/` (primary working directory, i.e. the project root), `//` (filesystem root) or `~/` (home) |

Hooks are not subject to the Claude Code sandbox. `SessionStart` cannot stop a session
(exit 2 only shows stderr), so it gets no `onFailure`; the working-directory gate (D17)
therefore sits on `UserPromptSubmit` and `PreToolUse`.

### PowerShell

The protected-file guards treat a `PowerShell` call exactly like `Bash`: they only
recognise an `apply_patch` command and check its file headers. Arbitrary writes from a
shell are out of a hook's reach by design; deny rules and, where enabled, the sandbox
cover them.

### Why `/` in path rules

A relative pattern such as `Read(.env)` or `Read(**/.env)` means "at or under the
current directory". After `cd backend/` the root `.env` is no longer covered. A pattern
with one leading `/` in the project settings is anchored on the session's primary
working directory, which is the project root when Claude Code is started there (the
project settings file is only read from that directory). `Read(/**/.env)` covers `.env`
at any depth of the project; `Read(/**/secrets/**)` covers every `secrets/` directory.
Deny rules are a usability guard, not a security boundary (D20).

## Known limits

- **`Stop` / `SubagentStop` stay fail-open.** `onFailure` does not apply there, so the
  living-plan execution-log reminder (`check_plan_execution_log`) is advisory: if its
  script cannot start, nothing is reported. Do not present it as a guarantee.
- **Claude Code older than 2.1.295** ignores `onFailure`; every protective hook then
  fails open again. `/doctor` warns (`hook_check.py version`). How older versions treat
  the unknown field was not verified.
- **Codex** has no `onFailure` equivalent (exit 0 and 2 only); its parity is P08c (D19).

## Recovery after fail-closed

Fail-closed means: if the hook cannot run, the action is blocked. When the interpreter
is missing, **every** tool call and every prompt is blocked with a message such as
`failed; blocking because onFailure is "block"`. Recover from a terminal, not from
inside the blocked session:

1. Check the interpreter the hooks use: `"${AI_PYTHON:-python3}" --version` (and `node
   --version` for Node hooks) in the same shell that starts `claude`.
2. Fix it: install Python 3 so that `python3` resolves, or point at an existing one
   with `export AI_PYTHON=/path/to/python3` (PowerShell: `$env:AI_PYTHON = 'C:/.../python.exe'`),
   then start `claude` again from that shell in the project root.
3. **Native Windows:** shell-form hooks run in Git Bash; without Git for Windows Claude
   Code falls back to PowerShell, which cannot expand `"${AI_PYTHON:-python3}"`, so all
   gated actions are blocked. Install Git for Windows (Git Bash) and set `AI_PYTHON` to
   the full path of `python.exe`.
4. Emergency only, one session, knowing that every guard (D17 included) is off:
   `claude --settings '{"disableAllHooks": true}'`. Use it to repair the environment,
   then restart normally. Setting it in user settings is not enough, because project
   settings take precedence.

Claude Code reloads edited settings files in a running session, so a fixed
`.claude/settings.json` takes effect without a restart; a fixed `PATH` or `AI_PYTHON`
does not — the hooks inherit the environment of the `claude` process.

## Commands

| Command | Exit |
|---|---|
| `python scripts/ai/hook_check.py settings` | 0 compliant; 1 findings (listed); 2 unreadable settings |
| `python scripts/ai/hook_check.py version` | 0 Claude Code ≥ 2.1.295; 1 older (warning); 3 version unknown. Also prints the Codex CLI version (no minimum) |

Sources: https://code.claude.com/docs/en/hooks · https://code.claude.com/docs/en/permissions ·
https://code.claude.com/docs/en/settings
