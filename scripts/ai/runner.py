"""Run catalogued checks against an isolated export of an exact Git candidate."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
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
    if not isinstance(document, dict) or set(document) != {"schema_version", "catalog_id", "profile", "policy", "invalidation_paths", "checks"}:
        raise ValueError("Invalid check catalog fields")
    if document["schema_version"] != 1 or not isinstance(document["catalog_id"], str) or not IDENTIFIER.fullmatch(document["catalog_id"]):
        raise ValueError("Invalid check catalog identity")
    if not isinstance(document["profile"], str) or not IDENTIFIER.fullmatch(document["profile"]):
        raise ValueError("Invalid check profile")
    policy = document["policy"]
    if not isinstance(policy, dict) or set(policy) != {"allow_mandatory_not_applicable"} or type(policy["allow_mandatory_not_applicable"]) is not bool:
        raise ValueError("Invalid catalog result policy")
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
        if not isinstance(applicability, dict) or set(applicability) != {"path_exists", "missing_status"}:
            raise ValueError("Invalid applicability")
        safe_relative(applicability["path_exists"])
        if applicability["missing_status"] not in ("NOT_APPLICABLE", "NOT_VERIFIED"):
            raise ValueError("Invalid applicability missing status")
        seen.add(identifier)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate check identifier")
    return document


def safe_relative(
    name: object, allow_dot: bool = False, allow_env_example: bool = False
) -> PurePosixPath:
    """Validate a portable candidate-relative path without resolving host links.

    Args:
        name: Catalog value expected to be a normalized POSIX path.
        allow_dot: Permit the repository-root marker ``.`` for command cwd.
        allow_env_example: Permit only the literal public ``.env.example`` while
            retaining rejection of every other env path.

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
        part in ("..", ".git", ".ai-runtime", "secrets", "credentials")
        or part.startswith(".env") and not (allow_env_example and name == ".env.example")
        for part in path.parts
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
                name = safe_relative(archive_name, allow_env_example=True).as_posix()
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


def file_digests(root: Path, names: list[str]) -> dict[str, dict[str, object]]:
    """Digest explicit invalidation files from the isolated candidate.

    Args:
        root: Isolated exact-candidate export.
        names: Validated candidate-relative paths.

    Returns:
        Mapping to explicit presence plus SHA-256 for each present input.

    Raises:
        ValueError: If a path is linked, escapes, or names a directory.
        OSError: If a present input cannot be read.

    Side effects:
        Reads candidate files only; no writes, subprocess, DB, or network access.
    """
    result: dict[str, dict[str, object]] = {}
    for name in names:
        path = root.joinpath(*safe_relative(name).parts)
        if path.is_symlink() or path.is_dir() or path.exists() and not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Invalid invalidation input: {name}")
        result[name] = (
            {"present": True, "sha256": digest_bytes(path.read_bytes())}
            if path.is_file() else {"present": False}
        )
    return result


def runner_digests() -> dict[str, str]:
    """Digest every local module and schema that controls runner semantics.

    Returns:
        Stable install-root-relative names mapped to SHA-256 digests.

    Raises:
        OSError: If an effective module or schema cannot be read.
        ValueError: If the expected installation layout is incomplete.

    Side effects:
        Reads only public runner implementation and schema files; no writes,
        subprocesses, databases, environment inspection, or network access.
    """
    install_root = Path(__file__).resolve().parents[2]
    names = (
        "scripts/ai/runner.py",
        "scripts/ai/detector.py",
        "templates/ai/schemas/check-catalog.schema.json",
        "templates/ai/schemas/check-result.schema.json",
    )
    result = {}
    for name in names:
        path = install_root.joinpath(*PurePosixPath(name).parts)
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(install_root):
            raise ValueError(f"Missing effective runner input: {name}")
        result[name] = digest_bytes(path.read_bytes())
    return result


