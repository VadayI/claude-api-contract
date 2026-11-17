"""Hook reliability checks (D18, D26): settings style and the Claude Code version gate.

Claude Code runs a command hook in the session's *current* directory, which moves
after ``cd``; a relative script path or a bare ``python`` then fails, and a failed
hook is a non-blocking error unless the handler declares ``"onFailure": "block"``
(Claude Code 2.1.295+). Relative ``Read(...)``/``Edit(...)`` permission patterns are
anchored on the current directory as well. This module checks a committed
``.claude/settings.json`` against the family standard (docs/ai/hooks.md), reports
whether the installed Claude Code honours ``onFailure`` and emulates the documented
hook spawn rules for fixtures. It never edits settings and never starts Claude Code.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

MINIMUM_CLAUDE = (2, 1, 295)
PYTHON_LAUNCHER = '"${AI_PYTHON:-python3}"'
PROJECT_VARS = ("$CLAUDE_PROJECT_DIR/", "${CLAUDE_PROJECT_DIR}/")
EXEC_PROJECT_VAR = "${CLAUDE_PROJECT_DIR}/"
ON_FAILURE = frozenset({"continue", "block"})
# Zdarzenia, w których hook może zatrzymać akcję: każdy handler deklaruje onFailure jawnie.
GATING_EVENTS = frozenset({"PreToolUse", "UserPromptSubmit", "UserPromptExpansion"})
# Według dokumentacji onFailure nie działa na tych zdarzeniach — "block" byłby fałszywą gwarancją.
NO_EFFECT_EVENTS = frozenset({"Stop", "SubagentStop", "TaskCompleted", "TeammateIdle"})
SCRIPT_TOKEN = re.compile(r"""[^\s"'=;&|()<>]*\.(?:py|mjs|cjs|js|sh|ps1)(?=["'\s;&|()<>]|$)""")
BARE_PYTHON = re.compile(r"""(?:^|[\s;&|()"'])(?:python(?:\d(?:\.\d+)?)?|py)(?=[\s;&|()"']|$)""")
PATH_RULE = re.compile(r"^(Read|Edit|Write|NotebookEdit)\((.*)\)$")
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _finding(location: str, code: str, message: str) -> dict:
    """Build one finding record.

    Args: location names the settings element; code is a stable identifier.
    Returns: A JSON-serializable finding.
    Side effects: None.
    """
    return {"location": location, "code": code, "message": message}


def _shell_findings(command: str, location: str) -> list[dict]:
    """Check one shell-form hook command.

    Args:
        command: The handler's ``command`` string (no ``args``).
        location: Settings element name used in findings.
    Returns:
        Findings for relative or unquoted script paths, a bare Python interpreter
        or a launcher other than ``"${AI_PYTHON:-python3}"``.
    Side effects: None.
    Business rule: D18 — scripts are addressed through ``$CLAUDE_PROJECT_DIR`` in
        double quotes; Python always through ``"${AI_PYTHON:-python3}"``.
    """
    findings = []
    for match in SCRIPT_TOKEN.finditer(command):
        token, start = match.group(0), match.start()
        quoted = start > 0 and command[start - 1] == '"'
        if not token.startswith(PROJECT_VARS):
            findings.append(_finding(location, "relative-path",
                                     f"script {token!r} must be addressed as \"$CLAUDE_PROJECT_DIR/...\""))
        elif not quoted:
            findings.append(_finding(location, "unquoted-path",
                                     f"script {token!r} must be wrapped in double quotes"))
    rest = command.replace(PYTHON_LAUNCHER, " ")
    if "AI_PYTHON" in rest:
        findings.append(_finding(location, "python-launcher",
                                 f"Python must be started exactly as {PYTHON_LAUNCHER}"))
    if BARE_PYTHON.search(rest):
        findings.append(_finding(location, "bare-python",
                                 f"bare Python interpreter; use {PYTHON_LAUNCHER}"))
    return findings


def _exec_findings(handler: dict, location: str) -> list[dict]:
    """Check one exec-form hook handler (``command`` plus ``args``).

    Args: handler is the hook handler object; location names it in findings.
    Returns: Findings for a non-node executable or an unanchored script argument.
    Side effects: None.
    Business rule: D18 — exec form only for ``node`` (no shell, so the
        ``${AI_PYTHON:-python3}`` default cannot work there).
    """
    findings = []
    if handler.get("command") != "node":
        findings.append(_finding(location, "exec-form",
                                 "exec form (args) is allowed only for node; use the shell form"))
    args = handler.get("args")
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        return findings + [_finding(location, "invalid-args", "args must be a list of strings")]
    for item in args:
        if SCRIPT_TOKEN.fullmatch(item) and not item.startswith(EXEC_PROJECT_VAR):
            findings.append(_finding(location, "relative-path",
                                     f"script {item!r} must start with {EXEC_PROJECT_VAR}"))
    return findings


def _matcher_findings(event: str, matcher: object, location: str) -> list[dict]:
    """Check a tool matcher for removed tools and shell-tool coverage.

    Args: event is the hook event; matcher is the group's matcher value.
    Returns: Findings for ``MultiEdit`` or a ``Bash`` matcher without ``PowerShell``.
    Side effects: None.
    """
    if event != "PreToolUse" or not isinstance(matcher, str):
        return []
    tools = {part.strip() for part in matcher.split("|")}
    findings = []
    if "MultiEdit" in tools:
        findings.append(_finding(location, "removed-tool", "MultiEdit no longer exists; drop it from the matcher"))
    if "Bash" in tools and "PowerShell" not in tools:
        findings.append(_finding(location, "shell-coverage", "a matcher with Bash must also list PowerShell"))
    return findings


def _handler_findings(event: str, handler: object, location: str) -> list[dict]:
    """Check one hook handler against D18.

    Args: event is the hook event name; handler is the raw handler value.
    Returns: Findings for path style, interpreter and ``onFailure`` use.
    Side effects: None.
    """
    if not isinstance(handler, dict):
        return [_finding(location, "invalid-handler", "hook handler must be an object")]
    findings = []
    on_failure = handler.get("onFailure")
    background = bool(handler.get("async") or handler.get("asyncRewake"))
    if on_failure is not None and on_failure not in ON_FAILURE:
        findings.append(_finding(location, "invalid-on-failure",
                                 f"onFailure must be \"continue\" or \"block\", not {on_failure!r}"))
    if on_failure == "block" and (event in NO_EFFECT_EVENTS or background):
        findings.append(_finding(location, "on-failure-no-effect",
                                 f"onFailure has no effect on {event} or background hooks; it would be a false guarantee"))
    if event in GATING_EVENTS and not background and on_failure is None:
        findings.append(_finding(location, "missing-on-failure",
                                 f"{event} hook must declare onFailure (\"block\" for a policy, \"continue\" for a log)"))
    if handler.get("type") != "command":
        return findings
    command = handler.get("command")
    if not isinstance(command, str) or not command.strip():
        return findings + [_finding(location, "invalid-command", "command must be a non-empty string")]
    if "args" in handler:
        return findings + _exec_findings(handler, location)
    return findings + _shell_findings(command, location)


def _permission_findings(permissions: object) -> list[dict]:
    """Check that Read/Edit path rules are anchored (D26).

    Args: permissions is the settings ``permissions`` object.
    Returns: Findings for path patterns relative to the current directory.
    Side effects: None.
    Business rule: A relative pattern follows the session's current directory, so
        after ``cd`` a root ``.env`` is no longer covered; ``/`` anchors on the
        primary working directory, ``//`` on the filesystem root, ``~/`` on home.
    """
    if not isinstance(permissions, dict):
        return []
    findings = []
    for kind in ("allow", "ask", "deny"):
        rules = permissions.get(kind, [])
        for index, rule in enumerate(rules if isinstance(rules, list) else []):
            match = PATH_RULE.match(rule) if isinstance(rule, str) else None
            if match and not match.group(2).startswith(("/", "~/")):
                findings.append(_finding(f"permissions.{kind}[{index}]", "unanchored-path-rule",
                                         f"{rule} is relative to the current directory; anchor it with '/'"))
    return findings


def check_settings(settings: object) -> list[dict]:
    """Check a parsed Claude settings document against D18 and D26.

    Args: settings is the parsed JSON of ``.claude/settings.json``.
    Returns: All findings in document order; an empty list means compliant.
    Raises: None; structural problems are reported as findings.
    Side effects: None; no filesystem, process, Git or network access.
    """
    if not isinstance(settings, dict):
        return [_finding("settings", "invalid-settings", "settings must be a JSON object")]
    findings = _permission_findings(settings.get("permissions"))
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return findings + [_finding("hooks", "invalid-hooks", "hooks must be an object")]
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            findings.append(_finding(f"hooks.{event}", "invalid-hooks", "event value must be a list"))
            continue
        for group_index, group in enumerate(groups):
            location = f"hooks.{event}[{group_index}]"
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                findings.append(_finding(location, "invalid-hooks", "group must contain a hooks list"))
                continue
            findings.extend(_matcher_findings(event, group.get("matcher"), location))
            for hook_index, handler in enumerate(group["hooks"]):
                findings.extend(_handler_findings(event, handler, f"{location}.hooks[{hook_index}]"))
    return findings


def parse_version(text: str) -> tuple[int, int, int] | None:
    """Extract the first ``X.Y.Z`` version from tool output.

    Args: text is e.g. ``"2.1.326 (Claude Code)"``.
    Returns: The version tuple, or ``None`` when no version is present.
    Side effects: None.
    """
    match = VERSION.search(text or "")
    return tuple(int(part) for part in match.groups()) if match else None


def _probe(executable: str) -> str | None:
    """Return the first output line of ``<executable> --version``.

    Args: executable is a tool name resolved on PATH.
    Returns: The first line, or ``None`` when the tool is missing or fails.
    Side effects: Starts one local child process without a shell (10 s limit).
    """
    if shutil.which(executable) is None:
        return None
    try:
        result = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10, shell=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = (result.stdout or result.stderr or "").strip().splitlines()
    return lines[0][:200] if result.returncode == 0 and lines else None


def version_report(claude_output: str | None, codex_output: str | None) -> dict:
    """Classify the observed Claude Code version against the D18 minimum.

    Args:
        claude_output: First line of ``claude --version`` or ``None`` if unavailable.
        codex_output: First line of ``codex --version`` or ``None`` (informational).
    Returns:
        ``status`` OK, BELOW_MINIMUM or NOT_VERIFIED with the observed strings.
    Side effects: None.
    Business rule: Below 2.1.295 ``"onFailure": "block"`` is not honoured, so the
        protective hooks fail open; this is a warning, never a fabricated version.
    """
    minimum = ".".join(map(str, MINIMUM_CLAUDE))
    version = parse_version(claude_output) if claude_output else None
    report = {"minimum": minimum, "claude": claude_output, "codex": codex_output}
    if version is None:
        report["status"] = "NOT_VERIFIED"
    else:
        report["status"] = "OK" if version >= MINIMUM_CLAUDE else "BELOW_MINIMUM"
    return report


def version_message(report: dict) -> str:
    """Render a version report for humans (one line per tool).

    Args: report is the output of :func:`version_report`.
    Returns: Text with the verdict first.
    Side effects: None.
    """
    status, minimum = report["status"], report["minimum"]
    claude = report["claude"] or "not found"
    if status == "OK":
        head = f"OK: Claude Code {claude} >= {minimum}; onFailure \"block\" is honoured."
    elif status == "BELOW_MINIMUM":
        head = (f"WARN: Claude Code {claude} < {minimum}: onFailure \"block\" is not honoured, protective "
                "hooks fail open. Update Claude Code (docs/ai/hooks.md).")
    else:
        head = f"NOT_VERIFIED: Claude Code version unknown ({claude}); fail-closed hooks need {minimum}+."
    return f"{head}\nCodex CLI: {report['codex'] or 'not found'} (no minimum)"


def hook_env(project_dir: Path, environ: dict | None = None) -> dict:
    """Return the environment Claude Code gives a hook process.

    Args: project_dir is the session's project root; environ is the base environment.
    Returns: A copy of ``environ`` (or ``os.environ``) with ``CLAUDE_PROJECT_DIR`` set.
    Side effects: None.
    """
    env = dict(os.environ if environ is None else environ)
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return env


def run_hook(handler: dict, *, project_dir: Path, cwd: Path, payload: dict, environ: dict | None = None,
             bash: str | None = None, timeout: int = 60) -> str:
    """Emulate the documented spawn of one command hook and its outcome.

    Fixtures use this to prove that a committed hook still works after ``cd`` and
    without ``python`` on PATH. It follows the documented rules only (shell form via
    bash with the placeholder exported; exec form with ``${CLAUDE_PROJECT_DIR}``
    substituted and no shell); live Claude Code behaviour is accepted manually.

    Args:
        handler: Hook handler from settings (``type: command``).
        project_dir: Value of ``CLAUDE_PROJECT_DIR``.
        cwd: The session's current directory (may be a subdirectory).
        payload: Hook input JSON written to stdin.
        environ: Process environment (``PATH`` decides which interpreters exist).
        bash: Absolute bash path for the shell form (default: bash from this process's PATH).
        timeout: Seconds before the run counts as a failure.
    Returns:
        ``"allow"`` (exit 0), ``"deny"`` (exit 2) or, for any other failure,
        ``"block"`` with ``onFailure: block`` and ``"error"`` otherwise.
    Raises: ValueError when the handler is not a command hook.
    Side effects: Starts one child process with the given cwd and environment.
    """
    if handler.get("type") != "command":
        raise ValueError("only command hooks can be emulated")
    env = hook_env(project_dir, environ)
    if "args" in handler:
        executable = shutil.which(handler["command"], path=env.get("PATH", ""))
        substitute = lambda text: text.replace("${CLAUDE_PROJECT_DIR}", str(project_dir))
        argv = [executable] + [substitute(item) for item in handler["args"]] if executable else None
    else:
        argv = [bash or shutil.which("bash") or "/bin/bash", "-c", handler["command"]]
    code = None
    if argv:
        try:
            code = subprocess.run(argv, cwd=cwd, env=env, input=json.dumps(payload), capture_output=True,
                                  text=True, timeout=timeout, shell=False).returncode
        except (OSError, subprocess.TimeoutExpired):
            code = None
    if code == 0:
        return "allow"
    if code == 2:
        return "deny"
    return "block" if handler.get("onFailure") == "block" else "error"


def main(argv: list[str] | None = None) -> int:
    """CLI: ``settings`` checks style, ``version`` checks the Claude Code minimum.

    Args: argv overrides ``sys.argv[1:]`` for tests.
    Returns: settings — 0 compliant, 1 findings, 2 unreadable file; version — 0 OK,
        1 BELOW_MINIMUM, 3 NOT_VERIFIED.
    Side effects: Reads one settings file or runs ``claude/codex --version``.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    settings_cmd = sub.add_parser("settings", help="check .claude/settings.json against D18/D26")
    settings_cmd.add_argument("--settings", type=Path, help="default: <root>/.claude/settings.json")
    version_cmd = sub.add_parser("version", help="check the installed Claude Code against 2.1.295")
    version_cmd.add_argument("--claude-version", help="use this text instead of running claude --version")
    args = parser.parse_args(argv)
    if args.command == "version":
        observed = args.claude_version if args.claude_version is not None else _probe("claude")
        report = version_report(observed, _probe("codex"))
        print(json.dumps(report, sort_keys=True) if args.json else version_message(report))
        return {"OK": 0, "BELOW_MINIMUM": 1}.get(report["status"], 3)
    path = args.settings or args.root / ".claude" / "settings.json"
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"FAIL: cannot read {path}: {error}", file=sys.stderr)
        return 2
    findings = check_settings(settings)
    if args.json:
        print(json.dumps({"settings": str(path), "findings": findings}, sort_keys=True))
    elif findings:
        print(f"FAIL: {len(findings)} hook/permission style finding(s) in {path}")
        for item in findings:
            print(f"  {item['location']}: [{item['code']}] {item['message']}")
    else:
        print(f"PASS: hook and permission style ({path.name})")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
