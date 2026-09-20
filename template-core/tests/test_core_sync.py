"""Exercise immutable source delivery and fail-closed ownership boundaries."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/ai"))
import core_sync


class CoreSyncTests(unittest.TestCase):
    """Use temporary Git sources and independent project targets; no remote/DB."""

    def setUp(self):
        """Create a disposable committed payload; writes only within a temp directory."""
        self.temp = tempfile.TemporaryDirectory(prefix="core sync ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.target = self.root / "target"
        self.target.mkdir()
        self.core = self.source / "template-core"
        self.files = {"core.json": json.dumps({"schema_version": 1, "version": "0.1.0-dev", "source_repository": "https://example.invalid/core.git"}),
                      "scripts/ai/example.py": "print('first')\n", "README.md": "source documentation\n"}
        for name, text in self.files.items():
            path = self.core / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        manifest = self.core / core_sync.MANIFEST
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"schema_version": 1, "files": {
            name: {"sha256": core_sync.digest(text), "ownership": "template"}
            for name, text in self.files.items()}}), encoding="utf-8")
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("add", "--", "template-core")
        self.git("commit", "-qm", "fixture")
        self.commit = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        """Run fixture-local Git argv and return text; raise on failures; no network/DB."""
        return subprocess.check_output(["git", "-C", str(self.source), *args], text=True, encoding="utf-8", stderr=subprocess.PIPE)

    def install(self, metadata, files):
        """Apply a conflict-free fixture preview; write only temporary target files."""
        pending, conflicts = core_sync.preview(self.target, metadata, files)
        self.assertEqual(conflicts, [])
        for name, content in pending.items():
            path = self.target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def test_exact_commit_ignores_dirty_source_and_repeat_is_empty(self):
        """Dirty source cannot change pinned delivery; repeated preview writes nothing."""
        (self.core / "scripts/ai/example.py").write_text("uncommitted\n", encoding="utf-8")
        metadata, files = core_sync.payload(self.source, self.commit)
        self.assertEqual(files, {"scripts/ai/example.py": "print('first')\n"})
        self.install(metadata, files)
        self.assertEqual(core_sync.preview(self.target, metadata, files), ({}, []))
        self.assertEqual(core_sync.verify(self.target), [])

    def test_custom_file_conflicts_without_writes(self):
        """An unowned existing file prevents delivery without altering any target bytes."""
        metadata, files = core_sync.payload(self.source, self.commit)
        path = self.target / "scripts/ai/example.py"
        path.parent.mkdir(parents=True)
        path.write_text("project-owned", encoding="utf-8")
        pending, conflicts = core_sync.preview(self.target, metadata, files)
        self.assertEqual(conflicts, ["scripts/ai/example.py"])
        self.assertIn(core_sync.PIN, pending)
        self.assertEqual(path.read_text(encoding="utf-8"), "project-owned")
        self.assertFalse((self.target / core_sync.PIN).exists())

    def test_customized_installed_file_fails_drift_and_update(self):
        """Local customization is detectable and cannot be overwritten by a new pin."""
        metadata, files = core_sync.payload(self.source, self.commit)
        self.install(metadata, files)
        (self.target / "scripts/ai/example.py").write_text("local edit", encoding="utf-8")
        self.assertEqual(core_sync.verify(self.target), ["scripts/ai/example.py"])
        self.assertEqual(core_sync.preview(self.target, metadata, files)[1], ["scripts/ai/example.py"])

    def test_unchanged_template_updates_but_removed_files_survive(self):
        """An unchanged owned file may update; omission from source never deletes it."""
        metadata, files = core_sync.payload(self.source, self.commit)
        self.install(metadata, files)
        incoming = {"scripts/ai/example.py": "second\n"}
        self.assertEqual(core_sync.preview(self.target, metadata, incoming)[1], [])
        self.assertEqual(core_sync.preview(self.target, metadata, {})[1], ["scripts/ai/example.py"])
        self.assertTrue((self.target / "scripts/ai/example.py").is_file())

    def test_pinned_manifest_corruption_rejected(self):
        """A committed content edit without a corresponding digest is rejected."""
        (self.core / "scripts/ai/example.py").write_text("corrupt", encoding="utf-8")
        self.git("add", "--", "template-core/scripts/ai/example.py")
        self.git("commit", "-qm", "corrupt fixture")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            core_sync.payload(self.source, self.git("rev-parse", "HEAD").strip())

    def test_unsafe_paths_and_abbreviated_pin_rejected(self):
        """Reject traversal, secret names and nonexact revisions without writes."""
        for name in ("../escape", "C:/escape", "a\\b", ".env", "secrets/key", "./same", "a/../b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                core_sync.safe_name(name)
        with self.assertRaises(ValueError):
            core_sync.payload(self.source, self.commit[:8])

    def test_linked_target_rejected(self):
        """A linked destination cannot redirect writes outside its project; no DB."""
        link = self.root / "linked"
        try:
            link.symlink_to(self.target, target_is_directory=True)
        except OSError:
            self.skipTest("Host does not allow symbolic-link creation")
        with self.assertRaises(ValueError):
            core_sync.target_root(link / "child")

    def test_integrated_pin_requires_remote_main_ancestry(self):
        """Only commits reachable from actual remote main qualify; no remote mutation by verifier."""
        remote = self.root / "remote.git"
        self.git("init", "--bare", "-q", str(remote))
        self.git("push", str(remote), self.commit + ":refs/heads/main")
        metadata, _ = core_sync.payload(self.source, self.commit)
        metadata["source_repository"] = str(remote)
        integrated = core_sync.integrated_pin(self.source, metadata)
        self.assertEqual(integrated["pin_status"], "integrated")
        self.assertEqual(integrated["observed_upstream_main"], self.commit)
        self.git("commit", "--allow-empty", "-qm", "unintegrated fixture")
        metadata["source_commit"] = self.git("rev-parse", "HEAD").strip()
        with self.assertRaises(subprocess.CalledProcessError):
            core_sync.integrated_pin(self.source, metadata)

    def test_unavailable_integration_evidence_is_not_a_development_fallback(self):
        """Missing remote main fails instead of silently accepting an unverified pin."""
        remote = self.root / "empty.git"
        self.git("init", "--bare", "-q", str(remote))
        metadata, _ = core_sync.payload(self.source, self.commit)
        metadata["source_repository"] = str(remote)
        with self.assertRaises(subprocess.CalledProcessError):
            core_sync.integrated_pin(self.source, metadata)


if __name__ == "__main__":
    unittest.main()
