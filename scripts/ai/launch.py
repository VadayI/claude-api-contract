"""Launch either agent with explicit environment initialization and ordinary trust."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from core_paths import contained
from core_sync import safe_name, target_root

PLATFORM_ENV = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP",
                "TMPDIR", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA",
                "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
                "TERM", "COLORTERM", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
                "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "SHELL"}
RUNTIME_ENV = {"codex": {"CODEX_HOME"}, "claude": {"CLAUDE_CONFIG_DIR"}}
OPTIONAL_ENV = {"GH_TOKEN", "GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN", "CONTEXT7_API_KEY",
                "OPENAI_API_KEY", "CODEX_API_KEY", "ANTHROPIC_API_KEY", "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY",
                "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS", "SSH_AUTH_SOCK"}


def child_environment(runtime: str, inherited: dict[str, str], requested: list[str]) -> dict[str, str]:
    """Filter inherited process variables without opening or executing env files.

    Args: runtime is claude/codex; inherited is the caller environment; requested
        lists explicitly selected optional credential/proxy variable names.
    Returns: A new environment mapping; values are never logged or persisted.
    Raises: ValueError for unsupported runtime or unapproved variable names.
    Side effects: None; caller environment, user config, files and DB are unchanged.
    Platform/config-location variables preserve normal CLI auth/model settings.
    """
    if runtime not in RUNTIME_ENV or set(requested) - OPTIONAL_ENV:
        raise ValueError("Unknown runtime or unsupported environment variable name")
    allowed = PLATFORM_ENV | RUNTIME_ENV[runtime] | set(requested)
    return {name: value for name, value in inherited.items() if name.upper() in allowed}


def command(runtime: str, executable: str, task: bool, read_only: bool, probe: bool) -> list[str]:
    """Build fixed argv without shell parsing, model selection or approval overrides.

    Args: runtime selects the CLI; executable is its resolved path; task indicates
        stdin input; read_only restricts reviewer capabilities; probe requests version.
    Returns: Command argv. Raises: ValueError for an unsupported runtime.
    Side effects: None; no subprocess, filesystem, network or database operations.
    Claude tool restriction is not an OS sandbox; Codex uses its native sandbox.
    """
    if runtime not in RUNTIME_ENV:
        raise ValueError("Unknown runtime")
    if probe:
        return [executable, "--version"]
    if runtime == "codex":
        return [executable, *(["exec", "--ephemeral"] if task else []), "--sandbox",
                "read-only" if read_only else "workspace-write", *(["-"] if task else [])]
    return [executable, *(["-p", "--no-session-persistence"] if task else []),
            *(["--tools", "Read,Glob,Grep"] if read_only else [])]


def execute(argv: list[str], root: Path, environment: dict[str, str], task: str | None) -> int:
    """Run the selected CLI from the reviewed project and preserve its exit status.

    Args: argv is prepared command; root is cwd; environment is filtered; task is
        optional non-secret stdin. Returns: CLI exit code (signal exits map to 128+n).
    Raises: OSError for unavailable executable/process startup errors.
    Side effects: Starts an interactive/model CLI under its existing permissions;
        its authorized actions may read/write project data. No direct DB access.
    This launcher never sources .env, persists tokens or modifies parent settings.
    """
    result = subprocess.run(argv, cwd=root, env=environment, input=task,
                            text=True, encoding="utf-8", shell=False, check=False)
    return result.returncode if result.returncode >= 0 else 128 - result.returncode


def main() -> int:
    """Initialize and launch an explicitly chosen runtime, or emit a read-only preview.

    Args: CLI runtime, --root, --task-file, --read-only, --probe, --dry-run and
        repeatable --pass-env names. Returns: Child status, or 2 for invalid setup.
    Side effects: Reads only an explicitly named non-secret task, locates the CLI,
        and optionally starts it. Preview prints names/argv only, never values/task.
    No global trust/config, credentials, env files or database are modified.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", choices=tuple(RUNTIME_ENV))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--task-file")
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pass-env", action="append", default=[], choices=sorted(OPTIONAL_ENV))
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    try:
        root = target_root(args.root)
        if not root.is_dir():
            raise ValueError("Project root must exist")
        if args.probe and args.task_file:
            raise ValueError("Version probe cannot execute a task")
        environment = child_environment(args.runtime, dict(os.environ), args.pass_env)
        executable = shutil.which(args.runtime)
        if not executable:
            raise ValueError(f"Missing executable: {args.runtime}")
        task = None
        if args.task_file:
            safe_name(args.task_file)
            task = contained(root, args.task_file).read_text(encoding="utf-8")
            if not task.strip():
                raise ValueError("Task file is empty")
        argv = command(args.runtime, executable, task is not None, args.read_only, args.probe)
        if args.dry_run:
            print(json.dumps({"runtime": args.runtime, "argv": argv,
                              "environment_names": sorted(environment),
                              "task_input": task is not None, "trust": "runtime-default"}))
            return 0
        return execute(argv, root, environment, task)
    except (ValueError, OSError) as error:
        print(f"Launcher error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
