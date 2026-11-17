"""D18/D26 fixtures: hook style check, Claude Code version gate and hook execution after cd."""

import copy
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import hook_check

GATE = '"${AI_PYTHON:-python3}" "$CLAUDE_PROJECT_DIR/scripts/ai/workdir.py" --hook'
GUARD = '"${AI_PYTHON:-python3}" "$CLAUDE_PROJECT_DIR/scripts/policy/guard.py"'
# Wzorcowe ustawienia zgodne z D18/D26; poszczególne testy psują po jednym elemencie.
COMPLIANT = {
    "permissions": {
        "allow": ["Read", "Read(/**/*.example)", "Bash(git status:*)"],
        "deny": ["Read(/.env)", "Read(/**/.env)", "Read(/**/secrets/**)", "Read(//etc/shadow)", "Read(~/.ssh/**)"],
    },
    "hooks": {
        "PreToolUse": [
            {"matcher": "Write|Edit|NotebookEdit|Bash|PowerShell", "hooks": [
                {"type": "command", "command": "node", "args": ["${CLAUDE_PROJECT_DIR}/scripts/policy/guard.mjs"],
                 "onFailure": "block"},
                {"type": "command", "command": GUARD, "onFailure": "block"}]},
            {"matcher": "*", "hooks": [{"type": "command", "command": GATE, "onFailure": "block"}]},
        ],
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": GATE, "onFailure": "block"}]}],
        "UserPromptExpansion": [{"matcher": ".*", "hooks": [
            {"type": "command", "command": '"${AI_PYTHON:-python3}" "$CLAUDE_PROJECT_DIR/scripts/policy/log.py"',
             "onFailure": "continue"}]}],
        "SubagentStop": [{"hooks": [{"type": "command", "command": 'bash "$CLAUDE_PROJECT_DIR/scripts/plan.sh"'}]}],
        "SessionStart": [{"hooks": [{"type": "command", "command": "node", "args": ["${CLAUDE_PROJECT_DIR}/s.mjs"]}]}],
    },
}


def codes(settings: dict) -> list[str]:
    """Return finding codes for a settings fixture."""
    return [item["code"] for item in hook_check.check_settings(settings)]


def mutate(path: tuple, value) -> dict:
    """Copy the compliant fixture and replace one nested value."""
    settings = copy.deepcopy(COMPLIANT)
    target = settings
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return settings


class SettingsStyleTests(unittest.TestCase):
    """Pure checks of a parsed settings document: no processes, files or network."""

    def test_compliant_settings_pass(self):
        self.assertEqual([], hook_check.check_settings(COMPLIANT))

    def test_relative_script_path_fails(self):
        relative = {"type": "command", "command": "python3 scripts/policy/guard.py", "onFailure": "block"}
        found = codes(mutate(("hooks", "PreToolUse", 0, "hooks", 1), relative))
        self.assertIn("relative-path", found)
        self.assertIn("bare-python", found)

    def test_bare_python_and_wrong_launcher_fail(self):
        for command in ('python "$CLAUDE_PROJECT_DIR/x.py"', 'cd "$CLAUDE_PROJECT_DIR" && py "$CLAUDE_PROJECT_DIR/x.py"'):
            found = codes(mutate(("hooks", "UserPromptSubmit", 0, "hooks", 0, "command"), command))
            self.assertIn("bare-python", found, command)
        found = codes(mutate(("hooks", "UserPromptSubmit", 0, "hooks", 0, "command"),
                             '"${AI_PYTHON:-python}" "$CLAUDE_PROJECT_DIR/x.py"'))
        self.assertIn("python-launcher", found)

    def test_unquoted_project_path_fails(self):
        found = codes(mutate(("hooks", "SubagentStop", 0, "hooks", 0, "command"), "bash $CLAUDE_PROJECT_DIR/plan.sh"))
        self.assertEqual(["unquoted-path"], found)

    def test_blocking_policy_without_on_failure_fails(self):
        for event, index in (("PreToolUse", 1), ("UserPromptSubmit", 0)):
            settings = copy.deepcopy(COMPLIANT)
            del settings["hooks"][event][0]["hooks"][index]["onFailure"]
            self.assertEqual(["missing-on-failure"], codes(settings), event)
        settings = copy.deepcopy(COMPLIANT)
        del settings["hooks"]["UserPromptExpansion"][0]["hooks"][0]["onFailure"]
        self.assertEqual(["missing-on-failure"], codes(settings))

    def test_invalid_on_failure_value_fails(self):
        found = codes(mutate(("hooks", "PreToolUse", 1, "hooks", 0, "onFailure"), "deny"))
        self.assertEqual(["invalid-on-failure"], found)

    def test_on_failure_block_without_effect_is_rejected(self):
        found = codes(mutate(("hooks", "SubagentStop", 0, "hooks", 0, "onFailure"), "block"))
        self.assertEqual(["on-failure-no-effect"], found)
        background = {"type": "command", "command": GATE, "onFailure": "block", "async": True}
        self.assertIn("on-failure-no-effect", codes(mutate(("hooks", "UserPromptSubmit", 0, "hooks", 0), background)))

    def test_matcher_drops_multiedit_and_covers_powershell(self):
        found = codes(mutate(("hooks", "PreToolUse", 0, "matcher"), "Write|Edit|MultiEdit|NotebookEdit|Bash"))
        self.assertEqual(["removed-tool", "shell-coverage"], found)

    def test_exec_form_only_for_node_with_anchored_args(self):
        python_exec = {"type": "command", "command": "python3", "args": ["${CLAUDE_PROJECT_DIR}/g.py"], "onFailure": "block"}
        self.assertEqual(["exec-form"], codes(mutate(("hooks", "PreToolUse", 1, "hooks", 0), python_exec)))
        relative = {"type": "command", "command": "node", "args": ["scripts/g.mjs"], "onFailure": "block"}
        self.assertEqual(["relative-path"], codes(mutate(("hooks", "PreToolUse", 1, "hooks", 0), relative)))
        plain_var = {"type": "command", "command": "node", "args": ["$CLAUDE_PROJECT_DIR/g.mjs"], "onFailure": "block"}
        self.assertEqual(["relative-path"], codes(mutate(("hooks", "PreToolUse", 1, "hooks", 0), plain_var)))

    def test_d26_relative_read_rules_fail_in_deny_and_allow(self):
        settings = mutate(("permissions", "deny"), ["Read(.env)", "Read(**/.env)", "Read(secrets/**)", "Edit(docs/**)"])
        self.assertEqual(["unanchored-path-rule"] * 4, codes(settings))
        settings = mutate(("permissions", "allow"), ["Read", "Read(**/*.example)", "Bash(npm:*)"])
        self.assertEqual(["unanchored-path-rule"], codes(settings))

    def test_structural_errors_are_findings(self):
        self.assertEqual(["invalid-settings"], codes([]))
        self.assertEqual(["invalid-hooks"], codes({"hooks": {"PreToolUse": {}}}))


