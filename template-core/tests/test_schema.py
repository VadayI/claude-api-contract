"""Exercise policy rejection and catalog routing using isolated non-secret fixtures."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import schema


class SchemaTests(unittest.TestCase):
    """Validate schemas, policy invariants and reference integrity without a DB."""

    def setUp(self):
        """Load bundled schemas and create temporary paths; return None, no network/DB."""
        self.temp = tempfile.TemporaryDirectory(prefix="schema paths ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project_schema = schema.load_json(ROOT / "templates/ai/schemas/project.schema.json")
        self.catalog_schema = schema.load_json(ROOT / "templates/ai/schemas/catalog.schema.json")
        self.project = {
            "schema_version": 1, "template": {"kind": "react", "is_scaffold": False},
            "ci": {"execution": "local"}, "git": {"merge_policy": "user_command"},
            "orchestration": {"coordinator_read": "reported_files_only"},
            "maturity": {"stage": "poc"}, "features": ["frontend"], "deployment": {},
            "documentation": {"handoff": "docs/HANDOFF.md"},
            "contract": {"source": "repo_pin", "url": "https://example.invalid/openapi.yml",
                         "pin": "v1.0.0", "digest": "sha256:" + "a" * 64, "artifact": "vendor/openapi.yml"}}

    def test_schema_and_valid_project(self):
        """Valid explicit configuration passes without creating referenced project files."""
        for document in (self.project_schema, self.catalog_schema):
            schema.check_schema(document)
        schema.validate(self.project, self.project_schema)
        schema.project_links(self.project, self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_choice_unknown_stage_and_permission_escalation_rejected(self):
        """Missing CI, unknown maturity and merge/coordinator bypass all fail closed."""
        for section, key, value in (("ci", "execution", "automatic"),
                                     ("maturity", "stage", "unknown"),
                                     ("git", "merge_policy", "auto"),
                                     ("orchestration", "coordinator_read", "all"),
                                     ("template", "is_scaffold", 1)):
            candidate = copy.deepcopy(self.project)
            candidate[section][key] = value
            with self.subTest(section=section), self.assertRaises(ValueError):
                schema.validate(candidate, self.project_schema)
        del self.project["ci"]
        with self.assertRaises(ValueError):
            schema.validate(self.project, self.project_schema)

    def test_contract_provenance_and_secret_paths(self):
        """Missing provenance, URL credentials and escaping/secret paths never validate."""
        for key, value in (("pin", ""), ("digest", ""), ("url", "https://user:secret@example.invalid/x"),
                           ("url", "https://example.invalid/x?token=secret"),
                           ("artifact", "../outside"), ("artifact", ".env.local")):
            candidate = copy.deepcopy(self.project)
            candidate["contract"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                schema.project_links(candidate, self.root)

    def test_duplicate_keys_nonfinite_and_unsupported_keyword(self):
        """Ambiguous JSON and ignored validation constructs are rejected explicitly."""
        path = self.root / "input.json"
        for text in ('{"ci": 1, "ci": 2}', '{"number": NaN}'):
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                schema.load_json(path)
        for value in ({"type": "object", "$ref": "https://example.invalid/schema"},
                      {"type": "object", "properties": {"x": {"type": "string", "format": "uri"}}},
                      {"type": "object", "minLength": 2},
                      {"type": "object", "required": ["missing"], "additionalProperties": False}):
            with self.assertRaises(ValueError):
                schema.check_schema(value)

    def test_catalog_dependency_closure_and_coordinator_scope(self):
        """Workers need all worker dependencies, while D02 excludes coordinator inheritance."""
        (self.root / "rule.md").write_text("Full rule\n", encoding="utf-8")
        catalog = {"schema_version": 1, "rules": [
            {"id": name, "path": "rule.md", "scope": scope, "dependencies": dependencies,
             "explicit_consumers": [], "declared_consumers": []}
            for name, scope, dependencies in (("first", "role", ["second", "workflow"]),
                                               ("second", "role", []), ("workflow", "coordinator", []))],
            "roles": {"worker": {"path": "rule.md", "rules": ["first"], "delivery": "role-pack"}},
            "workflows": {"orchestrate": "rule.md"}}
        schema.validate(catalog, self.catalog_schema)
        with self.assertRaisesRegex(ValueError, "closure"):
            schema.catalog_links(catalog, self.root)
        catalog["roles"]["worker"]["rules"].append("second")
        schema.catalog_links(catalog, self.root)
        catalog["rules"].append(copy.deepcopy(catalog["rules"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            schema.catalog_links(catalog, self.root)

    def test_unknown_feature_and_altered_legacy_floor(self):
        """Capabilities and historical check floors cannot be silently weakened."""
        import readiness
        self.project["features"] = ["imaginary"]
        with self.assertRaises(ValueError):
            schema.project_links(self.project, self.root)
        self.project["features"] = []
        self.project["template"]["kind"] = "django"
        self.project["maturity"]["legacy"] = readiness.migrate_stage("MVP", "django")["legacy"]
        schema.project_links(self.project, self.root)
        self.project["maturity"]["legacy"]["required_checks"] = []
        with self.assertRaisesRegex(ValueError, "floor"):
            schema.project_links(self.project, self.root)


if __name__ == "__main__":
    unittest.main()
