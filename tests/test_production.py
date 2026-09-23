"""Behavioral fixtures for conservative contract seed/update ownership."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import production


class ProductionTests(unittest.TestCase):
    """Exercise observable delivery without any network or application execution."""

    def setUp(self):
        """Create an isolated Unicode target for one fixture.

        Args: self is the test. Returns: None. Side effects: Temporary directory;
        no DB/network. OSError propagates; cleanup is registered on success.
        """
        self.temp = tempfile.TemporaryDirectory(prefix="contract доставка ")
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "new project"

    def install(self):
        """Apply the real source's complete seed after an empty conflict plan.

        Args: self owns the fixture target. Returns: None. Side effects: Fixture
        files only; no subprocess/DB/network. Assertion or file errors propagate.
        """
        pending, conflicts = production.delivery(ROOT, self.target)
        self.assertEqual(conflicts, [])
        production.apply(self.target, pending)

    def test_fresh_repeat_autonomous_and_no_workflows(self):
        """Require a complete standalone seed, empty repeat and inactive workflows.

        Args: self owns the fixture. Returns: None. Side effects: Temporary files
        and Python subprocess only; no DB/network. Failures are test assertions.
        """
        self.install()
        self.assertFalse((self.target / ".github/workflows").exists())
        self.assertTrue((self.target / ".agents/skills/bootstrap/SKILL.md").exists())
        self.assertTrue((self.target / ".codex/agents/tsp-author.toml").exists())
        self.assertEqual(production.delivery(ROOT, self.target), ({}, []))
        result = subprocess.run([sys.executable, "scripts/ai/production.py", "--check"], cwd=self.target, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_custom_mixed_conflict_prevents_all_writes(self):
        """Check custom root instructions stop CLI apply before any payload write.

        Args: self owns target. Returns: None. Side effects: Fixture and Python
        subprocess only; no DB/network. Assertion/I/O errors propagate.
        """
        self.target.mkdir()
        path = self.target / "CLAUDE.md"
        path.write_text("Custom project instructions\n")
        before = path.read_bytes()
        result = subprocess.run([sys.executable, str(ROOT / "scripts/ai/production.py"), "--target", str(self.target), "--apply"], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), ["CLAUDE.md"])

    def test_notes_secrets_and_foreign_workflows_preserved(self):
        """Ensure seed-once notes and unlisted secrets/workflows stay byte-identical.

        Args: self owns target. Returns: None. Side effects: Synthetic fixture
        data only; no actual credentials, DB/network. Assertions on preservation.
        """
        self.install()
        fixture = {"docs/HANDOFF.md": b"Project progress\xff", ".env": b"synthetic-not-a-secret", ".github/workflows/custom.yml": b"name: custom"}
        for name, content in fixture.items():
            path = self.target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        pending, conflicts = production.delivery(ROOT, self.target)
        self.assertEqual(conflicts, [])
        production.apply(self.target, pending)
        for name, content in fixture.items():
            self.assertEqual((self.target / name).read_bytes(), content)

    def test_interrupted_delivery_can_retry(self):
        """Simulate interruption before receipt and require a convergent retry.

        Args: self owns target. Returns: None. Side effects: Partial fixture writes
        only; no DB/network. Assertions expose unexpected conflicts or residuals.
        """
        pending, conflicts = production.delivery(ROOT, self.target)
        self.assertEqual(conflicts, [])
        names = [name for name in pending if name != production.MANIFEST][:20]
        production.apply(self.target, {name: pending[name] for name in names})
        self.install()
        self.assertEqual(production.delivery(ROOT, self.target), ({}, []))

    def test_unknown_ownership_and_secret_paths_rejected(self):
        """Reject malformed ownership and secret payloads before opening contents.

        Args: self is test. Returns: None. No side effects/DB/network. Expected
        ValueErrors establish fail-closed metadata rather than fictional evidence.
        """
        with self.assertRaises(ValueError):
            production.records({"schema_version": 1, "files": {"AGENTS.md": {"ownership": "custom", "sha256": "0" * 64}}}, True)
        for name in (".env", "secrets/test", ".claude/settings.local.json", "key.pem", "../outside"):
            with self.assertRaises(ValueError):
                production.payload_text(self.target, name)

    def test_source_drift_stops_delivery(self):
        """Mutate a source after generation and require no target writes.

        Args: self owns temporary directories. Returns: None. Side effects: Copies
        public manifested files only; no DB/network. Expected ValueError on drift.
        """
        source = Path(self.temp.name) / "reviewed source"
        pending, conflicts = production.delivery(ROOT, source)
        self.assertEqual(conflicts, [])
        production.apply(source, pending)
        (source / "scripts/seed.sh").write_text("changed after generation\n")
        with self.assertRaises(ValueError):
            production.delivery(source, self.target)
        self.assertFalse(self.target.exists())

    def test_receipt_update_and_custom_script_conflict(self):
        """Exercise base/local/new update with a previous receipt and customization.

        Args: self owns fixtures. Returns: None. Side effects: Public temp source
        and target writes; no DB/network. Assertion/I/O errors expose regressions.
        """
        self.install()
        old = "previous managed script\n"
        path = self.target / "scripts/seed.sh"
        path.write_text(old)
        receipt_path = self.target / production.MANIFEST
        receipt = json.loads(receipt_path.read_text())
        receipt["files"]["scripts/seed.sh"]["sha256"] = production.digest(old)
        receipt_path.write_text(json.dumps(receipt))
        pending, conflicts = production.delivery(ROOT, self.target)
        self.assertEqual(conflicts, [])
        self.assertIn("scripts/seed.sh", pending)
        path.write_text("local customization\n")
        _, conflicts = production.delivery(ROOT, self.target)
        self.assertIn("scripts/seed.sh", conflicts)

    def test_custom_mcp_is_a_conflict(self):
        """Preserve a project's custom MCP configuration without parsing values.

        Args: self owns fixture. Returns: None. Side effects: Synthetic config
        only; no secrets/DB/network. Assertion verifies conflict and unchanged data.
        """
        self.target.mkdir()
        path = self.target / ".mcp.json"
        content = '{"mcpServers":{"project":{"command":"custom"}}}\n'
        path.write_text(content)
        _, conflicts = production.delivery(ROOT, self.target)
        self.assertIn(".mcp.json", conflicts)
        self.assertEqual(path.read_text(), content)

    def test_linked_ancestor_is_rejected(self):
        """Reject target paths traversing a linked ancestor before any writes.

        Args: self owns disposable directories. Returns: None. Side effects:
        Fixture symlink only; no DB/network. Skip hosts lacking symlink permission.
        """
        real = Path(self.temp.name) / "real"
        real.mkdir()
        link = Path(self.temp.name) / "link"
        try:
            link.symlink_to(real, target_is_directory=True)
        except OSError:
            self.skipTest("Host does not permit fixture directory symlinks")
        with self.assertRaises(ValueError):
            production.delivery(ROOT, link / "project")
        self.assertEqual(list(real.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "POSIX fake-tool exit fixture; Git Bash is probed separately")
    def test_dependency_failure_is_not_masked(self):
        """Require install.sh to propagate npm ci failure without install fallback.

        Args: self owns disposable fake toolchain. Returns: None. Side effects:
        Local Bash subprocess/fake files; no dependency install/DB/network occurs.
        """
        project = Path(self.temp.name) / "install"
        (project / "scripts").mkdir(parents=True)
        shutil.copyfile(ROOT / "scripts/install.sh", project / "scripts/install.sh")
        (project / "package-lock.json").write_text("{}")
        tools = project / "fake-bin"
        tools.mkdir()
        for name, body in {"python": "exit 0", "node": "exit 0", "npm": 'test "$1" = ci || exit 99\nexit 47'}.items():
            path = tools / name
            path.write_text("#!/bin/sh\n" + body + "\n")
            path.chmod(0o755)
        environment = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]}
        result = subprocess.run(["bash", str(project / "scripts/install.sh")], env=environment, capture_output=True)
        self.assertEqual(result.returncode, 47)


if __name__ == "__main__":
    unittest.main()
