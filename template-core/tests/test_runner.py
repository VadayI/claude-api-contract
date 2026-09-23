"""Behavioral tests for the environment detector and exact-candidate runner."""

import json
import os
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
        (self.repo / ".gitignore").write_text(".ai-runtime/\n", encoding="utf-8")
        self.git("add", "--", "tracked.txt", "check.py", ".gitignore")
        self.git("commit", "-m", "fixture")
        self.candidate = self.git("rev-parse", "HEAD").stdout.strip()
        self.output = self.repo / ".ai-runtime" / "full.json"

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
            "policy": {"allow_mandatory_not_applicable": False},
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
            "applicability": {"path_exists": "check.py", "missing_status": "NOT_VERIFIED"},
            "expected_artifacts": [],
            "dependencies": [],
            "allowed_side_effects": ["evidence"],
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
            document["digests"]["invalidation_files"]["tracked.txt"]["sha256"],
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
        skipped = self.check("fixture.na", ["{python}", "check.py"], applicability={"path_exists": "absent.file", "missing_status": "NOT_APPLICABLE"}, mandatory=False)
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
        command = (
            "print('GH_TOKEN=fake-token'); print('DATABASE_PASSWORD=fake-password'); "
            "print('Authorization: Bearer fake-bearer'); print('https://user:fake-url@example.invalid/path'); "
            "print('/tmp/private/path')"
        )
        document, code = runner.run(
            self.repo, self.candidate, self.candidate,
            self.catalog([self.check("fixture.redact", ["{python}", "-c", command])]), self.output,
        )
        self.assertEqual(code, 0)
        evidence = self.output.parent / document["checks"][0]["evidence"][0]
        text = evidence.read_text(encoding="utf-8")
        for secret in ("fake-token", "fake-password", "fake-bearer", "fake-url"):
            self.assertNotIn(secret, text)
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

    def test_mandatory_not_applicable_requires_explicit_catalog_policy(self):
        """Prevent an all-skipped mandatory catalog from producing PASS.

        Args: self owns the fixture. Returns: None. Raises: AssertionError for a
        fail-open mandatory applicability policy; temporary I/O errors propagate.
        Side effects: Writes one isolated NOT_APPLICABLE result beneath the
        fixture runtime; no database, network, or user repository mutation.
        """
        check = self.check(
            "fixture.absent", ["{python}", "check.py"],
            applicability={"path_exists": "absent.py", "missing_status": "NOT_APPLICABLE"},
        )
        document, code = runner.run(
            self.repo, self.candidate, self.candidate, self.catalog([check]), self.output,
        )
        self.assertEqual(document["checks"][0]["status"], "NOT_APPLICABLE")
        self.assertEqual((document["outcome"], code), ("NOT_VERIFIED", 2))

    def test_missing_mandatory_implementation_is_not_verified(self):
        """Treat a missing mandatory implementation path as missing evidence.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when a
        deleted gate implementation skips or passes; fixture Git errors propagate.
        Side effects: Commits deletion only in the disposable repository and
        writes isolated evidence; no database, network, or external repository.
        """
        self.git("rm", "check.py")
        self.git("commit", "-m", "remove gate")
        candidate = self.git("rev-parse", "HEAD").stdout.strip()
        check = self.check("fixture.missing-implementation", ["{python}", "check.py"])
        document, code = runner.run(self.repo, candidate, self.candidate, self.catalog([check]), self.output)
        self.assertEqual((document["checks"][0]["status"], document["outcome"], code), ("NOT_VERIFIED", "NOT_VERIFIED", 2))

    def test_each_check_receives_a_pristine_candidate_export(self):
        """Keep an earlier check mutation out of every dependent check export.

        Args: self owns the fixture. Returns: None. Raises: AssertionError if a
        later check observes prior mutations; process and temporary I/O may raise.
        Side effects: Mutates only a disposable per-check export and writes bounded
        evidence; source worktree/index, database, and network stay untouched.
        """
        mutate = self.check(
            "fixture.mutate", ["{python}", "-c", "open('tracked.txt','w').write('mutated\\n')"],
            allowed_side_effects=["candidate_export", "evidence"],
        )
        verify = self.check("fixture.verify-pristine", ["{python}", "check.py"], dependencies=["fixture.mutate"])
        document, code = runner.run(self.repo, self.candidate, self.candidate, self.catalog([mutate, verify]), self.output)
        self.assertEqual((code, [item["status"] for item in document["checks"]]), (0, ["PASS", "PASS"]))
        self.assertTrue(document["checks"][0]["candidate_export_mutated"])
        self.assertFalse(document["checks"][1]["candidate_export_mutated"])

    def test_existing_result_symlink_cannot_overwrite_external_file(self):
        """Reject predictable linked output before any check or evidence write.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when a
        link is followed; platforms denying fixture links skip this one assertion.
        Side effects: Creates a temporary link/sentinel only; no DB or network.
        """
        self.output.parent.mkdir(parents=True)
        sentinel = Path(self.temp.name) / "external sentinel.txt"
        sentinel.write_text("unchanged\n", encoding="utf-8")
        try:
            self.output.symlink_to(sentinel)
        except OSError as error:
            self.skipTest(f"Host does not permit fixture file links: {error}")
        with self.assertRaises(ValueError):
            runner.run(self.repo, self.candidate, self.candidate, self.catalog([self.check("fixture.pass", ["{python}", "check.py"])]), self.output)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged\n")

    def test_metacharacters_remain_single_literal_argv_values(self):
        """Preserve spaces, Unicode, shell syntax, quotes, and backslashes in argv.

        Args: self owns the fixture. Returns: None. Raises: AssertionError if
        cross-platform argv transport changes or evaluates any literal value.
        Side effects: Runs one isolated Python child and writes temporary evidence;
        no shell, database, network, or external filesystem access.
        """
        values = ["space Україна", ";", "$()", 'quote"value', r"C:\\path with space"]
        program = "import sys; raise SystemExit(0 if sys.argv[1:] == " + repr(values) + " else 8)"
        document, code = runner.run(
            self.repo, self.candidate, self.candidate,
            self.catalog([self.check("fixture.argv", ["{python}", "-c", program, *values])]), self.output,
        )
        self.assertEqual((code, document["checks"][0]["status"]), (0, "PASS"))

    def test_base_and_detector_changes_invalidate_result_identity(self):
        """Bind alternate exact bases and detector bytes into result identity.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when a
        base/module change leaves reusable identity unchanged; Git/I/O may raise.
        Side effects: Adds fixture commits, runs two isolated checks, and mocks one
        public module read; no database, network, or user repository change.
        """
        original_base = self.candidate
        (self.repo / "tracked.txt").write_text("committed two\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        self.git("commit", "-m", "second")
        candidate = self.git("rev-parse", "HEAD").stdout.strip()
        first, _ = runner.run(self.repo, candidate, original_base, self.catalog([self.check("fixture.pass", ["{python}", "-c", "raise SystemExit(0)"])]), self.output)
        second_output = self.repo / ".ai-runtime" / "second.json"
        second, _ = runner.run(self.repo, candidate, candidate, self.catalog([self.check("fixture.pass", ["{python}", "-c", "raise SystemExit(0)"])]), second_output)
        self.assertNotEqual(first["base"], second["base"])
        before = runner.runner_digests()
        original_read = Path.read_bytes
        def changed_read(path):
            """Return fixture-altered detector bytes for invalidation testing.

            Args:
                path: Path instance intercepted from ``runner_digests``.

            Returns:
                Original public bytes, with a suffix only for ``detector.py``.

            Raises:
                OSError: If the original fixture read fails.

            Side effects:
                Reads the same public files as the production helper; performs no
                writes, subprocesses, database operations, or network access.
            """
            content = original_read(path)
            return content + b"fixture" if path.name == "detector.py" else content
        with mock.patch.object(Path, "read_bytes", changed_read):
            after = runner.runner_digests()
        self.assertNotEqual(before["scripts/ai/detector.py"], after["scripts/ai/detector.py"])
        self.assertEqual(before["scripts/ai/runner.py"], after["scripts/ai/runner.py"])

    def test_timeout_is_fail_without_invented_exit_code(self):
        """Represent an executed timeout as FAIL with explicit timeout metadata.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when a
        timeout passes, becomes infrastructure NA, or invents a process exit code.
        Side effects: Starts and times out one isolated sleeping child, then writes
        bounded evidence; descendant cleanup remains a documented later limit.
        """
        check = self.check("fixture.timeout", ["{python}", "-c", "import time; time.sleep(5)"], timeout_seconds=1)
        document, code = runner.run(self.repo, self.candidate, self.candidate, self.catalog([check]), self.output)
        result = document["checks"][0]
        self.assertEqual((code, result["status"], result["timed_out"]), (1, "FAIL", True))
        self.assertNotIn("exit_code", result)

    def test_expected_artifact_requires_new_regular_content(self):
        """Reject stale expected artifacts and record newly generated file digests.

        Args: self owns the fixture. Returns: None. Raises: AssertionError if an
        unchanged preexisting artifact satisfies provenance or a new one lacks a
        digest. Side effects: Uses isolated exports/results only; no DB/network.
        """
        stale = self.check("fixture.stale", ["{python}", "-c", "raise SystemExit(0)"], expected_artifacts=["tracked.txt"])
        stale_doc, stale_code = runner.run(self.repo, self.candidate, self.candidate, self.catalog([stale]), self.output)
        self.assertEqual((stale_code, stale_doc["checks"][0]["status"]), (1, "FAIL"))
        generated_output = self.repo / ".ai-runtime" / "generated.json"
        generate = self.check(
            "fixture.generate", ["{python}", "-c", "open('generated.txt','w').write('new')"],
            expected_artifacts=["generated.txt"], allowed_side_effects=["candidate_export", "evidence"],
        )
        generated, generated_code = runner.run(self.repo, self.candidate, self.candidate, self.catalog([generate]), generated_output)
        self.assertEqual((generated_code, generated["checks"][0]["status"]), (0, "PASS"))
        self.assertRegex(generated["checks"][0]["artifacts"]["generated.txt"], r"^[0-9a-f]{64}$")

    def test_linked_expected_artifact_fails_without_external_write(self):
        """Reject a child-created artifact symlink instead of following its target.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when a
        link is accepted; hosts that deny symlink creation return a normal FAIL.
        Side effects: The child attempts a link inside its disposable export only;
        no external file content, database, network, or source checkout is changed.
        """
        command = "import os; os.symlink('tracked.txt', 'linked.txt')"
        check = self.check(
            "fixture.linked-artifact", ["{python}", "-c", command],
            expected_artifacts=["linked.txt"], allowed_side_effects=["candidate_export", "evidence"],
        )
        document, code = runner.run(self.repo, self.candidate, self.candidate, self.catalog([check]), self.output)
        self.assertEqual((code, document["checks"][0]["status"]), (1, "FAIL"))
        self.assertIn("linked.txt", document["checks"][0]["invalid_artifacts"])

    def test_result_schema_rejects_unknown_fields_and_malformed_digests(self):
        """Prove the closed result schema rejects extra fields and weak hashes.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when
        malformed machine results validate; local schema/process errors propagate.
        Side effects: Runs one isolated check and validates in-memory copies; writes
        fixture evidence only, with no database or network interaction.
        """
        schema = load_json(ROOT / "templates/ai/schemas/check-result.schema.json")
        document, code = runner.run(
            self.repo, self.candidate, self.candidate,
            self.catalog([self.check("fixture.pass", ["{python}", "check.py"])]), self.output,
        )
        self.assertEqual(code, 0)
        extra = json.loads(json.dumps(document))
        extra["checks"][0]["unexpected_secret"] = "must-not-validate"
        with self.assertRaises(ValueError):
            validate(extra, schema)
        malformed = json.loads(json.dumps(document))
        malformed["candidate"]["commit"] = "a" * 41
        with self.assertRaises(ValueError):
            validate(malformed, schema)

        incomplete_execution = json.loads(json.dumps(document))
        del incomplete_execution["checks"][0]["stdout_sha256"]
        with self.assertRaises(ValueError):
            validate(incomplete_execution, schema)
        with self.assertRaises(ValueError):
            runner.validate_result_semantics(incomplete_execution, False)
        missing_present_digest = json.loads(json.dumps(document))
        del missing_present_digest["digests"]["invalidation_files"]["tracked.txt"]["sha256"]
        with self.assertRaises(ValueError):
            validate(missing_present_digest, schema)
        with self.assertRaises(ValueError):
            runner.validate_result_semantics(missing_present_digest, False)
        false_digest_with_sha = json.loads(json.dumps(document))
        false_digest_with_sha["digests"]["invalidation_files"]["tracked.txt"]["present"] = False
        with self.assertRaises(ValueError):
            validate(false_digest_with_sha, schema)
        available_without_version = json.loads(json.dumps(document))
        del available_without_version["environment"]["tools"]["python"]["version"]
        with self.assertRaises(ValueError):
            validate(available_without_version, schema)
        with self.assertRaises(ValueError):
            runner.validate_result_semantics(available_without_version, False)
        available_git_without_version = json.loads(json.dumps(document))
        self.assertEqual(available_git_without_version["environment"]["tools"]["git"]["status"], "AVAILABLE")
        del available_git_without_version["environment"]["tools"]["git"]["version"]
        with self.assertRaises(ValueError):
            validate(available_git_without_version, schema)
        empty_runner_digests = json.loads(json.dumps(document))
        empty_runner_digests["digests"]["runner_files"] = {}
        with self.assertRaises(ValueError):
            validate(empty_runner_digests, schema)
        with self.assertRaises(ValueError):
            runner.validate_result_semantics(empty_runner_digests, False)
        available_repository_without_tree = json.loads(json.dumps(document))
        del available_repository_without_tree["environment"]["repository"]["tree"]
        with self.assertRaises(ValueError):
            validate(available_repository_without_tree, schema)
        with self.assertRaises(ValueError):
            runner.validate_result_semantics(available_repository_without_tree, False)
        invalid_exit_relation = json.loads(json.dumps(document))
        invalid_exit_relation["checks"][0].update({"status": "FAIL", "timed_out": True})
        with self.assertRaises(ValueError):
            validate(invalid_exit_relation, schema)
        with self.assertRaises(ValueError):
            runner.validate_result_semantics(invalid_exit_relation, False)
        passing_nonzero = json.loads(json.dumps(document))
        passing_nonzero["checks"][0]["exit_code"] = 7
        with self.assertRaises(ValueError):
            validate(passing_nonzero, schema)
        skipped_with_evidence = json.loads(json.dumps(document))
        skipped_with_evidence["checks"][0]["status"] = "NOT_APPLICABLE"
        with self.assertRaises(ValueError):
            validate(skipped_with_evidence, schema)
        valid_timeout = json.loads(json.dumps(document))
        valid_timeout["checks"][0]["status"] = "FAIL"
        del valid_timeout["checks"][0]["exit_code"]
        valid_timeout["checks"][0]["timed_out"] = True
        validate(valid_timeout, schema)

    def test_post_check_failure_cleans_runtime_and_same_output_retries(self):
        """Roll back staging/evidence after a post-check failure, then retry safely.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when a
        partial result/evidence survives or exclusive retry cannot use the same
        final path; child/filesystem errors otherwise propagate.
        Side effects: Executes two isolated checks and injects one detector error;
        writes/removes only fixture runtime files, with no DB or network access.
        """
        catalog = self.catalog([self.check("fixture.retry", ["{python}", "check.py"])])
        with mock.patch.object(runner, "environment_report", side_effect=RuntimeError("post-check fixture")):
            with self.assertRaises(RuntimeError):
                runner.run(self.repo, self.candidate, self.candidate, catalog, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.output.parent.glob("full.pending-*")), [])
        self.assertEqual(list(self.output.parent.glob("full-evidence-*")), [])
        document, code = runner.run(self.repo, self.candidate, self.candidate, catalog, self.output)
        self.assertEqual((code, document["outcome"], self.output.is_file()), (0, "PASS", True))

    @unittest.skipUnless(os.name == "posix", "Executable-bit behavior requires a POSIX filesystem")
    def test_export_preserves_executable_bit_and_detects_chmod_only_mutation(self):
        """Execute a Git-marked script and detect a content-identical mode change.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when
        archive export loses Git's executable bit or snapshots ignore chmod-only
        mutation; fixture Git/process errors may propagate.
        Side effects: Commits one script in the disposable repository and mutates
        only an isolated export; no database, network, or user checkout changes.
        """
        script = self.repo / "direct-check.sh"
        script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
        script.chmod(0o755)
        self.git("add", "direct-check.sh")
        self.git("commit", "-m", "executable fixture")
        candidate = self.git("rev-parse", "HEAD").stdout.strip()
        direct = self.check(
            "fixture.direct-executable", ["./direct-check.sh"], prerequisites=[],
            applicability={"path_exists": "direct-check.sh", "missing_status": "NOT_VERIFIED"},
        )
        chmod_only = self.check(
            "fixture.chmod", ["{python}", "-c", "import os; os.chmod('tracked.txt', 0o755)"],
            dependencies=["fixture.direct-executable"], allowed_side_effects=["candidate_export", "evidence"],
        )
        document, code = runner.run(self.repo, candidate, self.candidate, self.catalog([direct, chmod_only]), self.output)
        self.assertEqual((code, [item["status"] for item in document["checks"]]), (0, ["PASS", "PASS"]))
        self.assertFalse(document["checks"][0]["candidate_export_mutated"])
        self.assertTrue(document["checks"][1]["candidate_export_mutated"])


if __name__ == "__main__":
    unittest.main()