def candidate_snapshot(root: Path) -> dict[str, str]:
    """Create a link-rejecting digest snapshot of one isolated export.

    Args:
        root: Exact-candidate export owned by the current check.

    Returns:
        Sorted candidate-relative regular-file digests and directory markers.

    Raises:
        ValueError: If a link, special file, or escaping entry is encountered.
        OSError: If metadata or bytes cannot be read.

    Side effects:
        Reads only the temporary export; no writes, subprocesses, DB or network.
    """
    snapshot: dict[str, str] = {}
    pending = [root]
    while pending:
        directory = pending.pop()
        for entry in sorted(directory.iterdir(), key=lambda item: item.name):
            relative = entry.relative_to(root).as_posix()
            mode = entry.lstat().st_mode
            if stat.S_ISLNK(mode) or not entry.resolve().is_relative_to(root.resolve()):
                raise ValueError(f"Linked or escaping candidate output: {relative}")
            if stat.S_ISDIR(mode):
                snapshot[relative + "/"] = "directory"
                pending.append(entry)
            elif stat.S_ISREG(mode):
                snapshot[relative] = digest_bytes(entry.read_bytes())
            else:
                raise ValueError(f"Unsupported candidate output: {relative}")
    return dict(sorted(snapshot.items()))


def artifact_digest(root: Path, name: str) -> str | None:
    """Return a contained regular artifact digest, rejecting links and specials.

    Args:
        root: Isolated exact-candidate export.
        name: Validated candidate-relative expected artifact path.

    Returns:
        SHA-256 for a present regular file, otherwise ``None`` when absent.

    Raises:
        ValueError: If the artifact or an existing ancestor is linked, escaping,
            a directory, or another unsupported type.
        OSError: If filesystem metadata or bytes cannot be read.

    Side effects:
        Reads temporary artifact metadata/content only; no writes, DB or network.
    """
    path = root.joinpath(*safe_relative(name).parts)
    current = root
    for part in safe_relative(name).parts:
        current = current / part
        if current.exists() or current.is_symlink():
            mode = current.lstat().st_mode
            if stat.S_ISLNK(mode) or not current.resolve().is_relative_to(root.resolve()):
                raise ValueError(f"Linked or escaping artifact: {name}")
    if not path.exists():
        return None
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError(f"Artifact is not a regular file: {name}")
    return digest_bytes(path.read_bytes())


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
        r"(?im)\b((?:[A-Z][A-Z0-9_]*_)?(?:TOKEN|PASSWORD|SECRET|KEY)|API[_-]?KEY)\s*[:=]\s*[^\s]+",
        lambda match: f"{match.group(1)}=<redacted>", text,
    )
    text = re.sub(
        r"(?im)\b(Authorization)\s*:\s*(?:Bearer|Basic)\s+[^\s]+",
        lambda match: f"{match.group(1)}: <redacted>", text,
    )
    text = re.sub(
        r"(?i)\b(https?://)[^/@\s:]+(?::[^/@\s]*)?@",
        lambda match: f"{match.group(1)}<redacted>@",
        text,
    )
    text = re.sub(r"(?<!\w)(?:[A-Za-z]:[\\/][^\s]+|/(?:home|tmp|var/tmp|Users)/[^\s]+)", "<external-path>", text)
    if truncated:
        text += "\n<evidence-truncated>\n"
    return text.encode("utf-8"), truncated


