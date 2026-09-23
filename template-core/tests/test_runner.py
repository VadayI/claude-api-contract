"""Behavioral tests for the environment detector and exact-candidate runner."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import detector
import runner
from schema import check_schema, load_json, validate


class RunnerTests(unittest.TestCase):
    """Exercise exact Git isolation, result states, schemas and invalidation."""

    def setUp(self):
        """Create a disposable Git repository with one exact candidate commit.

        Args:
            self: Current unittest fixture.

        Returns:
            None.

        Raises:
            subprocess/file errors if the local Git fixture cannot be created.

        Side effects:
            Creates and commits synthetic files in a temporary repository only;
            no network, database, global Git configuration or user files are used.
        """
        self.temp = tempfile.TemporaryDirectory(prefix="runner fixture ")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo Україна"
        self.repo.mkdir()
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.repo / "tracked.txt").write_text("committed\n", encoding="utf-8")
        (self.repo / "check.py").write_text(
            "from pathlib import Path\n"
            "raise SystemExit(0 if Path('tracked.txt').read_text() == 'committed\\n' "
            "and not Path('foreign.tmp').exists() else 9)\n",
            encoding="utf-8",
        )
        self.git("add", "--", "tracked.txt", "check.py")
        self.git("commit", "-m", "fixture")
        self.candidate = self.git("rev-parse", "HEAD").stdout.strip()
        self.output = Path(self.temp.name) / "results" / "full.json"

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run a fixture-local Git command with literal argv.

        Args:
            *args: Git arguments scoped to the disposable repository.

        Returns:
            Successful completed process with captured text.

        Raises:
            subprocess.CalledProcessError on fixture setup/query failure.

        Side effects:
            May mutate only the disposable fixture repository during setup; no
            database, network, global config, stash or external working tree.
        """
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], capture_output=True, text=True,
            check=True, timeout=20, shell=False,
        )

    def catalog(self, checks: list[dict], invalidation: list[str] | None = None) -> Path:
        """Write a minimal reviewed catalog for one runner behavior fixture.

        Args:
            checks: Fully specified synthetic check records.
            invalidation: Optional candidate-relative invalidation inputs.

        Returns:
            Path to the temporary JSON catalog.

        Raises:
            Filesystem/JSON errors from the disposable fixture.

        Side effects:
            Writes one public synthetic JSON file; no subprocess, DB or network.
        """
        path = Path(self.temp.name) / "catalog.json"
        document = {
            "schema_version": 1,
            "catalog_id": "fixture.runner",
            "profile": "full",
            "invalidation_paths": invalidation or ["tracked.txt"],
            "checks": checks,
        }
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def check(self, identifier: str, argv: list[str], **changes: object) -> dict:
        """Build one complete synthetic check record with safe defaults.

        Args:
            identifier: Stable portable check ID.
            argv: Literal command argument vector.
            **changes: Explicit field overrides for the fixture scenario.

        Returns:
            JSON-serializable check mapping.

        Side effects:
            None; no filesystem, subprocess, database or network access.
        """
        result = {
            "id": identifier,
            "description": "Synthetic runner behavior",
            "argv": argv,
            "cwd": ".",
            "mandatory": True,
            "timeout_seconds": 20,
            "prerequisites": ["python"],
            "applicability": {"path_exists": "check.py"},
            "expected_artifacts": [],
            "dependencies": [],
            "allowed_side_effects": ["candidate_export", "evidence"],
        }
        result.update(changes)
        return result

    def test_exact_export_excludes_dirty_and_untracked_files(self):
        """Prove commands execute committed bytes, not the caller working tree.

        Args: self owns the fixture. Returns: None. Raises: AssertionError for
        candidate/index/status isolation regressions; process/I/O errors propagate.
        Side effects: Modifies synthetic tracked/untracked fixture files, runs one
        isolated Python check, and writes temporary evidence; no DB/network.
        """
        (self.repo / "tracked.txt").write_text("staged\n", encoding="utf-8")
        self.git("add", "--", "tracked.txt")
        (self.repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
        (self.repo / "foreign.tmp").write_text("foreign\n", encoding="utf-8")
        status_before = self.git("status", "--porcelain=v2", "--untracked-files=all").stdout
        index_before = self.git("write-tree").stdout
        catalog = self.catalog([self.check("fixture.isolation", ["{python}", "check.py"])])
        document, code = runner.run(self.repo, self.candidate, self.candidate, catalog, self.output)
        self.assertEqual((code, document["outcome"]), (0, "PASS"))
        self.assertEqual(document["checks"][0]["status"], "PASS")
        self.assertNotIn(
            document["digests"]["invalidation_files"]["tracked.txt"],
            {runner.digest_bytes(b"dirty\n"), runner.digest_bytes(b"dirty\r\n")},
        )
        self.assertTrue(all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in document["checks"][0]["evidence"]))
        self.assertEqual(self.git("status", "--porcelain=v2", "--untracked-files=all").stdout, status_before)
        self.assertEqual(self.git("write-tree").stdout, index_before)

    def test_missing_mandatory_prerequisite_is_not_verified_and_nonzero(self):
        """Require missing mandatory tooling to produce NOT_VERIFIED and exit 2.

        Args: self owns the fixture. Returns: None. Raises: AssertionError for
        incorrect status/exit behavior; temporary process/I/O errors propagate.
        Side effects: Exports the synthetic commit and writes a result; the missing
        command is not executed and no database/network is accessed.
        """
        check = self.check("fixture.missing", ["{python}", "check.py"], prerequisites=["definitely-missing-tool"])
        document, code = runner.run(self.repo, self.candidate, self.candidate, self.catalog([check]), self.output)
        self.assertEqual((code, document["outcome"]), (2, "NOT_VERIFIED"))
        self.assertEqual(document["checks"][0]["status"], "NOT_VERIFIED")

    def test_failure_precedes_missing_and_not_applicable_is_explicit(self):
        """Keep FAIL, NOT_VERIFIED and NOT_APPLICABLE distinct in one result.

        Args: self owns the fixture. Returns: None. Raises: AssertionError for
        status precedence regressions; temporary process/I/O errors propagate.
        Side effects: Runs one failing synthetic Python child and writes temporary
        evidence/results; no database or network interaction occurs.
        """
        fail = self.check("fixture.fail", ["{python}", "-c", "raise SystemExit(7)"])
        missing = self.check("fixture.missing", ["{python}", "check.py"], prerequisites=["definitely-missing-tool"])
        skipped = self.check("fixture.na", ["{python}", "check.py"], applicability={"path_exists": "absent.file"})
        document, code = runner.run(self.repo, self.candidate, self.candidate, self.catalog([fail, missing, skipped]), self.output)
        self.assertEqual((code, document["outcome"]), (1, "FAIL"))
        self.assertEqual([item["status"] for item in document["checks"]], ["FAIL", "NOT_VERIFIED", "NOT_APPLICABLE"])

    def test_abbreviated_or_nonancestor_revision_is_rejected(self):
        """Reject abbreviated candidates and an exact base outside ancestry.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when
        invalid revision/base input is accepted; fixture Git errors propagate.
        Side effects: Creates one orphan fixture commit locally; no checkout of the
        user's repository, database, network, or global configuration is involved.
        """
        with self.assertRaises(ValueError):
            runner.run(self.repo, self.candidate[:12], self.candidate, self.catalog([self.check("fixture.pass", ["{python}", "check.py"])]), self.output)
        self.git("checkout", "--orphan", "other")
        for path in (self.repo / "tracked.txt", self.repo / "check.py"):
            path.unlink()
        (self.repo / "other.txt").write_text("other\n")
        self.git("add", "-A")
        self.git("commit", "-m", "other")
        other = self.git("rev-parse", "HEAD").stdout.strip()
        with self.assertRaises(ValueError):
            runner.run(self.repo, self.candidate, other, self.catalog([self.check("fixture.pass", ["{python}", "check.py"])]), self.output)

    def test_detector_report_is_explicit_without_environment_values(self):
        """Report repository facts without copying a synthetic secret variable.

        Args: self owns the fixture. Returns: None. Raises: AssertionError for
        leaked values or missing Git facts; local fixture Git errors propagate.
        Side effects: Reads fixture Git metadata under a mocked tool inventory;
        no file writes, child version probes, database or network access.
        """
        with mock.patch.dict("os.environ", {"SYNTHETIC_SECRET": "must-not-appear"}, clear=False), mock.patch.object(
            detector, "tool_report", return_value={"python": {"status": "AVAILABLE", "version": "fixture"}}
        ):
            document = detector.report(self.repo)
        serialized = json.dumps(document)
        self.assertNotIn("SYNTHETIC_SECRET", serialized)
        self.assertNotIn("must-not-appear", serialized)
        self.assertEqual(document["repository"]["head"], self.candidate)

    def test_versioned_catalog_and_result_schemas_validate(self):
        """Validate the shipped catalog and one actual result with bundled schemas.

        Args: self owns the fixture. Returns: None. Raises: Schema/value/assertion
        errors when contracts or emitted results drift from the versioned format.
        Side effects: Runs one isolated passing fixture and reads bundled public
        schemas/catalogs; writes temporary result evidence, no DB/network.
        """
        catalog_schema = load_json(ROOT / "templates/ai/schemas/check-catalog.schema.json")
        result_schema = load_json(ROOT / "templates/ai/schemas/check-result.schema.json")
        for schema in (catalog_schema, result_schema):
            check_schema(schema)
        shipped = load_json(ROOT / "templates/ai/checks/contract.json")
        validate(shipped, catalog_schema)
        runner.validate_catalog(shipped)
        catalog = self.catalog([self.check("fixture.pass", ["{python}", "check.py"])])
        document, code = runner.run(self.repo, self.candidate, self.candidate, catalog, self.output)
        self.assertEqual(code, 0)
        validate(document, result_schema)

    def test_dependencies_and_evidence_redaction_are_fail_closed(self):
        """Reject forward dependencies and redact secrets/host paths in evidence.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when
        dependency validation or evidence sanitization fails; I/O errors propagate.
        Side effects: Runs one synthetic child that prints fake sensitive data and
        writes bounded temporary evidence; no actual secrets, DB or network access.
        """
        dependent = self.check("fixture.dependent", ["{python}", "check.py"], dependencies=["fixture.future"])
        future = self.check("fixture.future", ["{python}", "check.py"])
        with self.assertRaises(ValueError):
            runner.validate_catalog(json.loads(self.catalog([dependent, future]).read_text()))
        command = "print('TOKEN=fake-secret'); print('/tmp/private/path')"
        document, code = runner.run(
            self.repo, self.candidate, self.candidate,
            self.catalog([self.check("fixture.redact", ["{python}", "-c", command])]), self.output,
        )
        self.assertEqual(code, 0)
        evidence = self.output.parent / document["checks"][0]["evidence"][0]
        text = evidence.read_text(encoding="utf-8")
        self.assertNotIn("fake-secret", text)
        self.assertNotIn("/tmp/private/path", text)
        self.assertIn("<redacted>", text)
        self.assertIn("<external-path>", text)

    def test_archive_allows_only_the_public_env_example(self):
        """Permit public env documentation without allowing private env paths.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when
        path policy accepts a secret env path or rejects the literal public file.
        Side effects: None; no file, subprocess, database or network operation.
        """
        self.assertEqual(
            runner.safe_relative(".env.example", allow_env_example=True).as_posix(),
            ".env.example",
        )
        for name in (".env", ".env.local", "nested/.env.example"):
            with self.assertRaises(ValueError):
                runner.safe_relative(name, allow_env_example=True)


if __name__ == "__main__":
    unittest.main()
