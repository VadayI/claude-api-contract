"""Exercise staged Git bytes and every proposed pre-push ref update."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import git_hooks
import prepare_husky


class GitHookTests(unittest.TestCase):
    """Keep hook fixtures isolated from the source index and remote state."""

    def test_precommit_reads_index_instead_of_working_tree(self):
        """Distinguish staged safe bytes from unstaged TODO and vice versa.

        Args: None; creates a disposable Git repository.
        Returns: None after staged-only behavior assertions.
        Raises: AssertionError if working-tree bytes affect the staged result.
        Side effects: Temporary Git init/add/commit only; no DB or network.
        """
        with tempfile.TemporaryDirectory(prefix="contract index hook ") as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.invalid"], check=True)
            spec = root / "spec" / "main.tsp"
            spec.parent.mkdir()
            spec.write_text("model Good {}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "spec/main.tsp"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
            spec.write_text("model Better {}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "spec/main.tsp"], check=True)
            spec.write_text("// TODO in working tree only\n", encoding="utf-8")
            self.assertEqual(git_hooks.pre_commit(root), 0)
            subprocess.run(["git", "-C", str(root), "add", "spec/main.tsp"], check=True)
            spec.write_text("model Better {}\n", encoding="utf-8")
            self.assertEqual(git_hooks.pre_commit(root), 1)
            spec.write_text("model Better {}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "spec/main.tsp"], check=True)
            openapi = root / "openapi.yml"
            openapi.write_text("openapi: 3.1.0\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "openapi.yml"], check=True)
            self.assertEqual(git_hooks.pre_commit(root), 0)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "spec and artifact"], check=True)
            subprocess.run(["git", "-C", str(root), "mv", "spec/main.tsp", "spec/renamed file.tsp"], check=True)
            self.assertIn(("R", "spec/renamed file.tsp"), git_hooks.staged_paths(root))

    def test_prepush_parses_creation_deletion_and_multiple_refs(self):
        """Verify every branch candidate and skip only an actual deletion.

        Args: None; mocked Git/runner isolate ref handling from network.
        Returns: None after two runner calls and tag rejection assertions.
        Raises: AssertionError or ValueError for incorrect ref handling.
        Side effects: No filesystem, database, or network writes; subprocess
            calls are mocked and output paths are synthetic.
        """
        old = "a" * 40
        first = "b" * 40
        second = "c" * 40
        zero = "0" * 40
        updates = git_hooks.ref_updates(
            f"refs/heads/one {first} refs/heads/one {old}\n"
            f"refs/heads/two {second} refs/heads/two {zero}\n"
            f"(delete) {zero} refs/heads/gone {old}\n"
        )
        self.assertEqual(len(updates), 3)

        def fake_git(_root: Path, *args: str) -> bytes:
            """Return exact mocked ref/parent OIDs for read-only Git probes.

            Args: _root is unused fixture root; args are Git argv.
            Returns: ASCII commit SHA and newline.
            Raises: AssertionError for an unexpected Git query.
            Side effects: None; no DB/network/filesystem access.
            """
            if args[-1] == "refs/heads/one^{commit}":
                return (first + "\n").encode()
            if args[-1] == "refs/heads/two^{commit}":
                return (second + "\n").encode()
            if args[-1] == second + "^":
                return (old + "\n").encode()
            raise AssertionError(args)

        with mock.patch.object(git_hooks, "git", side_effect=fake_git), mock.patch.object(
            git_hooks, "assert_candidate_tooling"
        ), mock.patch.object(
            git_hooks, "creation_base", return_value=old
        ), mock.patch.object(
            git_hooks.subprocess, "run", return_value=mock.Mock(returncode=0)
        ) as runner:
            self.assertEqual(git_hooks.pre_push(Path("C:/fixture"), updates, "origin"), 0)
            self.assertEqual(runner.call_count, 2)
            candidates = [call.args[0][call.args[0].index("--candidate") + 1] for call in runner.call_args_list]
            self.assertEqual(candidates, [first, second])
        with self.assertRaisesRegex(ValueError, "Tag push"):
            git_hooks.pre_push(Path("C:/fixture"), [("refs/tags/v1", first, "refs/tags/v1", zero)], "origin")
        with self.assertRaisesRegex(ValueError, "Malformed"):
            git_hooks.ref_updates("HEAD bad refs/heads/main also-bad\n")

    def test_candidate_tooling_rejects_dirty_runner(self):
        """Bind local runner bytes to the exact proposed commit.

        Args: None; uses a disposable repository with two verification inputs.
        Returns: None after matching and dirty runner assertions.
        Raises: AssertionError if a changed local runner is accepted.
        Side effects: Temporary Git init/add/commit and local file edit only;
            no network, database, or source checkout changes.
        """
        with tempfile.TemporaryDirectory(prefix="hook tooling ") as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.invalid"], check=True)
            hook = root / "scripts/ai/git_hooks.py"
            runner = root / "scripts/ai/runner.py"
            catalog = root / "templates/ai/checks/contract.json"
            for path in (hook, runner, catalog):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("reviewed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "candidate"], check=True)
            commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"]).decode().strip()
            git_hooks.assert_candidate_tooling(root, commit)
            runner.write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differs from candidate"):
                git_hooks.assert_candidate_tooling(root, commit)

    def test_new_branch_uses_verified_remote_main_merge_base(self):
        """Reject stale remote tracking and include all branch commits.

        Args: None; mocked read-only Git requests model remote main and fork.
        Returns: None after exact merge-base and stale-ref assertions.
        Raises: AssertionError if a first-parent shortcut or stale base is used.
        Side effects: None; no filesystem, database, or actual network access.
        """
        main = "a" * 40
        fork = "b" * 40
        candidate = "c" * 40

        def response(_root: Path, *args: str) -> bytes:
            """Map precise Git argv to synthetic remote and fork OIDs.

            Args: _root is unused; args are Git argv.
            Returns: ASCII Git output for the requested read.
            Raises: AssertionError on an unreviewed Git command.
            Side effects: None; no filesystem, database, or network.
            """
            if args[:2] == ("ls-remote", "--exit-code"):
                return f"{main}\trefs/heads/main\n".encode()
            if args[:2] == ("rev-parse", "--verify"):
                return (main + "\n").encode()
            if args[:1] == ("merge-base",):
                self.assertEqual(args[1:], (main, candidate))
                return (fork + "\n").encode()
            raise AssertionError(args)

        with mock.patch.object(git_hooks, "git", side_effect=response):
            self.assertEqual(git_hooks.creation_base(Path("C:/fixture"), "origin", candidate), fork)
        with mock.patch.object(git_hooks, "git", side_effect=lambda _root, *args:
                               f"{main}\trefs/heads/main\n".encode() if args[0] == "ls-remote" else
                               (fork + "\n").encode()):
            with self.assertRaisesRegex(ValueError, "stale"):
                git_hooks.creation_base(Path("C:/fixture"), "origin", candidate)

    def test_husky_prepare_preserves_foreign_hooks_path(self):
        """Keep a project's existing Git hooks directory unchanged.

        Args: None; uses a disposable Git repository with a foreign hooks path.
        Returns: None after read-only and prepare behavior assertions.
        Raises: AssertionError if setup rewrites core.hooksPath.
        Side effects: Temporary repo-local Git config only; no global config,
            database, network, npm install, or source checkout mutation.
        """
        with tempfile.TemporaryDirectory(prefix="hook compatibility ") as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "--local", "core.hooksPath", "custom/hooks"], check=True)
            self.assertEqual(prepare_husky.prepare(root, check=True), 1)
            self.assertEqual(prepare_husky.prepare(root), 0)
            observed = subprocess.check_output(
                ["git", "-C", str(root), "config", "--local", "--get", "core.hooksPath"]
            ).decode().strip()
            self.assertEqual(observed, "custom/hooks")


if __name__ == "__main__":
    unittest.main()
