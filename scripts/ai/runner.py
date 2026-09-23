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
from runner_caps import (
    build_run_context,
    compare_generated,
    evaluate_applicability,
    provision_node,
    run_argv,
)

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
    if not isinstance(document, dict) or set(document) not in (
        {"schema_version", "catalog_id", "profile", "policy", "invalidation_paths", "checks"},
        {"schema_version", "catalog_id", "profile", "policy", "invalidation_paths", "run_context", "inventory", "checks"},
    ):
        raise ValueError("Invalid check catalog fields")
    if document["schema_version"] not in (1, 2) or not isinstance(document["catalog_id"], str) or not IDENTIFIER.fullmatch(document["catalog_id"]):
        raise ValueError("Invalid check catalog identity")
    if document["schema_version"] == 2:
        context = document["run_context"]
        if not isinstance(context, dict) or set(context) != {"events", "network", "network_ttl_seconds"}:
            raise ValueError("Invalid run-context policy")
        if not isinstance(context["events"], list) or not context["events"] or set(context["events"]) - {"pull_request", "push", "manual", "schedule"}:
            raise ValueError("Invalid run-context events")
        if context["network"] not in ("disabled", "allowed") or type(context["network_ttl_seconds"]) is not int or context["network_ttl_seconds"] < 1:
            raise ValueError("Invalid network policy")
        inventory = document["inventory"]
        if not isinstance(inventory, dict) or set(inventory) != {"manifest", "expected_steps"} or inventory["expected_steps"] != 55:
            raise ValueError("Invalid workflow inventory binding")
        safe_relative(inventory["manifest"])
    if not isinstance(document["profile"], str) or not IDENTIFIER.fullmatch(document["profile"]):
        raise ValueError("Invalid check profile")
    policy = document["policy"]
    if not isinstance(policy, dict) or set(policy) != {"allow_mandatory_not_applicable"} or type(policy["allow_mandatory_not_applicable"]) is not bool:
        raise ValueError("Invalid catalog result policy")
    paths = document["invalidation_paths"]
    if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)):
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
        "allowed_side_effects", "provisioning", "generated_comparisons", "ephemeral_outputs",
    }
    seen: set[str] = set()
    for item in checks:
        legacy_allowed = allowed - {"provisioning", "generated_comparisons", "ephemeral_outputs"}
        if not isinstance(item, dict) or set(item) not in (allowed, legacy_allowed):
            raise ValueError("Invalid check fields")
        identifier = item["id"]
        if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
            raise ValueError("Invalid check identifier")
        identifiers.append(identifier)
        if not isinstance(item["description"], str) or not item["description"].strip():
            raise ValueError("Invalid check description")
        if not isinstance(item["argv"], list) or not item["argv"] or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in item["argv"]):
            raise ValueError("Invalid check argv")
        if any("{" in arg or "}" in arg for arg in item["argv"] if arg not in ("{python}", "{git_bash}")):
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
        if not isinstance(applicability, dict):
            raise ValueError("Invalid applicability")
        if set(applicability) == {"path_exists", "missing_status"}:
            safe_relative(applicability["path_exists"])
            if applicability["missing_status"] not in ("NOT_APPLICABLE", "NOT_VERIFIED"):
                raise ValueError("Invalid applicability missing status")
        else:
            kind = applicability.get("kind")
            fields = {
                "always": {"kind"},
                "path_exists": {"kind", "path", "missing_status"},
                "changed_any": {"kind", "prefixes"},
                "event_in": {"kind", "events"},
                "contract_spec": {"kind", "scaffold_package"},
            }
            if kind not in fields or set(applicability) != fields[kind]:
                raise ValueError("Invalid typed applicability")
            for value in applicability.get("prefixes", []):
                safe_relative(value)
            if "path" in applicability:
                safe_relative(applicability["path"])
            if applicability.get("missing_status") not in (None, "NOT_APPLICABLE", "NOT_VERIFIED"):
                raise ValueError("Invalid typed applicability status")
            if kind == "contract_spec" and applicability.get("scaffold_package") != "claude-api-contract":
                raise ValueError("Invalid scaffold identity")
            if set(applicability.get("events", [])) - {"pull_request", "push", "manual", "schedule"}:
                raise ValueError("Invalid applicability events")
        provisioning = item.get("provisioning", [])
        if not isinstance(provisioning, list) or len(provisioning) != len({step.get("id") for step in provisioning if isinstance(step, dict)}):
            raise ValueError("Invalid provisioning DAG")
        previous_provisions: set[str] = set()
        for provision in provisioning:
            if not isinstance(provision, dict) or set(provision) != {"id", "kind", "dependencies", "network", "ttl_seconds"}:
                raise ValueError("Invalid provisioning record")
            if provision["id"] != "npm-ci" or provision["kind"] != "npm-ci" or set(provision["dependencies"]) - previous_provisions:
                raise ValueError("Unsupported provisioning DAG")
            if provision["network"] not in ("disabled", "allowed") or type(provision["ttl_seconds"]) is not int or provision["ttl_seconds"] < 1:
                raise ValueError("Invalid provisioning network policy")
            previous_provisions.add(provision["id"])
        generated = item.get("generated_comparisons", [])
        if not isinstance(generated, list) or len(generated) != len(set(generated)):
            raise ValueError("Invalid generated comparisons")
        for name in generated:
            safe_relative(name)
        ephemeral = item.get("ephemeral_outputs", [])
        if not isinstance(ephemeral, list) or len(ephemeral) != len(set(ephemeral)):
            raise ValueError("Invalid ephemeral outputs")
        for name in ephemeral:
            safe_relative(name)
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
        allow_env_example: Permit only a final public ``.env.example`` basename,
            including below normal directories, while rejecting every other env
            basename and any directory named ``.env.example``.

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
        or part.startswith(".env") and not (
            allow_env_example and part == ".env.example" and part == path.name
        )
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
                    destination.chmod(0o755)
                elif member.isfile():
                    if member.mode & 0o7000:
                        raise ValueError("Unsafe candidate archive mode")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ValueError("Unreadable candidate archive entry")
                    destination.write_bytes(stream.read())
                    destination.chmod(0o755 if member.mode & 0o111 else 0o644)
                else:
                    raise ValueError("Linked or unsupported candidate archive entry")
        process.stdout.read()
    except BaseException:
        process.kill()
        process.stdout.close()
        process.wait(timeout=30)
        raise
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
        "scripts/ai/runner_caps.py",
        "templates/ai/schemas/check-catalog.schema.json",
        "templates/ai/schemas/check-result.schema.json",
        "templates/ai/schemas/run-context.schema.json",
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
            if entry.name in {"node_modules", ".ai-node-cache"}:
                continue
            mode = entry.lstat().st_mode
            if stat.S_ISLNK(mode) or not entry.resolve().is_relative_to(root.resolve()):
                raise ValueError(f"Linked or escaping candidate output: {relative}")
            if stat.S_ISDIR(mode):
                snapshot[relative + "/"] = "directory"
                pending.append(entry)
            elif stat.S_ISREG(mode):
                executable = "x" if mode & 0o111 else "-"
                snapshot[relative] = f"{executable}:{digest_bytes(entry.read_bytes())}"
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


