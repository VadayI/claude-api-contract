"""Behavioral tests for the environment detector and exact-candidate runner."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import detector
import runner
import runner_caps
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

    def test_large_candidate_archive_is_fully_drained(self):
        """Export a candidate larger than a pipe buffer without inducing SIGPIPE.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when
        streaming extraction closes Git stdout before archive padding is drained;
        local fixture Git/filesystem errors otherwise propagate.
        Side effects: Commits a large public fixture blob and exports it to a
        temporary directory; no user checkout, database, or network is touched.
        """
        (self.repo / "large-public.bin").write_bytes(b"contract-fixture\n" * 131072)
        self.git("add", "large-public.bin")
        self.git("commit", "-m", "large archive fixture")
        candidate = self.git("rev-parse", "HEAD").stdout.strip()
        with tempfile.TemporaryDirectory(prefix="large export ") as directory:
            target = Path(directory) / "candidate"
            target.mkdir()
            runner.export_candidate(self.repo, candidate, target)
            exported = target / "large-public.bin"
            self.assertGreater(exported.stat().st_size, 1024 * 1024)
            self.assertTrue(exported.read_bytes().startswith(b"contract-fixture"))

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
        context_schema = load_json(ROOT / "templates/ai/schemas/run-context.schema.json")
        for schema in (catalog_schema, result_schema, context_schema):
            check_schema(schema)
        for name in ("contract.json", "react.json"):
            shipped = load_json(ROOT / "templates/ai/checks" / name)
            validate(shipped, catalog_schema)
            runner.validate_catalog(shipped)
        catalog = self.catalog([self.check("fixture.pass", ["{python}", "check.py"])])
        document, code = runner.run(self.repo, self.candidate, self.candidate, catalog, self.output)
        self.assertEqual(code, 0)
        validate(document, result_schema)
        validate(document["run_context"], context_schema)

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
        self.assertEqual(
            runner.safe_relative("templates/.env.example", allow_env_example=True).as_posix(),
            "templates/.env.example",
        )
        for name in (
            ".env", ".env.local", ".env.production", ".env.example.backup",
            "nested/.env", "nested/.env.local", "nested/.env.production",
            "nested/.env.example.backup", "nested/.env.example/secret.txt",
        ):
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

    def test_run_context_binds_event_exact_diff_and_base(self):
        """Bind event, exact commits/trees, changed files and base into one digest.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when a
        context is ambiguous or a base/candidate change does not alter identity;
        fixture Git errors propagate.
        Side effects: Creates two fixture commits and runs read-only local Git
        diffs; no checkout of user code, database, network, or global config.
        """
        (self.repo / "changed file.txt").write_text("one\n", encoding="utf-8")
        self.git("add", "changed file.txt")
        self.git("commit", "-m", "context fixture")
        later = self.git("rev-parse", "HEAD").stdout.strip()
        later_tree = self.git("rev-parse", "HEAD^{tree}").stdout.strip()
        base_tree = self.git("rev-parse", self.candidate + "^{tree}").stdout.strip()
        first = runner_caps.build_run_context(
            self.repo, later, later_tree, self.candidate, base_tree, "pull_request", "disabled"
        )
        second = runner_caps.build_run_context(
            self.repo, later, later_tree, later, later_tree, "push", "disabled"
        )
        self.assertEqual(first["changed_files"], ["changed file.txt"])
        self.assertNotEqual(first["context_sha256"], second["context_sha256"])
        self.assertEqual(first["base"]["commit"], self.candidate)

    def test_contract_spec_applicability_is_typed_and_fail_closed(self):
        """Skip only the identified upstream scaffold and reject broken derived repos.

        Args: self owns the fixture. Returns: None. Raises: AssertionError for a
        fail-open applicability regression or malformed package fixture.
        Side effects: Writes public package/spec fixtures below a temporary export;
        no subprocess, database, environment, or network interaction occurs.
        """
        root = Path(self.temp.name) / "applicability"
        root.mkdir()
        rule = {"kind": "contract_spec", "scaffold_package": "claude-api-contract"}
        (root / "package.json").write_text('{"name":"claude-api-contract"}', encoding="utf-8")
        self.assertEqual(runner_caps.evaluate_applicability(rule, root, {})[0], "NOT_APPLICABLE")
        (root / "package.json").write_text('{"name":"derived-contract"}', encoding="utf-8")
        self.assertEqual(runner_caps.evaluate_applicability(rule, root, {})[0], "NOT_VERIFIED")
        (root / "spec").mkdir()
        self.assertEqual(runner_caps.evaluate_applicability(rule, root, {})[0], "APPLICABLE")

    def test_private_node_provisioning_and_generated_comparison(self):
        """Record private content-bound npm provisioning and exact artifact drift.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when npm
        arguments/network/cache semantics or generated comparison become ambiguous.
        Side effects: Creates disposable lock/artifact/cache paths and mocks the
        child execution; no real package installation, database, or network access.
        """
        root = Path(self.temp.name) / "node capsule"
        root.mkdir()
        (root / "package-lock.json").write_text('{"lockfileVersion":3}', encoding="utf-8")
        artifact = root / "generated.json"
        artifact.write_bytes(b"exact\n")
        with mock.patch.object(runner_caps.shutil, "which", return_value="npm"), mock.patch.object(
            runner_caps.subprocess, "run",
            return_value=subprocess.CompletedProcess(["npm", "--version"], 0, b"11.0.0\n", b""),
        ), mock.patch.object(
            runner_caps.platform, "system", return_value="Windows"
        ), mock.patch.object(
            runner_caps.platform, "machine", return_value="AMD64"
        ), mock.patch.object(
            runner_caps,
            "run_argv",
            return_value=(
                0,
                b"ok",
                f"GH_TOKEN=fake https://user:pass@example.test {root}".encode(),
                False,
                7,
            ),
        ) as invocation:
            provision = runner_caps.provision_node(
                root, {"network": "disabled", "ttl_seconds": 60}, {"PATH": "fixture"}, 10
            )
        self.assertEqual(provision["status"], "PASS")
        self.assertIn("--ignore-scripts", invocation.call_args.args[0])
        self.assertIn("--offline", invocation.call_args.args[0])
        self.assertEqual(
            {name: provision["cache"][name] for name in ("scope", "reused", "content_only")},
            {"scope": "per-check", "reused": False, "content_only": True},
        )
        self.assertRegex(provision["cache"]["key_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("fake", provision["stderr_excerpt"])
        self.assertNotIn("user:pass", provision["stderr_excerpt"])
        self.assertNotIn(str(root), provision["stderr_excerpt"])
        self.assertIn("[REDACTED]", provision["stderr_excerpt"])
        child_env = invocation.call_args.args[2]
        self.assertNotEqual(child_env["npm_config_userconfig"], child_env["npm_config_globalconfig"])
        self.assertEqual(child_env["npm_config_registry"], "https://registry.npmjs.org/")
        self.assertEqual(child_env["NODE_OPTIONS"], "--use-system-ca")
        self.assertEqual(
            set(provision["cache"]["identity"]),
            {
                "lock_sha256", "node_version", "npm_version", "registry", "os", "arch",
                "user_config_sha256", "global_config_sha256", "tls_ca_mode",
            },
        )
        self.assertEqual(provision["cache"]["identity"]["tls_ca_mode"], "system")
        self.assertTrue(runner_caps.compare_generated(root, {"generated.json": b"exact\n"}, ["generated.json"])["matched"])
        artifact.write_bytes(b"drift\n")
        self.assertFalse(runner_caps.compare_generated(root, {"generated.json": b"exact\n"}, ["generated.json"])["matched"])

    def test_ephemeral_output_allowlist_rejects_unrelated_mutation(self):
        """Permit an exact file/subtree but reject a prefix-confused sibling.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when an
        undeclared mutation passes or a declared transient output is rejected.
        Side effects: Runs two isolated Python children that create disposable
        files inside separate candidate exports; no DB, network, or user files.
        """
        common = {
            "allowed_side_effects": ["candidate_export", "evidence"],
            "provisioning": [],
            "generated_comparisons": [],
            "ephemeral_outputs": ["allowed.tmp", "coverage/"],
        }
        allowed = self.check(
            "fixture.ephemeral-allowed",
            [
                "{python}", "-c",
                "from pathlib import Path; Path('allowed.tmp').write_text('ok'); "
                "Path('coverage/nested').mkdir(parents=True); "
                "Path('coverage/nested/index.html').write_text('ok')",
            ],
            **common,
        )
        unexpected = self.check(
            "fixture.ephemeral-unexpected",
            [
                "{python}", "-c",
                "from pathlib import Path; Path('coverage-copy').mkdir(); "
                "Path('coverage-copy/index.html').write_text('bad')",
            ],
            dependencies=["fixture.ephemeral-allowed"],
            **common,
        )
        document, code = runner.run(
            self.repo, self.candidate, self.candidate, self.catalog([allowed, unexpected]), self.output
        )
        self.assertEqual(code, 1)
        self.assertEqual([item["status"] for item in document["checks"]], ["PASS", "FAIL"])
        self.assertEqual(
            document["checks"][0]["candidate_export_mutations"],
            ["allowed.tmp", "coverage/", "coverage/nested/", "coverage/nested/index.html"],
        )
        self.assertIn("candidate_export", document["checks"][1]["invalid_artifacts"])

    def test_ephemeral_directory_prefix_rejects_unsafe_catalog_paths(self):
        """Reject broad-root, traversal and non-normal directory authorizations.

        Args: self owns the fixture. Returns: None. Raises: AssertionError if an
        unsafe directory prefix reaches execution. Side effects: Writes temporary
        catalog JSON only; no subprocess, database, network or user-file access.
        """
        for unsafe in ("/", "./", "../", "coverage/../", "coverage//", "C:/temp/"):
            check = self.check(
                "fixture.unsafe-ephemeral",
                ["{python}", "check.py"],
                ephemeral_outputs=[unsafe],
            )
            with self.subTest(path=unsafe), self.assertRaises(ValueError):
                runner.validate_catalog(self.catalog([check]))

    @unittest.skipUnless(os.name == "posix", "Directory-link behavior requires POSIX symlinks")
    def test_ephemeral_directory_prefix_rejects_linked_descendant(self):
        """Reject a linked child even below an authorized ephemeral subtree.

        Args: self owns the fixture. Returns: None. Raises: AssertionError when a
        link can hide beneath an allowed prefix. Side effects: Creates one link
        inside a disposable candidate export; no external write, DB or network.
        """
        command = (
            "from pathlib import Path; Path('coverage').mkdir(); "
            "Path('coverage/outside').symlink_to('../tracked.txt')"
        )
        check = self.check(
            "fixture.ephemeral-linked",
            ["{python}", "-c", command],
            allowed_side_effects=["candidate_export", "evidence"],
            ephemeral_outputs=["coverage/"],
        )
        document, code = runner.run(
            self.repo, self.candidate, self.candidate, self.catalog([check]), self.output
        )
        self.assertEqual((code, document["checks"][0]["status"]), (1, "FAIL"))
        self.assertIn("candidate_export", document["checks"][0]["invalid_artifacts"])

    def test_npm_cache_rejects_future_and_expired_metadata(self):
        """Require cache age to stay between zero and the reviewed TTL.

        Args: self owns disposable capsule/cache roots. Returns: None. Raises:
        AssertionError when future-dated or expired content is reused. Side
        effects: Creates runtime-only cache fixtures and mocks npm execution; no
        real package installation, database, user config, or network access.
        """
        cache_root = Path(self.temp.name) / "npm cache"
        cache_root.mkdir()
        roots = []
        for name in ("seed", "future", "expired"):
            root = Path(self.temp.name) / name
            root.mkdir()
            (root / "package-lock.json").write_text('{"lockfileVersion":3}', encoding="utf-8")
            roots.append(root)
        common = (
            mock.patch.object(runner_caps.shutil, "which", side_effect=lambda name: name),
            mock.patch.object(
                runner_caps.subprocess, "run",
                return_value=subprocess.CompletedProcess(["tool", "--version"], 0, b"11.0.0\n", b""),
            ),
            mock.patch.object(runner_caps.platform, "system", return_value="Windows"),
            mock.patch.object(runner_caps.platform, "machine", return_value="AMD64"),
            mock.patch.object(runner_caps, "run_argv", return_value=(0, b"ok", b"", False, 7)),
        )
        with common[0], common[1], common[2], common[3], common[4]:
            with mock.patch.object(runner_caps.time, "time", return_value=100):
                seed = runner_caps.provision_node(
                    roots[0], {"network": "allowed", "ttl_seconds": 60}, {"PATH": "fixture"}, 10, cache_root
                )
            with mock.patch.object(runner_caps.time, "time", return_value=99):
                future = runner_caps.provision_node(
                    roots[1], {"network": "allowed", "ttl_seconds": 60}, {"PATH": "fixture"}, 10, cache_root
                )
            with mock.patch.object(runner_caps.time, "time", return_value=200):
                expired = runner_caps.provision_node(
                    roots[2], {"network": "allowed", "ttl_seconds": 60}, {"PATH": "fixture"}, 10, cache_root
                )
        self.assertFalse(seed["cache"]["reused"])
        self.assertFalse(future["cache"]["reused"])
        self.assertFalse(expired["cache"]["reused"])

    def test_external_command_network_is_blocked_and_exit_75_is_not_verified(self):
        """Gate external command access and preserve the reviewed NV exit protocol.

        Args: self owns the exact Git fixture. Returns: None. Raises:
        AssertionError when disabled external access starts or exit 75 becomes FAIL.
        Side effects: Runs one isolated local Python child for the allowed protocol
        case and writes run-scoped evidence; no database or network access.
        """
        blocked = self.check(
            "fixture.external", ["{python}", "-c", "raise SystemExit(0)"],
            network_access="external", not_verified_exit_codes=[75],
        )
        with mock.patch.object(runner, "run_argv") as invocation:
            document, code = runner.run(
                self.repo, self.candidate, self.candidate, self.catalog([blocked]), self.output,
                network="disabled",
            )
        self.assertEqual((code, document["checks"][0]["status"]), (2, "NOT_VERIFIED"))
        self.assertFalse(invocation.called)
        self.output.unlink()
        protocol = self.check(
            "fixture.protocol", ["{python}", "-c", "raise SystemExit(75)"],
            network_access="none", not_verified_exit_codes=[75],
        )
        with mock.patch.object(runner.time, "time", side_effect=[100, 99]):
            document, code = runner.run(
                self.repo, self.candidate, self.candidate, self.catalog([protocol]), self.output
            )
        self.assertEqual((code, document["checks"][0]["status"]), (2, "NOT_VERIFIED"))
        self.assertEqual(document["checks"][0]["exit_code"], 75)
        self.assertEqual((document["started_at"], document["finished_at"]), (100, 100))

    def test_process_tree_cleanup_after_leader_exit_releases_port(self):
        """Kill a listening descendant even when its direct leader already exited.

        Args: self owns a disposable runtime directory. Returns: None. Raises:
        AssertionError or socket/subprocess errors when cleanup is incomplete.
        Side effects: Starts a local child process and loopback listener, then
        verifies the runner-owned process group/job releases the port; no network
        beyond loopback, database, repository, or user-file mutation.
        """
        runtime = Path(self.temp.name) / "process tree"
        runtime.mkdir()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        child = (
            "import pathlib,socket,time; s=socket.socket(); "
            f"s.bind(('127.0.0.1',{port})); s.listen(); pathlib.Path('ready').write_text('1'); time.sleep(30)"
        )
        parent = (
            "import pathlib,subprocess,sys,time\n"
            f"p=subprocess.Popen([sys.executable,'-c',{child!r}])\n"
            "deadline=time.time()+5\n"
            "while not pathlib.Path('ready').exists() and time.time()<deadline:\n"
            "    time.sleep(.02)\n"
            "pathlib.Path('child.pid').write_text(str(p.pid))\n"
            "time.sleep(.2)\n"
        )
        exit_code, _, _, timed_out, _ = runner_caps.run_argv(
            [sys.executable, "-c", parent], runtime, dict(os.environ), 10
        )
        self.assertEqual((exit_code, timed_out), (0, False))
        deadline = time.monotonic() + 5
        while True:
            try:
                with socket.socket() as replacement:
                    replacement.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    replacement.bind(("127.0.0.1", port))
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

    def test_workflow_inventory_maps_all_steps_and_five_source_gates(self):
        """Require complete 55-step routing and exactly five requested real gates.

        Args: self reads canonical public catalogs. Returns: None. Raises:
        AssertionError when inventory entries vanish, duplicate, or claim success
        without a runnable mapping.
        Side effects: Reads checked-in JSON only; no writes, subprocess, DB/network.
        """
        inventory = json.loads((ROOT / "templates/ai/checks/workflow-inventory.json").read_text(encoding="utf-8"))
        self.assertEqual((inventory["expected_steps"], len(inventory["steps"])), (55, 55))
        self.assertEqual(len({item["id"] for item in inventory["steps"]}), 55)
        mapped = {gate for item in inventory["steps"] for gate in item["runner_check_ids"]}
        requested = {"contract.typespec-drift", "contract.spectral", "contract.examples", "react.typecheck", "react.lint"}
        self.assertTrue(requested.issubset(mapped))
        pending = [
            item for item in inventory["steps"]
            if item["disposition"] in {"NOT_VERIFIED_PENDING", "REPORTING_PENDING"}
        ]
        self.assertEqual(pending, [])
        executable = [item for item in inventory["steps"] if item["disposition"] == "EXECUTABLE"]
        self.assertTrue(all(item["reason"] and item["runner_check_ids"] for item in executable))

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

    def test_relative_executable_cannot_escape_candidate_export(self):
        """Reject a relative command whose normalized target leaves the export.

        Args: self owns the disposable repository. Returns: None. Raises:
        AssertionError when traversal reaches a host executable or is not reported
        as invalid catalog input. Side effects: Writes only run-scoped fixture
        catalog/output files; no database, network, or user checkout mutation.
        """
        escaped = self.check("fixture.escape", ["../outside.sh"])
        document, code = runner.run(
            self.repo, self.candidate, self.candidate, self.catalog([escaped]), self.output
        )
        self.assertEqual((code, document["checks"][0]["status"]), (2, "NOT_VERIFIED"))
        self.assertEqual(document["checks"][0]["missing_prerequisites"], ["command_executable"])


if __name__ == "__main__":
    unittest.main()
