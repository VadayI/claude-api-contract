"""Fail-closed run context, applicability, provisioning and process capabilities."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time


def sha256_bytes(content: bytes) -> str:
    """Return the lowercase SHA-256 digest of exact public input bytes.

    Args:
        content: Bytes whose identity must be bound to a machine result.

    Returns:
        A sixty-four-character lowercase hexadecimal digest.

    Side effects:
        None; this function performs no I/O, subprocess, database, or network work.
    """
    return hashlib.sha256(content).hexdigest()


def build_run_context(
    repository: Path,
    candidate: str,
    candidate_tree: str,
    base: str,
    base_tree: str,
    event: str,
    network: str,
    network_ttl_seconds: int = 86400,
) -> dict[str, object]:
    """Build a canonical context from exact Git objects and an explicit event.

    Args:
        repository: Local Git repository containing both exact commits.
        candidate: Full validated candidate commit SHA.
        candidate_tree: Full tree SHA belonging to ``candidate``.
        base: Full validated ancestor commit SHA used for diff gates.
        base_tree: Full tree SHA belonging to ``base``.
        event: Explicit ``pull_request``, ``push``, ``manual`` or ``schedule``.
        network: Explicit ``disabled`` or ``allowed`` provisioning policy.
        network_ttl_seconds: Positive freshness lifetime for network-bound proof.

    Returns:
        Versioned context with sorted changed files and a canonical context digest.

    Raises:
        ValueError: For an unsupported event/network policy, unsafe changed path,
            undecodable Git output, or failed exact diff operation.
        subprocess errors: If local Git cannot execute within the timeout.

    Side effects:
        Executes a read-only local Git diff with literal argv. It does not fetch,
        mutate refs/index/worktree, access a database, or contact the network.
    """
    if event not in {"pull_request", "push", "manual", "schedule"}:
        raise ValueError("Unsupported run event")
    if network not in {"disabled", "allowed"}:
        raise ValueError("Unsupported network policy")
    if type(network_ttl_seconds) is not int or network_ttl_seconds < 1:
        raise ValueError("Invalid network evidence TTL")
    process = subprocess.run(
        ["git", "-C", str(repository), "diff", "--name-only", "-z", base, candidate, "--"],
        capture_output=True,
        check=True,
        timeout=30,
        shell=False,
    )
    changed = []
    for raw in process.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            name = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise ValueError("Changed path is not UTF-8") from None
        path = Path(name)
        if path.is_absolute() or "\\" in name or any(part in ("", ".", "..") for part in path.parts):
            raise ValueError("Unsafe changed path")
        changed.append(path.as_posix())
    changed = sorted(set(changed))
    context: dict[str, object] = {
        "schema_version": 1,
        "event": event,
        "candidate": {"commit": candidate, "tree": candidate_tree},
        "base": {"commit": base, "tree": base_tree},
        "changed_files": changed,
        "changed_files_sha256": sha256_bytes(("\0".join(changed) + "\0").encode("utf-8")),
        "network": {"mode": network, "ttl_seconds": network_ttl_seconds},
    }
    canonical = json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")
    context["context_sha256"] = sha256_bytes(canonical)
    return context


def evaluate_applicability(
    specification: dict[str, object], root: Path, context: dict[str, object]
) -> tuple[str, dict[str, object]]:
    """Evaluate one typed predicate without treating unknown input as a skip.

    Args:
        specification: Validated predicate with an explicit ``kind``.
        root: Pristine exact-candidate export used for path predicates.
        context: Versioned run context used for event and changed-file predicates.

    Returns:
        ``APPLICABLE``, ``NOT_APPLICABLE`` or ``NOT_VERIFIED`` plus evaluated
        public evidence suitable for the machine result.

    Raises:
        ValueError: If a supposedly validated predicate has unsupported fields.

    Side effects:
        Reads only candidate path metadata. It performs no writes, subprocesses,
        database work, environment lookup, or network access.
    """
    kind = specification.get("kind")
    evidence: dict[str, object] = {"kind": kind}
    if kind == "always":
        return "APPLICABLE", evidence
    if kind == "path_exists":
        value = specification.get("path")
        if not isinstance(value, str):
            raise ValueError("Path predicate requires a path")
        path = root.joinpath(*Path(value).parts)
        exists = path.exists() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve())
        evidence.update({"path": value, "matched": exists})
        if exists:
            return "APPLICABLE", evidence
        return str(specification.get("missing_status", "NOT_VERIFIED")), evidence
    if kind == "contract_spec":
        spec = root / "spec"
        if spec.is_dir() and not spec.is_symlink():
            return "APPLICABLE", {**evidence, "matched": True, "repository_kind": "derived"}
        package = root / "package.json"
        try:
            identity = json.loads(package.read_text(encoding="utf-8")).get("name")
        except (OSError, ValueError, AttributeError):
            return "NOT_VERIFIED", {**evidence, "matched": False, "reason": "package_identity_unavailable"}
        if identity == specification.get("scaffold_package"):
            return "NOT_APPLICABLE", {**evidence, "matched": False, "repository_kind": "upstream_scaffold"}
        return "NOT_VERIFIED", {**evidence, "matched": False, "reason": "derived_spec_missing"}
    if kind == "changed_any":
        prefixes = specification.get("prefixes")
        changed = context.get("changed_files")
        if not isinstance(prefixes, list) or not isinstance(changed, list):
            return "NOT_VERIFIED", {**evidence, "reason": "predicate_input_missing"}
        matches = [name for name in changed if any(name == prefix or name.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)]
        evidence.update({"prefixes": prefixes, "matches": matches})
        return ("APPLICABLE" if matches else "NOT_APPLICABLE"), evidence
    if kind == "event_in":
        events = specification.get("events")
        event = context.get("event")
        if not isinstance(events, list) or not isinstance(event, str):
            return "NOT_VERIFIED", {**evidence, "reason": "predicate_input_missing"}
        evidence.update({"events": events, "event": event})
        return ("APPLICABLE" if event in events else "NOT_APPLICABLE"), evidence
    raise ValueError("Unsupported applicability predicate")


def terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    """Terminate and reap a spawned process tree on Windows and POSIX.

    Args:
        process: Child created by :func:`run_argv` in its own process group.

    Returns:
        None after a bounded best-effort graceful stop followed by forced cleanup.

    Side effects:
        Sends termination signals only to the owned child process group. On
        Windows it invokes ``taskkill /T`` with literal argv. It performs no file,
        database, configuration, or network changes.
    """
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=10,
            check=False,
            shell=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_argv(
    argv: list[str], cwd: Path, env: dict[str, str], timeout_seconds: int
) -> tuple[int | None, bytes, bytes, bool, int]:
    """Execute literal argv in a new process group with bounded tree cleanup.

    Args:
        argv: Nonempty argument vector; no shell parsing is performed.
        cwd: Contained working directory for the child.
        env: Explicit allowlisted child environment.
        timeout_seconds: Positive wall-clock deadline.

    Returns:
        Exit code or ``None``, captured stdout/stderr, timeout flag, and duration.

    Raises:
        OSError: If the executable cannot start.

    Side effects:
        Starts one local process tree, captures output in memory, and forcibly
        cleans descendants on timeout. Command-specific filesystem/network effects
        remain governed by its isolated export and explicit environment policy.
    """
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    started = time.monotonic()
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        start_new_session=os.name != "nt",
        creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return process.returncode, stdout, stderr, False, round((time.monotonic() - started) * 1000)
    except subprocess.TimeoutExpired as error:
        terminate_process_tree(process)
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        return None, stdout, stderr, True, round((time.monotonic() - started) * 1000)


def provision_node(
    root: Path,
    policy: dict[str, object],
    env: dict[str, str],
    timeout_seconds: int,
) -> dict[str, object]:
    """Install exact npm dependencies privately inside one candidate export.

    Args:
        root: Per-check pristine export that owns ``node_modules`` and cache.
        policy: Validated npm-ci policy containing network mode and TTL.
        env: Explicit environment copied for structural npm configuration.
        timeout_seconds: Bounded install deadline.

    Returns:
        Provisioning evidence with status, argv, lock digest, cache semantics,
        network policy, duration and exit/timeout information.

    Raises:
        OSError: If npm cannot start or private directories cannot be created.

    Side effects:
        Runs ``npm ci --ignore-scripts`` only inside the disposable export. The npm
        cache and ``node_modules`` are private to this check and are never reused;
        network is disabled via npm offline mode unless explicitly allowed.
    """
    lock = root / "package-lock.json"
    if not lock.is_file() or lock.is_symlink():
        return {"id": "npm-ci", "status": "NOT_VERIFIED", "reason": "package-lock.json missing"}
    npm = shutil.which("npm")
    if npm is None:
        return {"id": "npm-ci", "status": "NOT_VERIFIED", "reason": "npm missing"}
    cache = root / ".ai-node-cache"
    cache.mkdir()
    child_env = dict(env)
    child_env["npm_config_cache"] = str(cache)
    child_env["npm_config_ignore_scripts"] = "true"
    child_env["npm_config_audit"] = "false"
    child_env["npm_config_fund"] = "false"
    network = str(policy.get("network", "disabled"))
    argv = [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"]
    if network == "disabled":
        argv.append("--offline")
    exit_code, stdout, stderr, timed_out, duration = run_argv(argv, root, child_env, timeout_seconds)
    status = "PASS" if exit_code == 0 else "NOT_VERIFIED"
    result: dict[str, object] = {
        "id": "npm-ci", "status": status, "argv": ["npm", *argv[1:]],
        "duration_ms": duration, "timed_out": timed_out,
        "lock_sha256": sha256_bytes(lock.read_bytes()),
        "cache": {"scope": "per-check", "reused": False, "content_only": True},
        "network": {"mode": network, "ttl_seconds": int(policy.get("ttl_seconds", 86400))},
        "stdout_sha256": sha256_bytes(stdout), "stderr_sha256": sha256_bytes(stderr),
    }
    if exit_code is not None:
        result["exit_code"] = exit_code
    return result


def compare_generated(root: Path, before: dict[str, bytes | None], names: list[str]) -> dict[str, object]:
    """Compare generated files against exact committed candidate bytes.

    Args:
        root: Per-check disposable export after generator execution.
        before: Candidate bytes captured before provisioning/check execution.
        names: Reviewed candidate-relative generated artifact paths.

    Returns:
        Sorted equality records and an aggregate ``matched`` flag.

    Raises:
        ValueError: If an output is linked, nonregular, escaping, or unreviewed.
        OSError: If contained output metadata or bytes cannot be read.

    Side effects:
        Reads generated bytes only; no writes, subprocesses, database, or network.
    """
    records = []
    for name in sorted(names):
        path = root.joinpath(*Path(name).parts)
        if path.is_symlink() or path.exists() and (not path.is_file() or not path.resolve().is_relative_to(root.resolve())):
            raise ValueError("Unsafe generated artifact")
        after = path.read_bytes() if path.is_file() else None
        expected = before.get(name)
        record: dict[str, object] = {
            "path": name,
            "expected_present": expected is not None,
            "actual_present": after is not None,
            "matched": expected is not None and after == expected,
        }
        if expected is not None:
            record["expected_sha256"] = sha256_bytes(expected)
        if after is not None:
            record["actual_sha256"] = sha256_bytes(after)
        records.append(record)
    return {"matched": bool(records) and all(item["matched"] for item in records), "files": records}
