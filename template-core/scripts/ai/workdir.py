"""Working-directory gate (D17): no agent session on a Windows drive mounted into WSL.

A project whose working tree lives on a Windows drive seen from WSL (``/mnt/c``,
``/mnt/d``, or any 9P/drvfs mount) reads every file through the Windows → WSL
bridge: Docker bind mounts, pytest, ``node_modules`` and ``.git`` become one to
two orders of magnitude slower. Agents must not start work there unless the user
explicitly allowed it for the current session with ``ALLOW_MNT_SESSION=1`` in the
environment of the agent process. The allowance is never stored in the project.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

ALLOW_ENV = "ALLOW_MNT_SESSION"
WINDOWS_FS = frozenset({"9p", "drvfs", "v9fs"})
MOUNT_PATH = re.compile(r"^/mnt/[A-Za-z](?:/|$)")
MOUNTINFO = Path("/proc/self/mountinfo")
HOOK_BLOCK_EXIT = 2

CHECKLIST = (
    "Stop the running stack in the old checkout: docker compose down",
    "Push every local branch and stash you need, or note them; nothing is copied implicitly",
    "Clone into the WSL filesystem: mkdir -p ~/src && git clone <remote-url> ~/src/<repo>",
    "Copy only untracked local files by hand (.env*, .claude/settings.local.json); "
    "never copy node_modules, .venv or caches",
    "Keep .dockerignore in the repo (media, caches, node_modules, .git, .env*) and rebuild: "
    "docker compose build (or npm ci / a fresh venv)",
    "Mount large Windows-only data separately and read-only; code, venv and caches stay on ext4",
    "Measure: time ls -R ~/src/<repo> versus the /mnt checkout; then the full test command "
    "the agent gives you",
    "Open the project from WSL (cd ~/src/<repo> && code . via Remote-WSL; start claude/codex there) "
    "and archive the /mnt checkout after the first green run",
)


def _unescape(field: str) -> str:
    """Decode the octal escapes used by /proc/self/mountinfo (e.g. ``\\040``).

    Args: field is one raw mountinfo field.
    Returns: The decoded path text.
    Side effects: None.
    """
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), field)


def mount_type(path: str, mountinfo: str) -> str | None:
    """Return the filesystem type of the mount containing ``path``.

    Args:
        path: Absolute POSIX path of the project root.
        mountinfo: Text of ``/proc/self/mountinfo``.
    Returns:
        The fstype of the longest mount point that contains ``path``, or ``None``
        when no line parses.
    Side effects: None.
    """
    best, kind = "", None
    for line in mountinfo.splitlines():
        head, separator, tail = line.partition(" - ")
        fields = head.split()
        if not separator or len(fields) < 5 or not tail.split():
            continue
        point = _unescape(fields[4])
        inside = path == point or path.startswith(point.rstrip("/") + "/")
        if inside and len(point) >= len(best):
            best, kind = point, tail.split()[0]
    return kind


def state(root: Path, environ: dict | None = None, platform: str | None = None,
          mountinfo: str | None = None) -> dict:
    """Classify the project location and decide whether agent work is blocked.

    Args:
        root: Project root.
        environ: Environment to read the allowance from (default ``os.environ``).
        platform: ``sys.platform`` override for tests.
        mountinfo: Mount table text override for tests; on Linux the real table
            is read when omitted and silently ignored when unreadable.
    Returns:
        ``{"path", "location", "fstype", "allowed", "blocked", "allow_env"}`` where
        location is ``windows-mount`` (WSL path on a Windows drive), ``linux``
        (native Linux filesystem) or ``other-os`` (native Windows/macOS: D17 does
        not apply there).
    Side effects: Reads ``/proc/self/mountinfo`` on Linux only.
    Business rules: The allowance counts only as the exact value ``1`` in the
        agent's own environment, so an agent cannot grant it by editing files.
    """
    environ = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    path = Path(os.path.abspath(root)).as_posix()
    fstype = None
    if not platform.startswith("linux"):
        location = "other-os"
    else:
        if mountinfo is None:
            try:
                mountinfo = MOUNTINFO.read_text(encoding="utf-8", errors="replace")
            except OSError:
                mountinfo = ""
        fstype = mount_type(path, mountinfo)
        windows = bool(MOUNT_PATH.match(path)) or fstype in WINDOWS_FS
        location = "windows-mount" if windows else "linux"
    allowed = environ.get(ALLOW_ENV) == "1"
    return {"path": path, "location": location, "fstype": fstype, "allow_env": ALLOW_ENV,
            "allowed": location == "windows-mount" and allowed,
            "blocked": location == "windows-mount" and not allowed}


def message(report: dict) -> str:
    """Render the blocker (with the move checklist) or the allowance notice.

    Args: report is the output of :func:`state`.
    Returns: Text ending with a newline, or an empty string when nothing applies.
    Side effects: None.
    """
    if report["location"] != "windows-mount":
        return ""
    if report["allowed"]:
        return (f"Working directory: {report['path']} is on a Windows drive mounted into WSL; "
                f"the user allowed this session ({report['allow_env']}=1). Expect slow Docker "
                "bind mounts and tests; record the allowance in the session record.\n")
    lines = [f"BLOCKED (D17): {report['path']} is on a Windows drive mounted into WSL "
             f"({report['fstype'] if report['fstype'] in WINDOWS_FS else 'path under /mnt/<drive>'}).",
             "Agents do not work here without the user's explicit permission for this session.",
             "Agent: stop, show this message to the user and do not edit files or run commands.",
             f"User: either move the project to ext4, or restart the agent with {report['allow_env']}=1 "
             f"for this one session (e.g. {report['allow_env']}=1 claude).",
             "Move checklist:"]
    lines.extend(f"  {number}. {step}" for number, step in enumerate(CHECKLIST, 1))
    return "\n".join(lines) + "\n"


def main() -> int:
    """Check the working directory for a CLI caller or a Claude hook.

    Args:
        CLI ``--root`` (default: the project that contains this script),
        ``--json`` for the machine report, ``--hook`` for Claude
        UserPromptSubmit/PreToolUse hooks.
    Returns:
        Plain mode: 0 allowed or not applicable, 1 blocked (message on stdout).
        Hook mode: 0 allowed, ``HOOK_BLOCK_EXIT`` (2) blocked with the message on
        stderr — Claude Code then rejects the prompt or tool call.
    Side effects: Reads the mount table; no writes, network or Git.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--hook", action="store_true", help="Claude hook mode: exit 2, message on stderr")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    report = state(args.root)
    if args.json:
        print(json.dumps(report, sort_keys=True))
    text = message(report)
    if args.hook:
        if report["blocked"]:
            print(text, file=sys.stderr, end="")
            return HOOK_BLOCK_EXIT
        return 0
    if text and not args.json:
        print(text, end="")
    return 1 if report["blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
