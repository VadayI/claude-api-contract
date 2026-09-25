# Portable agent launchers

The shared Python launcher initializes an explicit child environment, sets the
project working directory, preserves argv boundaries and returns the CLI exit
code. Python 3.13+ is required. No optional MCP or marketplace is required by this
launcher; a runtime's independently configured required MCP can still prevent
that runtime from starting.

```text
python scripts/ai/launch.py codex --probe
python scripts/ai/launch.py claude --probe
python scripts/ai/launch.py codex
python scripts/ai/launch.py claude --task-file docs/tasks/review.md --read-only
python scripts/ai/launch.py codex --task-file docs/tasks/review.md --read-only
```

`--root` selects another reviewed project. Task paths are relative, contained,
non-secret text files. `--dry-run` prints argv and environment variable **names**,
never task text or credential values. `--probe` invokes only the CLI version; a
successful probe is not a model-session, authentication or tool-capability test.

Use `pwsh -NoProfile -File scripts/ai/launch.ps1 codex --probe` on PowerShell.
For Bash use `bash scripts/ai/launch.sh codex --probe`; on native Windows select
`C:/Program Files/Git/bin/bash.exe` explicitly instead of the WSL launcher found
on PATH. `AI_PYTHON` may select one Python executable path, including spaces;
it is never evaluated as a shell command. Do not dot-source the PowerShell wrapper.

## Environment and trust

The launcher never reads, sources or executes `.env`. Platform necessities and
runtime configuration locations (`CODEX_HOME` or `CLAUDE_CONFIG_DIR`) are inherited.
Authentication/model settings continue to come from the runtime's normal config.
If a particular credential, proxy or certificate variable is needed, opt in by
name, e.g. `--pass-env GH_TOKEN --pass-env CONTEXT7_API_KEY`. The allowlist is in
`scripts/ai/launch.py`. It excludes application/database secrets, loader options
and unrecognized variables. The caller's environment is unchanged; no token is
copied into a differently named variable, persisted or printed by the launcher.

Codex uses explicit `read-only` or `workspace-write` sandbox selection. Claude
review sessions restrict tools to Read/Glob/Grep; this is a tool restriction, not
an OS sandbox. No model, approval, hook-trust or global config override is added.
CLI/project trust decisions remain with the runtime. A denied permission is a
real limitation; the launcher does not retry with broader access.

The Codex invocation follows the [official non-interactive CLI documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
and the installed 0.155.0-alpha.9.2 help. P03's measured separate reviewer remains
the behavioral evidence; these generic launchers do not assert native custom-role
support. Role packs and role/session reports must still be supplied by the role
entry points. They do not turn a worker into a coordinator.

## Migration status

Existing stack-specific `scripts/claude.*` and Makefile targets are untouched by
core installation. Known legacy wrappers were migrated in P04 to
`legacy_launch.py` (literal allowlisted dotenv parsing, no shell evaluation);
customized wrappers conflict before writes and need explicit, reviewed wiring to
this launcher. Installing the shared files alone does not prove those entry
points are migrated.

## Legacy entry-point compatibility

`legacy_launch.py` is a separate adapter for existing Claude wrappers. It accepts
`claude|codex --root PROJECT --env-file .env -- CLI_ARGS`. Only CONTRACT_REPO,
CONTRACT_VERSION, VITE_API_BASE_URL, VITE_OPENAPI_URL, VITE_MSW_ENABLED,
GITHUB_PERSONAL_ACCESS_TOKEN and CONTEXT7_API_KEY are read as literal dotenv data.
Unknown application variables are not inherited. No shell evaluation or variable
expansion occurs; quoted single-line values and whitespace-prefixed comments are
supported, ambiguous duplicate/multiline values fail without logging their values.

Nonempty values override inherited selected variables; blank placeholders preserve
existing values. A nonempty PAT supplies GH_TOKEN and removes stale GITHUB_TOKEN
only in the child. The parent process is never modified. CLI argv/exit status are
preserved with no implicit model/trust/approval overrides. This explicitly selected
compatibility path reads dotenv data; the normal launch.py does not read .env.
Applications must load their own runtime environment separately. Configure secrets
through the intended project file or child environment, never global trust changes.
