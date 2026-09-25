"""Git lifecycle G0-G9 fixtures (plan section 10) on disposable repositories.

Every fixture uses a local bare remote reached through ``url.<path>.insteadOf``
for a GitHub-looking URL, and ``tests/fake_gh.py`` instead of gh. No network,
global Git configuration, database or real GitHub state is used.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import git_lifecycle as gl

FAKE_GH = Path(__file__).resolve().parent / "fake_gh.py"
SLUG = "fixture/app"
URL = f"https://github.com/{SLUG}.git"


class GitLifecycleTests(unittest.TestCase):
    """Real Git state transitions against a bare remote and an offline gh stand-in."""

    def setUp(self):
        """Create a bare remote with main, a clone on a task branch and fake gh state."""
        self.temp = tempfile.TemporaryDirectory(prefix="git lifecycle Україна ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bare = self.base / "remote.git"
        # Globalna konfiguracja fixture: insteadOf kieruje URL GitHub do lokalnego bare remote.
        (self.base / "gitconfig").write_text(
            f'[url "{self.bare.as_posix()}"]\n\tinsteadOf = {URL}\n'
            "[user]\n\tname = Fixture\n\temail = fixture@example.invalid\n[commit]\n\tgpgsign = false\n",
            encoding="utf-8")
        self.state_path = self.base / "gh-state.json"
        env = {"AI_GH": json.dumps([sys.executable, str(FAKE_GH)]), "FAKE_GH_STATE": str(self.state_path),
               "AI_GIT_POLL_SECONDS": "0", "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": str(self.base / "gitconfig")}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.run_git(self.base, "init", "--quiet", "--bare", "--initial-branch=main", str(self.bare))
        self.repo = self.base / "work tree"
        self.run_git(self.base, "init", "--quiet", "--initial-branch=main", str(self.repo))
        self.configure(self.repo)
        self.write("README.md", "# App\n")
        self.write(".gitignore", ".ai-runtime/\n")
        self.git("add", "README.md", ".gitignore")
        self.git("commit", "--quiet", "-m", "init")
        self.git("remote", "add", "origin", URL)
        self.git("push", "--quiet", "-u", "origin", "main")
        self.git("remote", "set-head", "origin", "main")
        self.git("switch", "--quiet", "-c", "feat/task")
        self.save_state({"offline": False, "repos": {SLUG: {"bare": str(self.bare), "next": 1,
                                                             "prs": {}, "checks": {}}}})

    # --- pomocnicze -------------------------------------------------------------
    def run_git(self, cwd: Path, *args: str) -> str:
        """Run Git for fixture setup and return stripped stdout."""
        return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                              text=True).stdout.strip()

    def git(self, *args: str, cwd: Path | None = None) -> str:
        """Run Git in the working clone (or ``cwd``)."""
        return self.run_git(cwd or self.repo, *args)

    def configure(self, path: Path) -> None:
        """Local identity so fixtures never depend on user configuration."""
        self.run_git(path, "config", "user.name", "Fixture")
        self.run_git(path, "config", "user.email", "fixture@example.invalid")
        self.run_git(path, "config", "commit.gpgsign", "false")

    def write(self, name: str, text: str, root: Path | None = None) -> None:
        """Write a UTF-8 file in the working clone."""
        path = (root or self.repo) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def save_state(self, state: dict) -> None:
        """Replace the fake gh state."""
        self.state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")

    def state(self) -> dict:
        """Read the fake gh state."""
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def set_checks(self, head: str, **checks: str) -> None:
        """Declare required check buckets for one PR head."""
        state = self.state()
        state["repos"][SLUG]["checks"][head] = {name.replace("_", " "): bucket for name, bucket in checks.items()}
        self.save_state(state)

    def head(self, ref: str = "HEAD") -> str:
        """Resolve a ref in the working clone."""
        return self.git("rev-parse", ref)

    def remote_branches(self) -> set[str]:
        """Branch names that exist in the bare remote."""
        out = self.run_git(self.bare, "for-each-ref", "--format=%(refname:short)", "refs/heads")
        return set(out.split())

    def xy(self) -> dict:
        """Porcelain v1 status map path -> XY for preservation checks."""
        out = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain=v1", "--untracked-files=all"],
                             check=True, capture_output=True, text=True).stdout
        return {line[3:]: line[:2] for line in out.splitlines() if line}

    def task_commit(self, name: str = "src/task.py", text: str = "print('task')\n") -> str:
        """Create one committed task change through the lifecycle commit step."""
        self.write(name, text)
        return gl.commit(self.repo, [name], f"feat: {name}", False)["head"]

    def shared_pr(self, name: str = "src/task.py") -> tuple[str, int]:
        """Commit, share and return (head, PR number) in MERGE_PENDING."""
        head = self.task_commit(name)
        body = self.base / "body.md"
        body.write_text("Body\n", encoding="utf-8")
        result = gl.share(self.repo, "feat: task", body, False)
        self.assertEqual(result["state"], gl.MERGE_PENDING, result)
        return head, result["pr"]["number"]

    def merge_elsewhere(self, number: int, method: str) -> None:
        """Merge the PR as if another machine or the GitHub UI did it."""
        branch = self.state()["repos"][SLUG]["prs"][str(number)]["headRefName"]
        subprocess.run([sys.executable, str(FAKE_GH), "pr", "merge", str(number), "--repo", SLUG,
                        f"--{method}", "--match-head-commit", self.run_git(self.bare, "rev-parse", branch)],
                       check=True, capture_output=True, text=True)

    # --- G0/G1 ------------------------------------------------------------------
    def test_inspect_reports_state_without_changing_work(self):
        """Inspect is read-only: foreign partial staging, untracked files and stash survive."""
        self.write("README.md", "# App\nstaged\n")
        self.git("add", "README.md")
        self.write("README.md", "# App\nstaged\nunstaged\n")
        self.write("notes.txt", "foreign\n")
        self.git("stash", "push", "--quiet", "--include-untracked", "--", "notes.txt")
        self.write("notes.txt", "foreign\n")
        before = self.xy()
        report = gl.inspect(self.repo, fetch=True)
        self.assertEqual(report["state"], gl.LOCAL_CHANGES)
        self.assertEqual(report["working_tree"]["partially_staged"], ["README.md"])
        self.assertEqual(report["stash_count"], 1)
        self.assertEqual(self.xy(), before)
        self.assertIn("State: LOCAL_CHANGES", gl.render(report))

    def test_blocked_by_lock_and_in_progress_operation(self):
        """A lock file or an unfinished merge blocks every writing step; the lock stays."""
        lock = self.repo / ".git/index.lock"
        lock.write_text("", encoding="utf-8")
        self.assertEqual(gl.inspect(self.repo, use_provider=False)["state"], gl.BLOCKED)
        self.write("a.txt", "a\n")
        with self.assertRaisesRegex(gl.LifecycleError, "lock file"):
            gl.commit(self.repo, ["a.txt"], "feat: a", False)
        self.assertTrue(lock.exists())
        lock.unlink()
        (self.repo / ".git/MERGE_HEAD").write_text(self.head() + "\n", encoding="utf-8")
        report = gl.inspect(self.repo, use_provider=False)
        self.assertEqual(report["state"], gl.BLOCKED)
        self.assertTrue(any("merge in progress" in item for item in report["blockers"]))

    def test_interrupted_step_is_reported_from_journal(self):
        """A started push without an end is listed; the state still comes from refs."""
        gl.journal(gl.discover(self.repo), {"step": "push", "phase": "start", "branch": "feat/task"})
        report = gl.inspect(self.repo, use_provider=False)
        self.assertEqual(len(report["interrupted_steps"]), 1)
        self.assertEqual(report["state"], gl.NO_CHANGES)

    # --- G3 ---------------------------------------------------------------------
    def test_commit_only_task_paths_preserves_foreign_state(self):
        """Partially staged foreign file, foreign untracked file and stash are untouched."""
        self.write("README.md", "# App\nforeign staged\n")
        self.git("add", "README.md")
        self.write("README.md", "# App\nforeign staged\nforeign unstaged\n")
        self.write("foreign.txt", "not mine\n")
        self.write("src/task.py", "print('task')\n")
        self.write("src/extra.py", "print('extra')\n")
        before = {path: code for path, code in self.xy().items() if not path.startswith("src/")}
        result = gl.commit(self.repo, ["src"], "feat: task", False)
        self.assertEqual(result["outcome"], "COMMITTED")
        self.assertEqual(result["paths"], ["src/extra.py", "src/task.py"])
        self.assertEqual(set(self.git("show", "--name-only", "--format=", "HEAD").split()),
                         {"src/extra.py", "src/task.py"})
        self.assertEqual(self.xy(), before)
        self.assertEqual(self.git("show", ":README.md"), "# App\nforeign staged")

    def test_commit_refuses_unseparable_or_foreign_staged_content(self):
        """Partially staged task path needs --staged; --staged refuses foreign index entries."""
        self.write("src/task.py", "one\n")
        self.git("add", "src/task.py")
        self.write("src/task.py", "one\ntwo\n")
        with self.assertRaisesRegex(gl.LifecycleError, "staged changes"):
            gl.commit(self.repo, ["src/task.py"], "feat: task", False)
        self.write("other.txt", "foreign\n")
        self.git("add", "other.txt")
        with self.assertRaisesRegex(gl.LifecycleError, "outside the task"):
            gl.commit(self.repo, ["src/task.py"], "feat: task", True)
        self.git("restore", "--staged", "other.txt")
        result = gl.commit(self.repo, ["src/task.py"], "feat: first hunk", True)
        self.assertEqual(self.git("show", "HEAD:src/task.py"), "one")
        self.assertEqual(self.xy()["src/task.py"], " M")
        self.assertEqual(result["outcome"], "COMMITTED")

    def test_commit_rules_base_branch_empty_and_unsafe_paths(self):
        """No commit on base, no empty commit, no escaping paths; deletions are committed."""
        self.assertEqual(gl.commit(self.repo, ["README.md"], "chore: nothing", False)["outcome"], gl.NO_CHANGES)
        with self.assertRaisesRegex(gl.LifecycleError, "Unsafe"):
            gl.commit(self.repo, ["../outside"], "x", False)
        (self.repo / "README.md").unlink()
        gl.commit(self.repo, ["README.md"], "chore: drop readme", False)
        self.assertNotIn("README.md", self.git("ls-tree", "--name-only", "HEAD").split())
        self.git("switch", "--quiet", "main")
        self.write("x.txt", "x\n")
        with self.assertRaisesRegex(gl.LifecycleError, "base branch"):
            gl.commit(self.repo, ["x.txt"], "feat: x", False)
        self.assertEqual(gl.inspect(self.repo, use_provider=False)["state"], gl.BASE_CHANGES)

    # --- G4 ---------------------------------------------------------------------
    def test_verify_local_binds_exact_candidate(self):
        """A runner result counts only for the exact commit and tree."""
        head = self.task_commit()
        folder = self.repo / ".ai-runtime/results"
        folder.mkdir(parents=True)
        tree = self.git("rev-parse", "HEAD^{tree}")
        (folder / "old.json").write_text(json.dumps({"candidate": {"commit": "0" * 40, "tree": tree},
                                                     "outcome": "PASS", "finished_at": "2"}), encoding="utf-8")
        self.assertEqual(gl.verify(self.repo, "local")["status"], "NOT_VERIFIED")
        (folder / "new.json").write_text(json.dumps({"candidate": {"commit": head, "tree": tree},
                                                     "base": {"commit": self.head("main")},
                                                     "outcome": "FAIL", "finished_at": "1"}), encoding="utf-8")
        self.assertEqual(gl.verify(self.repo, "local")["status"], "FAIL")
        with self.assertRaisesRegex(gl.LifecycleError, "CI mode unknown"):
            gl.verify(self.repo, None)

    # --- G5 ---------------------------------------------------------------------
    def test_share_is_idempotent_and_never_duplicates_pr(self):
        """Repeated share keeps one PR; an extra commit is pushed fast-forward."""
        head, number = self.shared_pr()
        self.assertEqual(self.run_git(self.bare, "rev-parse", "feat/task"), head)
        again = gl.share(self.repo, None, None, False)
        self.assertEqual((again["state"], again["pushed"], again["pr"]["number"]), (gl.MERGE_PENDING, False, number))
        second = self.task_commit("src/more.py")
        result = gl.share(self.repo, None, None, False)
        self.assertEqual((result["pushed"], result["pr"]["headRefOid"]), (True, second))
        self.assertEqual(len(self.state()["repos"][SLUG]["prs"]), 1)
        self.assertEqual(gl.inspect(self.repo)["state"], gl.MERGE_PENDING)

    def test_offline_provider_after_push_then_recovery(self):
        """gh failure after push is PR_NOT_VERIFIED; the next share opens exactly one PR."""
        head = self.task_commit()
        state = self.state()
        state["offline"] = True
        self.save_state(state)
        result = gl.share(self.repo, "feat: task", None, False)
        self.assertEqual((result["state"], result["remote_head"]), (gl.PR_UNKNOWN, head))
        self.assertTrue(gl.inspect(self.repo)["pr_evidence"].startswith("NOT_VERIFIED"))
        state["offline"] = False
        self.save_state(state)
        missing = gl.share(self.repo, None, None, False)
        self.assertEqual(missing["state"], gl.PR_MISSING)
        body = self.base / "body.md"
        body.write_text("Body\n", encoding="utf-8")
        created = gl.share(self.repo, "feat: task", body, True)
        self.assertEqual((created["state"], created["pushed"], created["pr"]["isDraft"]), (gl.MERGE_PENDING, False, True))

    def test_rejected_push_for_diverged_remote_and_branch_without_remote(self):
        """A diverged remote branch is never overwritten; no remote keeps work local."""
        self.task_commit()
        gl.share(self.repo, None, None, False)
        other = self.base / "other"
        self.run_git(self.base, "clone", "--quiet", str(self.bare), str(other))
        self.configure(other)
        self.run_git(other, "switch", "--quiet", "feat/task")
        self.write("remote.txt", "other machine\n", root=other)
        self.run_git(other, "add", "remote.txt")
        self.run_git(other, "commit", "--quiet", "-m", "feat: other machine")
        self.run_git(other, "push", "--quiet")
        remote_head = self.run_git(self.bare, "rev-parse", "feat/task")
        self.task_commit("src/local.py")
        with self.assertRaisesRegex(gl.LifecycleError, "never force-pushed"):
            gl.share(self.repo, None, None, False)
        self.assertEqual(self.run_git(self.bare, "rev-parse", "feat/task"), remote_head)
        self.git("fetch", "--quiet", "origin")
        self.assertEqual(gl.inspect(self.repo)["state"], gl.DIVERGED)
        self.git("remote", "remove", "origin")
        with self.assertRaisesRegex(gl.LifecycleError, "No Git remote"):
            gl.share(self.repo, None, None, False)
        self.assertEqual(gl.inspect(self.repo)["state"], gl.COMMITTED_UNPUSHED)

    # --- G7 ---------------------------------------------------------------------
    def test_merge_only_exact_head_with_passing_checks(self):
        """Wrong head, draft, failed or pending checks and BEHIND base are refused."""
        head, number = self.shared_pr()
        with self.assertRaisesRegex(gl.LifecycleError, "Checks .* are NONE"):
            gl.merge(self.repo, number, head, None, "github")
        self.set_checks(head, ci="fail")
        with self.assertRaisesRegex(gl.LifecycleError, "FAIL"):
            gl.merge(self.repo, number, head, None, "github")
        self.set_checks(head, ci="pending")
        with self.assertRaisesRegex(gl.LifecycleError, "PENDING"):
            gl.merge(self.repo, number, head, None, "github")
        self.set_checks(head, ci="pass")
        with self.assertRaisesRegex(gl.LifecycleError, "approved"):
            gl.merge(self.repo, number, "1" * 40, None, "github")
        with self.assertRaisesRegex(gl.LifecycleError, "full approved head"):
            gl.merge(self.repo, number, head[:7], None, "github")
        other = self.base / "other"
        self.run_git(self.base, "clone", "--quiet", str(self.bare), str(other))
        self.configure(other)
        self.write("base.txt", "new base\n", root=other)
        self.run_git(other, "add", "base.txt")
        self.run_git(other, "commit", "--quiet", "-m", "chore: new base")
        self.run_git(other, "push", "--quiet", "origin", "main")
        with self.assertRaisesRegex(gl.LifecycleError, "BEHIND"):
            gl.merge(self.repo, number, head, None, "github")
        self.assertEqual(self.state()["repos"][SLUG]["prs"][str(number)]["state"], "OPEN")
        self.git("fetch", "--quiet", "origin")
        self.git("merge", "--quiet", "--no-edit", "origin/main")
        updated = self.head()
        gl.share(self.repo, None, None, False)
        self.set_checks(updated, ci="pass")
        result = gl.merge(self.repo, number, updated, None, "github")
        self.assertEqual(result["state"], gl.CLEANUP_PENDING)
        self.assertEqual(gl.merge(self.repo, number, updated, None, "github")["skipped"], "already merged")

    # --- G8 ---------------------------------------------------------------------
    def test_cleanup_after_merge_from_other_machine(self):
        """Merged PR + leftover branch is pending cleanup without any local marker."""
        head, number = self.shared_pr()
        self.write("foreign.txt", "keep me\n")
        self.git("stash", "push", "--quiet", "--include-untracked")
        stash_oid = self.git("rev-parse", "stash@{0}")
        self.write("foreign.txt", "keep me\n")
        self.merge_elsewhere(number, "merge")
        report = gl.inspect(self.repo, fetch=True)
        self.assertEqual(report["state"], gl.CLEANUP_PENDING)
        result = gl.cleanup(self.repo, None)
        self.assertEqual(result["state"], gl.CLEANED, result)
        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertEqual(self.head("main"), self.run_git(self.bare, "rev-parse", "main"))
        self.assertNotIn("feat/task", self.git("branch", "--format=%(refname:short)").split())
        self.assertEqual(self.remote_branches(), {"main"})
        self.assertEqual(self.git("rev-parse", "stash@{0}"), stash_oid)
        self.assertEqual(self.xy(), {"foreign.txt": "??"})
        self.assertEqual(gl.cleanup(self.repo, "feat/task")["state"], gl.CLEANED)
        (self.repo / "foreign.txt").unlink()
        self.assertEqual(gl.inspect(self.repo)["state"], gl.NO_CHANGES)

    def test_cleanup_after_squash_and_rebase_merge_uses_inclusion_evidence(self):
        """Squash/rebase heads are not ancestors of main; merge-tree proves inclusion."""
        self.git("switch", "--quiet", "main")
        for method in ("squash", "rebase"):
            with self.subTest(method=method):
                branch = f"feat/{method}"
                self.git("switch", "--quiet", "-c", branch)
                _, number = self.shared_pr(f"src/{method}.py")
                self.task_commit(f"src/{method}-2.py")
                gl.share(self.repo, None, None, False)
                self.merge_elsewhere(number, method)
                self.git("fetch", "--quiet", "origin")
                self.assertFalse(gl.is_ancestor(self.repo, self.head(branch), self.head("origin/main")))
                result = gl.cleanup(self.repo, branch)
                self.assertEqual(result["state"], gl.CLEANED, result)
                self.assertEqual(self.remote_branches(), {"main"})

    def test_cleanup_keeps_additional_commit_after_pr(self):
        """A commit made after the PR head keeps the local branch."""
        _, number = self.shared_pr()
        self.merge_elsewhere(number, "merge")
        self.task_commit("src/after.py")
        self.assertEqual(gl.inspect(self.repo, fetch=True)["state"], gl.MERGED_EXTRA)
        result = gl.cleanup(self.repo, None)
        self.assertEqual(result["state"], gl.CLEANUP_PENDING)
        self.assertIn("feat/task", self.git("branch", "--format=%(refname:short)").split())
        self.assertEqual(self.git("branch", "--show-current"), "feat/task")
        self.assertEqual(self.remote_branches(), {"main"})

    def test_cleanup_respects_dirty_worktree_and_removes_clean_one(self):
        """A linked worktree with untracked work is kept; a clean one is removed."""
        _, number = self.shared_pr()
        self.git("switch", "--quiet", "main")
        linked = self.base / "linked tree"
        self.git("worktree", "add", "--quiet", str(linked), "feat/task")
        self.write("scratch.txt", "user work\n", root=linked)
        self.merge_elsewhere(number, "merge")
        result = gl.cleanup(self.repo, "feat/task")
        self.assertEqual(result["state"], gl.CLEANUP_PENDING)
        self.assertTrue((linked / "scratch.txt").exists())
        self.assertIn("feat/task", self.git("branch", "--format=%(refname:short)").split())
        (linked / "scratch.txt").unlink()
        result = gl.cleanup(self.repo, "feat/task")
        self.assertEqual(result["state"], gl.CLEANED, result)
        self.assertFalse(linked.exists())

    def test_cleanup_without_merge_evidence_keeps_everything(self):
        """Open PR or unavailable gh means the branch stays."""
        _, number = self.shared_pr()
        with self.assertRaisesRegex(gl.LifecycleError, "No merged PR"):
            gl.cleanup(self.repo, None)
        state = self.state()
        state["offline"] = True
        self.save_state(state)
        with self.assertRaisesRegex(gl.LifecycleError, "gh"):
            gl.cleanup(self.repo, None)
        self.assertEqual(self.remote_branches(), {"main", "feat/task"})

    # --- poprawki po niezależnym przeglądzie ------------------------------------
    def other_clone(self) -> Path:
        """A second machine: clone of the bare remote with its own identity."""
        other = self.base / "other machine"
        if not other.exists():
            self.run_git(self.base, "clone", "--quiet", str(self.bare), str(other))
            self.configure(other)
        return other

    def test_skipped_or_unknown_required_checks_are_not_pass(self):
        """Skipping/neutral buckets are NOT_VERIFIED; a merge is refused."""
        head, number = self.shared_pr()
        self.set_checks(head, ci="pass", lint="skipping")
        self.assertEqual(gl.verify(self.repo, "github")["status"], gl.NOT_VERIFIED)
        with self.assertRaisesRegex(gl.LifecycleError, "NOT_VERIFIED"):
            gl.merge(self.repo, number, head, None, "github")
        self.assertEqual(self.state()["repos"][SLUG]["prs"][str(number)]["state"], "OPEN")

    def test_merge_refuses_draft_and_other_base_then_local_mode_merges(self):
        """Draft and base mismatch are refused; local mode needs a result on the current fork point."""
        head = self.task_commit()
        body = self.base / "body.md"
        body.write_text("Body\n", encoding="utf-8")
        number = gl.share(self.repo, "feat: task", body, True)["pr"]["number"]
        self.set_checks(head, ci="pass")
        with self.assertRaisesRegex(gl.LifecycleError, "draft"):
            gl.merge(self.repo, number, head, None, "github")
        state = self.state()
        state["repos"][SLUG]["prs"][str(number)]["isDraft"] = False
        self.save_state(state)
        with self.assertRaisesRegex(gl.LifecycleError, "expected release"):
            gl.merge(self.repo, number, head, None, "github", expect_base="release")
        folder = self.repo / ".ai-runtime/results"
        folder.mkdir(parents=True)
        tree = self.git("rev-parse", "HEAD^{tree}")
        result = {"candidate": {"commit": head, "tree": tree}, "base": {"commit": "0" * 40},
                  "outcome": "PASS", "finished_at": "1"}
        (folder / "r.json").write_text(json.dumps(result), encoding="utf-8")
        with self.assertRaisesRegex(gl.LifecycleError, "merge base"):
            gl.merge(self.repo, number, head, None, "local")
        result["base"]["commit"] = self.head("origin/main")
        (folder / "r.json").write_text(json.dumps(result), encoding="utf-8")
        self.assertEqual(gl.merge(self.repo, number, head, None, "local")["state"], gl.CLEANUP_PENDING)

    def test_fork_pr_with_same_head_name_is_ignored(self):
        """A cross-repository PR on the same branch name is never edited or merged."""
        self.task_commit()
        state = self.state()
        state["repos"][SLUG]["prs"]["7"] = {"number": 7, "state": "OPEN", "isDraft": False, "headRefName": "feat/task",
                                            "headRefOid": "1" * 40, "baseRefName": "main", "title": "fork",
                                            "url": "https://fork/7", "mergeCommit": None, "isCrossRepository": True}
        state["repos"][SLUG]["next"] = 8
        self.save_state(state)
        body = self.base / "body.md"
        body.write_text("Body\n", encoding="utf-8")
        result = gl.share(self.repo, "feat: ours", body, False)
        self.assertEqual((result["state"], result["pr"]["number"]), (gl.MERGE_PENDING, 8))
        self.assertEqual(self.state()["repos"][SLUG]["prs"]["7"]["title"], "fork")

    def test_no_repush_or_duplicate_pr_after_merge_with_deleted_branch(self):
        """Squash merge + auto-deleted head branch: share refuses; offline inspect is NOT_VERIFIED."""
        _, number = self.shared_pr()
        self.merge_elsewhere(number, "squash")
        self.run_git(self.bare, "update-ref", "-d", "refs/heads/feat/task")
        self.git("fetch", "--quiet", "--prune", "origin")
        self.assertEqual(gl.inspect(self.repo)["state"], gl.CLEANUP_PENDING)
        with self.assertRaisesRegex(gl.LifecycleError, "already merged"):
            gl.share(self.repo, "feat: again", None, False)
        state = self.state()
        state["offline"] = True
        self.save_state(state)
        self.assertEqual(gl.inspect(self.repo)["state"], gl.NOT_VERIFIED)
        with self.assertRaisesRegex(gl.LifecycleError, "not pushing it again"):
            gl.share(self.repo, None, None, False)
        self.assertEqual(self.remote_branches(), {"main"})
        self.assertEqual(len(self.state()["repos"][SLUG]["prs"]), 1)

    def test_commit_literal_paths_renames_and_index_only_changes(self):
        """Glob characters are literal; half a rename or an index-only change is refused."""
        self.write("pages/i.tsx", "base\n")
        self.git("add", "pages/i.tsx")
        self.git("commit", "--quiet", "-m", "base page")
        self.write("pages/i.tsx", "foreign edit\n")
        self.write("pages/[id].tsx", "task\n")
        gl.commit(self.repo, ["pages/[id].tsx"], "feat: id page", False)
        self.assertEqual(self.xy()["pages/i.tsx"], " M")
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD"), "pages/[id].tsx")
        self.git("mv", "README.md", "DOCS.md")
        with self.assertRaisesRegex(gl.LifecycleError, "list both"):
            gl.commit(self.repo, ["README.md"], "docs: rename", False)
        gl.commit(self.repo, ["README.md", "DOCS.md"], "docs: rename", True)
        self.write("run.sh", "echo\n")
        self.git("add", "run.sh")
        self.git("commit", "--quiet", "-m", "script")
        self.git("update-index", "--chmod=+x", "run.sh")
        with self.assertRaisesRegex(gl.LifecycleError, "staged changes"):
            gl.commit(self.repo, ["run.sh"], "chore: exec bit", False)
        gl.commit(self.repo, ["run.sh"], "chore: exec bit", True)
        self.assertEqual(self.git("ls-tree", "HEAD", "run.sh").split()[0], "100755")

    def test_commit_hooks_are_reported_and_failures_restore_the_index(self):
        """A failing hook commits nothing and unstages new task files; a greedy hook is reported."""
        hooks = self.repo / ".git/hooks"
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        self.write("src/new.py", "x = 1\n")
        with self.assertRaisesRegex(gl.LifecycleError, "not created"):
            gl.commit(self.repo, ["src/new.py"], "feat: new", False)
        self.assertEqual(self.xy()["src/new.py"], "??")
        hook.write_text("#!/bin/sh\ngit add -A\n", encoding="utf-8")
        self.write("foreign.txt", "foreign\n")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = gl.main(["--root", str(self.repo), "commit", "--path", "src/new.py", "--message", "feat: new"])
        report = json.loads(output.getvalue())
        self.assertEqual((code, report["state"]), (gl.EXIT_INCOMPLETE, gl.COMMIT_UNEXPECTED))
        self.assertIn("foreign.txt", report["unexpected_paths"] + report["changed_foreign_paths"])

    def test_cleanup_keeps_ignored_files_and_never_overwrites_them(self):
        """Worktrees with ignored files are kept; switch/fast-forward refuse to overwrite ignored files."""
        _, number = self.shared_pr()
        self.git("switch", "--quiet", "main")
        linked = self.base / "linked"
        self.git("worktree", "add", "--quiet", str(linked), "feat/task")
        self.write(".ai-runtime/secret.env", "TOKEN=1\n", root=linked)
        self.merge_elsewhere(number, "merge")
        result = gl.cleanup(self.repo, "feat/task")
        self.assertEqual(result["state"], gl.CLEANUP_PENDING)
        self.assertTrue((linked / ".ai-runtime/secret.env").exists())
        # Druga część: plik wykluczony lokalnie, a baza dodaje go jako śledzony.
        self.git("worktree", "remove", "--force", str(linked))
        self.git("switch", "--quiet", "feat/task")
        (self.repo / ".git/info/exclude").write_text("local.cfg\n", encoding="utf-8")
        self.write("local.cfg", "private\n")
        other = self.other_clone()
        self.write("local.cfg", "default\n", root=other)
        self.run_git(other, "add", "local.cfg")
        self.run_git(other, "commit", "--quiet", "-m", "chore: default cfg")
        self.run_git(other, "push", "--quiet", "origin", "main")
        result = gl.cleanup(self.repo, "feat/task")
        self.assertEqual(result["state"], gl.CLEANUP_PENDING)
        self.assertEqual((self.repo / "local.cfg").read_text(encoding="utf-8"), "private\n")

    def test_cleanup_remote_branch_with_new_commits_is_kept_and_lease_protects_race(self):
        """A remote tip beyond the PR head is kept; a push between read and delete is not lost."""
        _, number = self.shared_pr()
        self.merge_elsewhere(number, "merge")
        other = self.other_clone()
        self.run_git(other, "fetch", "--quiet", "origin")
        self.run_git(other, "switch", "--quiet", "feat/task")
        self.write("late.txt", "late\n", root=other)
        self.run_git(other, "add", "late.txt")
        self.run_git(other, "commit", "--quiet", "-m", "feat: late")
        self.run_git(other, "push", "--quiet", "origin", "feat/task")
        result = gl.cleanup(self.repo, None)
        self.assertEqual(result["state"], gl.CLEANUP_PENDING)
        self.assertIn("feat/task", self.remote_branches())
        # Wyścig: odczytany tip to head PR, ale zanim nastąpi usunięcie, ktoś wypycha nowy commit.
        _, second = self.shared_pr_on("feat/race", "src/race.py")
        self.merge_elsewhere(second, "merge")
        pr_head = self.run_git(self.bare, "rev-parse", "feat/race")
        real_tip = gl.remote_tip

        def racing(root, remote, branch):
            answer = real_tip(root, remote, branch)
            if branch == "feat/race" and answer[0] == pr_head and not racing.done:
                racing.done = True
                self.run_git(other, "fetch", "--quiet", "origin")
                self.run_git(other, "switch", "--quiet", "-c", "race", "origin/feat/race")
                self.write("race.txt", "race\n", root=other)
                self.run_git(other, "add", "race.txt")
                self.run_git(other, "commit", "--quiet", "-m", "feat: race")
                self.run_git(other, "push", "--quiet", "origin", "race:feat/race")
            return answer
        racing.done = False
        with mock.patch.object(gl, "remote_tip", side_effect=racing):
            result = gl.cleanup(self.repo, "feat/race")
        self.assertEqual(result["state"], gl.CLEANUP_PENDING)
        self.assertIn("feat/race", self.remote_branches())

    def shared_pr_on(self, branch: str, name: str) -> tuple[str, int]:
        """Start ``branch`` from origin/main and share one commit on it."""
        self.git("fetch", "--quiet", "origin")
        self.git("switch", "--quiet", "-c", branch, "origin/main")
        return self.shared_pr(name)

    def test_cleanup_local_branch_behind_updated_pr_head(self):
        """PR head updated on GitHub (update-branch): the older local tip is still cleaned."""
        _, number = self.shared_pr()
        other = self.other_clone()
        self.write("base.txt", "base\n", root=other)
        self.run_git(other, "add", "base.txt")
        self.run_git(other, "commit", "--quiet", "-m", "chore: base")
        self.run_git(other, "push", "--quiet", "origin", "main")
        self.run_git(other, "fetch", "--quiet", "origin")
        self.run_git(other, "switch", "--quiet", "-c", "upd", "origin/feat/task")
        self.run_git(other, "merge", "--quiet", "--no-edit", "origin/main")
        self.run_git(other, "push", "--quiet", "origin", "upd:feat/task")
        self.merge_elsewhere(number, "merge")
        self.assertEqual(gl.inspect(self.repo, fetch=True)["state"], gl.CLEANUP_PENDING)
        self.assertEqual(gl.cleanup(self.repo, None)["state"], gl.CLEANED)

    def test_cleanup_after_squash_with_later_conflicting_base_change_and_after_gc(self):
        """The PR merge commit proves inclusion; a repeated cleanup after gc stays CLEANED."""
        self.write("README.md", "# App\nline\n")
        gl.commit(self.repo, ["README.md"], "docs: line", False)
        body = self.base / "body.md"
        body.write_text("Body\n", encoding="utf-8")
        number = gl.share(self.repo, "docs: line", body, False)["pr"]["number"]
        self.merge_elsewhere(number, "squash")
        other = self.other_clone()
        self.run_git(other, "pull", "--quiet", "origin", "main")
        self.write("README.md", "# App\nchanged later\n", root=other)
        self.run_git(other, "commit", "--quiet", "-am", "docs: later")
        self.run_git(other, "push", "--quiet", "origin", "main")
        self.assertEqual(gl.cleanup(self.repo, None)["state"], gl.CLEANED)
        self.git("reflog", "expire", "--expire=now", "--all")
        self.git("gc", "--quiet", "--prune=now")
        self.assertEqual(gl.cleanup(self.repo, "feat/task")["state"], gl.CLEANED)

    def test_cleanup_refuses_branch_targeted_by_open_pr(self):
        """A branch used as the base of another open PR is not deleted."""
        _, number = self.shared_pr()
        self.merge_elsewhere(number, "merge")
        state = self.state()
        state["repos"][SLUG]["prs"]["9"] = {"number": 9, "state": "OPEN", "isDraft": False, "headRefName": "feat/next",
                                            "headRefOid": "2" * 40, "baseRefName": "feat/task", "title": "stacked",
                                            "url": "u", "mergeCommit": None}
        self.save_state(state)
        with self.assertRaisesRegex(gl.LifecycleError, "target feat/task"):
            gl.cleanup(self.repo, None)
        self.assertIn("feat/task", self.remote_branches())

    def test_inspect_base_branch_states(self):
        """Local commits on base, unavailable gh and remote-only leftovers are visible."""
        _, number = self.shared_pr()
        self.merge_elsewhere(number, "merge")
        self.git("switch", "--quiet", "main")
        self.git("update-ref", "-d", "refs/heads/feat/task")
        report = gl.inspect(self.repo, fetch=True)
        self.assertEqual((report["state"], report["pending_cleanup"][0]["where"]), (gl.CLEANUP_PENDING, ["remote"]))
        state = self.state()
        state["offline"] = True
        self.save_state(state)
        self.git("merge", "--quiet", "--ff-only", "origin/main")
        self.git("push", "--quiet", "origin", "--delete", "feat/task")
        self.git("fetch", "--quiet", "--prune", "origin")
        self.assertEqual(gl.inspect(self.repo)["state"], gl.NOT_VERIFIED)
        self.write("local.txt", "x\n")
        self.git("add", "local.txt")
        self.git("commit", "--quiet", "-m", "oops on main")
        self.assertEqual(gl.inspect(self.repo)["state"], gl.BASE_COMMITS)

    def test_base_from_remote_when_origin_head_is_missing(self):
        """Without refs/remotes/origin/HEAD the base comes from the remote (ls-remote --symref)."""
        self.git("switch", "--quiet", "main")
        self.git("switch", "--quiet", "-c", "trunk")
        self.git("push", "--quiet", "origin", "trunk")
        self.run_git(self.bare, "symbolic-ref", "HEAD", "refs/heads/trunk")
        self.git("remote", "set-head", "origin", "--delete")
        self.write("x.txt", "x\n")
        with self.assertRaisesRegex(gl.LifecycleError, "base branch 'trunk'"):
            gl.commit(self.repo, ["x.txt"], "feat: x", False)
        self.assertEqual(gl.inspect(self.repo, use_provider=False)["base_source"], "remote")

    def test_hook_globs_still_work_and_newline_names_are_safe(self):
        """Hooks keep their own glob pathspecs; odd foreign file names do not break commits."""
        hook = self.repo / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nif git diff --cached --name-only -- '*.py' | grep -q .; then\n"
                        "  echo 'python staged' >&2; exit 1\nfi\n", encoding="utf-8")
        hook.chmod(0o755)
        self.write("src/app.py", "x = 1\n")
        with self.assertRaisesRegex(gl.LifecycleError, "python staged"):
            gl.commit(self.repo, ["src/app.py"], "feat: app", False)
        hook.unlink()
        if os.name != "nt":
            (self.repo / "weird\nname.txt").write_text("foreign\n", encoding="utf-8")
        result = gl.commit(self.repo, ["src/app.py"], "feat: app", False)
        self.assertEqual(result["outcome"], gl.COMMITTED)

    def test_teammate_remote_branch_is_information_only(self):
        """A merged remote-only branch of another author does not demand cleanup."""
        other = self.other_clone()
        self.run_git(other, "switch", "--quiet", "-c", "alice/feature")
        self.write("alice.txt", "alice\n", root=other)
        self.run_git(other, "add", "alice.txt")
        self.run_git(other, "commit", "--quiet", "-m", "feat: alice")
        self.run_git(other, "push", "--quiet", "origin", "alice/feature")
        tip = self.run_git(other, "rev-parse", "HEAD")
        state = self.state()
        state["repos"][SLUG]["prs"]["5"] = {"number": 5, "state": "OPEN", "isDraft": False,
                                            "headRefName": "alice/feature", "headRefOid": tip, "baseRefName": "main",
                                            "title": "alice", "url": "u", "mergeCommit": None, "author": "alice"}
        state["repos"][SLUG]["next"] = 6
        self.save_state(state)
        self.merge_elsewhere(5, "merge")
        self.git("switch", "--quiet", "main")
        gl.inspect(self.repo, fetch=True)
        self.git("merge", "--quiet", "--ff-only", "origin/main")
        report = gl.inspect(self.repo)
        self.assertEqual(report["state"], gl.NO_CHANGES)
        self.assertEqual([item["branch"] for item in report["other_merged_remote_branches"]], ["alice/feature"])
        self.assertIn("belongs to someone else", gl.render(report))

    def test_fork_pr_targeting_the_branch_blocks_cleanup(self):
        """A cross-repository PR whose base is the task branch keeps the branch."""
        _, number = self.shared_pr()
        self.merge_elsewhere(number, "merge")
        state = self.state()
        state["repos"][SLUG]["prs"]["11"] = {"number": 11, "state": "OPEN", "isDraft": False, "headRefName": "x",
                                             "headRefOid": "3" * 40, "baseRefName": "feat/task", "title": "fork",
                                             "url": "u", "mergeCommit": None, "isCrossRepository": True}
        self.save_state(state)
        with self.assertRaisesRegex(gl.LifecycleError, "#11"):
            gl.cleanup(self.repo, None)

    # --- CLI --------------------------------------------------------------------
    def test_cli_exit_codes_and_json(self):
        """0 for reports and completed steps, 1 for refused steps with a reason."""
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(gl.main(["--root", str(self.repo), "--json", "inspect", "--offline"]), 0)
        self.assertEqual(json.loads(output.getvalue())["state"], gl.NO_CHANGES)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = gl.main(["--root", str(self.repo), "--json", "merge", "--pr", "1", "--expect-head", "abc"])
        self.assertEqual((code, json.loads(output.getvalue())["outcome"]), (1, "REFUSED"))
        self.write("cli.txt", "cli\n")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(gl.main(["--root", str(self.repo), "commit", "--path", "cli.txt",
                                      "--message", "feat: cli"]), 0)
        self.assertEqual(json.loads(output.getvalue())["outcome"], "COMMITTED")


if __name__ == "__main__":
    unittest.main()
