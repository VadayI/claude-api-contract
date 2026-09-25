"""Agent-neutral Git lifecycle G0-G9: inspect, commit, verify, share, merge on command, cleanup."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time

# Stany raportowane użytkownikowi; zawsze wyliczane z faktycznego stanu Git/PR,
# nigdy z lokalnego znacznika (dziennik jest tylko informacją o przerwanych krokach).
BLOCKED = "BLOCKED"
DETACHED = "DETACHED"
NOT_VERIFIED = "NOT_VERIFIED"
NO_CHANGES = "NO_CHANGES"
LOCAL_CHANGES = "LOCAL_CHANGES"
BASE_CHANGES = "LOCAL_CHANGES_ON_BASE"
BASE_COMMITS = "LOCAL_COMMITS_ON_BASE"
COMMITTED_UNPUSHED = "COMMITTED_UNPUSHED"
DIVERGED = "DIVERGED"
BEHIND_REMOTE = "BEHIND_REMOTE"
PR_MISSING = "BRANCH_SYNCED / PR_MISSING"
PR_UNKNOWN = "BRANCH_SYNCED / PR_NOT_VERIFIED"
MERGE_PENDING = "BRANCH_SYNCED / MERGE_PENDING"
PR_HEAD_MISMATCH = "PR_HEAD_MISMATCH"
PR_CLOSED = "PR_CLOSED"
CLEANUP_PENDING = "MERGED / CLEANUP_PENDING"
MERGED_EXTRA = "MERGED / EXTRA_COMMITS"
CLEANED = "MERGED / CLEANED"
COMMITTED = "COMMITTED"
COMMIT_UNEXPECTED = "COMMITTED_WITH_UNEXPECTED_CHANGES"
MERGE_NOT_CONFIRMED = "MERGE_NOT_CONFIRMED"

IN_PROGRESS = {"MERGE_HEAD": "merge", "CHERRY_PICK_HEAD": "cherry-pick", "REVERT_HEAD": "revert",
               "rebase-merge": "rebase", "rebase-apply": "rebase/am", "BISECT_LOG": "bisect"}
LOCK_NAMES = ("index.lock", "HEAD.lock", "config.lock", "packed-refs.lock", "shallow.lock")
OID = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
BRANCH_NAME = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
GITHUB_URL = re.compile(r"^(?:https://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)"
                        r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
MERGE_METHODS = ("merge", "squash", "rebase")
ACCEPTED_MERGE_STATES = ("CLEAN", "HAS_HOOKS", "UNSTABLE")
EXIT_OK, EXIT_REFUSED, EXIT_ERROR, EXIT_INCOMPLETE = 0, 1, 2, 3
READ_TIMEOUT, NETWORK_TIMEOUT = 120, 300
MAX_HASHED_FOREIGN = 2000
MAX_HASHED_BYTES = 64 * 1024 * 1024


class LifecycleError(Exception):
    """A refused step: a precondition failed and this step changed nothing."""


class IncompleteError(LifecycleError):
    """A step that may have changed state but could not confirm its result."""

    def __init__(self, state: str, message: str, details: dict | None = None):
        """Carry the resulting state and evidence for the report."""
        super().__init__(message)
        self.state, self.details = state, details or {}


def run(argv: list[str], cwd: Path | None, env: dict, timeout: int | None,
        input_text: str | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess; on timeout terminate it first so Git can remove its locks.

    Args:
        argv: Program and arguments (never a shell string).
        cwd: Working directory.
        env: Complete child environment.
        timeout: Seconds, or ``None`` for no limit (commits and pushes run hooks).
        input_text: Optional standard input.
    Returns:
        The completed process with text output.
    Raises:
        FileNotFoundError when the program is missing; LifecycleError on timeout.
    Side effects:
        Starts the child; on timeout sends terminate, then kill after a grace period.
    """
    proc = subprocess.Popen(argv, cwd=cwd, env=env, text=True, encoding="utf-8", errors="replace",
                            stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = proc.communicate(input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        # Najpierw łagodne zakończenie: Git sprząta wtedy własne pliki .lock.
        proc.terminate()
        try:
            proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        raise LifecycleError(f"{Path(argv[0]).name} {' '.join(argv[1:4])} timed out after {timeout}s; "
                             "verify the actual state before retrying")
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def git(root: Path, *args: str, check: bool = True, read_only: bool = False,
        timeout: int | None = READ_TIMEOUT, input_text: str | None = None) -> subprocess.CompletedProcess:
    """Run Git with separate argv items and no interactive prompts.

    Args:
        root: Working tree passed to ``git -C``.
        *args: Git subcommand and arguments.
        check: Raise :class:`LifecycleError` on a nonzero exit.
        read_only: Set ``GIT_OPTIONAL_LOCKS=0`` so queries never refresh the index.
        timeout: Seconds, or ``None`` for commands that run hooks.
        input_text: Optional standard input.
    Returns:
        The completed process with text output.
    Raises:
        LifecycleError for a missing Git, timeout, or a failed checked command.
    Side effects:
        Whatever the Git subcommand does; hooks run normally (no ``--no-verify``).
    """
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    if read_only:
        env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        result = run(["git", "-c", "core.quotepath=false", "-C", str(root), *args], None, env,
                     timeout, input_text)
    except FileNotFoundError as error:
        raise LifecycleError("Git is not installed or not in PATH") from error
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise LifecycleError(f"git {' '.join(args[:3])} failed ({result.returncode}): "
                             f"{detail[-1] if detail else 'no output'}")
    return result


def git_out(root: Path, *args: str) -> str | None:
    """Return stripped stdout of a successful read-only Git query, else ``None``."""
    result = git(root, *args, check=False, read_only=True)
    return result.stdout.strip() if result.returncode == 0 else None


def rev(root: Path, ref: str) -> str | None:
    """Resolve a ref to a commit OID, or ``None`` when it does not exist."""
    return git_out(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")


def is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    """Tell whether ``ancestor`` is reachable from ``descendant`` (both must exist)."""
    return git(root, "merge-base", "--is-ancestor", ancestor, descendant,
               check=False, read_only=True).returncode == 0


def merges_cleanly_into(root: Path, target: str, commit: str) -> bool:
    """True when merging ``commit`` into ``target`` changes nothing (tree stays equal)."""
    merged = git(root, "merge-tree", "--write-tree", target, commit, check=False, read_only=True)
    return merged.returncode == 0 and merged.stdout.split()[:1] == [git_out(root, "rev-parse", f"{target}^{{tree}}")]


def included_in(root: Path, commit: str, base: str, merge_commit: str | None = None) -> bool:
    """Prove that the changes of ``commit`` (a PR head) are contained in ``base``.

    Args:
        root: Repository containing the commits.
        commit: Task head (the merged PR head).
        base: Current base tip.
        merge_commit: PR merge/squash commit reported by GitHub, if known.
    Returns:
        True for ancestry (merge commit, fast-forward); for squash/rebase merges
        when the PR merge commit is in ``base`` and already contains the head's
        changes, or when merging the head into ``base`` changes nothing.
    Side effects:
        ``git merge-tree --write-tree`` writes only loose objects; no refs, index
        or working tree changes and no network.
    """
    if is_ancestor(root, commit, base):
        return True
    if merge_commit and rev(root, merge_commit) and is_ancestor(root, merge_commit, base) \
            and merges_cleanly_into(root, merge_commit, commit):
        return True
    return merges_cleanly_into(root, base, commit)


def discover(start: Path) -> dict:
    """Locate the working tree, its Git directory and the shared common directory.

    Args:
        start: Any path inside the repository.
    Returns:
        ``root``, ``gitdir``, ``common_dir`` and ``linked`` (a linked worktree).
    Raises:
        LifecycleError when ``start`` is not inside a Git working tree.
    Side effects:
        Read-only Git queries.
    """
    top = git_out(start, "rev-parse", "--show-toplevel")
    if not top:
        raise LifecycleError(f"Not a Git working tree: {start}")
    root = Path(top)
    gitdir = Path(git_out(root, "rev-parse", "--absolute-git-dir") or "")
    common = Path(git_out(root, "rev-parse", "--path-format=absolute", "--git-common-dir") or "")
    return {"root": root, "gitdir": gitdir, "common_dir": common,
            "linked": gitdir.resolve() != common.resolve()}


def parse_status(root: Path) -> dict:
    """Parse ``git status --porcelain=v2 -z`` into staged/unstaged/untracked sets.

    Args:
        root: Working tree.
    Returns:
        ``entries`` mapping path -> ``{"x", "y", "orig", "mode_head", "mode_index",
        "oid_head", "oid_index"}``, plus sorted lists ``staged``, ``unstaged``,
        ``untracked``, ``partially_staged`` and ``conflicted``.
    Raises:
        LifecycleError when status cannot be read.
    Side effects:
        Read-only (``GIT_OPTIONAL_LOCKS=0``); ignored files are not listed.
    """
    raw = git(root, "status", "--porcelain=v2", "-z", "--untracked-files=all", read_only=True).stdout
    tokens = raw.split("\0")
    entries, conflicted, untracked = {}, [], []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        kind = token[0]
        if kind in "12":
            fields = token.split(" ", 8 if kind == "1" else 9)
            path = fields[-1]
            entries[path] = {"x": fields[1][0], "y": fields[1][1], "orig": None,
                             "mode_head": fields[3], "mode_index": fields[4],
                             "oid_head": fields[6], "oid_index": fields[7]}
            if kind == "2":
                entries[path]["orig"] = tokens[index]
                index += 1
        elif kind == "u":
            conflicted.append(token.split(" ", 10)[10])
        elif kind == "?":
            untracked.append(token[2:])
    staged = sorted(path for path, item in entries.items() if item["x"] != ".")
    unstaged = sorted(path for path, item in entries.items() if item["y"] != ".")
    return {"entries": entries, "staged": staged, "unstaged": unstaged,
            "untracked": sorted(untracked), "conflicted": sorted(conflicted),
            "partially_staged": sorted(set(staged) & set(unstaged))}


def worktrees(root: Path) -> list[dict]:
    """List worktrees (NUL-separated porcelain) with path, HEAD, branch and flags."""
    items, current = [], None
    output = git(root, "worktree", "list", "--porcelain", "-z", read_only=True).stdout
    for token in output.split("\0"):
        if not token:
            current = None
            continue
        if token.startswith("worktree "):
            current = {"path": token[9:], "head": None, "branch": None, "locked": False, "prunable": False}
            items.append(current)
        elif current is None:
            continue
        elif token.startswith("HEAD "):
            current["head"] = token[5:]
        elif token.startswith("branch "):
            current["branch"] = token[7:].removeprefix("refs/heads/")
        elif token.startswith("locked"):
            current["locked"] = True
        elif token.startswith("prunable"):
            current["prunable"] = True
    return items


def same_path(first: str | Path, second: str | Path) -> bool:
    """Compare two filesystem paths after resolution and case normalization."""
    return os.path.normcase(os.path.realpath(first)) == os.path.normcase(os.path.realpath(second))


def blockers(repo: dict) -> list[str]:
    """Report in-progress operations and lock files; locks are never removed."""
    found = []
    for name, label in IN_PROGRESS.items():
        if (repo["gitdir"] / name).exists():
            found.append(f"{label} in progress ({name})")
    for directory in {repo["gitdir"], repo["common_dir"]}:
        for name in LOCK_NAMES:
            if (directory / name).exists():
                found.append(f"lock file present: {directory / name} (not removed automatically)")
    return sorted(set(found))


def pick_remote(root: Path, requested: str | None) -> str | None:
    """Return the requested remote, ``origin``, or the only configured remote."""
    remotes = (git_out(root, "remote") or "").split()
    if requested:
        if requested not in remotes:
            raise LifecycleError(f"Remote '{requested}' is not configured")
        return requested
    if "origin" in remotes:
        return "origin"
    return remotes[0] if len(remotes) == 1 else None


def resolve_base(root: Path, remote: str | None, requested: str | None) -> tuple[str, str]:
    """Resolve the base branch and how it was found.

    Returns:
        ``(name, source)`` where source is ``explicit``, ``remote-head``
        (``refs/remotes/<remote>/HEAD``), ``remote`` (``ls-remote --symref``) or
        ``guess`` (main/master without remote evidence).
    Side effects:
        At most one ``ls-remote --symref`` network read when the local
        remote-HEAD ref is missing; nothing is written.
    """
    if requested:
        if not BRANCH_NAME.fullmatch(requested) or requested.startswith("-"):
            raise LifecycleError(f"Invalid base branch name: {requested}")
        return requested, "explicit"
    if remote:
        default = git_out(root, "symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD")
        if default and default.startswith(f"{remote}/"):
            return default[len(remote) + 1:], "remote-head"
        answer = git(root, "ls-remote", "--symref", remote, "HEAD", check=False, read_only=True,
                     timeout=NETWORK_TIMEOUT)
        match = re.search(r"^ref: refs/heads/(\S+)\tHEAD$", answer.stdout or "", re.MULTILINE)
        if answer.returncode == 0 and match:
            return match.group(1), "remote"
    for name in ("main", "master"):
        if rev(root, f"refs/heads/{name}") or (remote and rev(root, f"refs/remotes/{remote}/{name}")):
            return name, "guess"
    return "main", "guess"


def remote_tip(root: Path, remote: str, branch: str) -> tuple[str | None, str | None]:
    """Read the actual branch tip on the remote with ``ls-remote``.

    Returns:
        ``(oid or None, error or None)``; an error means the remote was not reached
        and the tip is unknown (never treated as "absent").
    Side effects:
        Network read using the user's normal Git authentication.
    """
    result = git(root, "ls-remote", "--heads", remote, f"refs/heads/{branch}", check=False,
                 read_only=True, timeout=NETWORK_TIMEOUT)
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        return None, detail[-1] if detail else f"ls-remote exit {result.returncode}"
    for line in result.stdout.splitlines():
        oid, _, ref = line.partition("\t")
        if ref == f"refs/heads/{branch}":
            return oid, None
    return None, None


def project_settings(root: Path, ref: str | None = None) -> dict:
    """Read ``docs/project-state/project.json`` from ``ref`` (reviewed base) or the worktree."""
    try:
        if ref:
            text = git_out(root, "show", f"{ref}:docs/project-state/project.json")
            return json.loads(text) if text else {}
        path = root / "docs/project-state/project.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        return {}


def upstream_gone(root: Path, branch: str | None) -> bool:
    """True when the branch has a configured upstream whose tracking ref disappeared."""
    if not branch:
        return False
    merge_ref = git_out(root, "config", "--get", f"branch.{branch}.merge")
    remote = git_out(root, "config", "--get", f"branch.{branch}.remote")
    if not merge_ref or not remote or remote == ".":
        return False
    return rev(root, f"refs/remotes/{remote}/{merge_ref.removeprefix('refs/heads/')}") is None


class GitHubProvider:
    """Pull-request operations through the ``gh`` CLI; unavailable means NOT_VERIFIED.

    ``AI_GH`` may hold a JSON argv list (for example a fixture) replacing ``gh``.
    Pull requests from forks (``isCrossRepository``) are never treated as ours.
    """

    PR_FIELDS = ("number,state,isDraft,headRefName,headRefOid,baseRefName,url,mergeCommit,title,"
                 "isCrossRepository,author")

    def __init__(self, root: Path, remote: str | None):
        """Bind to the GitHub repository behind ``remote``; record why it is unavailable."""
        self.root, self.repo, self.reason = root, None, None
        configured = os.environ.get("AI_GH")
        self.command = json.loads(configured) if configured else (["gh"] if shutil.which("gh") else None)
        # Surowy URL z konfiguracji (bez rozwinięcia insteadOf): identyfikuje repozytorium GitHub.
        url = git_out(root, "config", "--get", f"remote.{remote}.url") if remote else None
        match = GITHUB_URL.match(url or "")
        if not remote:
            self.reason = "no Git remote configured"
        elif not match:
            self.reason = f"remote '{remote}' is not a GitHub repository"
        elif not self.command:
            self.reason = "gh CLI is not installed"
        else:
            self.repo = f"{match.group(1)}/{match.group(2)}"

    @property
    def available(self) -> bool:
        """True when a GitHub repository and a gh command are known."""
        return self.repo is not None

    def run(self, *args: str, allow: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess:
        """Run gh without prompts; raise LifecycleError on unexpected exits or timeouts."""
        env = {**os.environ, "GH_PROMPT_DISABLED": "1", "GIT_TERMINAL_PROMPT": "0", "NO_COLOR": "1"}
        try:
            result = run([*self.command, *args], self.root, env, NETWORK_TIMEOUT)
        except OSError as error:
            raise LifecycleError(f"gh {args[0] if args else ''} failed: {error}") from error
        if result.returncode not in allow:
            detail = (result.stderr or result.stdout).strip().splitlines()
            raise LifecycleError(f"gh {' '.join(args[:2])} failed ({result.returncode}): "
                                 f"{detail[-1] if detail else 'no output'}")
        return result

    def _list(self, *filters: str, same_repo: bool = True) -> list[dict]:
        """List PRs matching gh filters, newest first; forks excluded unless ``same_repo`` is False."""
        result = self.run("pr", "list", "--repo", self.repo, *filters, "--json", self.PR_FIELDS)
        prs = [pr for pr in json.loads(result.stdout or "[]") if not (same_repo and pr.get("isCrossRepository"))]
        return sorted(prs, key=lambda pr: pr["number"], reverse=True)

    def prs_for_branch(self, branch: str) -> list[dict]:
        """All same-repository PRs (any state) whose head is ``branch``."""
        return self._list("--head", branch, "--state", "all", "--limit", "30")

    def recent_prs(self) -> list[dict]:
        """Recent same-repository PRs of any state (pending-cleanup detection)."""
        return self._list("--state", "all", "--limit", "200")

    def open_prs_with_base(self, branch: str) -> list[dict]:
        """Open PRs that target ``branch`` (stacked on it)."""
        return self._list("--base", branch, "--state", "open", "--limit", "30", same_repo=False)

    def viewer(self) -> str | None:
        """Login of the authenticated gh user, or ``None`` when unknown."""
        try:
            return json.loads(self.run("api", "user").stdout).get("login")
        except (LifecycleError, ValueError, AttributeError):
            return None

    def view(self, number: int) -> dict:
        """Return one PR with merge state and the status rollup of its head."""
        result = self.run("pr", "view", str(number), "--repo", self.repo, "--json",
                          self.PR_FIELDS + ",mergeStateStatus,statusCheckRollup")
        return json.loads(result.stdout)

    def required_checks(self, number: int) -> dict:
        """Summarize required checks: PASS only when all reported buckets are ``pass``.

        Returns:
            ``status`` FAIL (fail/cancel), PENDING, NONE (nothing reported),
            NOT_VERIFIED (skipped, neutral or unknown buckets) or PASS, plus checks.
        Notes:
            gh lists only required checks that reported; a required check that never
            ran is caught by the merge state (BLOCKED), not by this summary.
        """
        result = self.run("pr", "checks", str(number), "--repo", self.repo, "--required",
                          "--json", "name,state,bucket,link", allow=(0, 1, 8))
        text = (result.stdout or "").strip()
        if not text.startswith("["):
            message = (result.stderr or text).strip()
            if "no required checks" in message.lower() or "no checks" in message.lower():
                return {"status": "NONE", "checks": []}
            raise LifecycleError(f"gh pr checks failed: {message or result.returncode}")
        checks = json.loads(text)
        buckets = [check.get("bucket") for check in checks]
        if not checks:
            status = "NONE"
        elif any(bucket in ("fail", "cancel") for bucket in buckets):
            status = "FAIL"
        elif "pending" in buckets:
            status = "PENDING"
        elif all(bucket == "pass" for bucket in buckets):
            status = "PASS"
        else:
            status = NOT_VERIFIED
        return {"status": status, "checks": [{"name": c.get("name"), "bucket": c.get("bucket"),
                                              "link": c.get("link")} for c in checks]}

    def create(self, base: str, branch: str, title: str, body_file: Path, draft: bool) -> None:
        """Create a PR for ``branch`` against ``base``."""
        args = ["pr", "create", "--repo", self.repo, "--base", base, "--head", branch,
                "--title", title, "--body-file", str(body_file)]
        self.run(*args, *(["--draft"] if draft else []))

    def edit(self, number: int, title: str | None, body_file: Path | None) -> None:
        """Update the title and/or body of an existing PR."""
        args = ["pr", "edit", str(number), "--repo", self.repo]
        if title:
            args += ["--title", title]
        if body_file:
            args += ["--body-file", str(body_file)]
        self.run(*args)

    def merge(self, number: int, method: str, head: str) -> None:
        """Merge the PR only if its head is still ``head``; never uses ``--admin``."""
        self.run("pr", "merge", str(number), "--repo", self.repo, f"--{method}", "--match-head-commit", head)


def journal_path(repo: dict) -> Path:
    """Journal in the shared Git directory: never untracked, shared by all worktrees."""
    return repo["common_dir"] / "ai-lifecycle" / "journal.jsonl"


def journal(repo: dict, event: dict) -> str | None:
    """Append one lifecycle event to the journal; failures are informational only.

    Returns:
        ``None`` on success, otherwise the reason.
    Side effects:
        Appends a JSON line below the Git common directory.
    """
    path = journal_path(repo)
    record = {"time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "worktree": str(repo["root"]), **event}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError as error:
        return str(error)
    return None


def unfinished_steps(repo: dict) -> list[str]:
    """List journal steps that started without a recorded end (possibly interrupted)."""
    path = journal_path(repo)
    open_steps: dict[str, dict] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    except OSError:
        return []
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        key = f"{event.get('step')}:{event.get('branch')}"
        if event.get("phase") == "start":
            open_steps[key] = event
        elif event.get("phase") == "end":
            open_steps.pop(key, None)
    return sorted(f"{event.get('step')} on {event.get('branch')} started {event.get('time')}"
                  for event in open_steps.values())


def select_pr(prs: list[dict], head: str | None) -> dict | None:
    """Prefer the open PR, then the PR whose head equals ``head``, then the newest one."""
    for pr in prs:
        if pr["state"] == "OPEN":
            return pr
    for pr in prs:
        if head and pr.get("headRefOid") == head:
            return pr
    return prs[0] if prs else None


def merged_pr_containing(root: Path, prs: list[dict], head: str | None) -> dict | None:
    """A merged PR whose head equals ``head`` or already contains it."""
    for pr in prs:
        if pr["state"] == "MERGED" and head and (pr.get("headRefOid") == head or (
                rev(root, pr.get("headRefOid", "")) and is_ancestor(root, head, pr["headRefOid"]))):
            return pr
    return None


def inspect(start: Path, remote_name: str | None = None, base_name: str | None = None,
            fetch: bool = False, use_provider: bool = True) -> dict:
    """G0/G1: describe the actual repository, remote and PR state without changing work.

    Args:
        start: Path inside the repository.
        remote_name: Remote to use (default ``origin`` or the only remote).
        base_name: Base branch (default: remote default branch, then main/master).
        fetch: Refresh remote-tracking refs first (``git fetch --prune``; no merge/rebase).
        use_provider: Query GitHub PR state through gh when available.
    Returns:
        A JSON-serializable report with ``state``, ``next_step`` and evidence.
    Raises:
        LifecycleError when the path is not a Git working tree.
    Side effects:
        Read-only Git queries; optional fetch updates only remote-tracking refs;
        optional gh reads. Never stashes, resets, cleans or removes locks.
    """
    repo = discover(start)
    root = repo["root"]
    notes: list[str] = []
    remote = pick_remote(root, remote_name)
    if fetch and remote:
        fetched = git(root, "fetch", "--prune", "--no-tags", remote, check=False, timeout=NETWORK_TIMEOUT)
        if fetched.returncode != 0:
            notes.append(f"fetch from {remote} failed; remote refs may be stale")
    base, base_source = resolve_base(root, remote, base_name)
    if base_source == "guess":
        notes.append(f"base branch '{base}' is a guess (no remote default branch); pass --base if wrong")
    branch = git_out(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    head = rev(root, "HEAD")
    status = parse_status(root)
    stash = git_out(root, "stash", "list") or ""
    report = {
        "schema_version": 1,
        "repository": {"root": str(root), "gitdir": str(repo["gitdir"]),
                       "common_dir": str(repo["common_dir"]), "linked_worktree": repo["linked"]},
        "branch": branch, "head": head, "base": base, "base_source": base_source, "remote": remote,
        "working_tree": {key: status[key] for key in
                         ("staged", "unstaged", "untracked", "partially_staged", "conflicted")},
        "stash_count": len([line for line in stash.splitlines() if line.strip()]),
        "worktrees": worktrees(root),
        "blockers": blockers(repo),
        "interrupted_steps": unfinished_steps(repo),
        "upstream_gone": upstream_gone(root, branch),
        "notes": notes,
    }
    base_remote = rev(root, f"refs/remotes/{remote}/{base}") if remote else None
    base_local = rev(root, f"refs/heads/{base}")
    report["base_refs"] = {"local": base_local, "remote_tracking": base_remote}
    report["remote_tracking"] = rev(root, f"refs/remotes/{remote}/{branch}") if remote and branch else None
    provider = GitHubProvider(root, remote) if use_provider else None
    pr, pr_error, recent = None, None, None
    if provider is None:
        pr_error = "PR provider disabled"
    elif not provider.available:
        pr_error = provider.reason
    else:
        try:
            recent = provider.recent_prs()
            if branch and branch != base:
                pr = select_pr(provider.prs_for_branch(branch), head)
        except LifecycleError as error:
            pr_error = str(error)
    report["pr"] = pr
    report["pr_evidence"] = "VERIFIED" if pr_error is None else f"NOT_VERIFIED: {pr_error}"
    owned, others = pending_cleanup(root, remote, base, recent, provider.viewer()) if recent is not None else ([], [])
    report["pending_cleanup"], report["other_merged_remote_branches"] = owned, others
    dirty = bool(status["staged"] or status["unstaged"] or status["untracked"])
    report["state"], report["next_step"] = derive_state(report, dirty, base_remote or base_local, root)
    return report


def pending_cleanup(root: Path, remote: str | None, base: str, recent: list[dict],
                    viewer: str | None) -> tuple[list[dict], list[dict]]:
    """Merged branches whose tip is their PR head, split into owned and informational.

    Returns:
        ``(owned, others)``: owned are local branches or remote-only branches whose
        PR author is the current gh user (cleanup needed); others are remote-only
        branches of other authors, reported for information only. Branches that
        open PRs target (stacked or long-lived) are never listed.
    """
    stacked = {pr["baseRefName"] for pr in recent if pr["state"] == "OPEN"}
    candidates: dict[str, dict] = {}
    output = git_out(root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads",
                     *([f"refs/remotes/{remote}"] if remote else [])) or ""
    for line in output.splitlines():
        ref, _, oid = line.partition(" ")
        if ref.startswith("refs/heads/"):
            name, where = ref.removeprefix("refs/heads/"), "local"
        else:
            name, where = ref.removeprefix(f"refs/remotes/{remote}/"), "remote"
        if name in (base, "HEAD") or name in stacked:
            continue
        candidates.setdefault(name, {})[where] = oid
    owned, others = [], []
    for pr in recent:
        tips = candidates.get(pr.get("headRefName"))
        if pr["state"] != "MERGED" or not tips:
            continue
        pr_head = pr.get("headRefOid", "")
        if all(tip == pr_head or (rev(root, pr_head) and is_ancestor(root, tip, pr_head)) for tip in tips.values()):
            author = (pr.get("author") or {}).get("login")
            item = {"branch": pr["headRefName"], "pr": pr["number"], "where": sorted(tips), "author": author}
            mine = "local" in tips or (viewer is not None and author == viewer)
            (owned if mine else others).append(item)
            candidates.pop(pr["headRefName"])
    return sorted(owned, key=lambda item: item["branch"]), sorted(others, key=lambda item: item["branch"])


def derive_state(report: dict, dirty: bool, base_tip: str | None, root: Path) -> tuple[str, str]:
    """Map the evidence to one lifecycle state and the single next action."""
    branch, head, base, pr = report["branch"], report["head"], report["base"], report["pr"]
    tracking = report["remote_tracking"]
    verified = report["pr_evidence"] == "VERIFIED"
    if report["blockers"] or report["working_tree"]["conflicted"]:
        return BLOCKED, "Resolve the reported in-progress operation, conflict or lock manually; nothing is changed automatically."
    if branch is None:
        return DETACHED, "Check out or create a task branch; lifecycle commands require a named branch."
    if branch == base:
        local, remote = report["base_refs"]["local"], report["base_refs"]["remote_tracking"]
        if dirty:
            return BASE_CHANGES, f"Create a task branch (git switch -c <type>/<name>) before committing; never commit to {base}."
        if local and remote and not is_ancestor(root, local, remote):
            return BASE_COMMITS, (f"Local {base} has commits that are not on the remote; move them to a task "
                                  "branch and open a PR (nothing is reset automatically).")
        if report["pending_cleanup"]:
            names = ", ".join(item["branch"] for item in report["pending_cleanup"])
            return CLEANUP_PENDING, f"Run cleanup for merged branch(es): {names}."
        if not verified:
            return NOT_VERIFIED, f"Merged-branch detection unavailable ({report['pr_evidence']}); retry with gh access."
        return NO_CHANGES, "Nothing to finalize on the base branch."
    unique = head and base_tip and not is_ancestor(root, head, base_tip)
    if pr and pr["state"] == "MERGED":
        if head == pr["headRefOid"] or (head and rev(root, pr["headRefOid"]) and is_ancestor(root, head, pr["headRefOid"])):
            return CLEANUP_PENDING, f"PR #{pr['number']} is merged; run cleanup (G8)."
        return MERGED_EXTRA, (f"PR #{pr['number']} is merged but {branch} has commits after its head; "
                              "keep the branch and open a new PR for them.")
    if pr and pr["state"] == "CLOSED":
        return PR_CLOSED, f"PR #{pr['number']} was closed without merge; decide with the user before reuse."
    if report["upstream_gone"] and not verified:
        return NOT_VERIFIED, (f"The remote branch of {branch} was deleted and PR evidence is unavailable "
                              f"({report['pr_evidence']}); do not push again before checking the PR.")
    suffix = " Uncommitted changes remain; commit task-owned paths or leave foreign ones untouched." if dirty else ""
    if tracking and head and tracking != head:
        if is_ancestor(root, tracking, head):
            return COMMITTED_UNPUSHED, "Verify the candidate (G4), then share (G5): push without force." + suffix
        if is_ancestor(root, head, tracking):
            return BEHIND_REMOTE, "The remote branch has newer commits; review them before continuing." + suffix
        return DIVERGED, "Local and remote branch diverged; reconcile manually (no force push, no blind rebase)."
    if not tracking:
        if not unique:
            return (LOCAL_CHANGES, "Commit task-owned paths (G3).") if dirty else (NO_CHANGES, "No task commits to share.")
        return COMMITTED_UNPUSHED, "Verify the candidate (G4), then share (G5): push and open a PR." + suffix
    if pr and pr["state"] == "OPEN":
        if pr["headRefOid"] == head:
            return MERGE_PENDING, f"PR #{pr['number']} awaits the user's merge command (D01).{suffix}"
        return PR_HEAD_MISMATCH, f"PR #{pr['number']} head differs from local HEAD; refresh and re-verify.{suffix}"
    if not verified:
        return PR_UNKNOWN, f"Branch pushed; PR state could not be verified ({report['pr_evidence']}).{suffix}"
    return PR_MISSING, f"Branch pushed without a PR; run share with --title/--body-file.{suffix}"


def safe_paths(root: Path, paths: list[str]) -> list[str]:
    """Normalize repository-relative task paths and reject escaping or special names."""
    result = []
    for raw in paths:
        candidate = raw.replace("\\", "/").strip()
        pure = PurePosixPath(candidate)
        if (not candidate or pure.is_absolute() or ".." in pure.parts or candidate.startswith("-")
                or ":" in candidate or pure.parts[:1] == (".git",) or "\0" in candidate):
            raise LifecycleError(f"Unsafe task path: {raw!r}")
        normalized = pure.as_posix()
        if (root / normalized).is_symlink():
            raise LifecycleError(f"Symbolic link task path is not committed automatically: {raw!r}")
        result.append(normalized)
    return sorted(set(result))


def file_digest(path: Path) -> str:
    """SHA-256 of raw file bytes (no Git filters); very large files use size and mtime."""
    info = path.stat()
    if info.st_size > MAX_HASHED_BYTES:
        return f"size:{info.st_size}:mtime:{info.st_mtime_ns}"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def foreign_snapshot(root: Path, status: dict, task: set[str]) -> dict:
    """Capture index entries and worktree content digests of every non-task path.

    Returns:
        ``codes`` (XY, index mode and object per path), ``untracked`` and
        ``content`` (digest of existing changed/untracked foreign files, bounded).
    Side effects:
        Reads foreign files; Git objects, filters and the index are not touched.
    """
    codes = {path: (item["x"], item["y"], item["mode_index"], item["oid_index"])
             for path, item in status["entries"].items()
             if path not in task and (item["orig"] or "") not in task}
    untracked = [path for path in status["untracked"] if path not in task]
    hashed = [path for path, item in status["entries"].items()
              if path in codes and item["y"] not in (".", "D")] + untracked
    hashed = [path for path in hashed if (root / path).is_file()][:MAX_HASHED_FOREIGN]
    content = {path: file_digest(root / path) for path in hashed}
    return {"codes": codes, "untracked": sorted(untracked), "content": content}


def pathspec_input(paths: list[str]) -> str:
    """NUL-separated literal pathspecs for ``--pathspec-from-file=- --pathspec-file-nul``.

    Each entry carries ``:(literal)`` so glob characters in file names never match
    other files; nothing is exported to hooks (their own globs keep working).
    """
    return "".join(f":(literal){path}\0" for path in paths)


def commit(start: Path, paths: list[str], message: str, staged_only: bool, base_name: str | None = None) -> dict:
    """G3: commit exactly the task-owned paths while preserving foreign work.

    Args:
        start: Path inside the repository.
        paths: Repository-relative task files or directories (literal, no globs).
        message: Commit message (hooks run normally).
        staged_only: Commit the current index, which must contain only task paths.
        base_name: Base branch override (commits on the base are refused).
    Returns:
        ``outcome`` COMMITTED or NO_CHANGES with the new HEAD and committed paths.
    Raises:
        LifecycleError when a precondition fails (nothing committed, index restored);
        IncompleteError (COMMITTED_WITH_UNEXPECTED_CHANGES) when a hook or Git put
        other paths into the commit or changed foreign state.
    Side effects:
        Default mode: ``git add`` of listed untracked paths, then
        ``git commit --only`` with a NUL pathspec file, so other staged entries stay
        staged. No stash, reset, clean or blanket staging.
    """
    repo = discover(start)
    root = repo["root"]
    if blockers(repo):
        raise LifecycleError("Blocked: " + "; ".join(blockers(repo)))
    branch = git_out(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch is None:
        raise LifecycleError("Detached HEAD: create a task branch first")
    remote = pick_remote(root, None)
    base, source = resolve_base(root, remote, base_name)
    if branch == base:
        raise LifecycleError(f"Refusing to commit on the base branch '{base}'; create a task branch")
    if source == "guess":
        raise LifecycleError(f"Base branch is only a guess ('{base}'); pass --base <name> "
                             "(or record the remote default: git remote set-head <remote> --auto)")
    if not message.strip():
        raise LifecycleError("An explicit commit message is required")
    task = set(safe_paths(root, paths))
    if not task:
        raise LifecycleError("At least one --path is required")
    status = parse_status(root)
    if status["conflicted"]:
        raise LifecycleError("Unmerged paths present: " + ", ".join(status["conflicted"]))
    entries = status["entries"]
    changed = set(entries) | set(status["untracked"])
    renamed_sources = {item["orig"] for item in entries.values() if item["orig"]}
    # Ścieżka zadania może być plikiem albo katalogiem (wtedy obejmuje zmienione pliki pod nim).
    task |= {path for path in changed | renamed_sources
             if any(path == item or path.startswith(item.rstrip("/") + "/") for item in task)}
    for path, item in entries.items():
        if item["orig"] and (path in task) != (item["orig"] in task):
            raise LifecycleError(f"Rename {item['orig']} -> {path}: list both paths")
    listed = sorted(path for path in task if path in changed or path in renamed_sources)
    if not listed:
        return {"outcome": NO_CHANGES, "head": rev(root, "HEAD"), "paths": sorted(task)}
    before = foreign_snapshot(root, status, task)
    old_head = rev(root, "HEAD")
    added: list[str] = []
    with tempfile.TemporaryDirectory(prefix="git-lifecycle-") as temp:
        message_file = Path(temp) / "message.txt"
        message_file.write_text(message, encoding="utf-8", newline="\n")
        if staged_only:
            staged = set(status["staged"]) | {entries[p]["orig"] for p in status["staged"] if entries[p]["orig"]}
            if not status["staged"]:
                raise LifecycleError("Nothing is staged; stage the task hunks explicitly or omit --staged")
            foreign = sorted(staged - task)
            if foreign:
                raise LifecycleError("Staged paths outside the task would be committed: " + ", ".join(foreign))
            expected = staged
            result = git(root, "commit", "--quiet", "--file", str(message_file), check=False, timeout=None)
        else:
            # Tryb domyślny bierze treść z drzewa roboczego; zmiany tylko w indeksie
            # (tryb pliku, rm --cached, wybrane hunki) wymagają jawnego --staged.
            staged_task = sorted(path for path in listed if path in entries and entries[path]["x"] != ".")
            if staged_task:
                raise LifecycleError("Task paths have staged changes: " + ", ".join(staged_task)
                                     + "; stage all task changes exactly and use --staged")
            added = [path for path in listed if path in status["untracked"]]
            if added:
                git(root, "add", "--pathspec-from-file=-", "--pathspec-file-nul", timeout=None,
                    input_text=pathspec_input(added))
            expected = set(listed)
            result = git(root, "commit", "--quiet", "--only", "--file", str(message_file),
                         "--pathspec-from-file=-", "--pathspec-file-nul", check=False, timeout=None,
                         input_text=pathspec_input(listed))
    new_head = rev(root, "HEAD")
    if new_head == old_head:
        if added:
            # Przywróć stan sprzed kroku: nowe pliki zadania znowu nieśledzone.
            git(root, "reset", "--quiet", "--pathspec-from-file=-", "--pathspec-file-nul", check=False,
                timeout=None, input_text=pathspec_input(added))
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise LifecycleError("Commit was not created" + (f": {detail[-1]}" if detail else ""))
    report = {"outcome": COMMITTED, "head": new_head, "previous": old_head, "branch": branch}
    try:
        if old_head:
            listing = git(root, "diff-tree", "--no-commit-id", "-r", "--name-only", "--no-renames", "-z",
                          old_head, new_head, read_only=True).stdout
        else:
            listing = git(root, "ls-tree", "-r", "--name-only", "-z", new_head, read_only=True).stdout
        committed = set(listing.split("\0")) - {""}
        after = foreign_snapshot(root, parse_status(root), task)
    except (LifecycleError, OSError) as error:
        raise IncompleteError(COMMIT_UNEXPECTED, f"Commit created, but its verification failed: {error}",
                              {**report, "outcome": COMMIT_UNEXPECTED}) from error
    unexpected = sorted(committed - expected)
    changed_foreign = sorted({path for path in set(before["codes"]) | set(after["codes"])
                              if before["codes"].get(path) != after["codes"].get(path)}
                             | {path for path in set(before["content"]) | set(after["content"])
                                if before["content"].get(path) != after["content"].get(path)}
                             | (set(before["untracked"]) ^ set(after["untracked"])))
    report["paths"] = sorted(committed & expected)
    if unexpected or changed_foreign:
        raise IncompleteError(COMMIT_UNEXPECTED,
                              "Commit created, but hooks or Git changed paths outside the task; review it",
                              {**report, "outcome": COMMIT_UNEXPECTED, "unexpected_paths": unexpected,
                               "changed_foreign_paths": changed_foreign})
    return {**report, "foreign_preserved": True}


def local_result(root: Path, head: str) -> dict:
    """Find the newest runner result for exactly ``head`` (commit and tree)."""
    tree = git_out(root, "rev-parse", f"{head}^{{tree}}")
    if not tree:
        return {"status": NOT_VERIFIED, "reason": f"candidate {head} is not available locally"}
    best = None
    folder = root / ".ai-runtime/results"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        candidate = data.get("candidate") or {}
        if candidate.get("commit") != head or candidate.get("tree") != tree:
            continue
        if best is None or str(data.get("finished_at", "")) > str(best[1].get("finished_at", "")):
            best = (path, data)
    if best is None:
        return {"status": NOT_VERIFIED, "reason": f"no runner result for candidate {head}"}
    path, data = best
    outcome = data.get("outcome")
    return {"status": outcome if outcome in ("PASS", "FAIL") else NOT_VERIFIED,
            "result": path.relative_to(root).as_posix(),
            "base": (data.get("base") or {}).get("commit"), "finished_at": data.get("finished_at")}


def ci_mode(root: Path, requested: str | None, ref: str | None = None) -> str | None:
    """Return the requested CI mode or ``ci.execution`` from project settings at ``ref``."""
    if requested:
        return requested
    mode = (project_settings(root, ref).get("ci") or {}).get("execution")
    return mode if mode in ("local", "github") else None


def verify(start: Path, mode: str | None, pr_number: int | None = None) -> dict:
    """G4: report the verification status of the exact current candidate.

    Args:
        start: Path inside the repository.
        mode: ``local`` (runner result for HEAD) or ``github`` (required PR checks).
        pr_number: PR to read in GitHub mode (default: the open PR of the branch).
    Returns:
        ``{"candidate", "mode", "status"}`` with PASS, FAIL, PENDING, NONE or NOT_VERIFIED.
    Side effects:
        Reads result files or gh output only; never runs or re-labels checks.
    """
    repo = discover(start)
    root = repo["root"]
    head = rev(root, "HEAD")
    remote = pick_remote(root, None)
    base_ref = f"refs/remotes/{remote}/{resolve_base(root, remote, None)[0]}" if remote else None
    mode = ci_mode(root, mode, base_ref if base_ref and rev(root, base_ref) else None)
    if mode is None:
        raise LifecycleError("CI mode unknown: pass --mode local|github or save ci.execution in project.json")
    if mode == "local":
        return {"candidate": head, "mode": mode, **local_result(root, head)}
    provider = GitHubProvider(root, remote)
    if not provider.available:
        return {"candidate": head, "mode": mode, "status": NOT_VERIFIED, "reason": provider.reason}
    if pr_number is None:
        branch = git_out(root, "symbolic-ref", "--quiet", "--short", "HEAD")
        pr = select_pr(provider.prs_for_branch(branch), head) if branch else None
        if not pr or pr["state"] != "OPEN":
            return {"candidate": head, "mode": mode, "status": NOT_VERIFIED, "reason": "no open PR"}
        pr_number = pr["number"]
    view = provider.view(pr_number)
    if view["headRefOid"] != head:
        return {"candidate": head, "mode": mode, "status": NOT_VERIFIED, "pr": pr_number,
                "reason": f"PR head {view['headRefOid']} is not the local candidate"}
    return {"candidate": head, "mode": mode, "pr": pr_number, **provider.required_checks(pr_number)}


def share(start: Path, title: str | None, body_file: Path | None, draft: bool,
          base_name: str | None = None, remote_name: str | None = None) -> dict:
    """G5: push the task branch without force and create or update its single PR.

    Args:
        start: Path inside the repository.
        title/body_file: Needed to create a PR; optional to update an existing one.
        draft: Create the PR as a draft.
        base_name/remote_name: Overrides for base branch and remote.
    Returns:
        Result with ``state`` (MERGE_PENDING, PR_MISSING, PR_NOT_VERIFIED ...),
        remote head and PR evidence.
    Raises:
        LifecycleError when the branch cannot be shared safely (diverged remote,
        base branch, already merged, rejected push); nothing is forced.
    Side effects:
        ``git push --set-upstream`` (hooks run), gh PR create/edit, journal lines.
    """
    repo = discover(start)
    root = repo["root"]
    if blockers(repo):
        raise LifecycleError("Blocked: " + "; ".join(blockers(repo)))
    remote = pick_remote(root, remote_name)
    if remote is None:
        raise LifecycleError("No Git remote configured; the branch stays local (COMMITTED_UNPUSHED)")
    base, _ = resolve_base(root, remote, base_name)
    branch = git_out(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    head = rev(root, "HEAD")
    if branch is None or head is None:
        raise LifecycleError("A named branch with at least one commit is required")
    if branch == base:
        raise LifecycleError(f"Refusing to share the base branch '{base}' directly; use a task branch and PR")
    provider = GitHubProvider(root, remote)
    prs, provider_error = None, provider.reason
    if provider.available:
        try:
            prs = provider.prs_for_branch(branch)
        except LifecycleError as error:
            provider_error = str(error)
    if prs is not None:
        merged = merged_pr_containing(root, prs, head)
        if merged and not any(pr["state"] == "OPEN" for pr in prs):
            raise LifecycleError(f"{branch} at {head[:12]} is already merged in PR #{merged['number']}; "
                                 "run cleanup instead of pushing it again")
    elif upstream_gone(root, branch):
        raise LifecycleError(f"The remote branch of {branch} was deleted and PR state is unavailable "
                             f"({provider_error}); not pushing it again")
    tip, error = remote_tip(root, remote, branch)
    if error:
        raise LifecycleError(f"Remote not reachable ({error}); nothing was pushed")
    result = {"branch": branch, "head": head, "remote": remote, "base": base, "pushed": False}
    if tip != head:
        if tip and not (rev(root, tip) and is_ancestor(root, tip, head)):
            raise LifecycleError(f"{remote}/{branch} ({tip}) is not an ancestor of HEAD; "
                                 "diverged branch is never force-pushed")
        journal(repo, {"step": "push", "phase": "start", "branch": branch, "head": head})
        pushed = git(root, "push", "--set-upstream", remote, f"refs/heads/{branch}:refs/heads/{branch}",
                     check=False, timeout=None)
        tip, error = remote_tip(root, remote, branch)
        if tip != head:
            detail = (pushed.stderr or "").strip().splitlines()
            message = "Push not confirmed" + (f": {detail[-1]}" if detail else "") + (
                f" (remote check: {error})" if error else "")
            if error:
                raise IncompleteError("PUSH_NOT_CONFIRMED", message, result)
            raise LifecycleError(message)
        journal(repo, {"step": "push", "phase": "end", "branch": branch, "head": head})
        result["pushed"] = True
    result["remote_head"] = tip
    if prs is None:
        return {**result, "state": PR_UNKNOWN, "reason": provider_error}
    try:
        pr = select_pr([item for item in prs if item["state"] == "OPEN"], head)
        if pr is None:
            if not title or not body_file:
                return {**result, "state": PR_MISSING,
                        "next_step": "Run share again with --title and --body-file to open the PR."}
            provider.create(base, branch, title, body_file, draft)
            result["pr_created"] = True
        elif title or body_file:
            provider.edit(pr["number"], title, body_file)
        # GitHub aktualizuje PR asynchronicznie po push/utworzeniu: krótkie odpytywanie.
        for _ in range(6):
            pr = select_pr([item for item in provider.prs_for_branch(branch) if item["state"] == "OPEN"], head)
            if pr and pr["headRefOid"] == head:
                break
            time.sleep(float(os.environ.get("AI_GIT_POLL_SECONDS", "2")))
    except LifecycleError as error:
        return {**result, "state": PR_UNKNOWN, "reason": str(error)}
    if pr is None:
        return {**result, "state": PR_UNKNOWN, "reason": "PR not visible after creation"}
    state = MERGE_PENDING if pr["headRefOid"] == head else PR_HEAD_MISMATCH
    return {**result, "state": state, "pr": {key: pr.get(key) for key in
                                               ("number", "url", "headRefOid", "baseRefName", "isDraft")}}


def merge(start: Path, number: int, expect_head: str, method: str | None, mode: str | None,
          expect_base: str | None = None) -> dict:
    """G7: merge one PR on the user's explicit command after re-verifying it.

    Args:
        start: Path inside the repository.
        number: PR number named by the user.
        expect_head: Full head SHA the user approved; any other head is refused.
        method: merge, squash or rebase (default: ``git.merge_method`` on the base, else merge).
        mode: CI mode (default: ``ci.execution`` on the base branch).
        expect_base: Required base branch name (default: the repository base).
    Returns:
        ``{"state": "MERGED / CLEANUP_PENDING", "merge_commit": ...}``.
    Raises:
        LifecycleError for any mismatch, missing/failed/skipped checks, draft,
        BEHIND/BLOCKED/DIRTY state; the PR is left unchanged. IncompleteError when
        the merge call's outcome cannot be confirmed.
    Side effects:
        fetch of remote-tracking refs; one ``gh pr merge --match-head-commit``
        call (never ``--admin``); journal lines.
    """
    repo = discover(start)
    root = repo["root"]
    if not OID.fullmatch(expect_head or ""):
        raise LifecycleError("--expect-head must be the full approved head SHA")
    remote = pick_remote(root, None)
    provider = GitHubProvider(root, remote)
    if not provider.available:
        raise LifecycleError(f"Cannot merge: {provider.reason}")
    base = expect_base or resolve_base(root, remote, None)[0]
    git(root, "fetch", "--prune", "--no-tags", remote, check=False, timeout=NETWORK_TIMEOUT)
    base_ref = f"refs/remotes/{remote}/{base}"
    # Ustawienia z bazy (przeglądnięty stan), nie z gałęzi, która jest właśnie scalana.
    settings_ref = base_ref if rev(root, base_ref) else None
    method = method or (project_settings(root, settings_ref).get("git") or {}).get("merge_method") or "merge"
    if method not in MERGE_METHODS:
        raise LifecycleError(f"Unsupported merge method: {method}")
    view = provider.view(number)
    if view.get("isCrossRepository"):
        raise LifecycleError(f"PR #{number} comes from another repository; merge it manually")
    if view["state"] == "MERGED":
        if view["headRefOid"] != expect_head:
            raise LifecycleError(f"PR #{number} was merged with head {view['headRefOid']}, not {expect_head}")
        return {"state": CLEANUP_PENDING, "pr": number, "merge_commit": (view.get("mergeCommit") or {}).get("oid"),
                "skipped": "already merged"}
    if view["state"] != "OPEN":
        raise LifecycleError(f"PR #{number} is {view['state']}")
    if view["headRefOid"] != expect_head:
        raise LifecycleError(f"PR #{number} head is {view['headRefOid']}, not the approved {expect_head}; "
                             "a new head needs new checks and a new command")
    if view["baseRefName"] != base:
        raise LifecycleError(f"PR #{number} targets {view['baseRefName']}, expected {base}")
    if view.get("isDraft"):
        raise LifecycleError(f"PR #{number} is a draft; mark it ready first")
    mode = ci_mode(root, mode, settings_ref)
    if mode == "local":
        evidence = local_result(root, expect_head)
        fork = git_out(root, "merge-base", expect_head, base_ref) if rev(root, base_ref) else None
        if evidence["status"] == "PASS" and evidence.get("base") != fork:
            evidence = {"status": NOT_VERIFIED,
                        "reason": f"result base {evidence.get('base')} is not the current merge base {fork}"}
    elif mode == "github":
        evidence = provider.required_checks(number)
    else:
        raise LifecycleError("CI mode unknown: pass --mode local|github or save ci.execution in project.json")
    if evidence["status"] != "PASS":
        raise LifecycleError(f"Checks for {expect_head} are {evidence['status']}; not merging "
                             f"({evidence.get('reason') or evidence.get('checks')})")
    if view.get("mergeStateStatus") not in ACCEPTED_MERGE_STATES:
        raise LifecycleError(f"PR #{number} merge state is {view.get('mergeStateStatus')} (BEHIND: update the "
                             "branch and verify again; BLOCKED: a required check or review is missing)")
    journal(repo, {"step": "merge", "phase": "start", "branch": view["headRefName"], "head": expect_head,
                   "pr": number, "method": method})
    try:
        provider.merge(number, method, expect_head)
    except LifecycleError as error:
        try:
            after = provider.view(number)
        except LifecycleError:
            after = {}
        if after.get("state") != "MERGED":
            if "timed out" in str(error) or not after:
                raise IncompleteError(MERGE_NOT_CONFIRMED, f"Merge call outcome unknown: {error}") from error
            raise
    try:
        after = provider.view(number)
    except LifecycleError as error:
        raise IncompleteError(MERGE_NOT_CONFIRMED, f"Merge requested; confirmation failed: {error}") from error
    if after["state"] != "MERGED":
        raise IncompleteError(MERGE_NOT_CONFIRMED, f"PR #{number} is {after['state']} after the merge call")
    journal(repo, {"step": "merge", "phase": "end", "branch": view["headRefName"], "head": expect_head,
                   "pr": number})
    return {"state": CLEANUP_PENDING, "pr": number, "method": method,
            "merge_commit": (after.get("mergeCommit") or {}).get("oid")}


def ignored_files(path: str) -> list[str]:
    """Ignored (untracked) files in a worktree, which ``worktree remove`` would delete."""
    listed = git(Path(path), "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z",
                 check=False, read_only=True)
    if listed.returncode != 0:
        return ["<ignored files could not be listed>"]
    return [item for item in listed.stdout.split("\0") if item][:5]


def cleanup(start: Path, branch: str | None, number: int | None = None,
            base_name: str | None = None, remote_name: str | None = None) -> dict:
    """G8: remove only the proven-merged task branch and its clean worktrees.

    Args:
        start: Path inside the repository.
        branch: Task branch (default: the current branch).
        number: PR number (default: the latest same-repository PR of the branch).
        base_name/remote_name: Overrides.
    Returns:
        ``state`` CLEANED or CLEANUP_PENDING with ``done`` and ``pending`` lists.
    Raises:
        LifecycleError when merge evidence is missing or other open PRs target the
        branch; nothing is removed then.
    Side effects:
        fetch; ``git switch --no-overwrite-ignore`` / fast-forward of the base in a
        clean current worktree; ``git worktree remove`` (never forced, never with
        ignored files); ``update-ref -d`` of the local branch at its known tip;
        remote deletion with ``--force-with-lease`` bound to the observed tip.
        Stash, other branches, dirty worktrees and lock files are never touched.
    """
    repo = discover(start)
    root = repo["root"]
    if blockers(repo):
        raise LifecycleError("Blocked: " + "; ".join(blockers(repo)))
    remote = pick_remote(root, remote_name)
    if remote is None:
        raise LifecycleError("No Git remote configured; merge evidence unavailable")
    base, _ = resolve_base(root, remote, base_name)
    current = git_out(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    branch = branch or current
    if not branch or branch == base:
        raise LifecycleError("Name the merged task branch with --branch")
    provider = GitHubProvider(root, remote)
    if not provider.available:
        raise LifecycleError(f"Merge evidence unavailable ({provider.reason}); branch kept")
    prs = provider.prs_for_branch(branch)
    pr = next((item for item in prs if item["number"] == number), None) if number else select_pr(prs, None)
    if not pr or pr["state"] != "MERGED":
        raise LifecycleError(f"No merged PR for {branch}; branch kept (state: {pr and pr['state']})")
    stacked = provider.open_prs_with_base(branch)
    if stacked:
        raise LifecycleError(f"Open PR(s) {', '.join('#' + str(p['number']) for p in stacked)} target {branch}; "
                             "retarget them first")
    pr_head = pr["headRefOid"]
    local_tip = rev(root, f"refs/heads/{branch}")
    remote_head, remote_error = remote_tip(root, remote, branch)
    used = [tree for tree in worktrees(root) if tree["branch"] == branch]
    if not local_tip and not remote_head and not remote_error and not used:
        return {"state": CLEANED, "branch": branch, "pr": pr["number"], "done": [], "pending": []}
    done, pending = [], []
    git(root, "fetch", "--prune", "--no-tags", remote, check=False, timeout=NETWORK_TIMEOUT)
    base_tip = rev(root, f"refs/remotes/{remote}/{base}")
    merge_commit = (pr.get("mergeCommit") or {}).get("oid")
    if not base_tip or not rev(root, pr_head) or not included_in(root, pr_head, base_tip, merge_commit):
        raise LifecycleError(f"PR #{pr['number']} head {pr_head} is not proven to be in {remote}/{base}; branch kept")
    local_ok = local_tip is None or local_tip == pr_head or is_ancestor(root, local_tip, pr_head)
    journal(repo, {"step": "cleanup", "phase": "start", "branch": branch, "head": pr_head, "pr": pr["number"]})
    # 1. Worktree na gałęzi zadania: bieżący przełącz na bazę, inne usuń tylko czyste i bez plików ignorowanych.
    for tree in used:
        if not local_ok:
            pending.append(f"{branch} has commits after PR #{pr['number']}; worktree {tree['path']} kept")
            continue
        if same_path(tree["path"], root):
            status = parse_status(root)
            if status["staged"] or status["unstaged"]:
                pending.append(f"current worktree has tracked changes; switch to {base} manually")
            elif repo["linked"]:
                pending.append(f"run cleanup from another worktree to remove {tree['path']}")
            else:
                switched = git(root, "switch", "--no-overwrite-ignore", base, check=False, timeout=None)
                if switched.returncode != 0:
                    pending.append(f"could not switch to {base}: {(switched.stderr or '').strip()}")
                else:
                    done.append(f"switched current worktree to {base}")
            continue
        if tree["locked"]:
            pending.append(f"worktree {tree['path']} is locked; kept")
            continue
        ignored = ignored_files(tree["path"])
        if ignored:
            pending.append(f"worktree {tree['path']} kept: ignored files would be deleted ({', '.join(ignored)})")
            continue
        removed = git(root, "worktree", "remove", tree["path"], check=False, timeout=None)
        if removed.returncode != 0:
            pending.append(f"worktree {tree['path']} kept: {(removed.stderr or '').strip()}")
        else:
            done.append(f"removed worktree {tree['path']}")
    # 2. Baza: tylko fast-forward, bez nadpisywania plików ignorowanych.
    base_local = rev(root, f"refs/heads/{base}")
    holder = next((tree for tree in worktrees(root) if tree["branch"] == base), None)
    if base_local and base_local != base_tip:
        if not is_ancestor(root, base_local, base_tip):
            pending.append(f"local {base} has commits not on {remote}/{base}; not updated")
        elif holder and same_path(holder["path"], root):
            merged = git(root, "merge", "--ff-only", "--no-overwrite-ignore", "--quiet",
                         f"refs/remotes/{remote}/{base}", check=False, timeout=None)
            if merged.returncode == 0:
                done.append(f"fast-forwarded {base} to {base_tip[:12]}")
            else:
                pending.append(f"fast-forward of {base} failed: {(merged.stderr or '').strip()}")
        elif holder:
            pending.append(f"{base} is checked out in {holder['path']}; fast-forward it there")
        else:
            git(root, "update-ref", f"refs/heads/{base}", base_tip, base_local, timeout=None)
            done.append(f"fast-forwarded {base} to {base_tip[:12]}")
    # 3. Lokalna gałąź zadania: usuwana tylko przy znanym tipie (compare-and-swap).
    if local_tip:
        if not local_ok:
            pending.append(f"local {branch} kept: commits after PR #{pr['number']} head")
        elif any(tree["branch"] == branch for tree in worktrees(root)):
            pending.append(f"local {branch} kept: still checked out in a worktree")
        elif git(root, "update-ref", "-d", f"refs/heads/{branch}", local_tip, check=False,
                 timeout=None).returncode == 0:
            git(root, "config", "--remove-section", f"branch.{branch}", check=False, timeout=None)
            done.append(f"deleted local branch {branch} (was {local_tip[:12]})")
        else:
            pending.append(f"local {branch} changed during cleanup; kept")
    # 4. Gałąź zdalna: tylko gdy jej tip nie zawiera nic poza scalonym head PR (lease na obserwowany tip).
    if remote_error:
        pending.append(f"remote branch state unknown ({remote_error}); retry cleanup later")
    elif remote_head:
        if remote_head == pr_head or (rev(root, remote_head) and is_ancestor(root, remote_head, pr_head)):
            deleted = git(root, "push", f"--force-with-lease=refs/heads/{branch}:{remote_head}", remote,
                          f":refs/heads/{branch}", check=False, timeout=None)
            confirm, confirm_error = remote_tip(root, remote, branch)
            if deleted.returncode == 0 and confirm is None and not confirm_error:
                done.append(f"deleted {remote}/{branch}")
            else:
                reason = (deleted.stderr or confirm_error or "remote branch still present").strip().splitlines()
                pending.append(f"{remote}/{branch} not deleted: {reason[-1] if reason else 'unknown'}")
        else:
            pending.append(f"{remote}/{branch} ({remote_head[:12]}) has commits after PR #{pr['number']}; kept")
    git(root, "fetch", "--prune", "--no-tags", remote, check=False, timeout=NETWORK_TIMEOUT)
    state = CLEANED if not pending else CLEANUP_PENDING
    journal(repo, {"step": "cleanup", "phase": "end", "branch": branch, "head": pr_head, "state": state})
    return {"state": state, "branch": branch, "pr": pr["number"], "done": done, "pending": pending}


def render(report: dict) -> str:
    """Human summary of an inspect report (G9 wording)."""
    tree = report["working_tree"]
    lines = [f"State: {report['state']}",
             f"Branch: {report['branch'] or '(detached)'} @ {(report['head'] or 'unborn')[:12]}; "
             f"base {report['base']} ({report['base_source']}); remote {report['remote'] or '-'}",
             f"Working tree: {len(tree['staged'])} staged, {len(tree['unstaged'])} unstaged, "
             f"{len(tree['untracked'])} untracked, {len(tree['partially_staged'])} partially staged; "
             f"stash {report['stash_count']} (never touched)"]
    if report["pr"]:
        pr = report["pr"]
        lines.append(f"PR #{pr['number']} {pr['state']} head {pr['headRefOid'][:12]} -> {pr['baseRefName']} {pr.get('url', '')}")
    if report["pr_evidence"] != "VERIFIED":
        lines.append(f"PR evidence: {report['pr_evidence']}")
    for item in report["blockers"]:
        lines.append(f"Blocker: {item}")
    for item in report["interrupted_steps"]:
        lines.append(f"Interrupted step (verify actual state): {item}")
    for item in report["pending_cleanup"]:
        lines.append(f"Pending cleanup: {item['branch']} (PR #{item['pr']} merged; {', '.join(item['where'])})")
    for item in report.get("other_merged_remote_branches", []):
        lines.append(f"Info: merged remote branch {item['branch']} (PR #{item['pr']} by {item['author']}) "
                     "belongs to someone else; not cleaned automatically")
    for item in report["notes"]:
        lines.append(f"Note: {item}")
    lines.append(f"Next: {report['next_step']}")
    return "\n".join(lines)


def exit_code(command: str, result: dict) -> int:
    """0 for a completed step, 1 for a failed verification, 3 when incomplete or unverified."""
    if command == "verify":
        status = result.get("status")
        return EXIT_OK if status == "PASS" else EXIT_REFUSED if status == "FAIL" else EXIT_INCOMPLETE
    if command == "share":
        return EXIT_OK if result.get("state") == MERGE_PENDING else EXIT_INCOMPLETE
    if command == "cleanup":
        return EXIT_OK if result.get("state") == CLEANED else EXIT_INCOMPLETE
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns:
        0 done/unchanged, 1 refused (this step changed nothing) or verify FAIL,
        2 usage/environment error, 3 incomplete or not verified (see the state).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "report"):
        item = sub.add_parser(name, help="G0/G1/G9: actual state and next step")
        item.add_argument("--fetch", action="store_true")
        item.add_argument("--base")
        item.add_argument("--remote")
        item.add_argument("--offline", action="store_true", help="skip gh PR queries")
    item = sub.add_parser("commit", help="G3: commit exact task paths")
    item.add_argument("--path", action="append", default=[], required=True)
    group = item.add_mutually_exclusive_group(required=True)
    group.add_argument("--message")
    group.add_argument("--message-file", type=Path)
    item.add_argument("--staged", action="store_true", help="commit the index; it may hold only task paths")
    item.add_argument("--base")
    item = sub.add_parser("verify", help="G4: status of the exact candidate")
    item.add_argument("--mode", choices=("local", "github"))
    item.add_argument("--pr", type=int)
    item = sub.add_parser("share", help="G5: push without force, create/update one PR")
    item.add_argument("--title")
    item.add_argument("--body-file", type=Path)
    item.add_argument("--draft", action="store_true")
    item.add_argument("--base")
    item.add_argument("--remote")
    item = sub.add_parser("merge", help="G7: merge on the user's explicit command")
    item.add_argument("--pr", type=int, required=True)
    item.add_argument("--expect-head", required=True)
    item.add_argument("--method", choices=MERGE_METHODS)
    item.add_argument("--mode", choices=("local", "github"))
    item.add_argument("--expect-base")
    item = sub.add_parser("cleanup", help="G8: remove the proven-merged task branch")
    item.add_argument("--branch")
    item.add_argument("--pr", type=int)
    item.add_argument("--base")
    item.add_argument("--remote")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    def emit(payload: dict) -> None:
        print(json.dumps(payload, indent=2, sort_keys=True))

    try:
        if args.command in ("inspect", "report"):
            result = inspect(args.root, args.remote, args.base, args.fetch, not args.offline)
            print(json.dumps(result, indent=2, sort_keys=True) if args.json else render(result))
            return EXIT_OK
        if args.command == "commit":
            message = args.message if args.message is not None else args.message_file.read_text(encoding="utf-8")
            result = commit(args.root, args.path, message, args.staged, args.base)
        elif args.command == "verify":
            result = verify(args.root, args.mode, args.pr)
        elif args.command == "share":
            result = share(args.root, args.title, args.body_file, args.draft, args.base, args.remote)
        elif args.command == "merge":
            result = merge(args.root, args.pr, args.expect_head, args.method, args.mode, args.expect_base)
        else:
            result = cleanup(args.root, args.branch, args.pr, args.base, args.remote)
    except IncompleteError as error:
        emit({"outcome": "INCOMPLETE", "state": error.state, "reason": str(error), **error.details})
        return EXIT_INCOMPLETE
    except LifecycleError as error:
        if args.json:
            emit({"outcome": "REFUSED", "reason": str(error)})
        else:
            print(f"REFUSED: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except (OSError, ValueError) as error:
        print(f"Git lifecycle error: {error}", file=sys.stderr)
        return EXIT_ERROR
    emit(result)
    return exit_code(args.command, result)


if __name__ == "__main__":
    raise SystemExit(main())
