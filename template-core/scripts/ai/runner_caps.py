"""Fail-closed run context, applicability, provisioning and process capabilities."""

import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import tempfile
import time

CAPTURE_LIMIT = 65537


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


def create_windows_kill_job(process: subprocess.Popen[bytes]) -> int | None:
    """Assign a Windows child to a kill-on-close Job Object.

    Args:
        process: Newly started subprocess whose descendants must be owned.

    Returns:
        Integer Job Object handle on Windows, otherwise ``None``.

    Raises:
        OSError: If Windows cannot create, configure, or assign the Job Object.

    Side effects:
        Creates one process-scoped Windows kernel Job Object and assigns the child.
        It does not access files, databases, configuration, or the network.
    """
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class BASIC_LIMIT(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class EXTENDED_LIMIT(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
    limits = EXTENDED_LIMIT()
    limits.BasicLimitInformation.LimitFlags = 0x00002000
    if not kernel32.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        kernel32.CloseHandle(handle)
        raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
    if not kernel32.AssignProcessToJobObject(handle, wintypes.HANDLE(process._handle)):
        kernel32.CloseHandle(handle)
        raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
    return int(handle)


def terminate_process_tree(process: subprocess.Popen[bytes], windows_job: int | None = None) -> None:
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
    if os.name == "nt":
        if windows_job is None:
            raise OSError("Windows subprocess lacks a kill-on-close Job Object")
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.TerminateJobObject(windows_job, 1)
        kernel32.CloseHandle(windows_job)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        time.sleep(0.1)
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
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(
            argv, cwd=cwd, env=env, stdout=stdout_file, stderr=stderr_file,
            shell=False, start_new_session=os.name != "nt", creationflags=creationflags,
        )
        try:
            windows_job = create_windows_kill_job(process)
        except OSError:
            process.kill()
            process.wait(timeout=5)
            raise
        timed_out = False
        exit_code: int | None
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = None
        finally:
            terminate_process_tree(process, windows_job)
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read(CAPTURE_LIMIT)
        stderr = stderr_file.read(CAPTURE_LIMIT)
        return exit_code, stdout, stderr, timed_out, round((time.monotonic() - started) * 1000)


def provision_node(
    root: Path,
    policy: dict[str, object],
    env: dict[str, str],
    timeout_seconds: int,
    cache_root: Path | None = None,
) -> dict[str, object]:
    """Install exact npm dependencies privately inside one candidate export.

    Args:
        root: Per-check pristine export that owns ``node_modules`` and cache.
        policy: Validated npm-ci policy containing network mode and TTL.
        env: Explicit environment copied for structural npm configuration.
        timeout_seconds: Bounded install deadline.
        cache_root: Optional secured runtime directory for a lock/toolchain-keyed
            npm content cache. Every check still receives a private copied cache.

    Returns:
        Provisioning evidence with status, argv, lock digest, cache semantics,
        network policy, duration and exit/timeout information.

    Raises:
        OSError: If npm cannot start or private directories cannot be created.

    Side effects:
        Runs ``npm ci --ignore-scripts`` only inside the disposable export. The npm
        cache and ``node_modules`` are private to this check. A validated,
        unexpired content-addressed npm cache may seed the private cache; the
        installed dependency tree is never reused. Network is disabled via npm
        offline mode unless explicitly allowed.
    """
    lock = root / "package-lock.json"
    if not lock.is_file() or lock.is_symlink():
        return {"id": "npm-ci", "status": "NOT_VERIFIED", "reason": "package-lock.json missing"}
    npm = shutil.which("npm")
    node = shutil.which("node")
    if npm is None or node is None:
        return {"id": "npm-ci", "status": "NOT_VERIFIED", "reason": "node_or_npm_missing"}
    version_probe = subprocess.run(
        [npm, "--version"], capture_output=True, timeout=20, check=False, shell=False
    )
    if version_probe.returncode != 0:
        return {"id": "npm-ci", "status": "NOT_VERIFIED", "reason": "npm version unavailable"}
    npm_version = version_probe.stdout.decode("utf-8", errors="replace").strip()
    node_probe = subprocess.run(
        [node, "--version"], capture_output=True, timeout=20, check=False, shell=False
    )
    if node_probe.returncode != 0:
        return {"id": "npm-ci", "status": "NOT_VERIFIED", "reason": "node version unavailable"}
    node_version = node_probe.stdout.decode("utf-8", errors="replace").strip()
    lock_digest = sha256_bytes(lock.read_bytes())
    registry = str(policy.get("registry", "https://registry.npmjs.org/"))
    system = platform.system().lower()
    architecture = platform.machine().lower()
    empty_config = root / ".ai-empty-npmrc"
    empty_config.write_bytes(b"")
    config_digest = sha256_bytes(b"")
    cache_identity = {
        "lock_sha256": lock_digest,
        "node_version": node_version,
        "npm_version": npm_version,
        "registry": registry,
        "os": system,
        "arch": architecture,
        "config_sha256": config_digest,
    }
    cache_key = sha256_bytes(json.dumps(cache_identity, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    cache = root / ".ai-node-cache"
    cache.mkdir()
    reused = False
    replaceable_stale = False
    stable_cache = cache_root / cache_key if cache_root is not None else None
    if stable_cache is not None:
        if cache_root.is_symlink() or cache_root.exists() and not cache_root.is_dir():
            return {"id": "npm-ci", "status": "NOT_VERIFIED", "reason": "unsafe npm cache root"}
        cache_root.mkdir(exist_ok=True)
        if stable_cache.is_dir() and not stable_cache.is_symlink():
            try:
                metadata = json.loads((stable_cache / "metadata.json").read_text(encoding="utf-8"))
                created_at = metadata.get("created_at")
                age_seconds = int(time.time()) - created_at if type(created_at) is int else -1
                fresh = (
                    metadata == {"schema_version": 2, "key_sha256": cache_key, **cache_identity, "created_at": created_at}
                    and type(created_at) is int
                    and 0 <= age_seconds <= int(policy.get("ttl_seconds", 86400))
                )
                content = stable_cache / "content"
                safe_entries = content.is_dir() and not content.is_symlink() and all(
                    not path.is_symlink() for path in content.rglob("*")
                )
                if fresh and safe_entries:
                    shutil.copytree(content, cache, dirs_exist_ok=True)
                    reused = True
                elif safe_entries:
                    replaceable_stale = True
            except (OSError, ValueError, KeyError, TypeError):
                reused = False
    child_env = dict(env)
    child_env["npm_config_cache"] = str(cache)
    child_env["npm_config_ignore_scripts"] = "true"
    child_env["npm_config_audit"] = "false"
    child_env["npm_config_fund"] = "false"
    child_env["npm_config_userconfig"] = str(empty_config)
    child_env["npm_config_globalconfig"] = str(empty_config)
    child_env["npm_config_registry"] = registry
    network = str(policy.get("network", "disabled"))
    argv = [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"]
    if network == "disabled":
        argv.append("--offline")
    exit_code, stdout, stderr, timed_out, duration = run_argv(argv, root, child_env, timeout_seconds)
    status = "PASS" if exit_code == 0 else "NOT_VERIFIED"
    result: dict[str, object] = {
        "id": "npm-ci", "status": status, "argv": ["npm", *argv[1:]],
        "duration_ms": duration, "timed_out": timed_out,
        "lock_sha256": lock_digest,
        "cache": {
            "scope": "per-check", "reused": reused, "content_only": True,
            "key_sha256": cache_key, "identity": cache_identity,
        },
        "network": {"mode": network, "ttl_seconds": int(policy.get("ttl_seconds", 86400))},
        "stdout_sha256": sha256_bytes(stdout), "stderr_sha256": sha256_bytes(stderr),
    }
    if exit_code is not None:
        result["exit_code"] = exit_code
    if status == "NOT_VERIFIED":
        result["reason"] = "offline_cache_miss_or_install_error" if network == "disabled" else "network_install_error"
    if reused:
        result["cache"].update({"created_at": created_at, "age_seconds": age_seconds})
    stale_quarantine: Path | None = None
    if status == "PASS" and stable_cache is not None and replaceable_stale and network == "allowed":
        stale_quarantine = cache_root / f"{cache_key}.stale-{os.getpid()}-{time.time_ns()}"
        try:
            stable_cache.rename(stale_quarantine)
        except (FileNotFoundError, FileExistsError):
            stale_quarantine = None
    if status == "PASS" and stable_cache is not None and not stable_cache.exists():
        staging = Path(tempfile.mkdtemp(prefix=cache_key + ".pending-", dir=cache_root))
        try:
            shutil.rmtree(cache / "_logs", ignore_errors=True)
            shutil.copytree(cache, staging / "content")
            created_at = int(time.time())
            metadata = {"schema_version": 2, "key_sha256": cache_key, **cache_identity, "created_at": created_at}
            (staging / "metadata.json").write_text(
                json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
            )
            try:
                staging.rename(stable_cache)
            except FileExistsError:
                pass
            result["cache"].update({"created_at": created_at, "age_seconds": 0})
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    if stale_quarantine is not None and stale_quarantine.exists():
        shutil.rmtree(stale_quarantine)
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
