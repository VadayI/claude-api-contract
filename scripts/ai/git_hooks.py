"""Index-bound commit guards and per-ref exact-candidate push verification."""

import argparse
from pathlib import Path
import re
import subprocess
import sys
import uuid

HEX_OID = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
TODO = re.compile(r"\b(?:TODO|FIXME)\b")


def git(root: Path, *args: str) -> bytes:
    """Read Git output from a reviewed repository with separate argv items.

    Args: root is a Git repository; args are Git subcommand arguments.
    Returns: Raw stdout bytes, preserving NUL-delimited path records.
    Raises: subprocess.CalledProcessError for a failed Git command.
    Side effects: Git subprocess without ref/index mutation. Commands such as
        ls-remote may read the network; no database or credential writes.
    """
    return subprocess.check_output(["git", "-C", str(root), *args])


def staged_paths(root: Path) -> list[tuple[str, str]]:
    """Return changed index paths with status, including rename destinations.

    Args: root is the local repository containing the proposed index.
    Returns: Status/path pairs from Git's NUL-delimited staged diff.
    Raises: ValueError for malformed records; Git errors propagate.
    Side effects: Reads index metadata only; no writes, DB, or network.
    Business rule: Deletes are represented but never read from working tree.
    """
    records = git(root, "diff", "--cached", "--name-status", "-z", "--diff-filter=ACMRD").split(b"\0")
    if records[-1:] == [b""]:
        records.pop()
    changes = []
    index = 0
    while index < len(records):
        status = records[index].decode("ascii")
        index += 1
        count = 2 if status.startswith("R") else 1
        if not status or status[0] not in "ACMRD" or index + count > len(records):
            raise ValueError("Malformed staged Git path record")
        names = [record.decode("utf-8", errors="surrogateescape") for record in records[index:index + count]]
        index += count
        changes.append((status[0], names[-1]))
    return changes


def pre_commit(root: Path) -> int:
    """Check proposed staged contract edits without reading working-tree bytes.

    Args: root is the repository whose index will be committed.
    Returns: 0 for approved index or 1 for a policy violation.
    Raises: Git/decoding errors propagate to CLI failure 2.
    Side effects: Read-only staged Git diff queries; no formatting, writes,
        database, network, or application execution.
    Business rule: Generated OpenAPI requires a staged spec change; newly added
        bare TODO/FIXME in staged contract artifacts is rejected.
    """
    changes = staged_paths(root)
    names = {name for _, name in changes}
    if "openapi.yml" in names and not any(name.startswith("spec/") for name in names):
        print("[pre-commit] staged openapi.yml requires a staged spec/ change", file=sys.stderr)
        return 1
    for status, name in changes:
        if status == "D" or not (name.startswith(("spec/", "examples/")) or name == "openapi.yml"):
            continue
        diff = git(root, "diff", "--cached", "--unified=0", "--", name).decode("utf-8", errors="replace")
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++") and TODO.search(line[1:]) and "STUB:" not in line:
                print(f"[pre-commit] bare TODO/FIXME added in staged {name}", file=sys.stderr)
                return 1
    return 0


def ref_updates(stream: str) -> list[tuple[str, str, str, str]]:
    """Parse every Git pre-push stdin update with zero-OID validation.

    Args: stream is the exact UTF-8 stdin supplied by Git pre-push.
    Returns: Local-ref/OID and remote-ref/OID tuples in input order.
    Raises: ValueError for malformed records or unsupported object IDs.
    Side effects: None; no filesystem, database, network, or Git access.
    Business rule: Empty stdin means no updates; no branch is inferred from HEAD.
    """
    updates = []
    for line in stream.splitlines():
        parts = line.split()
        if len(parts) != 4 or not all(HEX_OID.fullmatch(oid) for oid in (parts[1], parts[3])):
            raise ValueError("Malformed pre-push ref update")
        updates.append(tuple(parts))
    return updates


def assert_candidate_tooling(root: Path, commit: str) -> None:
    """Require runner and catalog bytes to match the proposed commit.

    Args: root is local repository; commit is the exact candidate OID.
    Returns: None when all local execution inputs equal committed blobs.
    Raises: ValueError for dirty/stale tooling; Git errors propagate.
    Side effects: Reads three working files and exact Git blobs; no writes,
        database, network, or Git ref/index mutation.
    Business rule: A dirty local catalog or runner cannot claim a result for
        different committed verification logic.
    """
    for name in ("scripts/ai/git_hooks.py", "scripts/ai/runner.py", "templates/ai/checks/contract.json"):
        committed = git(root, "show", f"{commit}:{name}")
        if (root / name).read_text(encoding="utf-8").encode("utf-8") != committed:
            raise ValueError(f"Working verification input differs from candidate: {name}")


