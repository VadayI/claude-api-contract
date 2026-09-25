"""Exercise project-state fallback and lossless legacy migration fixtures."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import project_state


class ProjectStateTests(unittest.TestCase):
    """Use disposable repository trees; fixtures perform no Git/network/DB I/O."""

    def setUp(self):
        """Create a temporary repository root and register its cleanup."""
        self.temp = tempfile.TemporaryDirectory(prefix="project state ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_legacy(self, name: str, content: str) -> Path:
        """Write one test-only legacy artifact and return its path.

        Args:
            name: Allowlisted artifact basename.
            content: Fixture text to write.
        Returns:
            The legacy path beneath the disposable temporary root.
        Side effects:
            Creates test directories/files only; no database, Git or network.
        """
        path = self.root / ".claude/memory" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_reads_legacy_until_canonical_state_exists(self):
        """Resolver reads an old registry but directs future writes through migration."""
        legacy = self.write_legacy("routes.json", '[{"path":"/home"}]\n')

        self.assertEqual(project_state.resolve_state(self.root, "routes.json"), legacy)
        with self.assertRaisesRegex(ValueError, "Migrate legacy state"):
            project_state.writable_state_path(self.root, "routes.json")

    def test_canonical_state_is_used_without_legacy_copy(self):
        """New projects resolve project state from the canonical directory."""
        canonical = self.root / "docs/project-state/routes.json"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("[]\n", encoding="utf-8")

        self.assertEqual(project_state.resolve_state(self.root, "routes.json"), canonical)
        self.assertEqual(project_state.writable_state_path(self.root, "routes.json"), canonical)

    def test_conflicting_copies_fail_without_using_timestamps(self):
        """Differing legacy and canonical bytes require an explicit human merge."""
        self.write_legacy("endpoints.json", "[]\n")
        canonical = self.root / "docs/project-state/endpoints.json"
        canonical.parent.mkdir(parents=True)
        canonical.write_text('[{"path":"/v1"}]\n', encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "Conflicting state copies"):
            project_state.resolve_state(self.root, "endpoints.json")
        report = project_state.plan_migration(self.root)
        self.assertEqual(len(report["conflicts"]), 1)

    def test_preview_is_read_only_and_reports_unknown_files(self):
        """Preview classifies known files while leaving unknown memory untouched."""
        legacy = self.write_legacy("pages.json", "[]\n")
        unknown = self.write_legacy("custom-notes.md", "keep me\n")

        report = project_state.plan_migration(self.root)

        self.assertEqual(report["actions"][0]["status"], "copy")
        self.assertEqual(report["unknown"], ["custom-notes.md"])
        self.assertTrue(legacy.exists())
        self.assertFalse((self.root / "docs/project-state/pages.json").exists())
        self.assertEqual(unknown.read_text(encoding="utf-8"), "keep me\n")

    def test_apply_migrates_project_and_runtime_state_idempotently(self):
        """Apply moves known files, preserves bytes and removes only verified sources."""
        registry = self.write_legacy("routes.json", '[{"path":"/home"}]\n')
        runtime = self.write_legacy("env-detect.json", '{"platform":"test"}\n')
        runtime_bytes = runtime.read_bytes()

        report = project_state.apply_migration(self.root)

        self.assertEqual(report["actions"], [])
        self.assertFalse(registry.exists())
        self.assertFalse(runtime.exists())
        self.assertEqual((self.root / "docs/project-state/routes.json").read_text(encoding="utf-8"),
                         '[{"path":"/home"}]\n')
        self.assertEqual((self.root / ".ai-runtime/env-detect.json").read_bytes(), runtime_bytes)
        self.assertFalse((self.root / ".ai-runtime/environment.json").exists())
        self.assertEqual(project_state.apply_migration(self.root)["actions"], [])

    def test_apply_removes_identical_duplicate_after_reviewed_migration(self):
        """An identical preexisting canonical file permits safe legacy cleanup."""
        legacy = self.write_legacy("pages.json", "[]\n")
        canonical = self.root / "docs/project-state/pages.json"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("[]\n", encoding="utf-8")

        report = project_state.apply_migration(self.root)

        self.assertEqual(report["actions"], [])
        self.assertFalse(legacy.exists())

    def test_conflict_does_not_block_other_allowlisted_artifact(self):
        """Migration skips only the conflicting artifact and moves safe peers."""
        self.write_legacy("routes.json", '[{"legacy":true}]\n')
        self.write_legacy("pages.json", "[]\n")
        canonical = self.root / "docs/project-state/routes.json"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("[]\n", encoding="utf-8")

        report = project_state.apply_migration(self.root)

        self.assertEqual([item["artifact"] for item in report["conflicts"]], ["routes.json"])
        self.assertTrue((self.root / ".claude/memory/routes.json").exists())
        self.assertFalse((self.root / ".claude/memory/pages.json").exists())
        self.assertTrue((self.root / "docs/project-state/pages.json").exists())

    def test_invalid_json_is_not_migrated(self):
        """Malformed or ambiguous state stays in place and is reported."""
        legacy = self.write_legacy("endpoints.json", '{"duplicate":1,"duplicate":2}\n')

        report = project_state.apply_migration(self.root)

        self.assertEqual(len(report["invalid"]), 1)
        self.assertTrue(legacy.exists())
        self.assertFalse((self.root / "docs/project-state/endpoints.json").exists())

    def test_unknown_artifact_cannot_be_resolved_automatically(self):
        """A basename outside the migration map fails closed."""
        with self.assertRaisesRegex(ValueError, "Unknown project state artifact"):
            project_state.resolve_state(self.root, "custom.json")

    def test_jsonl_records_are_validated_before_runtime_migration(self):
        """Malformed command-log rows are reported without creating runtime output."""
        legacy = self.write_legacy("command-log.jsonl", '{bad json}\n')

        report = project_state.apply_migration(self.root)

        self.assertEqual(len(report["invalid"]), 1)
        self.assertTrue(legacy.exists())
        self.assertFalse((self.root / ".ai-runtime/command-log.jsonl").exists())

    def test_runtime_migration_leaves_project_registries_and_unknown_files(self):
        """A runtime writer moves only its own disposable records."""
        registry = self.write_legacy("routes.json", "[]\n")
        unknown = self.write_legacy("notes.md", "keep\n")
        self.write_legacy("command-log.jsonl", '{"ts":"1","cmd":"/x","args":""}\n')

        report = project_state.migrate_runtime(self.root)

        self.assertEqual(report["actions"], [])
        self.assertEqual(report["unknown"], ["notes.md"])
        self.assertTrue(registry.exists())
        self.assertTrue(unknown.exists())
        self.assertFalse((self.root / ".claude/memory/command-log.jsonl").exists())
        self.assertEqual((self.root / ".ai-runtime/command-log.jsonl").read_text(encoding="utf-8"),
                         '{"ts":"1","cmd":"/x","args":""}\n')
        self.assertFalse((self.root / "docs/project-state/routes.json").exists())
        with self.assertRaisesRegex(ValueError, "Unknown state category"):
            project_state.apply_migration(self.root, ("secrets",))

    def test_runtime_conflict_is_reported_and_blocks_only_that_writer(self):
        """Differing runtime copies never pick a winner; the writer must refuse."""
        self.write_legacy("env-detect.json", '{"platform":"old"}\n')
        canonical = self.root / ".ai-runtime/env-detect.json"
        canonical.parent.mkdir(parents=True)
        canonical.write_text('{"platform":"new"}\n', encoding="utf-8")

        report = project_state.migrate_runtime(self.root)

        self.assertEqual([item["artifact"] for item in report["conflicts"]], ["env-detect.json"])
        self.assertEqual(canonical.read_text(encoding="utf-8"), '{"platform":"new"}\n')
        with self.assertRaisesRegex(ValueError, "Migrate legacy state"):
            project_state.writable_state_path(self.root, "env-detect.json", "runtime")

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        """Run the module CLI against the disposable root in a subprocess.

        Args:
            arguments: CLI options appended after ``--root``.
        Returns:
            Exit code, stdout and stderr text.
        Side effects:
            Starts one local Python process; no Git, network or database use.
        """
        import subprocess

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/ai/project_state.py"), "--root", str(self.root), *arguments],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        return result.returncode, result.stdout, result.stderr

    def test_cli_resolves_readable_and_writable_paths_for_shell_consumers(self):
        """Shell and Node callers get root-relative POSIX paths from one resolver."""
        self.write_legacy("endpoints.json", "[]\n")

        code, out, _ = self.run_cli("--resolve", "endpoints.json")
        self.assertEqual((code, out.strip()), (0, ".claude/memory/endpoints.json"))
        code, out, _ = self.run_cli("--resolve", "pages.json")
        self.assertEqual((code, out.strip()), (0, "docs/project-state/pages.json"))
        code, out, _ = self.run_cli("--resolve", "command-log.jsonl", "--category", "runtime")
        self.assertEqual((code, out.strip()), (0, ".ai-runtime/command-log.jsonl"))
        code, _, err = self.run_cli("--writable", "endpoints.json")
        self.assertEqual(code, 2)
        self.assertIn("Migrate legacy state", err)
        code, out, _ = self.run_cli("--writable", "env-detect.json", "--category", "runtime")
        self.assertEqual((code, out.strip()), (0, ".ai-runtime/env-detect.json"))
        code, _, err = self.run_cli("--resolve", "custom.json")
        self.assertEqual(code, 2)
        self.assertIn("Unknown project state artifact", err)

    def test_interrupted_copy_rolls_back_partial_canonical_and_keeps_legacy(self):
        """A write failure removes the partial canonical file and leaves legacy intact."""
        from unittest import mock

        legacy = self.write_legacy("routes.json", '[{"path":"/home"}]\n')
        canonical = self.root / "docs/project-state/routes.json"

        with mock.patch.object(project_state.os, "fsync", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                project_state.apply_migration(self.root)

        self.assertFalse(canonical.exists())
        self.assertEqual(legacy.read_text(encoding="utf-8"), '[{"path":"/home"}]\n')
        # Powtórzenie po usunięciu przyczyny kończy migrację bez śladów częściowego zapisu.
        report = project_state.apply_migration(self.root)
        self.assertEqual((report["actions"], report["conflicts"]), ([], []))
        self.assertFalse(legacy.exists())
        self.assertEqual(canonical.read_text(encoding="utf-8"), '[{"path":"/home"}]\n')

    def test_cli_runtime_migration_ignores_unknown_files_in_exit_code(self):
        """``--migrate-runtime`` succeeds for a writer even when odd legacy files remain."""
        self.write_legacy("env-detect.json", '{"platform":"test"}\n')
        self.write_legacy("notes.md", "keep\n")

        code, out, _ = self.run_cli("--migrate-runtime")

        self.assertEqual(code, 0, out)
        self.assertTrue((self.root / ".ai-runtime/env-detect.json").exists())
        code, out, _ = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn('"notes.md"', out)


if __name__ == "__main__":
    unittest.main()