class VersionGateTests(unittest.TestCase):
    """D18.5: below Claude Code 2.1.295 onFailure is not honoured."""

    def test_versions_are_classified(self):
        self.assertEqual("OK", hook_check.version_report("2.1.326 (Claude Code)", None)["status"])
        self.assertEqual("OK", hook_check.version_report("2.1.295 (Claude Code)", "codex-cli 0.169.0")["status"])
        self.assertEqual("BELOW_MINIMUM", hook_check.version_report("2.1.294 (Claude Code)", None)["status"])
        self.assertEqual("BELOW_MINIMUM", hook_check.version_report("1.9.999", None)["status"])
        self.assertEqual("NOT_VERIFIED", hook_check.version_report(None, None)["status"])
        self.assertEqual("NOT_VERIFIED", hook_check.version_report("Claude Code", None)["status"])

    def test_cli_exit_codes_and_message(self):
        for text, code, marker in (("2.1.326 (Claude Code)", 0, "OK:"), ("2.1.200 (Claude Code)", 1, "WARN:"),
                                   ("garbage", 3, "NOT_VERIFIED:")):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(code, hook_check.main(["version", "--claude-version", text]))
            self.assertIn(marker, out.getvalue())
            self.assertIn("2.1.295", out.getvalue())
            self.assertIn("Codex CLI:", out.getvalue())

    def test_settings_cli_reports_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(json.dumps(mutate(("permissions", "deny"), ["Read(.env)"])), encoding="utf-8")
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(1, hook_check.main(["settings", "--settings", str(path)]))
            self.assertIn("unanchored-path-rule", out.getvalue())
            path.write_text(json.dumps(COMPLIANT), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, hook_check.main(["settings", "--settings", str(path)]))
            path.write_text("{", encoding="utf-8")
            self.assertEqual(2, hook_check.main(["settings", "--settings", str(path)]))


GUARD_SOURCE = '''import json, sys
payload = json.load(sys.stdin)
name = payload["tool_input"].get("file_path", "").replace("\\\\", "/").split("/")[-1]
sys.exit(2 if name == "protected.txt" else 0)
'''
NODE_GUARD_SOURCE = '''import { readFileSync } from 'node:fs';
const payload = JSON.parse(readFileSync(0, 'utf8'));
process.exitCode = (payload.tool_input.file_path || '').endsWith('protected.txt') ? 2 : 0;
'''


