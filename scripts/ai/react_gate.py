"""Run React workflow gates that need reviewed multi-step orchestration."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import time
from typing import NoReturn
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


NOT_VERIFIED = 75
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
VERSION = re.compile(r"^[A-Za-z0-9._-]+$")
NETWORK_ERRORS = (
    "eai_again", "enetwork", "enetunreach", "econnrefused", "econnreset",
    "etimedout", "network request", "fetch failed", "socket hang up", "unable to get local issuer",
)
PLAYWRIGHT_MISSING = (
    "executable doesn't exist", "please run the following command to download new browsers",
    "playwright install", "browser executable", "failed to launch browser",
)


class NotVerified(RuntimeError):
    """Represent an unavailable declared prerequisite without claiming gate failure."""


def executable(name: str) -> str:
    """Resolve one declared executable without invoking a command shell.

    Args:
        name: Reviewed tool name such as ``npm`` or ``npx``.

    Returns:
        Absolute executable/shim path, including ``.cmd`` resolution on Windows.

    Raises:
        NotVerified: If the declared prerequisite is unavailable on the runner PATH.

    Side effects:
        Reads PATH/PATHEXT metadata only; no subprocess, file write, DB, or network.
    """
    resolved = shutil.which(name)
    if resolved is None:
        raise NotVerified(f"declared executable is unavailable: {name}")
    return resolved


def canonical_digest(value: object) -> str:
    """Return the SHA-256 of canonical compact JSON.

    Args:
        value: JSON-compatible public metadata.

    Returns:
        Lowercase SHA-256 digest.

    Side effects:
        None; no filesystem, subprocess, database, environment, or network access.
    """
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_run_context(path: Path) -> dict[str, object]:
    """Load and validate the runner-supplied exact candidate/base context.

    Args:
        path: Absolute path supplied through the ``{run_context}`` argv token.

    Returns:
        Validated run-context document with a sorted exact changed-file manifest.

    Raises:
        ValueError: If fields, Git identities, ordering, or the context digest differ.
        OSError/JSONDecodeError: If the public context cannot be read.

    Side effects:
        Reads one runner-owned JSON file. It performs no writes, Git, DB, or network.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "event", "candidate", "base", "changed_files",
        "changed_files_sha256", "network", "context_sha256",
    }
    if not isinstance(document, dict) or set(document) != required or document["schema_version"] != 1:
        raise ValueError("Invalid exact run context fields")
    if document["event"] not in {"pull_request", "push", "manual", "schedule"}:
        raise ValueError("Invalid exact run context event")
    for name in ("candidate", "base"):
        identity = document[name]
        if not isinstance(identity, dict) or set(identity) != {"commit", "tree"}:
            raise ValueError(f"Invalid {name} identity")
        if not SHA40.fullmatch(str(identity["commit"])) or not SHA40.fullmatch(str(identity["tree"])):
            raise ValueError(f"Invalid {name} Git object")
    changed = document["changed_files"]
    if not isinstance(changed, list) or changed != sorted(set(changed)) or any(
        not isinstance(name, str) or not name or "\\" in name or name.startswith("/") or ".." in Path(name).parts
        for name in changed
    ):
        raise ValueError("Invalid changed-file manifest")
    changed_digest = hashlib.sha256(("\n".join(changed) + ("\n" if changed else "")).encode("utf-8")).hexdigest()
    if document["changed_files_sha256"] != changed_digest:
        raise ValueError("Changed-file digest mismatch")
    canonical = dict(document)
    recorded = canonical.pop("context_sha256")
    if not SHA256.fullmatch(str(recorded)) or canonical_digest(canonical) != recorded:
        raise ValueError("Run-context digest mismatch")
    return document


def require_base_root(path: Path) -> Path:
    """Validate the immutable base export supplied by the exact runner.

    Args:
        path: Absolute ``{base_export}`` directory.

    Returns:
        Resolved base-export directory.

    Raises:
        ValueError: If the value is relative, linked, missing, or not a directory.

    Side effects:
        Reads path metadata only; no writes, subprocess, DB, or network.
    """
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ValueError("Exact base export is unavailable")
    return path.resolve()


