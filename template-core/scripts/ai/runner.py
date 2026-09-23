"""Run catalogued checks against an isolated export of an exact Git candidate."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

from detector import report as environment_report

SHA = re.compile(r"[0-9a-f]{40}")
IDENTIFIER = re.compile(r"[a-z][a-z0-9.-]*")
STATUSES = {"PASS", "FAIL", "NOT_APPLICABLE", "NOT_VERIFIED"}
EVIDENCE_LIMIT = 65536


def digest_bytes(content: bytes) -> str:
    """Return a lowercase SHA-256 digest for immutable result inputs.

    Args:
        content: Exact bytes to bind into the verification result.

    Returns:
        Sixty-four-character hexadecimal SHA-256 digest.

    Side effects:
        None; no files, subprocesses, databases, or networks are accessed.
    """
    return hashlib.sha256(content).hexdigest()


def git(repository: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a bounded Git command with literal argv and captured text output.

    Args:
        repository: Git working tree or bare repository path.
        *args: Git subcommand and literal arguments.
        check: Raise when Git exits nonzero if true.

    Returns:
        Completed process with captured stdout/stderr.

    Raises:
        subprocess.CalledProcessError: For a rejected checked command.
        subprocess.TimeoutExpired: If Git exceeds thirty seconds.
        OSError: If Git cannot be executed.

    Side effects:
        Executes Git without a shell. Callers in this module use read-only object,
        ancestry, identity, and archive operations; no refs/index/config are changed.
    """
    return subprocess.run(
        ["git", "-C", str(repository), *args], capture_output=True, text=True,
        timeout=30, check=check, shell=False, encoding="utf-8", errors="strict",
    )


def exact_commit(repository: Path, revision: str, label: str) -> tuple[str, str]:
    """Validate one full commit ID and return its exact commit and tree IDs.

    Args:
        repository: Repository containing the object.
        revision: Required full lowercase SHA-1, never a branch or abbreviation.
        label: Human-readable field name used in safe error messages.

    Returns:
        Tuple of verified commit SHA and its tree SHA.

    Raises:
        ValueError: If syntax, object type, or exact identity is invalid.
        Git process errors are converted to ValueError without object contents.

    Side effects:
        Reads local Git objects only; no checkout, network, DB, ref or index change.
    """
    if not SHA.fullmatch(revision):
        raise ValueError(f"{label} must be a full lowercase commit SHA")
    try:
        commit = git(repository, "rev-parse", "--verify", revision + "^{commit}").stdout.strip()
        tree = git(repository, "rev-parse", "--verify", revision + "^{tree}").stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise ValueError(f"{label} is not an available commit") from None
    if commit != revision or not SHA.fullmatch(tree):
        raise ValueError(f"{label} did not resolve exactly")
    return commit, tree


def validate_catalog(document: object) -> dict[str, object]:
    """Validate executable catalog semantics not expressible in the JSON schema.

    Args:
        document: Decoded candidate catalog.

    Returns:
        The same typed catalog after complete validation.

    Raises:
        ValueError: For unknown fields, unsafe IDs/paths, shell-like argv, invalid
        timeouts, duplicate checks, placeholders, prerequisites, or applicability.

    Side effects:
        None; no filesystem, subprocess, database, network, or environment access.
    """
    if not isinstance(document, dict) or set(document) != {"schema_version", "catalog_id", "profile", "invalidation_paths", "checks"}:
        raise ValueError("Invalid check catalog fields")
    if document["schema_version"] != 1 or not isinstance(document["catalog_id"], str) or not IDENTIFIER.fullmatch(document["catalog_id"]):
        raise ValueError("Invalid check catalog identity")
    if not isinstance(document["profile"], str) or not IDENTIFIER.fullmatch(document["profile"]):
        raise ValueError("Invalid check profile")
    paths = document["invalidation_paths"]
    if not isinstance(paths, list) or len(paths) != len(set(paths)):
        raise ValueError("Invalid invalidation paths")
    for name in paths:
        safe_relative(name)
    checks = document["checks"]
    if not isinstance(checks, list) or not checks:
        raise ValueError("Catalog must contain checks")
    identifiers = []
    allowed = {
        "id", "description", "argv", "cwd", "mandatory", "timeout_seconds",
        "prerequisites", "applicability", "expected_artifacts", "dependencies",
        "allowed_side_effects",
    }
    seen: set[str] = set()
    for item in checks:
        if not isinstance(item, dict) or set(item) != allowed:
            raise ValueError("Invalid check fields")
        identifier = item["id"]
        if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
            raise ValueError("Invalid check identifier")
        identifiers.append(identifier)
        if not isinstance(item["description"], str) or not item["description"].strip():
            raise ValueError("Invalid check description")
        if not isinstance(item["argv"], list) or not item["argv"] or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in item["argv"]):
            raise ValueError("Invalid check argv")
        if any("{" in arg or "}" in arg for arg in item["argv"] if arg != "{python}"):
            raise ValueError("Unsupported argv placeholder")
        safe_relative(item["cwd"], allow_dot=True)
        if type(item["mandatory"]) is not bool or type(item["timeout_seconds"]) is not int or not 1 <= item["timeout_seconds"] <= 3600:
            raise ValueError("Invalid check policy")
        if not isinstance(item["prerequisites"], list) or any(not isinstance(value, str) or not IDENTIFIER.fullmatch(value) for value in item["prerequisites"]):
            raise ValueError("Invalid prerequisites")
        dependencies = item["dependencies"]
        if not isinstance(dependencies, list) or len(dependencies) != len(set(dependencies)) or any(value not in seen for value in dependencies):
            raise ValueError("Dependencies must be unique known preceding check IDs")
        artifacts = item["expected_artifacts"]
        if not isinstance(artifacts, list) or len(artifacts) != len(set(artifacts)):
            raise ValueError("Invalid expected artifacts")
        for name in artifacts:
            safe_relative(name)
        side_effects = item["allowed_side_effects"]
        if not isinstance(side_effects, list) or len(side_effects) != len(set(side_effects)) or set(side_effects) - {"candidate_export", "evidence"}:
            raise ValueError("Invalid allowed side effects")
        applicability = item["applicability"]
        if not isinstance(applicability, dict) or set(applicability) != {"path_exists"}:
            raise ValueError("Invalid applicability")
        safe_relative(applicability["path_exists"])
        seen.add(identifier)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate check identifier")
    return document


