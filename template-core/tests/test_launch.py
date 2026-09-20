"""Test launcher process boundaries without model sessions or real credentials."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/ai"))
import launch


class LaunchTests(unittest.TestCase):
    """Use synthetic env/argv and disposable child processes; no network or DB."""

    def test_environment_is_explicit_and_parent_is_unchanged(self):
        """Only platform/config and selected optional values reach the child."""
        inherited = {"PATH": "synthetic path", "CODEX_HOME": "synthetic home",
                     "GH_TOKEN": "synthetic-token", "DATABASE_URL": "synthetic-db",
                     "NODE_OPTIONS": "unwanted-loader", "UNRELATED_SECRET": "synthetic"}
        before = dict(inherited)
        filtered = launch.child_environment("codex", inherited, ["GH_TOKEN"])
        self.assertEqual(set(filtered), {"PATH", "CODEX_HOME", "GH_TOKEN"})
        self.assertEqual(inherited, before)
        self.assertNotIn("GH_TOKEN", launch.child_environment("codex", inherited, []))
        with self.assertRaises(ValueError):
            launch.child_environment("codex", inherited, ["NODE_OPTIONS"])

    def test_review_permissions_and_defaults(self):
        """Reviewer argv restricts tools/sandbox without model or trust overrides."""
        codex = launch.command("codex", "codex", True, True, False)
        claude = launch.command("claude", "claude", True, True, False)
        self.assertEqual(codex[codex.index("--sandbox") + 1], "read-only")
        self.assertEqual(claude[claude.index("--tools") + 1], "Read,Glob,Grep")
        for argv in (codex, claude):
            self.assertNotIn("--model", argv)
            self.assertFalse(any("bypass" in item or "approve-for-me" in item for item in argv))
        self.assertEqual(launch.command("codex", "codex", False, False, True), ["codex", "--version"])

    def test_real_child_preserves_argv_stdin_cwd_and_exit_code(self):
        """Shell metacharacters stay literal, .env is not sourced, and exit 7 survives."""
        with tempfile.TemporaryDirectory(prefix="launcher space ") as directory:
            root = Path(directory)
            (root / ".env").write_text("UNRELATED_SECRET=from-file\n", encoding="utf-8")
            child = root / "child.py"
            child.write_text(
                "import json, os, pathlib, sys\n"
                "pathlib.Path('result.json').write_text(json.dumps({"
                "'argv': sys.argv[1:], 'input': sys.stdin.read(), 'cwd': os.getcwd(),"
                "'secret': os.environ.get('UNRELATED_SECRET')}), encoding='utf-8')\n"
                "sys.exit(7)\n", encoding="utf-8")
            literal = 'space value; $(not-a-command) & "quoted"'
            code = launch.execute([sys.executable, str(child), literal], root,
                                  launch.child_environment("codex", dict(os.environ), []), "task stdin")
            self.assertEqual(code, 7)
            result = json.loads((root / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["argv"], [literal])
            self.assertEqual(result["input"], "task stdin")
            self.assertEqual(Path(result["cwd"]), root)
            self.assertIsNone(result["secret"])


if __name__ == "__main__":
    unittest.main()