def run_process(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None,
                timeout: int = 600) -> subprocess.CompletedProcess[str]:
    """Run one literal bounded child process without a shell.

    Args:
        argv: Executable plus literal arguments.
        cwd: Candidate-export working directory.
        env: Optional explicit public environment.
        timeout: Maximum runtime in seconds.

    Returns:
        Captured completed process, including nonzero results.

    Raises:
        OSError: If the executable cannot start.
        TimeoutExpired: If the declared bound is exceeded.

    Side effects:
        Executes one local process which may create gate-declared candidate outputs.
        It never invokes a shell or mutates Git/database state directly.
    """
    return subprocess.run(
        argv, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False, shell=False,
    )


def emit_process(result: subprocess.CompletedProcess[str]) -> None:
    """Forward bounded child output to runner-captured stdout and stderr.

    Args:
        result: Completed child process.

    Returns:
        None.

    Side effects:
        Writes already captured public output to this process streams only.
    """
    if result.stdout:
        sys.stdout.buffer.write(result.stdout.encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    if result.stderr:
        sys.stderr.buffer.write(result.stderr.encode("utf-8", errors="replace"))
        sys.stderr.buffer.flush()


def audit(root: Path) -> int:
    """Run npm advisory audit and distinguish vulnerabilities from service outages.

    Args:
        root: Exact candidate export with provisioned dependencies and lockfile.

    Returns:
        0 when clean, the npm nonzero code for a real advisory/policy failure, or
        75 when the external advisory service/transport is unavailable.

    Side effects:
        Runs ``npm audit`` which may contact the npm advisory service. No files,
        Git refs, database records, or configuration are modified.
    """
    result = run_process([executable("npm"), "audit", "--audit-level=high", "--json"], cwd=root, timeout=300)
    emit_process(result)
    if result.returncode == 0:
        return 0
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    vulnerabilities = payload.get("metadata", {}).get("vulnerabilities", {}) if isinstance(payload, dict) else {}
    if isinstance(vulnerabilities, dict) and any(
        isinstance(vulnerabilities.get(level), int) and vulnerabilities[level] > 0
        for level in ("high", "critical")
    ):
        return result.returncode or 1
    diagnostic = f"{result.stdout}\n{result.stderr}".lower()
    error_code = str(payload.get("error", {}).get("code", "")).lower() if isinstance(payload, dict) else ""
    if error_code or any(token in diagnostic for token in NETWORK_ERRORS):
        raise NotVerified("npm advisory service or transport is unavailable")
    return result.returncode or 1


def contract_sync(root: Path) -> int:
    """Compare vendored OpenAPI bytes and lock digest with the pinned remote tag.

    Args:
        root: Exact candidate export.

    Returns:
        0 for exact three-way agreement or 1 for reviewed contract drift.

    Raises:
        NotVerified: If the declared external GitHub object cannot be retrieved.
        ValueError/OSError/JSON errors: If versioned local inputs are malformed.

    Side effects:
        Performs one bounded HTTPS GET to a public raw GitHub URL. It reads local
        public contract files and performs no writes, Git, DB, or secret access.
    """
    lock = json.loads((root / "contract.lock.json").read_text(encoding="utf-8"))
    if not isinstance(lock, dict) or set(lock) != {"repo", "version", "path", "sha256"}:
        raise ValueError("Invalid contract.lock.json fields")
    if not REPOSITORY.fullmatch(str(lock["repo"])) or not VERSION.fullmatch(str(lock["version"])):
        raise ValueError("Unsafe contract repository or version")
    remote_path = str(lock["path"])
    if not remote_path or "\\" in remote_path or remote_path.startswith("/") or ".." in Path(remote_path).parts:
        raise ValueError("Unsafe contract path")
    if not SHA256.fullmatch(str(lock["sha256"])):
        raise ValueError("Invalid contract lock digest")
    vendor = (root / "src/lib/api/openapi.yml").read_bytes()
    url = "https://raw.githubusercontent.com/{}/{}/{}".format(
        lock["repo"], quote(lock["version"], safe="._-"), quote(remote_path, safe="/._-"),
    )
    try:
        with urlopen(Request(url, headers={"User-Agent": "react-exact-gate/1"}), timeout=30) as response:
            remote = response.read(20 * 1024 * 1024 + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise NotVerified(f"pinned contract network input unavailable: {type(error).__name__}") from error
    if len(remote) > 20 * 1024 * 1024:
        raise ValueError("Remote contract exceeds the reviewed size limit")
    remote_sha = hashlib.sha256(remote).hexdigest()
    vendor_sha = hashlib.sha256(vendor).hexdigest()
    print(f"remote_sha256={remote_sha}\nvendor_sha256={vendor_sha}\nlock_sha256={lock['sha256']}")
    return 0 if remote_sha == vendor_sha == lock["sha256"] else 1


def policy(kind: str, root: Path, context_path: Path, base_root: Path) -> int:
    """Evaluate base-sensitive React policy against the exact changed-file manifest.

    Args:
        kind: One of ``plan``, ``routes`` or ``guides``.
        root: Exact candidate export.
        context_path: Runner-owned canonical exact run-context JSON.
        base_root: Runner-owned pristine exact base export; required to prevent any
            fallback to refs, environment variables, HEAD~1, fetch, or host state.

    Returns:
        0 when the applicable policy is satisfied and 1 for a policy violation.

    Raises:
        ValueError/OSError/JSON errors: If exact inputs or candidate JSON are invalid.

    Side effects:
        Reads candidate/base/context files only. No subprocess, Git, DB, network,
        environment lookup, or filesystem write occurs.
    """
    context = load_run_context(context_path)
    require_base_root(base_root)
    changed = set(context["changed_files"])
    if context["event"] == "push":
        print(f"react.{kind}: push event is intentionally not enforced")
        return 0
    if kind == "plan":
        source_count = sum(name.startswith(("src/", "e2e/")) for name in changed)
        if source_count <= 2 or any(name.startswith("docs/plans/") and name.endswith(".md") for name in changed):
            return 0
        print(f"react.plan-sync: {source_count} src/e2e files changed without docs/plans/*.md", file=sys.stderr)
        return 1
    if kind == "routes":
        registry = root / ".claude/memory/routes.json"
        if registry.is_file():
            json.loads(registry.read_text(encoding="utf-8"))
        if "src/app/router.tsx" not in changed:
            return 0
        satisfied = ".claude/memory/routes.json" in changed and any(
            name.startswith("docs/verify/") and name.endswith(".md") for name in changed
        )
        if not satisfied:
            print("react.routes-sync: router change lacks routes registry or verification handoff", file=sys.stderr)
        return 0 if satisfied else 1
    if kind == "guides":
        relevant = "src/app/router.tsx" in changed or any(name.startswith("src/lib/auth/") for name in changed)
        satisfied = any(name.startswith("docs/guides/") and name.endswith(".md") for name in changed)
        if relevant and not satisfied:
            print("react.guides-sync: route/auth change lacks docs/guides/*.md", file=sys.stderr)
            return 1
        return 0
    raise ValueError(f"Unknown policy gate: {kind}")


def bundle_budget(root: Path) -> int:
    """Enforce checked-in gzip budgets against one production build.

    Args:
        root: Exact candidate export containing ``dist`` and the budget JSON.

    Returns:
        0 when the initial JavaScript, initial transfer, and every lazy chunk
        satisfy their positive numeric limits; otherwise 1.

    Raises:
        ValueError/OSError/JSON errors: If required inputs are absent or invalid.

    Side effects:
        Reads candidate build artifacts and prints measurements only. Compression
        is in memory with a fixed timestamp; no shell, Git, DB, network, or write.
    """
    budget_path = root / ".performance-budget.json"
    index_path = root / "dist/index.html"
    assets_root = root / "dist/assets"
    if not budget_path.is_file() or not index_path.is_file() or not assets_root.is_dir():
        raise ValueError("bundle budget, dist/index.html, and dist/assets must all exist")
    document = json.loads(budget_path.read_text(encoding="utf-8"))
    budgets = document.get("bundle")
    names = ("initialJsGzipKb", "totalInitialTransferGzipKb", "lazyChunkGzipKb")
    if not isinstance(budgets, dict) or any(
        isinstance(budgets.get(name), bool)
        or not isinstance(budgets.get(name), (int, float))
        or budgets[name] <= 0
        for name in names
    ):
        raise ValueError("bundle budgets must be positive numeric values")
    html = index_path.read_text(encoding="utf-8")
    referenced = {
        Path(value.split("?", 1)[0].split("#", 1)[0]).name
        for value in re.findall(r'(?:src|href)="([^"?#]+\.(?:js|css)(?:[?#][^"]*)?)"', html)
    }
    assets = sorted(path for path in assets_root.rglob("*") if path.is_file() and path.suffix in {".js", ".css"})
    if not assets:
        raise ValueError("dist/assets contains no JavaScript or CSS artifacts")

    def gzip_kb(path: Path) -> float:
        """Return deterministic in-memory gzip size for one emitted asset.

        Args:
            path: JavaScript or CSS artifact under the exact candidate export.

        Returns:
            Compressed byte length divided by 1024.

        Side effects:
            Reads the supplied file only; no writes, subprocess, DB, or network.
        """
        return len(gzip.compress(path.read_bytes(), mtime=0)) / 1024

    initial_js = sum(gzip_kb(path) for path in assets if path.suffix == ".js" and path.name in referenced)
    initial_css = sum(gzip_kb(path) for path in assets if path.suffix == ".css" and path.name in referenced)
    lazy = [(path, gzip_kb(path)) for path in assets if path.suffix == ".js" and path.name not in referenced]
    total = initial_js + initial_css
    print(
        "[react.bundle-size] measured "
        f"initial_js={initial_js:.1f}KB initial_transfer={total:.1f}KB lazy_chunks={len(lazy)}"
    )
    failures: list[str] = []
    if initial_js > budgets["initialJsGzipKb"]:
        failures.append(f"initial JS {initial_js:.1f}KB > {budgets['initialJsGzipKb']}KB")
    if total > budgets["totalInitialTransferGzipKb"]:
        failures.append(f"initial transfer {total:.1f}KB > {budgets['totalInitialTransferGzipKb']}KB")
    failures.extend(
        f"lazy chunk {path.name} {size:.1f}KB > {budgets['lazyChunkGzipKb']}KB"
        for path, size in lazy
        if size > budgets["lazyChunkGzipKb"]
    )
    for failure in failures:
        print(f"OVER: {failure}", file=sys.stderr)
    return 1 if failures else 0


def bundle(root: Path) -> int:
    """Build the exact candidate then apply its checked-in gzip bundle budget.

    Args:
        root: Exact candidate export with npm dependencies provisioned.
    Returns:
        0 only when both build and bundle-budget validation succeed; otherwise
        the first nonzero result.

    Side effects:
        Runs local build commands and writes only declared ``dist``/TypeScript
        transient outputs inside the disposable candidate export. No network/DB/Git.
    """
    built = run_process([executable("npm"), "run", "build"], cwd=root, timeout=600)
    emit_process(built)
    if built.returncode:
        return built.returncode
    return bundle_budget(root)


def stop_process_tree(process: subprocess.Popen[str]) -> None:
    """Stop the supervised local Vite process tree on Windows or POSIX.

    Args:
        process: Running process-group leader created by :func:`e2e`.

    Returns:
        None.

    Side effects:
        Terminates only the supplied disposable process group/tree and waits up to
        ten seconds. It does not inspect or signal unrelated host processes.
    """
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
            text=True, timeout=10, check=False, shell=False,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def wait_for_server(process: subprocess.Popen[str], url: str, timeout: int = 120) -> None:
    """Wait for the supervised loopback Vite server or fail deterministically.

    Args:
        process: Supervised Vite process.
        url: Fixed loopback health URL.
        timeout: Maximum startup wait in seconds.

    Raises:
        RuntimeError: If the server exits early or does not become healthy.

    Side effects:
        Performs bounded loopback-only HTTP GETs; no external network, DB, or writes.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Vite server exited before health check: {process.returncode}")
        try:
            with urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return
        except (URLError, TimeoutError, OSError):
            time.sleep(0.25)
    raise RuntimeError("Vite loopback health check timed out")


def e2e(root: Path) -> int:
    """Supervise Vite, Chromium Playwright tests, a11y scans, and HTML reporting.

    Args:
        root: Exact candidate export with npm dependencies provisioned.

    Returns:
        0 when Playwright succeeds, its nonzero result for test/a11y failure, or 75
        when the declared Chromium prerequisite is unavailable.

    Raises:
        RuntimeError/OSError: If the local server cannot start or be supervised.

    Side effects:
        Starts one loopback Vite server, runs Playwright (including checked-in axe
        assertions), writes declared reports inside the disposable export, and always
        terminates the supervised process tree. No external network or DB is used.
    """
    env = dict(os.environ)
    env.update({
        "PLAYWRIGHT_BASE_URL": "http://127.0.0.1:5173",
        "PLAYWRIGHT_EXTERNAL_SERVER": "true",
        "VITE_MSW_ENABLED": "true",
        "VITE_API_BASE_URL": "http://127.0.0.1:5173",
    })
    options: dict[str, object] = {
        "cwd": root, "env": env, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
        "text": True, "encoding": "utf-8", "errors": "replace", "shell": False,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    server = subprocess.Popen(
        [executable("npm"), "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
        **options,
    )
    try:
        wait_for_server(server, "http://127.0.0.1:5173/")
        result = run_process([executable("npx"), "playwright", "test", "--workers=1"], cwd=root, env=env, timeout=900)
        emit_process(result)
        diagnostic = f"{result.stdout}\n{result.stderr}".lower()
        if result.returncode and any(token in diagnostic for token in PLAYWRIGHT_MISSING):
            raise NotVerified("Chromium/Playwright browser prerequisite is unavailable")
        return result.returncode
    finally:
        stop_process_tree(server)


def parser() -> argparse.ArgumentParser:
    """Build the strict command-line interface for versioned React gate modes.

    Returns:
        Configured argument parser.

    Side effects:
        None; parsing and gate execution happen in :func:`main`.
    """
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("audit")
    sub.add_parser("contract-sync")
    policy_parser = sub.add_parser("policy")
    policy_parser.add_argument("kind", choices=("plan", "routes", "guides"))
    policy_parser.add_argument("--run-context", type=Path, required=True)
    policy_parser.add_argument("--base-root", type=Path, required=True)
    sub.add_parser("bundle")
    sub.add_parser("e2e")
    return result


def main() -> int:
    """Dispatch one reviewed React gate and preserve PASS/FAIL/NV semantics.

    Returns:
        0 for PASS, ordinary nonzero for FAIL, or exactly 75 for runner-classified
        ``NOT_VERIFIED`` when a declared external prerequisite is unavailable.

    Side effects:
        Depends on the selected gate; all effects are documented by its function and
        constrained to declared candidate outputs, loopback processes, or public GET.
    """
    args = parser().parse_args()
    root = Path.cwd().resolve()
    try:
        if args.command == "audit":
            return audit(root)
        if args.command == "contract-sync":
            return contract_sync(root)
        if args.command == "policy":
            return policy(args.kind, root, args.run_context, args.base_root)
        if args.command == "bundle":
            return bundle(root)
        if args.command == "e2e":
            return e2e(root)
        raise ValueError(f"Unsupported command: {args.command}")
    except NotVerified as error:
        print(f"NOT_VERIFIED: {error}", file=sys.stderr)
        return NOT_VERIFIED


if __name__ == "__main__":
    raise SystemExit(main())