def creation_base(root: Path, remote: str, candidate: str) -> str:
    """Bind a new branch baseline to the observed remote main fork point.

    Args: root is local repository; remote is a configured simple remote name;
        candidate is the proposed new branch commit.
    Returns: Exact merge-base commit shared with verified remote main.
    Raises: ValueError for absent/stale remote main or no common ancestor;
        Git subprocess errors propagate.
    Side effects: Read-only ls-remote network request and local Git reads;
        no fetch, ref/index write, database, release, or deployment.
    Business rule: A first-parent shortcut can omit older branch commits and
        is forbidden. Unknown first-push baselines fail closed.
    """
    if not re.fullmatch(r"[A-Za-z0-9._-]+", remote):
        raise ValueError("Pre-push remote must be a configured name")
    response = git(root, "ls-remote", "--exit-code", remote, "refs/heads/main").decode("ascii").strip().split()
    if len(response) != 2 or response[1] != "refs/heads/main" or not HEX_OID.fullmatch(response[0]):
        raise ValueError("Cannot verify remote main for new branch")
    observed = response[0]
    tracking = git(root, "rev-parse", "--verify", f"refs/remotes/{remote}/main^{{commit}}").decode("ascii").strip()
    if tracking != observed:
        raise ValueError("Remote main tracking ref is stale; refresh and retry")
    base = git(root, "merge-base", observed, candidate).decode("ascii").strip()
    if not HEX_OID.fullmatch(base):
        raise ValueError("No exact fork point for new branch")
    return base


def pre_push(root: Path, updates: list[tuple[str, str, str, str]], remote: str) -> int:
    """Verify each nondeleted branch candidate with the shared exact runner.

    Args: root is the local repository; updates are parsed Git stdin records;
        remote is the configured Git remote name provided by pre-push.
    Returns: 0 only if every branch candidate passes; otherwise 1 or 2.
    Raises: ValueError for tags, missing creation base or mismatched local ref;
        Git/process errors propagate to CLI exit two.
    Side effects: Runner creates ignored local evidence and may access the
        declared external network; no Git ref/index, DB, release, or push writes.
    Business rule: Zero local OID is deletion; new branches use a verified
        remote-main merge-base so all branch commits are included. Tags use a
        separate explicit release procedure. Hooks remain locally bypassable.
    """
    for local_ref, local_oid, remote_ref, remote_oid in updates:
        if local_oid == "0" * len(local_oid):
            continue
        if remote_ref.startswith("refs/tags/") or local_ref.startswith("refs/tags/"):
            raise ValueError("Tag push requires the separate release procedure")
        if not remote_ref.startswith("refs/heads/"):
            raise ValueError(f"Unsupported push destination: {remote_ref}")
        observed = git(root, "rev-parse", "--verify", local_ref + "^{commit}").decode("ascii").strip()
        if observed != local_oid:
            raise ValueError(f"Local ref moved during push: {local_ref}")
        assert_candidate_tooling(root, local_oid)
        if remote_oid == "0" * len(remote_oid):
            base = creation_base(root, remote, local_oid)
        else:
            base = remote_oid
        output = root / ".ai-runtime/results" / f"prepush-{local_oid[:12]}-{uuid.uuid4().hex}.json"
        command = [sys.executable, str(root / "scripts/ai/runner.py"), "--repository", str(root),
                   "--candidate", local_oid, "--base", base, "--event", "push", "--network", "allowed",
                   "--catalog", str(root / "templates/ai/checks/contract.json"), "--output", str(output)]
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode:
            print(f"[pre-push] exact checks failed for {remote_ref}: {output}", file=sys.stderr)
            return result.returncode
    return 0


def main() -> int:
    """Dispatch Husky stage or push hook with explicit failure reporting.

    Args: CLI command is pre-commit or pre-push; pre-push reads Git stdin.
    Returns: 0 pass, 1 policy/check failure, 2 malformed state/tool error.
    Raises: None for supported errors; diagnostics omit file contents/secrets.
    Side effects: pre-commit reads index; pre-push runs exact runner per ref and
        writes ignored evidence. No formatting, Git mutation, DB, or merge.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pre-commit", "pre-push"))
    parser.add_argument("--remote")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        if args.command == "pre-commit":
            return pre_commit(root)
        if not args.remote:
            raise ValueError("pre-push requires Git's remote name")
        return pre_push(root, ref_updates(sys.stdin.read()), args.remote)
    except (ValueError, OSError, UnicodeError, subprocess.CalledProcessError) as error:
        print(f"[git-hook] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
