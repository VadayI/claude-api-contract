"""Behavioral fixtures for full rule delivery and conservative adapter generation."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE / "scripts/ai"))
import adapters
import generate_adapters as generator


class AdapterTests(unittest.TestCase):
    """Use isolated source trees; no agent/model, remote, credentials or database."""

    def setUp(self):
        """Create complete canonical fixture sources; return None, temporary writes only."""
        self.temp = tempfile.TemporaryDirectory(prefix="adapter fixture ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = {"schema_version": 1, "rules": [
            {"id": "full", "path": "docs/ai/rules/full.md", "scope": "role",
             "legacy_path": ".claude/rules/full.md", "dependencies": [],
             "explicit_consumers": ["audit"], "declared_consumers": []}],
            "roles": {"audit": {"path": "docs/ai/roles/audit.md", "rules": ["full"],
                                  "delivery": "role-pack", "read_only": True}},
            "workflows": {"custom-procedure": "docs/ai/workflows/custom.md"}}
        self.write("AGENTS.md", "Shared invariants\n")
        self.write("docs/ai/rules/full.md", "Full normative rule\n" + "Never omit this condition.\n" * 200)
        self.write("docs/ai/roles/audit.md", "Audit contract, read only.\n")
        self.write("docs/ai/workflows/custom.md", "Execute all steps.\n")
        self.save_catalog()

    def write(self, name, content):
        """Write UTF-8 fixture text under the temporary root; no external effects/DB."""
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    def save_catalog(self):
        """Serialize current fixture catalog; return None, temporary writes only."""
        self.write("docs/ai/catalog.json", json.dumps(self.catalog))

    def apply_fixture(self, legacy=False):
        """Apply a conflict-free fixture plan, asserting no conflicts; temp writes only."""
        pending, conflicts = generator.plan(self.root, legacy)
        self.assertEqual(conflicts, [])
        for name, text in pending.items():
            self.write(name, text)

    def test_full_pack_custom_workflow_and_read_only_role(self):
        """All source bytes/end markers and explicit custom reviewer restrictions survive."""
        rendered = adapters.outputs(self.root)
        pack = rendered["docs/ai/generated/role-packs/audit.md"]
        self.assertIn((self.root / "docs/ai/rules/full.md").read_text(encoding="utf-8"), pack)
        self.assertIn("<!-- SOURCE docs/ai/roles/audit.md SHA256", pack)
        self.assertTrue(pack.rstrip().endswith("<!-- END ROLE PACK audit -->"))
        self.assertIn('sandbox_mode = "read-only"', rendered[".codex/agents/audit.toml"])
        self.assertIn("tools: [Read, Glob, Grep]", rendered[".claude/agents/audit.md"])
        self.assertIn(".agents/skills/custom-procedure/SKILL.md", rendered)

    def test_preview_repeat_and_source_update(self):
        """Preview does not write, replay is empty, changed sources refresh owned packs."""
        pending, conflicts = generator.plan(self.root)
        self.assertFalse((self.root / "CLAUDE.md").exists())
        self.assertTrue(pending)
        self.assertEqual(conflicts, [])
        self.apply_fixture()
        self.assertEqual(generator.plan(self.root), ({}, []))
        self.write("docs/ai/rules/full.md", "Updated full rule\n")
        pending, conflicts = generator.plan(self.root)
        self.assertEqual(conflicts, [])
        self.assertIn("docs/ai/generated/role-packs/audit.md", pending)

    def test_conflicting_apply_writes_nothing(self):
        """Customized output prevents every CLI write, including planned new files."""
        self.apply_fixture()
        self.write(".codex/agents/audit.toml", "project customization\n")
        self.write("docs/ai/rules/full.md", "New source\n")
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = subprocess.run([sys.executable, str(CORE / "scripts/ai/generate_adapters.py"),
                                 "--root", str(self.root), "--apply"], capture_output=True, check=False)
        self.assertEqual(result.returncode, 1)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_project_claude_and_removed_outputs_preserved(self):
        """Mixed root instructions and stale generated files require reconciliation."""
        self.write("CLAUDE.md", "Project instructions\n")
        self.assertIn("CLAUDE.md", generator.plan(self.root)[1])
        self.write("CLAUDE.md", adapters.outputs(self.root)["CLAUDE.md"])
        self.apply_fixture()
        self.catalog["workflows"] = {}
        self.save_catalog()
        self.assertIn(".agents/skills/custom-procedure/SKILL.md", generator.plan(self.root)[1])
        self.assertTrue((self.root / ".agents/skills/custom-procedure/SKILL.md").exists())

    def test_legacy_import_requires_explicit_flag_and_exact_digest(self):
        """Only unchanged legacy template files are adoptable, and only explicitly."""
        name = ".claude/agents/audit.md"
        self.write(name, "Old generated adapter\n")
        self.write(generator.LEGACY, json.dumps({"schema_version": 1, "files": {
            name: {"ownership": "template", "sha256": generator.digest("Old generated adapter\n")}}}))
        self.assertIn(name, generator.plan(self.root)[1])
        self.assertEqual(generator.plan(self.root, True)[1], [])
        self.write(name, "Locally changed adapter\n")
        self.assertIn(name, generator.plan(self.root, True)[1])

    def test_unsafe_identifier_and_coordinator_leak_rejected(self):
        """Traversal role names and direct worker inclusion of coordinator rules fail."""
        self.catalog["rules"][0]["scope"] = "coordinator-only"
        self.save_catalog()
        with self.assertRaisesRegex(ValueError, "Coordinator"):
            adapters.outputs(self.root)
        self.catalog["rules"][0]["scope"] = "role"
        self.catalog["workflows"]["../../escape"] = "docs/ai/workflows/custom.md"
        self.save_catalog()
        with self.assertRaisesRegex(ValueError, "identifier"):
            adapters.outputs(self.root)


if __name__ == "__main__":
    unittest.main()
