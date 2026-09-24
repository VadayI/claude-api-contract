"""Portable exact-context contract policy and breaking-change checks."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


def load_context(path: Path) -> dict[str, object]:
    """Load and minimally verify a runner-produced exact run context.

    Args:
        path: Explicit run-context JSON path supplied by the shared runner.

    Returns:
        Decoded context containing exact Git identities and changed paths.

    Raises:
        ValueError: If the document is not version one or lacks changed paths.
        OSError/JSONDecodeError: If the reviewed runtime file cannot be read.

    Side effects:
        Reads one runtime-owned JSON file; no writes, DB, subprocess, or network.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or not isinstance(document.get("changed_files"), list)
        or any(not isinstance(name, str) for name in document["changed_files"])
    ):
        raise ValueError("invalid exact run context")
    return document


def unreleased(text: str) -> str | None:
    """Extract normalized content of the first CHANGELOG Unreleased section.

    Args:
        text: UTF-8 CHANGELOG content.

    Returns:
        Trimmed section content, or ``None`` when the heading is absent.

    Side effects:
        None; no files, subprocesses, databases, or network are accessed.
    """
    match = re.search(r"(?ms)^## \[Unreleased\]\s*$\n(.*?)(?=^## |\Z)", text)
    return match.group(1).strip() if match else None


def check_todos(root: Path, context: dict[str, object]) -> int:
    """Reject bare TODO/FIXME markers in changed contract artifacts.

    Args:
        root: Exact candidate export.
        context: Validated run context with exact changed paths.

    Returns:
        Zero when clean and one when an applicable tracked file has a bare marker.

    Side effects:
        Reads changed candidate text files and writes diagnostics to stdout only.
    """
    failures = []
    for name in context["changed_files"]:
        if not (name == "openapi.yml" or name.startswith(("spec/", "examples/"))):
            continue
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\b(?:TODO|FIXME)\b", line) and "STUB:" not in line:
                failures.append(f"{name}:{number}")
    if failures:
        print("bare TODO/FIXME: " + ", ".join(failures), file=sys.stderr)
        return 1
    print("changed contract artifacts contain no bare TODO/FIXME")
    return 0


def check_adr(context: dict[str, object]) -> int:
    """Require a changed ADR whenever the oasdiff ignore file changes.

    Args:
        context: Validated run context with exact changed paths.

    Returns:
        Zero when irrelevant/compliant, otherwise one.

    Side effects:
        Writes a bounded diagnostic only; no file, DB, subprocess, or network I/O.
    """
    changed = set(context["changed_files"])
    if ".oasdiff-ignore.txt" not in changed:
        return 0
    if any(re.fullmatch(r"docs/decisions/.+\.md", name) for name in changed):
        return 0
    print(".oasdiff-ignore.txt changed without a changed ADR", file=sys.stderr)
    return 1


def check_changelog(root: Path, base_root: Path, context: dict[str, object]) -> int:
    """Require a real changed Unreleased fragment for contract changes.

    Args:
        root: Exact candidate export.
        base_root: Exact base export from the runner.
        context: Validated exact changed-file context.

    Returns:
        Zero when irrelevant or a substantive fragment differs from base; one for
        missing, unchanged, or placeholder-only Unreleased content.

    Side effects:
        Reads candidate/base CHANGELOG files and writes diagnostics; no mutation,
        database, subprocess, or network work.
    """
    changed = set(context["changed_files"])
    if not any(name == "openapi.yml" or name.startswith("spec/") for name in changed):
        return 0
    candidate = root / "CHANGELOG.md"
    baseline = base_root / "CHANGELOG.md"
    if "CHANGELOG.md" not in changed or not candidate.is_file():
        print("contract changed without CHANGELOG.md", file=sys.stderr)
        return 1
    current = unreleased(candidate.read_text(encoding="utf-8"))
    previous = unreleased(baseline.read_text(encoding="utf-8")) if baseline.is_file() else None
    if not current or current == previous or current.strip().lower() in {"- <pending changes>", "<pending changes>"}:
        print("CHANGELOG [Unreleased] lacks a new substantive fragment", file=sys.stderr)
        return 1
    return 0


def check_readme_version(root: Path) -> int:
    """Verify README status version equals the package version.

    Args:
        root: Exact candidate export containing package.json and README.md.

    Returns:
        Zero for equal semantic versions, otherwise one.

    Side effects:
        Reads two candidate files and writes diagnostics; no mutation/DB/network.
    """
    try:
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))["version"]
        readme = (root / "README.md").read_text(encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError):
        print("cannot read package/README version", file=sys.stderr)
        return 1
    match = re.search(r"Status: \*\*v([0-9]+\.[0-9]+\.[0-9]+)", readme)
    if match is None or match.group(1) != package:
        print("README status version differs from package.json", file=sys.stderr)
        return 1
    return 0


def check_breaking(root: Path, base_root: Path) -> int:
    """Run pinned external oasdiff against the runner's exact base artifact.

    Args:
        root: Exact candidate export containing openapi.yml.
        base_root: Exact base export containing the comparison openapi.yml.

    Returns:
        Oasdiff exit code, or 75 when the exact base artifact/tool is unavailable.

    Side effects:
        Executes local ``oasdiff`` with literal argv and reads two OpenAPI files.
        It performs no fetch, ref fallback, file mutation, database, or network I/O.
    """
    executable = shutil.which("oasdiff")
    current = root / "openapi.yml"
    baseline = base_root / "openapi.yml"
    if executable is None or not baseline.is_file():
        print("oasdiff or exact-base openapi.yml unavailable", file=sys.stderr)
        return 75
    if not current.is_file():
        print("candidate openapi.yml unavailable", file=sys.stderr)
        return 1
    argv = [executable, "breaking", str(baseline), str(current), "--fail-on", "ERR"]
    ignore = root / ".oasdiff-ignore.txt"
    if ignore.is_file():
        argv.extend(["--err-ignore", str(ignore)])
    return subprocess.run(argv, check=False, shell=False, timeout=240).returncode


def main() -> int:
    """Dispatch one portable policy check with explicit runtime inputs.

    Returns:
        Zero for PASS, one for policy FAIL, and 75 for missing mandatory runtime
        evidence that the shared runner maps to NOT_VERIFIED.

    Side effects:
        Reads exact candidate/base/runtime inputs and may execute local oasdiff for
        the breaking subcommand. No Git fetch/ref fallback, DB, or implicit network.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("todos", "adr", "changelog", "readme-version", "breaking"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--run-context", type=Path)
    parser.add_argument("--base-root", type=Path)
    args = parser.parse_args()
    context = load_context(args.run_context) if args.run_context else None
    if args.check == "todos":
        return check_todos(args.root, context)
    if args.check == "adr":
        return check_adr(context)
    if args.check == "changelog":
        return check_changelog(args.root, args.base_root, context)
    if args.check == "readme-version":
        return check_readme_version(args.root)
    return check_breaking(args.root, args.base_root)


if __name__ == "__main__":
    raise SystemExit(main())