def safe_relative(name: object, allow_dot: bool = False) -> PurePosixPath:
    """Validate a portable candidate-relative path without resolving host links.

    Args:
        name: Catalog value expected to be a normalized POSIX path.
        allow_dot: Permit the repository-root marker ``.`` for command cwd.

    Returns:
        Validated PurePosixPath.

    Raises:
        ValueError: For non-string, absolute, traversing, secret/runtime, backslash,
        colon, empty, or non-normalized paths.

    Side effects:
        None; no filesystem, database, subprocess, or network access.
    """
    if allow_dot and name == ".":
        return PurePosixPath(".")
    if not isinstance(name, str):
        raise ValueError("Path must be a string")
    path = PurePosixPath(name)
    if not name or path.is_absolute() or "\\" in name or ":" in name or path.as_posix() != name or any(
        part in ("..", ".git", ".ai-runtime", "secrets", "credentials") or part.startswith(".env") for part in path.parts
    ):
        raise ValueError(f"Unsafe catalog path: {name}")
    return path


def export_candidate(repository: Path, candidate: str, target: Path) -> None:
    """Export only committed regular files from an exact candidate tree.

    Args:
        repository: Source Git repository; dirty/untracked files are ignored.
        candidate: Previously validated exact commit SHA.
        target: Empty temporary destination owned by this run.

    Returns:
        None after all archive entries are copied.

    Raises:
        ValueError: For links, devices, unsafe names, duplicates, or Git failure.
        OSError/tarfile errors: For local archive or destination failures.

    Side effects:
        Starts ``git archive`` without a shell and writes only inside target. It
        does not checkout, mutate Git, access a DB/network, or copy working files.
    """
    process = subprocess.Popen(
        ["git", "-C", str(repository), "archive", "--format=tar", candidate],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    seen: set[str] = set()
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                archive_name = member.name[:-1] if member.isdir() and member.name.endswith("/") else member.name
                name = safe_relative(archive_name).as_posix()
                if name in seen:
                    raise ValueError("Duplicate archive path")
                seen.add(name)
                destination = target / Path(name)
                if not destination.resolve().is_relative_to(target.resolve()):
                    raise ValueError("Archive path escaped candidate root")
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ValueError("Unreadable candidate archive entry")
                    destination.write_bytes(stream.read())
                else:
                    raise ValueError("Linked or unsupported candidate archive entry")
    finally:
        process.stdout.close()
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    if process.stderr:
        process.stderr.close()
    if process.wait(timeout=30) != 0:
        raise ValueError(f"Candidate archive failed: {stderr.splitlines()[0][:200] if stderr else 'Git error'}")


def file_digests(root: Path, names: list[str]) -> dict[str, str | None]:
    """Digest explicit invalidation files from the isolated candidate.

    Args:
        root: Isolated exact-candidate export.
        names: Validated candidate-relative paths.

    Returns:
        Mapping to SHA-256, or null for an explicitly absent input.

    Raises:
        ValueError: If a path is linked, escapes, or names a directory.
        OSError: If a present input cannot be read.

    Side effects:
        Reads candidate files only; no writes, subprocess, DB, or network access.
    """
    result: dict[str, str | None] = {}
    for name in names:
        path = root.joinpath(*safe_relative(name).parts)
        if path.is_symlink() or path.is_dir() or path.exists() and not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Invalid invalidation input: {name}")
        result[name] = digest_bytes(path.read_bytes()) if path.is_file() else None
    return result


def sanitized_evidence(content: bytes, candidate_root: Path) -> tuple[bytes, bool]:
    """Redact common credential assignments and host paths from bounded evidence.

    Args:
        content: Captured child output bytes.
        candidate_root: Temporary export path that must not escape into reports.

    Returns:
        Sanitized UTF-8 bytes and whether the original output was truncated.

    Side effects:
        None; output is decoded with replacement in memory. No file, subprocess,
        database, environment, or network operation occurs.
    """
    truncated = len(content) > EVIDENCE_LIMIT
    text = content[:EVIDENCE_LIMIT].decode("utf-8", errors="replace")
    for value in {str(candidate_root), candidate_root.as_posix()}:
        text = text.replace(value, "<candidate>")
    text = re.sub(
        r"(?i)\b(token|password|secret|api[_-]?key)\s*[:=]\s*[^\s]+",
        lambda match: f"{match.group(1)}=<redacted>", text,
    )
    text = re.sub(r"(?<!\w)(?:[A-Za-z]:[\\/][^\s]+|/(?:home|tmp|var/tmp|Users)/[^\s]+)", "<external-path>", text)
    if truncated:
        text += "\n<evidence-truncated>\n"
    return text.encode("utf-8"), truncated


def execute_check(
    check: dict[str, object], root: Path, evidence: Path, completed: dict[str, dict[str, object]]
) -> dict[str, object]:
    """Execute one applicable catalog check and persist bounded raw evidence.

    Args:
        check: Fully validated catalog record.
        root: Isolated candidate export.
        evidence: Run-specific evidence directory outside the export.
        completed: Earlier dependency results keyed by stable check ID.

    Returns:
        Machine result with exactly one of the four allowed statuses.

    Raises:
        OSError: If evidence cannot be written. Catalog validation errors should
        have been rejected before this function.

    Side effects:
        May run one catalogued local subprocess with an allowlisted environment and
        write its stdout/stderr evidence. It performs no shell concatenation, DB or
        implicit network operation; command behavior is declared by the catalog.
    """
    identifier = str(check["id"])
    argv = [sys.executable if arg == "{python}" else arg for arg in check["argv"]]
    result: dict[str, object] = {
        "id": identifier,
        "mandatory": check["mandatory"],
        "argv": check["argv"],
        "cwd": check["cwd"],
    }
    dependency_states = {name: completed[name]["status"] for name in check["dependencies"]}
    if any(status in ("FAIL", "NOT_VERIFIED") for status in dependency_states.values()):
        result.update({"status": "NOT_VERIFIED", "dependency_statuses": dependency_states})
        return result
    if any(status == "NOT_APPLICABLE" for status in dependency_states.values()):
        result.update({"status": "NOT_APPLICABLE", "dependency_statuses": dependency_states})
        return result
    applicability = root.joinpath(*safe_relative(check["applicability"]["path_exists"]).parts)
    if not applicability.exists():
        result.update({"status": "NOT_APPLICABLE", "applicability": {"path_exists": False}})
        return result
    result["applicability"] = {"path_exists": True}
    missing = [
        name for name in check["prerequisites"]
        if not (name == "python" and Path(sys.executable).is_file()) and shutil.which(name) is None
    ]
    if missing:
        result.update({"status": "NOT_VERIFIED", "missing_prerequisites": missing})
        return result
    cwd = root if check["cwd"] == "." else root.joinpath(*safe_relative(check["cwd"]).parts)
    if not cwd.is_dir() or not cwd.resolve().is_relative_to(root.resolve()):
        result.update({"status": "NOT_VERIFIED", "missing_prerequisites": ["working_directory"]})
        return result
    started = time.time()
    env = {key: os.environ[key] for key in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL") if key in os.environ}
    try:
        process = subprocess.run(
            argv, cwd=cwd, env=env, capture_output=True, timeout=check["timeout_seconds"], shell=False,
        )
        status = "PASS" if process.returncode == 0 else "FAIL"
        stdout, stderr, exit_code = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as error:
        status, exit_code = "FAIL", 124
        stdout, stderr = error.stdout or b"", error.stderr or b""
    evidence.mkdir(parents=True, exist_ok=True)
    stdout_path = evidence / f"{identifier}.stdout.txt"
    stderr_path = evidence / f"{identifier}.stderr.txt"
    stdout, stdout_truncated = sanitized_evidence(stdout, root)
    stderr, stderr_truncated = sanitized_evidence(stderr, root)
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    missing_artifacts = [name for name in check["expected_artifacts"] if not root.joinpath(*safe_relative(name).parts).is_file()]
    if status == "PASS" and missing_artifacts:
        status = "FAIL"
        exit_code = 1
    result.update({
        "status": status,
        "exit_code": exit_code,
        "duration_ms": round((time.time() - started) * 1000),
        "stdout_sha256": digest_bytes(stdout),
        "stderr_sha256": digest_bytes(stderr),
        "stdout_size": len(stdout),
        "stderr_size": len(stderr),
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "evidence": [f"{evidence.name}/{stdout_path.name}", f"{evidence.name}/{stderr_path.name}"],
    })
    if missing_artifacts:
        result["missing_artifacts"] = missing_artifacts
    return result


def run(repository: Path, candidate: str, base: str, catalog_path: Path, output: Path) -> tuple[dict[str, object], int]:
    """Verify one exact candidate in isolation and write a bound machine result.

    Args:
        repository: Git repository containing candidate and base objects.
        candidate: Exact full candidate commit SHA.
        base: Exact full base commit SHA required to be candidate ancestry.
        catalog_path: Reviewed versioned check catalog outside candidate execution.
        output: Explicit result JSON path; evidence is written beside it.

    Returns:
        Tuple of result document and process code: 0 success, 1 failed mandatory
        check, 2 missing mandatory evidence or invalid runner configuration.

    Raises:
        ValueError/OSError/JSON errors: For invalid inputs before a result can be
        trusted. The CLI converts these to exit two without claiming verification.

    Side effects:
        Reads local Git/catalog data, exports a temporary candidate, runs declared
        argv commands, and writes result/evidence paths only. Dirty/untracked files,
        refs, index, stash, DB, network, and global settings are not modified.
    """
    candidate, candidate_tree = exact_commit(repository, candidate, "candidate")
    base, base_tree = exact_commit(repository, base, "base")
    if git(repository, "merge-base", "--is-ancestor", base, candidate, check=False).returncode != 0:
        raise ValueError("base must be an ancestor of candidate")
    catalog_bytes = catalog_path.read_bytes()
    catalog = validate_catalog(json.loads(catalog_bytes))
    started = int(time.time())
    evidence_name = output.stem + "-evidence"
    evidence = output.parent / evidence_name
    with tempfile.TemporaryDirectory(prefix="ai-candidate-") as directory:
        export = Path(directory) / "candidate"
        export.mkdir()
        export_candidate(repository, candidate, export)
        digests = {
            "catalog_sha256": digest_bytes(catalog_bytes),
            "runner_sha256": digest_bytes(Path(__file__).read_bytes()),
            "invalidation_files": file_digests(export, catalog["invalidation_paths"]),
        }
        checks = []
        completed: dict[str, dict[str, object]] = {}
        for item in catalog["checks"]:
            result = execute_check(item, export, evidence, completed)
            checks.append(result)
            completed[str(item["id"])] = result
    failed = any(item["mandatory"] and item["status"] == "FAIL" for item in checks)
    missing = any(item["mandatory"] and item["status"] == "NOT_VERIFIED" for item in checks)
    outcome, code = ("FAIL", 1) if failed else ("NOT_VERIFIED", 2) if missing else ("PASS", 0)
    document: dict[str, object] = {
        "schema_version": 1,
        "repository": {
            "name": Path(git(repository, "rev-parse", "--show-toplevel").stdout.strip()).name,
            "identity_sha256": digest_bytes(str(Path(repository).resolve()).encode("utf-8")),
        },
        "candidate": {"commit": candidate, "tree": candidate_tree},
        "base": {"commit": base, "tree": base_tree},
        "profile": catalog["profile"],
        "catalog_id": catalog["catalog_id"],
        "digests": digests,
        "environment": environment_report(repository),
        "started_at": started,
        "finished_at": int(time.time()),
        "outcome": outcome,
        "checks": checks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return document, code


def main() -> int:
    """Validate CLI input, run exact-candidate checks, and report honest status.

    Returns:
        0 for verified mandatory checks, 1 for mandatory FAIL, and 2 for invalid
        input or mandatory NOT_VERIFIED evidence.

    Side effects:
        Delegates only to :func:`run`; errors are sanitized and never include file
        contents or environment values. No DB, implicit network, or Git mutation.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    try:
        document, code = run(args.repository, args.candidate, args.base, args.catalog, args.output)
        print(json.dumps({"outcome": document["outcome"], "result": str(args.output)}))
        return code
    except (ValueError, OSError, json.JSONDecodeError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"Runner error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
