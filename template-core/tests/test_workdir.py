"""D17 fixtures: a session on a Windows drive mounted into WSL is blocked without permission."""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import workdir

SCRIPT = ROOT / "scripts/ai/workdir.py"
# Fragment prawdziwego mountinfo z WSL2: ext4 dla /, 9p dla /mnt/d, drvfs pod niestandardowym rootem.
MOUNTINFO = "\n".join((
    "60 1 8:32 / / rw,relatime - ext4 /dev/sdc rw,discard",
    "80 60 0:58 / /mnt/d rw,noatime - 9p drvfs rw,aname=drvfs;path=D:\\",
    "81 60 0:59 / /win/e rw,noatime - drvfs E:\\ rw",
    "82 60 0:60 / /mnt/wsl rw,relatime - tmpfs none rw",
    "83 60 0:61 / /home/dev/my\\040data rw - ext4 /dev/sdd rw",
))


def check(path: str, environ: dict | None = None, platform: str = "linux") -> dict:
    """Classify a fake path with the fixture mount table."""
    return workdir.state(Path(path), environ=environ or {}, platform=platform, mountinfo=MOUNTINFO)


class WorkdirStateTests(unittest.TestCase):
    """Pure classification: no filesystem, Git or network access."""

    def test_mnt_without_permission_is_blocked_with_checklist(self):
        report = check("/mnt/d/Dev/shop")
        self.assertEqual(("windows-mount", "9p", True, False),
                         (report["location"], report["fstype"], report["blocked"], report["allowed"]))
        text = workdir.message(report)
        self.assertIn("BLOCKED (D17)", text)
        self.assertIn("ALLOW_MNT_SESSION=1", text)
        self.assertIn(f"{len(workdir.CHECKLIST)}. ", text)
        self.assertEqual(8, len(workdir.CHECKLIST))

    def test_permission_is_only_the_exact_value_one(self):
        for value in ("0", "yes", "true", ""):
            self.assertTrue(check("/mnt/c/x", {"ALLOW_MNT_SESSION": value})["blocked"], value)
        report = check("/mnt/c/x", {"ALLOW_MNT_SESSION": "1"})
        self.assertEqual((False, True), (report["blocked"], report["allowed"]))
        self.assertIn("allowed this session", workdir.message(report))

    def test_ext4_and_other_linux_mounts_pass_silently(self):
        for path in ("/home/dev/src/shop", "/mnt/wsl/shared", "/home/dev/my data/shop"):
            report = check(path)
            self.assertEqual(("linux", False), (report["location"], report["blocked"]), path)
            self.assertEqual("", workdir.message(report))

    def test_drvfs_under_custom_automount_root_is_detected(self):
        report = check("/win/e/projects/shop")
        self.assertEqual(("windows-mount", "drvfs", True), (report["location"], report["fstype"], report["blocked"]))

    def test_path_rule_holds_without_a_readable_mount_table(self):
        report = workdir.state(Path("/mnt/d/x"), environ={}, platform="linux", mountinfo="")
        self.assertTrue(report["blocked"])

    def test_native_windows_and_macos_are_out_of_scope(self):
        for platform in ("win32", "darwin"):
            report = check("/mnt/d/x", platform=platform)
            self.assertEqual(("other-os", False), (report["location"], report["blocked"]))


class WorkdirCliTests(unittest.TestCase):
    """The CLI on the real machine: the fixture root is a native temp/checkout path."""

    def run_cli(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(ROOT), *args],
                              capture_output=True, text=True, encoding="utf-8", env=env, check=False)

    def test_cli_on_native_path_exits_zero_in_both_modes(self):
        if workdir.state(ROOT)["location"] == "windows-mount":
            self.skipTest("checkout itself lives on a Windows mount")
        self.assertEqual((0, ""), (self.run_cli().returncode, self.run_cli().stdout))
        self.assertEqual(0, self.run_cli("--hook").returncode)
        self.assertIn('"blocked": false', self.run_cli("--json").stdout)

    def test_hook_mode_blocks_with_exit_two_on_stderr(self):
        report = check("/mnt/d/shop")
        original = workdir.state
        try:
            workdir.state = lambda root: report
            with mock.patch.object(sys, "argv", ["workdir.py", "--hook"]), \
                 mock.patch("sys.stderr") as stderr:
                self.assertEqual(workdir.HOOK_BLOCK_EXIT, workdir.main())
            self.assertIn("BLOCKED (D17)", "".join(call.args[0] for call in stderr.write.call_args_list))
            with mock.patch.object(sys, "argv", ["workdir.py"]), \
                 mock.patch("sys.stdout") as stdout:
                self.assertEqual(1, workdir.main())
            self.assertIn("Move checklist", "".join(call.args[0] for call in stdout.write.call_args_list))
        finally:
            workdir.state = original


if __name__ == "__main__":
    unittest.main()
