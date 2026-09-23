"""Produce a sanitized, explicit environment and repository capability report."""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


TOOLS = {
    "git": ["git", "--version"],
    "node": ["node", "--version"],
    "npm": ["npm", "--version"],
    "gh": ["gh", "--version"],
    "docker": ["docker", "--version"],
    "claude": ["claude", "--version"],
    "codex": ["codex", "--version"],
}


def command(argv: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """Run one bounded read-only probe without a shell.

    Args:
        argv: Executable and literal arguments; interpolation and shell syntax are
            never evaluated.
        cwd: Optional working directory for repository probes.

    Returns:
        Tuple of process exit code and the first normalized output line.

    Raises:
        subprocess.TimeoutExpired: If a probe exceeds ten seconds.
        OSError: If process creation fails after executable discovery.

    Side effects:
        Starts one local child process and reads its output. It performs no file
        writes, database operations, network requests, or configuration changes.
    """
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=10, shell=False)
    output = (result.stdout or result.stderr).replace("\r\n", "\n").splitlines()
    return result.returncode, output[0][:500] if output else ""


def tool_report() -> dict[str, dict[str, str]]:
    """Report installed local tool versions without exposing environment values.

    Returns:
        Mapping from stable tool ID to AVAILABLE, MISSING, or NOT_VERIFIED and a
        bounded version string when observed.

    Raises:
        No expected probe exception escapes; unexpected failures are represented
        as NOT_VERIFIED so the detector cannot invent availability.

    Side effects:
        Executes local version commands only. No files, databases, networks,
        credentials, trust settings, or parent environment values are modified.
    """
    report = {}
    for name, argv in TOOLS.items():
        if shutil.which(argv[0]) is None:
            report[name] = {"status": "MISSING"}
            continue
        try:
            code, version = command(argv)
        except (OSError, subprocess.TimeoutExpired):
            report[name] = {"status": "NOT_VERIFIED"}
            continue
        report[name] = {"status": "AVAILABLE" if code == 0 and version else "NOT_VERIFIED"}
        if version:
            report[name]["version"] = version
    report["python"] = {"status": "AVAILABLE", "version": platform.python_version()}
    return report


def git_value(repository: Path, *args: str) -> str:
    """Read a single Git value from a reviewed repository using literal argv.

    Args:
        repository: Candidate Git working tree used only for metadata reads.
        *args: Git subcommand and arguments.

    Returns:
        Stripped UTF-8-compatible Git stdout.

    Raises:
        subprocess.CalledProcessError: If Git rejects the repository or query.
        subprocess.TimeoutExpired: If Git does not return within ten seconds.

    Side effects:
        Runs read-only Git commands. No checkout, fetch, config, database, network,
        index, ref, stash, or working-tree mutation occurs.
    """
    result = subprocess.run(
        ["git", "-C", str(repository), *args], capture_output=True, text=True,
        timeout=10, check=True, shell=False, encoding="utf-8", errors="strict",
    )
    return result.stdout.replace("\r\n", "\n").strip()


def repository_report(repository: Path) -> dict[str, object]:
    """Describe current Git identity while keeping dirty content out of the report.

    Args:
        repository: Existing path expected to belong to a Git working tree.

    Returns:
        Repository root, git-dir, HEAD/tree/branch and dirty/untracked counts, or a
        NOT_VERIFIED record when the path is not a readable repository.

    Raises:
        No expected Git/filesystem error escapes; it becomes NOT_VERIFIED.

    Side effects:
        Reads Git metadata and porcelain status only. File contents, secret values,
        databases, network resources, and Git configuration are not read or changed.
    """
    try:
        root = Path(git_value(repository, "rev-parse", "--show-toplevel"))
        status = git_value(root, "status", "--porcelain=v1", "--untracked-files=all").splitlines()
        branch = git_value(root, "branch", "--show-current")
        result = {
            "status": "AVAILABLE",
            "root_name": root.name,
            "git_dir_name": Path(git_value(root, "rev-parse", "--absolute-git-dir")).name,
            "head": git_value(root, "rev-parse", "HEAD"),
            "tree": git_value(root, "rev-parse", "HEAD^{tree}"),
            "dirty_tracked": sum(not line.startswith("??") for line in status),
            "untracked": sum(line.startswith("??") for line in status),
        }
        if branch:
            result["branch"] = branch
        return result
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, UnicodeError):
        return {"status": "NOT_VERIFIED"}


def report(repository: Path | None = None) -> dict[str, object]:
    """Build the versioned detector report consumed by the shared runner.

    Args:
        repository: Optional project path for Git state inspection.

    Returns:
        JSON-serializable platform, Python, tool and optional repository facts.

    Raises:
        No expected local capability error escapes; unavailable facts are explicit.

    Side effects:
        Runs bounded local version/Git probes only. Environment variable names and
        values, secrets, databases, network services, and files are not recorded.
    """
    result: dict[str, object] = {
        "schema_version": 1,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "tools": tool_report(),
    }
    if repository is not None:
        result["repository"] = repository_report(repository)
    return result


def main() -> int:
    """Print or write one explicit detector report.

    Returns:
        Zero after a report is produced; argparse returns two for invalid CLI use.

    Side effects:
        Performs the probes documented by :func:`report`; optionally writes one
        UTF-8 JSON file. No database, network, trust, or Git state is changed.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    document = json.dumps(report(args.repository), sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8", newline="\n")
    else:
        print(document, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
