"""Exercise the Node runtime-state writers against legacy `.claude/memory` records."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@unittest.skipIf(NODE is None, "Node.js is required for the runtime-state writer fixtures")
class RuntimeStateWriterTests(unittest.TestCase):
    """Disposable project roots only; no Git, database, network or secret access."""

    def setUp(self):
        """Copy the Node writers into a temporary project root."""
        self.temp = tempfile.TemporaryDirectory(prefix="runtime state ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        for name in ("runtime-state.mjs", "log-cmd.mjs"):
            shutil.copy(ROOT / "scripts" / name, self.root / "scripts" / name)
        # Python-owy resolver (scripts/ai) jest potrzebny do fixture'a cross-runtime.
        shutil.copytree(ROOT / "scripts" / "ai", self.root / "scripts" / "ai",
                        ignore=shutil.ignore_patterns("__pycache__", "test_*"))

    def log(self, command: str) -> subprocess.CompletedProcess:
        """Run the command logger once from the temporary root.

        Args:
            command: Slash command name passed to ``log-cmd.mjs``.
        Returns:
            The completed process with captured text output.
        Side effects:
            Starts one Node process that may create ``.ai-runtime`` files.
        """
        return subprocess.run([NODE, "scripts/log-cmd.mjs", command, ""], cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8", check=False)

    def test_legacy_log_moves_to_runtime_directory_without_losing_rows(self):
        """A single legacy copy is moved, then appended to, in the canonical place."""
        legacy = self.root / ".claude/memory/command-log.jsonl"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('{"ts":"1","cmd":"/old","args":""}\n', encoding="utf-8")

        result = self.log("/doctor")

        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertFalse(legacy.exists())
        rows = [json.loads(line) for line in
                (self.root / ".ai-runtime/command-log.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["cmd"] for row in rows], ["/old", "/doctor"])

    def test_conflicting_copies_are_reported_and_neither_is_changed(self):
        """Two differing logs never merge; the writer refuses and names both paths."""
        legacy = self.root / ".claude/memory/command-log.jsonl"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('{"ts":"1","cmd":"/a","args":""}\n', encoding="utf-8")
        canonical = self.root / ".ai-runtime/command-log.jsonl"
        canonical.parent.mkdir(parents=True)
        canonical.write_text('{"ts":"2","cmd":"/b","args":""}\n', encoding="utf-8")

        result = self.log("/doctor")

        self.assertEqual(result.returncode, 0)
        self.assertIn("Conflicting runtime state copies", result.stderr)
        self.assertEqual(legacy.read_text(encoding="utf-8"), '{"ts":"1","cmd":"/a","args":""}\n')
        self.assertEqual(canonical.read_text(encoding="utf-8"), '{"ts":"2","cmd":"/b","args":""}\n')

    def test_python_and_node_writers_share_one_canonical_log(self):
        """Cross-runtime: the Python migration and the Node logger use the same file."""
        import sys

        legacy = self.root / ".claude/memory/command-log.jsonl"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('{"ts":"1","cmd":"/py","args":""}\n', encoding="utf-8")
        migrate = subprocess.run(
            [sys.executable, "scripts/ai/project_state.py", "--root", ".", "--migrate-runtime"],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(migrate.returncode, 0, migrate.stderr)
        self.assertFalse(legacy.exists())

        result = self.log("/node")

        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertFalse(legacy.exists())
        self.assertEqual(sorted(path.name for path in (self.root / ".ai-runtime").iterdir()), ["command-log.jsonl"])
        rows = [json.loads(line) for line in
                (self.root / ".ai-runtime/command-log.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["cmd"] for row in rows], ["/py", "/node"])

    def test_identical_copies_drop_the_legacy_file(self):
        """Byte-identical copies keep the canonical file and remove the legacy one."""
        legacy = self.root / ".claude/memory/command-log.jsonl"
        legacy.parent.mkdir(parents=True)
        canonical = self.root / ".ai-runtime/command-log.jsonl"
        canonical.parent.mkdir(parents=True)
        for path in (legacy, canonical):
            path.write_text('{"ts":"1","cmd":"/a","args":""}\n', encoding="utf-8")

        result = self.log("/verify")

        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertFalse(legacy.exists())
        self.assertEqual(len(canonical.read_text(encoding="utf-8").splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