def reserve_runtime_output(repository: Path, output: Path) -> tuple[Path, Path, int, tuple[int, int], Path]:
    """Reserve a staging result and unique evidence directory safely.

    Args:
        repository: Git repository whose ``.ai-runtime`` is the only writable
            result root accepted by the runner.
        output: Requested result path, absolute or relative to the caller.

    Returns:
        Resolved final path, staging path, exclusive staging descriptor, its
        device/inode identity, and newly-created run-unique evidence directory.

    Raises:
        ValueError: If output escapes ``.ai-runtime`` or any existing component
            is a link/non-directory, or the predictable result already exists.
        OSError: If secure directory/file creation fails.

    Side effects:
        Creates missing directories beneath repository ``.ai-runtime``, reserves
        one unique staging file, and creates one unique evidence directory. The
        predictable final path remains absent until atomic exclusive finalization.
        It never overwrites an existing path or performs DB/network I/O.
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
    descriptor, staging_name = tempfile.mkstemp(
        prefix=requested.stem + ".pending-", suffix=".json", dir=requested.parent
    )
    staging = Path(staging_name)
    metadata = os.fstat(descriptor)
    identity = (metadata.st_dev, metadata.st_ino)
    try:
        evidence = Path(tempfile.mkdtemp(prefix=requested.stem + "-evidence-", dir=requested.parent))
    except BaseException:
        os.close(descriptor)
        staging.unlink(missing_ok=True)
        raise
    return requested, staging, descriptor, identity, evidence


def cleanup_runtime_output(
    output: Path,
    staging: Path,
    descriptor: int,
    identity: tuple[int, int],
    evidence: Path,
    final_created: bool,
) -> None:
    """Remove only this failed run's staging/final files and evidence directory.

    Args:
        output: Predictable final result path.
        staging: Unique staging file created by this run.
        descriptor: Staging descriptor, or ``-1`` after it was closed.
        identity: Device/inode pair captured from the exclusive staging file.
        evidence: Unique evidence directory created by this run.
        final_created: Whether this run atomically linked its staging inode to the
            final output name before a later failure.

    Returns:
        None. Cleanup is best effort and never masks the original failure.

    Side effects:
        Closes this run's descriptor and unlinks only matching regular-file inodes;
        removes the owned non-linked evidence directory. No external paths, DB,
        subprocesses, or network resources are accessed.
    """
    if descriptor >= 0:
        try:
            os.close(descriptor)
        except OSError:
            pass
    for path in (staging, output if final_created else None):
        if path is None:
            continue
        try:
            metadata = path.lstat()
            if stat.S_ISREG(metadata.st_mode) and (metadata.st_dev, metadata.st_ino) == identity:
                path.unlink()
        except OSError:
            pass
    try:
        if not evidence.is_symlink() and evidence.is_dir():
            shutil.rmtree(evidence)
    except OSError:
        pass


def finalize_runtime_output(staging: Path, output: Path, descriptor: int, payload: bytes) -> None:
    """Durably write staging bytes and atomically claim an absent final path.

    Args:
        staging: Unique regular staging path owned by this run.
        output: Final result path that must remain absent until finalization.
        descriptor: Exclusive open descriptor for ``staging``.
        payload: Complete canonical JSON bytes to persist.

    Returns:
        None after the complete staging inode is linked to the final name. The
        caller removes the staging name while retaining rollback state.

    Raises:
        OSError: If writing, syncing, exclusive hard-link finalization, or staging
        operation fails. An existing/symlink output is never overwritten.

    Side effects:
        Writes and fsyncs the owned staging file, closes its descriptor, creates
        one same-filesystem hard link atomically. No database, subprocess, or
        network operation occurs.
    """
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(staging, output, follow_symlinks=False)


def execute_check(
    check: dict[str, object],
    root: Path,
    evidence: Path,
    completed: dict[str, dict[str, object]],
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    """Execute one applicable catalog check and persist bounded raw evidence.

    Args:
        check: Fully validated catalog record.
        root: Isolated candidate export.
        evidence: Run-specific evidence directory outside the export.
        completed: Earlier dependency results keyed by stable check ID.
        context: Versioned exact event/base/candidate context. Legacy direct tests
            may omit it and receive an explicit local manual context substitute.

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
    git_bash = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else "bash"
    argv = [sys.executable if arg == "{python}" else git_bash if arg == "{git_bash}" else arg for arg in check["argv"]]
    result: dict[str, object] = {
        "id": identifier,
        "mandatory": check["mandatory"],
        "argv": check["argv"],
        "cwd": check["cwd"],
    }
    applicability_spec = check["applicability"]
    if "path_exists" in applicability_spec:
        applicability_spec = {
            "kind": "path_exists",
            "path": applicability_spec["path_exists"],
            "missing_status": applicability_spec["missing_status"],
        }
    applicability_state, applicability_evidence = evaluate_applicability(
        applicability_spec,
        root,
        context or {"event": "manual", "changed_files": []},
    )
    result["applicability"] = applicability_evidence
    if applicability_state != "APPLICABLE":
        result["status"] = applicability_state
        return result
    dependency_states = {name: completed[name]["status"] for name in check["dependencies"]}
    if any(status in ("FAIL", "NOT_VERIFIED", "NOT_APPLICABLE") for status in dependency_states.values()):
        result.update({"status": "NOT_VERIFIED", "dependency_statuses": dependency_states})
        return result
    missing = [
        name for name in check["prerequisites"]
        if not (name == "python" and Path(sys.executable).is_file())
        and not (name == "git-bash" and (Path(git_bash).is_file() or shutil.which(git_bash)))
        and shutil.which(name) is None
    ]
    if missing:
        result.update({"status": "NOT_VERIFIED", "missing_prerequisites": missing})
        return result
    if not Path(argv[0]).is_absolute():
        executable = shutil.which(argv[0])
        if executable is None:
            result.update({"status": "NOT_VERIFIED", "missing_prerequisites": ["command_executable"]})
            return result
        argv[0] = executable
    cwd = root if check["cwd"] == "." else root.joinpath(*safe_relative(check["cwd"]).parts)
    if not cwd.is_dir() or not cwd.resolve().is_relative_to(root.resolve()):
        result.update({"status": "NOT_VERIFIED", "missing_prerequisites": ["working_directory"]})
        return result
    env = {key: os.environ[key] for key in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL") if key in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    provisions = []
    for provision in check.get("provisioning", []):
        effective_provision = dict(provision)
        requested_network = (context or {}).get("network", {}).get("mode", "disabled")
        effective_provision["network"] = (
            "allowed" if requested_network == "allowed" and provision["network"] == "allowed" else "disabled"
        )
        provision_result = provision_node(
            root, effective_provision, env, check["timeout_seconds"], evidence.parent / ".npm-content-cache"
        )
        provisions.append(provision_result)
        if provision_result["status"] != "PASS":
            result.update({"status": "NOT_VERIFIED", "provisioning": provisions})
            return result
    if provisions:
        result["provisioning"] = provisions
    artifact_before = {name: artifact_digest(root, name) for name in check["expected_artifacts"]}
    generated_before = {
        name: (root.joinpath(*safe_relative(name).parts).read_bytes() if root.joinpath(*safe_relative(name).parts).is_file() else None)
        for name in check.get("generated_comparisons", [])
    }
    snapshot_before = candidate_snapshot(root)
    try:
        exit_code, stdout, stderr, timed_out, duration_ms = run_argv(
            argv, cwd, env, check["timeout_seconds"]
        )
        status = "PASS" if exit_code == 0 else "FAIL"
    except OSError:
        result.update({"status": "NOT_VERIFIED", "missing_prerequisites": ["command_executable"]})
        return result
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
        snapshot_after = {}
    mutations = sorted(
        name for name in set(snapshot_before) | set(snapshot_after)
        if snapshot_before.get(name) != snapshot_after.get(name)
    )
    if "ephemeral_outputs" in check:
        allowed_files = set(check["generated_comparisons"]) | set(check["ephemeral_outputs"])
        allowed_directories = {
            "/".join(parts[:index]) + "/"
            for name in allowed_files for parts in [safe_relative(name).parts]
            for index in range(1, len(parts))
        }
        unexpected_mutations = set(mutations) - allowed_files - allowed_directories
        if unexpected_mutations:
            invalid_artifacts.append("candidate_export")
    elif mutated and "candidate_export" not in check["allowed_side_effects"]:
        invalid_artifacts.append("candidate_export")
    if check.get("generated_comparisons"):
        try:
            comparison = compare_generated(root, generated_before, check["generated_comparisons"])
        except ValueError:
            comparison = {"matched": False, "files": []}
        result["generated_comparison"] = comparison
        if not comparison["matched"]:
            invalid_artifacts.append("generated_comparison")
    invalid_artifacts = sorted(set(invalid_artifacts))
    if status == "PASS" and invalid_artifacts:
        status = "FAIL"
        exit_code = 1
    execution = {
        "status": status,
        "duration_ms": duration_ms,
        "stdout_sha256": digest_bytes(stdout),
        "stderr_sha256": digest_bytes(stderr),
        "stdout_size": len(stdout),
        "stderr_size": len(stderr),
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "evidence": [f"{evidence.name}/{stdout_path.name}", f"{evidence.name}/{stderr_path.name}"],
        "candidate_export_mutated": mutated,
        "candidate_export_mutations": mutations,
    }
    if exit_code is not None:
        execution["exit_code"] = exit_code
    elif timed_out:
        execution["timed_out"] = True
    result.update(execution)
    if artifacts:
        result["artifacts"] = artifacts
    if invalid_artifacts:
        result["invalid_artifacts"] = invalid_artifacts
    ephemeral_outputs = {}
    for name in check.get("ephemeral_outputs", []):
        try:
            digest = artifact_digest(root, name)
        except ValueError:
            digest = None
        if digest is not None:
            ephemeral_outputs[name] = digest
    if ephemeral_outputs:
        result["ephemeral_outputs"] = ephemeral_outputs
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
    digest_pattern = re.compile(r"[0-9a-f]{64}")
    digests = document.get("digests")
    if not isinstance(digests, dict) or not digest_pattern.fullmatch(str(digests.get("catalog_sha256", ""))):
        raise ValueError("Catalog digest is incomplete")
    runner_files = digests.get("runner_files")
    required_runner_files = {
        "scripts/ai/runner.py", "scripts/ai/detector.py", "scripts/ai/runner_caps.py",
        "templates/ai/schemas/check-catalog.schema.json",
        "templates/ai/schemas/check-result.schema.json",
        "templates/ai/schemas/run-context.schema.json",
    }
    if not isinstance(runner_files, dict) or set(runner_files) != required_runner_files or any(
        not isinstance(value, str) or not digest_pattern.fullmatch(value) for value in runner_files.values()
    ):
        raise ValueError("Effective runner digests are incomplete")
    invalidation = digests.get("invalidation_files")
    if not isinstance(invalidation, dict) or not invalidation:
        raise ValueError("Invalidation digest map is empty")
    for record in invalidation.values():
        if not isinstance(record, dict) or type(record.get("present")) is not bool:
            raise ValueError("Invalid invalidation digest record")
        expected_fields = {"present", "sha256"} if record["present"] else {"present"}
        if set(record) != expected_fields or record["present"] and not digest_pattern.fullmatch(str(record["sha256"])):
            raise ValueError("Present invalidation input requires one exact digest")
    repository = document.get("repository")
    if not isinstance(repository, dict) or not repository.get("name") or not digest_pattern.fullmatch(str(repository.get("identity_sha256", ""))):
        raise ValueError("Repository identity is incomplete")
    context = document.get("run_context")
    if not isinstance(context, dict) or context.get("schema_version") != 1:
        raise ValueError("Run context is incomplete")
    canonical_context = dict(context)
    recorded_context_digest = canonical_context.pop("context_sha256", None)
    if not digest_pattern.fullmatch(str(recorded_context_digest)) or digest_bytes(
        json.dumps(canonical_context, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ) != recorded_context_digest:
        raise ValueError("Run context digest is inconsistent")
    if context.get("candidate") != document.get("candidate") or context.get("base") != document.get("base"):
        raise ValueError("Run context Git identity differs from result")
    environment = document.get("environment")
    if not isinstance(environment, dict) or not isinstance(environment.get("tools"), dict) or not environment["tools"]:
        raise ValueError("Tool environment is incomplete")
    for tool in environment["tools"].values():
        if not isinstance(tool, dict) or tool.get("status") not in ("AVAILABLE", "MISSING", "NOT_VERIFIED"):
            raise ValueError("Invalid tool identity")
        if tool["status"] == "AVAILABLE" and (not isinstance(tool.get("version"), str) or not tool["version"]):
            raise ValueError("Available tool requires a version identity")
    repository_environment = environment.get("repository")
    if not isinstance(repository_environment, dict) or repository_environment.get("status") not in ("AVAILABLE", "NOT_VERIFIED"):
        raise ValueError("Repository environment is incomplete")
    if repository_environment["status"] == "AVAILABLE":
        required_repository = {"root_name", "git_dir_name", "head", "tree", "dirty_tracked", "untracked"}
        if any(name not in repository_environment for name in required_repository):
            raise ValueError("Available repository requires complete identity")
        if not SHA.fullmatch(str(repository_environment["head"])) or not SHA.fullmatch(str(repository_environment["tree"])):
            raise ValueError("Available repository requires exact Git identity")
    checks = document["checks"]
    executed_fields = {
        "duration_ms", "stdout_sha256", "stderr_sha256", "stdout_size",
        "stderr_size", "stdout_truncated", "stderr_truncated", "evidence",
        "candidate_export_mutated", "candidate_export_mutations",
    }
    for item in checks:
        status = item["status"]
        executed = status in ("PASS", "FAIL")
        if executed and not executed_fields.issubset(item):
            raise ValueError("Executed check evidence is incomplete")
        if not executed and (executed_fields.intersection(item) or "exit_code" in item or "timed_out" in item):
            raise ValueError("Unexecuted check contains execution metadata")
        if executed and (
            type(item["duration_ms"]) is not int or item["duration_ms"] < 0
            or type(item["stdout_size"]) is not int or item["stdout_size"] < 0
            or type(item["stderr_size"]) is not int or item["stderr_size"] < 0
            or type(item["stdout_truncated"]) is not bool or type(item["stderr_truncated"]) is not bool
            or type(item["candidate_export_mutated"]) is not bool
            or not isinstance(item["candidate_export_mutations"], list)
            or item["candidate_export_mutated"] != bool(item["candidate_export_mutations"])
            or not digest_pattern.fullmatch(str(item["stdout_sha256"]))
            or not digest_pattern.fullmatch(str(item["stderr_sha256"]))
            or not isinstance(item["evidence"], list) or len(item["evidence"]) != 2
        ):
            raise ValueError("Executed check metadata has invalid types")
        if status == "PASS" and (item.get("exit_code") != 0 or "timed_out" in item):
            raise ValueError("PASS requires a completed zero exit")
        if status == "FAIL":
            timed_out = item.get("timed_out")
            has_exit = "exit_code" in item
            if "timed_out" in item and timed_out is not True:
                raise ValueError("Timeout marker must be true when present")
            if (timed_out is True) == has_exit:
                raise ValueError("FAIL requires exactly timeout or exit code")
            if has_exit and (type(item["exit_code"]) is not int or item["exit_code"] == 0):
                raise ValueError("FAIL requires a nonzero exit code")
        for provision in item.get("provisioning", []):
            if not isinstance(provision, dict) or provision.get("id") != "npm-ci" or provision.get("status") not in ("PASS", "NOT_VERIFIED"):
                raise ValueError("Invalid provisioning result")
            started_provision = "argv" in provision
            if started_provision:
                required = {"duration_ms", "timed_out", "lock_sha256", "cache", "network", "stdout_sha256", "stderr_sha256"}
                if not required.issubset(provision) or any(
                    not digest_pattern.fullmatch(str(provision[name]))
                    for name in ("lock_sha256", "stdout_sha256", "stderr_sha256")
                ):
                    raise ValueError("Started provisioning evidence is incomplete")
                successful = provision.get("exit_code") == 0 and provision.get("timed_out") is False
                if (provision["status"] == "PASS") != successful:
                    raise ValueError("Provisioning status differs from execution")
            elif provision["status"] != "NOT_VERIFIED" or not provision.get("reason"):
                raise ValueError("Unstarted provisioning requires an explicit reason")
        comparison = item.get("generated_comparison")
        if comparison is not None:
            if not isinstance(comparison, dict) or not isinstance(comparison.get("files"), list) or not comparison["files"]:
                raise ValueError("Generated comparison is incomplete")
            matches = []
            for artifact in comparison["files"]:
                if not isinstance(artifact, dict):
                    raise ValueError("Generated artifact evidence is invalid")
                for prefix in ("expected", "actual"):
                    present = artifact.get(prefix + "_present")
                    has_digest = prefix + "_sha256" in artifact
                    if type(present) is not bool or present != has_digest:
                        raise ValueError("Generated artifact presence/digest mismatch")
                    if has_digest and not digest_pattern.fullmatch(str(artifact[prefix + "_sha256"])):
                        raise ValueError("Generated artifact digest is invalid")
                matches.append(
                    artifact.get("expected_present") is True
                    and artifact.get("actual_present") is True
                    and artifact.get("expected_sha256") == artifact.get("actual_sha256")
                    and artifact.get("matched") is True
                )
            if comparison.get("matched") != all(matches):
                raise ValueError("Generated comparison aggregate is inconsistent")
            if status == "PASS" and comparison["matched"] is not True:
                raise ValueError("PASS requires matching generated artifacts")
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


def run(
    repository: Path,
    candidate: str,
    base: str,
    catalog_path: Path,
    output: Path,
    event: str = "manual",
    network: str = "disabled",
) -> tuple[dict[str, object], int]:
    """Verify one exact candidate in isolation and write a bound machine result.

    Args:
        repository: Git repository containing candidate and base objects.
        candidate: Exact full candidate commit SHA.
        base: Exact full base commit SHA required to be candidate ancestry.
        catalog_path: Reviewed versioned check catalog outside candidate execution.
        output: Explicit result JSON path; evidence is written beside it.
        event: Explicit trigger kind used by typed applicability predicates.
        network: Explicit provisioning policy; disabled is the safe default.

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
    if catalog["schema_version"] == 2:
        if event not in catalog["run_context"]["events"]:
            raise ValueError("Event is not permitted by catalog")
        if network == "allowed" and catalog["run_context"]["network"] != "allowed":
            raise ValueError("Catalog forbids network provisioning")
    context = build_run_context(
        repository, candidate, candidate_tree, base, base_tree, event, network,
        catalog.get("run_context", {}).get("network_ttl_seconds", 86400),
    )
    started = int(time.time())
    output, staging, descriptor, identity, evidence = reserve_runtime_output(repository, output)
    final_created = False
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
                result = execute_check(item, check_export, evidence, completed, context)
                checks.append(result)
                completed[str(item["id"])] = result
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
            "run_context": context,
            "digests": digests,
            "environment": environment_report(repository),
            "started_at": started,
            "finished_at": int(time.time()),
            "outcome": outcome,
            "checks": checks,
        }
        validate_result_semantics(document, catalog["policy"]["allow_mandatory_not_applicable"])
        payload = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode("utf-8")
        finalize_runtime_output(staging, output, descriptor, payload)
        descriptor = -1
        final_created = True
        staging.unlink()
        return document, code
    except BaseException:
        cleanup_runtime_output(output, staging, descriptor, identity, evidence, final_created)
        raise


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
    parser.add_argument("--event", choices=("pull_request", "push", "manual", "schedule"), default="manual")
    parser.add_argument("--network", choices=("disabled", "allowed"), default="disabled")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    try:
        document, code = run(
            args.repository, args.candidate, args.base, args.catalog, args.output,
            event=args.event, network=args.network,
        )
        print(json.dumps({"outcome": document["outcome"], "result": str(args.output)}))
        return code
    except (ValueError, OSError, json.JSONDecodeError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"Runner error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
