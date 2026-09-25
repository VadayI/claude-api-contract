"""Offline stand-in for the gh CLI used by git lifecycle fixtures.

State lives in the JSON file named by ``FAKE_GH_STATE``:
``{"repos": {"owner/name": {"bare": path, "next": 1, "prs": {}, "checks": {}}},
"offline": false}``. PR heads of open PRs follow the bare remote branch tip, as
on GitHub. Merges are performed for real in a temporary clone of the bare remote.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

STATE = Path(os.environ["FAKE_GH_STATE"])
PR_KEYS = ("number", "state", "isDraft", "headRefName", "headRefOid", "baseRefName", "url", "title")


def load() -> dict:
    """Read the shared fixture state."""
    return json.loads(STATE.read_text(encoding="utf-8"))


def save(state: dict) -> None:
    """Persist the shared fixture state."""
    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")


def git(cwd: str, *args: str) -> str:
    """Run Git in a fixture directory and return stdout."""
    env = {**os.environ, "GIT_AUTHOR_NAME": "Remote", "GIT_AUTHOR_EMAIL": "remote@example.invalid",
           "GIT_COMMITTER_NAME": "Remote", "GIT_COMMITTER_EMAIL": "remote@example.invalid"}
    return subprocess.run(["git", "-C", cwd, *args], check=True, capture_output=True, text=True,
                          env=env).stdout.strip()


def tip(repo: dict, branch: str) -> str | None:
    """Current branch tip in the bare remote."""
    result = subprocess.run(["git", "-C", repo["bare"], "rev-parse", "--verify", "--quiet",
                             f"refs/heads/{branch}"], capture_output=True, text=True)
    return result.stdout.strip() or None


def refresh(repo: dict, pr: dict) -> dict:
    """Open PRs follow their branch tip; merged/closed PRs keep their last head."""
    if pr["state"] == "OPEN":
        pr["headRefOid"] = tip(repo, pr["headRefName"]) or pr["headRefOid"]
    return pr


def arg(args: list[str], name: str) -> str | None:
    """Value following ``name`` in argv, if present."""
    return args[args.index(name) + 1] if name in args else None


def public(pr: dict, fields: str) -> dict:
    """Project a PR onto the requested --json fields."""
    out = {}
    for field in fields.split(","):
        if field == "mergeCommit":
            out[field] = {"oid": pr["mergeCommit"]} if pr.get("mergeCommit") else None
        elif field == "isCrossRepository":
            out[field] = bool(pr.get(field))
        elif field == "author":
            out[field] = {"login": pr.get("author", "fixture")}
        elif field in pr:
            out[field] = pr[field]
    return out


def merge_state(repo: dict, pr: dict) -> str:
    """Emulate strict protection: DRAFT, BEHIND (base tip missing from head) or CLEAN."""
    if pr["isDraft"]:
        return "DRAFT"
    base = tip(repo, pr["baseRefName"])
    ancestor = subprocess.run(["git", "-C", repo["bare"], "merge-base", "--is-ancestor", base,
                               pr["headRefOid"]]).returncode == 0
    return "CLEAN" if ancestor else "BEHIND"


def do_merge(repo: dict, pr: dict, method: str) -> str:
    """Merge the PR into its base in a temporary clone and push the result."""
    with tempfile.TemporaryDirectory() as temp:
        git(temp, "clone", "--quiet", repo["bare"], "work")
        work = str(Path(temp) / "work")
        git(work, "checkout", "--quiet", pr["baseRefName"])
        source = f"origin/{pr['headRefName']}"
        if method == "merge":
            git(work, "merge", "--no-ff", "--quiet", "-m", f"Merge pull request #{pr['number']}", source)
        elif method == "squash":
            git(work, "merge", "--squash", "--quiet", source)
            git(work, "commit", "--quiet", "-m", f"{pr['title']} (#{pr['number']})")
        else:
            commits = git(work, "rev-list", "--reverse", f"HEAD..{source}").split()
            for commit in commits:
                git(work, "cherry-pick", "--quiet", commit)
        git(work, "push", "--quiet", "origin", pr["baseRefName"])
        return git(work, "rev-parse", "HEAD")


def main() -> int:
    """Dispatch the gh subcommands used by git_lifecycle.py."""
    args = sys.argv[1:]
    state = load()
    if state.get("offline"):
        print("error connecting to api.github.com", file=sys.stderr)
        return 1
    if args[:2] == ["api", "user"]:
        print(json.dumps({"login": state.get("viewer", "fixture")}))
        return 0
    repo_name = arg(args, "--repo")
    repo = state["repos"][repo_name]
    command = args[:2]
    if command == ["pr", "list"]:
        prs = [refresh(repo, pr) for pr in repo["prs"].values()]
        head, base, wanted = arg(args, "--head"), arg(args, "--base"), arg(args, "--state")
        prs = [pr for pr in prs if (head is None or pr["headRefName"] == head)
               and (base is None or pr["baseRefName"] == base)
               and (wanted in (None, "all") or pr["state"] == wanted.upper())]
        save(state)
        print(json.dumps([public(pr, arg(args, "--json")) for pr in prs]))
        return 0
    number = args[2]
    pr = refresh(repo, repo["prs"][number]) if number in repo["prs"] else None
    if command == ["pr", "view"]:
        out = public(pr, arg(args, "--json"))
        out["mergeStateStatus"] = merge_state(repo, pr) if pr["state"] == "OPEN" else "UNKNOWN"
        out["statusCheckRollup"] = []
        save(state)
        print(json.dumps(out))
        return 0
    if command == ["pr", "checks"]:
        checks = repo["checks"].get(pr["headRefOid"])
        if not checks:
            print(f"no required checks reported on the '{pr['headRefName']}' branch", file=sys.stderr)
            return 1
        print(json.dumps([{"name": name, "state": bucket.upper(), "bucket": bucket, "link": "https://ci"}
                          for name, bucket in checks.items()]))
        return 8 if "pending" in checks.values() else 1 if "fail" in checks.values() else 0
    if command == ["pr", "create"]:
        number = str(repo["next"])
        repo["next"] += 1
        branch = arg(args, "--head")
        repo["prs"][number] = {"number": int(number), "state": "OPEN", "isDraft": "--draft" in args,
                               "headRefName": branch, "headRefOid": tip(repo, branch),
                               "baseRefName": arg(args, "--base"), "title": arg(args, "--title"),
                               "url": f"https://github.com/{repo_name}/pull/{number}", "mergeCommit": None}
        save(state)
        print(repo["prs"][number]["url"])
        return 0
    if command == ["pr", "edit"]:
        if arg(args, "--title"):
            pr["title"] = arg(args, "--title")
        if arg(args, "--base"):
            pr["baseRefName"] = arg(args, "--base")
        save(state)
        return 0
    if command == ["pr", "ready"]:
        pr["isDraft"] = False
        save(state)
        return 0
    if command == ["pr", "merge"]:
        if "--admin" in args or arg(args, "--match-head-commit") != pr["headRefOid"]:
            print("head mismatch or forbidden flag", file=sys.stderr)
            return 1
        method = next(name for name in ("merge", "squash", "rebase") if f"--{name}" in args)
        pr["mergeCommit"] = do_merge(repo, pr, method)
        pr["state"] = "MERGED"
        save(state)
        return 0
    print(f"fake gh: unsupported {' '.join(args)}", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
