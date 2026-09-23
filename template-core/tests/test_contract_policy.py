"""Tests for portable exact-context contract policies."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import contract_policy


class ContractPolicyTests(unittest.TestCase):
    """Exercise fail-closed policy behavior without Git or network access."""

    def setUp(self):
        """Create isolated candidate and base roots for each policy fixture.

        Args: self receives fixture paths. Returns: None. Raises: Filesystem
        errors if temporary roots cannot be created. Side effects: Creates only
        disposable directories; no database, subprocess, or network operations.
        """
        self.temp = tempfile.TemporaryDirectory(prefix="contract policy ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "candidate"
        self.base = Path(self.temp.name) / "base"
        self.root.mkdir()
        self.base.mkdir()

    def test_todo_and_adr_use_only_exact_changed_files(self):
        """Reject bare markers and ignore-file changes without a changed ADR.

        Args: self owns disposable roots. Returns: None. Raises: AssertionError
        on fail-open changed-file behavior. Side effects: Writes fixture text
        files only; no database, subprocess, or network access.
        """
        (self.root / "spec").mkdir()
        (self.root / "spec/main.tsp").write_text("// TODO unsafe\n", encoding="utf-8")
        context = {"changed_files": ["spec/main.tsp", ".oasdiff-ignore.txt"]}
        self.assertEqual(contract_policy.check_todos(self.root, context), 1)
        self.assertEqual(contract_policy.check_adr(context), 1)
        context["changed_files"].append("docs/decisions/0012-reviewed.md")
        self.assertEqual(contract_policy.check_adr(context), 0)

    def test_changelog_requires_new_substantive_unreleased_content(self):
        """Reject filename-only or placeholder CHANGELOG updates.

        Args: self owns candidate/base fixtures. Returns: None. Raises:
        AssertionError when unchanged/placeholder content passes. Side effects:
        Writes disposable CHANGELOG files; no DB, subprocess, or network.
        """
        old = "# Changelog\n\n## [Unreleased]\n- old\n\n## [1.0.0]\n- release\n"
        (self.base / "CHANGELOG.md").write_text(old, encoding="utf-8")
        (self.root / "CHANGELOG.md").write_text(old, encoding="utf-8")
        context = {"changed_files": ["spec/main.tsp", "CHANGELOG.md"]}
        self.assertEqual(contract_policy.check_changelog(self.root, self.base, context), 1)
        (self.root / "CHANGELOG.md").write_text(old.replace("- old", "- old\n- new endpoint"), encoding="utf-8")
        self.assertEqual(contract_policy.check_changelog(self.root, self.base, context), 0)

    def test_breaking_uses_exact_base_and_distinguishes_missing_tool(self):
        """Pass literal exact-base artifacts and map missing oasdiff to exit 75.

        Args: self owns candidate/base fixtures. Returns: None. Raises:
        AssertionError when a ref fallback appears or NV becomes PASS/FAIL.
        Side effects: Writes disposable OpenAPI files and mocks one subprocess;
        no real binary, Git, database, or network access.
        """
        (self.root / "openapi.yml").write_text("openapi: 3.1.0\n", encoding="utf-8")
        (self.base / "openapi.yml").write_text("openapi: 3.1.0\n", encoding="utf-8")
        with mock.patch.object(contract_policy.shutil, "which", return_value=None):
            self.assertEqual(contract_policy.check_breaking(self.root, self.base), 75)
        completed = subprocess.CompletedProcess([], 0)
        with mock.patch.object(contract_policy.shutil, "which", return_value="oasdiff"), mock.patch.object(
            contract_policy.subprocess, "run", return_value=completed
        ) as invocation:
            self.assertEqual(contract_policy.check_breaking(self.root, self.base), 0)
        argv = invocation.call_args.args[0]
        self.assertEqual(argv[:2], ["oasdiff", "breaking"])
        self.assertEqual(Path(argv[2]), self.base / "openapi.yml")
        self.assertNotIn("HEAD~1", argv)


if __name__ == "__main__":
    unittest.main()