def reserve_runtime_output(repository: Path, output: Path) -> tuple[Path, int, Path]:
    """Reserve a no-follow result file and unique evidence directory safely.

    Args:
        repository: Git repository whose ``.ai-runtime`` is the only writable
            result root accepted by the runner.
        output: Requested result path, absolute or relative to the caller.

    Returns:
        Resolved output path, exclusive open file descriptor, and newly-created
        run-unique evidence directory.

    Raises:
        ValueError: If output escapes ``.ai-runtime`` or any existing component
            is a link/non-directory, or the predictable result already exists.
        OSError: If secure directory/file creation fails.

    Side effects:
        Creates missing directories beneath repository ``.ai-runtime``, reserves
        one new result file, and creates one unique evidence directory. It never
        overwrites an existing path and performs no DB, subprocess, or network I/O.
    """
    root = Path(git(repository, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    runtime = root / ".ai-runtime"
    requested = output if output.is_absolute() else Path.cwd() / output
    requested = requested.absolute()
    try:
        relative = requested.relative_to(runtime)
    except ValueError:
        raise ValueError("Result output must be inside repository .ai-runtime") from None
    if not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
        raise ValueError("Invalid result output path")
    current = root
    for part in (".ai-runtime", *relative.parts[:-1]):
        current = current / part
        if current.exists() or current.is_symlink():
            mode = current.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode) or not current.resolve().is_relative_to(root):
                raise ValueError("Linked or non-directory result ancestor")
        else:
            current.mkdir()
    if requested.exists() or requested.is_symlink():
        raise ValueError("Result output already exists")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(requested, flags, 0o600)
    try:
        evidence = Path(tempfile.mkdtemp(prefix=requested.stem + "-evidence-", dir=requested.parent))
    except BaseException:
        os.close(descriptor)
        requested.unlink(missing_ok=True)
        raise
    return requested, descriptor, evidence


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
        result.update({"status": "NOT_VERIFIED", "dependency_statuses": dependency_states})
        return result
    applicability = root.joinpath(*safe_relative(check["applicability"]["path_exists"]).parts)
    if not applicability.exists():
        result.update({"status": check["applicability"]["missing_status"], "applicability": {"path_exists": False}})
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
    artifact_before = {name: artifact_digest(root, name) for name in check["expected_artifacts"]}
    snapshot_before = candidate_snapshot(root)
    started = time.time()
    env = {key: os.environ[key] for key in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL") if key in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        process = subprocess.run(
            argv, cwd=cwd, env=env, capture_output=True, timeout=check["timeout_seconds"], shell=False,
        )
        status = "PASS" if process.returncode == 0 else "FAIL"
        stdout, stderr, exit_code = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as error:
        status, exit_code = "FAIL", None
        stdout, stderr = error.stdout or b"", error.stderr or b""
    stdout_path = evidence / f"{identifier}.stdout.txt"
    stderr_path = evidence / f"{identifier}.stderr.txt"
    stdout, stdout_truncated = sanitized_evidence(stdout, root)
    stderr, stderr_truncated = sanitized_evidence(stderr, root)
    with stdout_path.open("xb") as stream:
        stream.write(stdout)
    with stderr_path.open("xb") as stream:
        stream.write(stderr)
    invalid_artifacts = []
    artifacts = {}
    for name, before in artifact_before.items():
        try:
            after = artifact_digest(root, name)
        except ValueError:
            after = None
            invalid_artifacts.append(name)
        if after is None or after == before:
            invalid_artifacts.append(name)
        elif after is not None:
            artifacts[name] = after
    try:
        snapshot_after = candidate_snapshot(root)
        mutated = snapshot_after != snapshot_before
    except ValueError:
        mutated = True
        invalid_artifacts.extend(name for name in check["expected_artifacts"] if name not in invalid_artifacts)
    if mutated and "candidate_export" not in check["allowed_side_effects"]:
        invalid_artifacts.append("candidate_export")
    invalid_artifacts = sorted(set(invalid_artifacts))
    if status == "PASS" and invalid_artifacts:
        status = "FAIL"
        exit_code = 1
    execution = {
        "status": status,
        "duration_ms": round((time.time() - started) * 1000),
        "stdout_sha256": digest_bytes(stdout),
        "stderr_sha256": digest_bytes(stderr),
        "stdout_size": len(stdout),
        "stderr_size": len(stderr),
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "evidence": [f"{evidence.name}/{stdout_path.name}", f"{evidence.name}/{stderr_path.name}"],
        "candidate_export_mutated": mutated,
    }
    if exit_code is not None:
        execution["exit_code"] = exit_code
    else:
        execution["timed_out"] = True
    result.update(execution)
    if artifacts:
        result["artifacts"] = artifacts
    if invalid_artifacts:
        result["invalid_artifacts"] = invalid_artifacts
    return result


def validate_result_semantics(document: dict[str, object], allow_mandatory_na: bool) -> None:
    """Enforce result relationships beyond the bundled JSON Schema vocabulary.

    Args:
        document: Fully assembled machine result.
        allow_mandatory_na: Reviewed catalog policy controlling whether mandatory
            NOT_APPLICABLE checks may still produce an overall PASS.

    Returns:
        None when statuses, exit metadata, timestamps, and outcome agree.

    Raises:
        ValueError: If a result is internally inconsistent or could claim PASS
            without the evidence required by catalog policy.

    Side effects:
        None; validates in-memory public metadata without I/O, DB, or network.
    """
    checks = document["checks"]
    for item in checks:
        status = item["status"]
        executed = "duration_ms" in item
        if executed != ("evidence" in item):
            raise ValueError("Executed check evidence is inconsistent")
        if status == "PASS" and (not executed or item.get("exit_code") != 0 or item.get("timed_out")):
            raise ValueError("PASS requires a completed zero exit")
        if status == "FAIL" and not executed:
            raise ValueError("FAIL requires attempted execution")
        if status in ("NOT_APPLICABLE", "NOT_VERIFIED") and ("exit_code" in item or "timed_out" in item):
            raise ValueError("Unexecuted status cannot contain exit metadata")
        if item.get("timed_out") is True and "exit_code" in item:
            raise ValueError("Timed out check cannot invent an exit code")
    mandatory = [item for item in checks if item["mandatory"]]
    if any(item["status"] == "FAIL" for item in mandatory):
        expected = "FAIL"
    elif any(item["status"] == "NOT_VERIFIED" for item in mandatory) or (
        not allow_mandatory_na and any(item["status"] == "NOT_APPLICABLE" for item in mandatory)
    ):
        expected = "NOT_VERIFIED"
    else:
        expected = "PASS"
    if document["outcome"] != expected or document["finished_at"] < document["started_at"]:
        raise ValueError("Result outcome or timestamps are inconsistent")


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
    output, descriptor, evidence = reserve_runtime_output(repository, output)
    try:
        with tempfile.TemporaryDirectory(prefix="ai-candidate-input-") as directory:
            export = Path(directory) / "candidate"
            export.mkdir()
            export_candidate(repository, candidate, export)
            invalidation_files = file_digests(export, catalog["invalidation_paths"])
        digests = {
            "catalog_sha256": digest_bytes(catalog_bytes),
            "runner_files": runner_digests(),
            "invalidation_files": invalidation_files,
        }
        checks = []
        completed: dict[str, dict[str, object]] = {}
        for item in catalog["checks"]:
            with tempfile.TemporaryDirectory(prefix="ai-candidate-check-") as directory:
                check_export = Path(directory) / "candidate"
                check_export.mkdir()
                export_candidate(repository, candidate, check_export)
                result = execute_check(item, check_export, evidence, completed)
                checks.append(result)
                completed[str(item["id"])] = result
    except BaseException:
        os.close(descriptor)
        output.unlink(missing_ok=True)
        shutil.rmtree(evidence, ignore_errors=True)
        raise
    failed = any(item["mandatory"] and item["status"] == "FAIL" for item in checks)
    missing = any(item["mandatory"] and item["status"] == "NOT_VERIFIED" for item in checks)
    mandatory_na = any(item["mandatory"] and item["status"] == "NOT_APPLICABLE" for item in checks)
    if mandatory_na and not catalog["policy"]["allow_mandatory_not_applicable"]:
        missing = True
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
    validate_result_semantics(document, catalog["policy"]["allow_mandatory_not_applicable"])
    payload = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
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
