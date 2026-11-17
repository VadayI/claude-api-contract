"""Q02 (D18, D25.2, D26): the committed Claude settings follow the hook standard and work after cd."""

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import hook_check

SETTINGS = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
GATE = '"${AI_PYTHON:-python3}" "$CLAUDE_PROJECT_DIR/scripts/ai/workdir.py" --hook'


def handlers(event: str) -> list[dict]:
    """Return every hook handler registered for one event."""
    return [hook for group in SETTINGS["hooks"].get(event, []) for hook in group["hooks"]]


class CommittedSettingsTests(unittest.TestCase):
    """Static checks of `.claude/settings.json`; no processes."""

    def test_settings_pass_the_core_style_check(self):
        self.assertEqual([], hook_check.check_settings(SETTINGS))

    def test_policies_are_fail_closed_and_advisory_hooks_are_not(self):
        guard = SETTINGS["hooks"]["PreToolUse"][0]
        self.assertEqual("Write|Edit|NotebookEdit|Bash|PowerShell", guard["matcher"])
        self.assertEqual(["${CLAUDE_PROJECT_DIR}/scripts/policy/claude_edit_guard.mjs"], guard["hooks"][0]["args"])
        for event in ("PreToolUse", "UserPromptSubmit", "UserPromptExpansion"):
            self.assertEqual({"block"}, {hook["onFailure"] for hook in handlers(event)}, event)
        for event in ("SessionStart", "SubagentStop"):
            self.assertNotIn("onFailure", handlers(event)[0], event)
        for event in ("UserPromptSubmit", "PreToolUse"):
            self.assertIn(GATE, [hook["command"] for hook in handlers(event)], event)

    def test_secret_rules_are_anchored_and_1m_context_is_off(self):
        deny = SETTINGS["permissions"]["deny"]
        for rule in ("Read(/.env)", "Read(/**/.env)", "Read(/**/*.pem)", "Read(/**/secrets/**)",
                     "Read(/.claude/settings.local.json)"):
            self.assertIn(rule, deny)
        self.assertIn("Read(/**/*.example)", SETTINGS["permissions"]["allow"])
        self.assertEqual("1", SETTINGS["env"]["CLAUDE_CODE_DISABLE_1M_CONTEXT"])


@unittest.skipIf(os.name == "nt", "emulates the POSIX shell form; Windows is accepted manually")
@unittest.skipUnless(shutil.which("bash") and shutil.which("node"), "bash and node are required")
class CommittedHookExecutionTests(unittest.TestCase):
    """Run the committed hooks from a subdirectory with `python` absent from PATH."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name)
        (self.bin / "python3").symlink_to(sys.executable)
        (self.bin / "node").symlink_to(shutil.which("node"))
        self.environ = {"PATH": str(self.bin), "ALLOW_MNT_SESSION": "1"}

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, handler: dict, payload: dict) -> str:
        return hook_check.run_hook(handler, project_dir=ROOT, cwd=ROOT / "docs/ai", payload=payload,
                                   environ=self.environ, bash=shutil.which("bash"))

    def test_guard_blocks_openapi_edit_from_subdirectory(self):
        guard = handlers("PreToolUse")[0]
        self.assertIsNone(shutil.which("python", path=str(self.bin)))
        edit = {"tool_name": "Edit", "tool_input": {"file_path": str(ROOT / "openapi.yml")}}
        patch = {"tool_name": "PowerShell", "tool_input": {"command":
                 "apply_patch <<'P'\n*** Begin Patch\n*** Update File: ../../openapi.yml\n*** End Patch\nP"}}
        self.assertEqual("deny", self.run_hook(guard, edit))
        self.assertEqual("deny", self.run_hook(guard, patch))
        other = {"tool_name": "Edit", "tool_input": {"file_path": str(ROOT / "spec/main.tsp")}}
        self.assertEqual("allow", self.run_hook(guard, other))

    def test_workdir_gate_runs_through_python3(self):
        gate = next(hook for hook in handlers("UserPromptSubmit") if hook["command"] == GATE)
        self.assertEqual("allow", self.run_hook(gate, {"prompt": "ok"}))


if __name__ == "__main__":
    unittest.main()