@unittest.skipIf(os.name == "nt", "emulates the POSIX shell form; Windows is accepted manually")
@unittest.skipUnless(shutil.which("bash"), "bash is required for the shell form")
class HookExecutionTests(unittest.TestCase):
    """§21.2 criterion fixtures: the hook runs from a subdirectory and without `python`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        (self.project / "backend").mkdir(parents=True)
        (self.project / "scripts/policy").mkdir(parents=True)
        (self.project / "scripts/policy/guard.py").write_text(GUARD_SOURCE, encoding="utf-8")
        (self.project / "scripts/policy/guard.mjs").write_text(NODE_GUARD_SOURCE, encoding="utf-8")
        # PATH bez `python`: tylko python3 (dowiązanie do bieżącego interpretera).
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        (self.bin / "python3").symlink_to(sys.executable)
        self.bash = shutil.which("bash")
        self.edit = {"tool_name": "Edit", "tool_input": {"file_path": "protected.txt"}}
        self.other = {"tool_name": "Edit", "tool_input": {"file_path": "notes.txt"}}

    def tearDown(self):
        self.tmp.cleanup()

    def run_from_backend(self, handler: dict, payload: dict, path: str, extra: dict | None = None) -> str:
        environ = {"PATH": path, **(extra or {})}
        return hook_check.run_hook(handler, project_dir=self.project, cwd=self.project / "backend",
                                   payload=payload, environ=environ, bash=self.bash)

    def test_guard_blocks_protected_edit_from_subdirectory_without_python(self):
        self.assertIsNone(shutil.which("python", path=str(self.bin)))
        handler = COMPLIANT["hooks"]["PreToolUse"][0]["hooks"][1]
        self.assertEqual("deny", self.run_from_backend(handler, self.edit, str(self.bin)))
        self.assertEqual("allow", self.run_from_backend(handler, self.other, str(self.bin)))

    def test_ai_python_works_with_no_python_on_path(self):
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        handler = COMPLIANT["hooks"]["PreToolUse"][0]["hooks"][1]
        self.assertEqual("deny", self.run_from_backend(handler, self.edit, str(empty), {"AI_PYTHON": sys.executable}))
        # Bez AI_PYTHON i bez python3 hook nie startuje: fail-closed blokuje akcję.
        self.assertEqual("block", self.run_from_backend(handler, self.edit, str(empty)))

    def test_old_relative_python_style_blocks_everything_after_cd(self):
        # `python3 brak.py` kończy się kodem 2, a 2 to dla Claude Code blokada: po cd każda edycja stoi.
        legacy = {"type": "command", "command": "python3 scripts/policy/guard.py"}
        self.assertEqual("deny", self.run_from_backend(legacy, self.other, str(self.bin)))
        self.assertIn("relative-path", codes(mutate(("hooks", "PreToolUse", 0, "hooks", 1), legacy)))

    def test_missing_python_script_exits_two(self):
        (self.project / "scripts/policy/guard.py").rename(self.project / "scripts/policy/guard.py.off")
        handler = dict(COMPLIANT["hooks"]["PreToolUse"][0]["hooks"][1])
        handler.pop("onFailure")
        self.assertEqual("deny", self.run_from_backend(handler, self.other, str(self.bin)))

    def test_missing_shell_script_blocks_only_with_on_failure(self):
        handler = {"type": "command", "command": 'bash "$CLAUDE_PROJECT_DIR/scripts/policy/absent.sh"',
                   "onFailure": "block"}
        self.assertEqual("block", self.run_from_backend(handler, self.other, os.environ.get("PATH", "")))
        handler.pop("onFailure")
        self.assertEqual("error", self.run_from_backend(handler, self.other, os.environ.get("PATH", "")))

    @unittest.skipUnless(shutil.which("node"), "node is required for the exec form")
    def test_node_exec_form_from_subdirectory(self):
        node_dir = Path(self.tmp.name) / "nodebin"
        node_dir.mkdir()
        (node_dir / "node").symlink_to(shutil.which("node"))
        handler = COMPLIANT["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual("deny", self.run_from_backend(handler, self.edit, str(node_dir)))
        self.assertEqual("allow", self.run_from_backend(handler, self.other, str(node_dir)))
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        self.assertEqual("block", self.run_from_backend(handler, self.edit, str(empty)))
        # Stary styl node: po cd skrypt nie istnieje, node kończy się kodem 1 — bez onFailure akcja przechodzi.
        legacy = {"type": "command", "command": "node scripts/policy/guard.mjs"}
        self.assertEqual("error", self.run_from_backend(legacy, self.edit, str(node_dir)))
        (self.project / "scripts/policy/guard.mjs").rename(self.project / "scripts/policy/guard.mjs.off")
        self.assertEqual("block", self.run_from_backend(handler, self.other, str(node_dir)))


if __name__ == "__main__":
    unittest.main()
