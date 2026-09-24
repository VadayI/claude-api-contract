"""Exercise Claude PreToolUse payload parser as early policy feedback."""

import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts/policy/claude_edit_guard.mjs"


class ClaudeEditGuardTests(unittest.TestCase):
    """Verify known tool payload shapes without claiming shell coverage."""

    def probe(self, payload: dict | str) -> subprocess.CompletedProcess[str]:
        """Run the reviewed Node parser on one synthetic Claude payload.

        Args: payload is a JSON object or intentionally malformed raw text.
        Returns: Completed Node process with exit code and diagnostic text.
        Raises: OSError if Node cannot start.
        Side effects: One local Node subprocess; no DB, network, or file writes.
        Business rule: Exit two blocks an affected tool invocation early.
        """
        data = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(["node", str(GUARD)], input=data, capture_output=True,
                              text=True, encoding="utf-8", check=False)

    def test_write_and_windows_path(self):
        """Block root artifact edits through POSIX or Windows paths.

        Args: None; synthetic Write/Edit payloads.
        Returns: None after protected and ordinary file assertions.
        Raises: AssertionError on parser underreach or false block.
        Side effects: Local Node subprocesses only; no DB/network/writes.
        """
        for path in ("openapi.yml", "C:\\work\\contract\\openapi.yml"):
            self.assertEqual(self.probe({"tool_name": "Write", "tool_input": {"file_path": path}}).returncode, 2)
        self.assertEqual(self.probe({"tool_name": "Edit", "tool_input":
                                     {"file_path": "spec/models.tsp"}}).returncode, 0)

    def test_patch_rename_delete_and_multiple_files(self):
        """Inspect patch headers, rename destinations, and multi-file lists.

        Args: None; synthetic Bash apply_patch and MultiEdit payloads.
        Returns: None after every protected-path shape blocks.
        Raises: AssertionError if one changed file escapes early feedback.
        Side effects: Local Node subprocesses only; no DB/network/writes.
        """
        patches = (
            "apply_patch <<'PATCH'\n*** Begin Patch\n*** Delete File: openapi.yml\n*** End Patch\nPATCH",
            "apply_patch <<'PATCH'\n*** Begin Patch\n*** Move to: C:\\repo\\openapi.yml\n*** End Patch\nPATCH",
            "apply_patch <<'PATCH'\n*** Begin Patch\n*** Update File: spec/main.tsp\n*** Update File: openapi.yml\n*** End Patch\nPATCH",
        )
        for command in patches:
            self.assertEqual(self.probe({"tool_name": "Bash", "tool_input": {"command": command}}).returncode, 2)
        multi = {"tool_name": "MultiEdit", "tool_input": {"files": [
            {"file_path": "spec/main.tsp"}, {"new_path": "openapi.yml"}]}}
        self.assertEqual(self.probe(multi).returncode, 2)

    def test_malformed_payload_fails_and_arbitrary_shell_is_out_of_scope(self):
        """Fail malformed edit payloads while stating shell coverage limit.

        Args: None; malformed JSON and unrelated Bash command fixture.
        Returns: None after fail-closed/limited-coverage assertions.
        Raises: AssertionError if malformed edits pass silently.
        Side effects: Local Node subprocesses only; no DB/network/writes.
        """
        self.assertEqual(self.probe("{").returncode, 2)
        self.assertEqual(self.probe({"tool_name": "Write", "tool_input": {}}).returncode, 2)
        shell = {"tool_name": "Bash", "tool_input": {"command": "printf x > openapi.yml"}}
        self.assertEqual(self.probe(shell).returncode, 0)


if __name__ == "__main__":
    unittest.main()
