"""Test React P05 wrapper semantics without network, browsers, or repository writes."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("react_gate", Path(__file__).with_name("react_gate.py"))
assert SPEC and SPEC.loader
react_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(react_gate)


def context(path: Path, changed: list[str], event: str = "pull_request") -> Path:
    """Write a canonical exact runner-context fixture.

    Args:
        path: Fixture output path.
        changed: Sorted candidate/base changed-file manifest.
        event: Exact runner event.

    Returns:
        The supplied path after writing valid versioned JSON.

    Side effects:
        Writes one disposable public JSON fixture; no Git, DB, subprocess, or network.
    """
    document = {
        "schema_version": 1,
        "event": event,
        "candidate": {"commit": "a" * 40, "tree": "b" * 40},
        "base": {"commit": "c" * 40, "tree": "d" * 40},
        "changed_files": sorted(changed),
        "changed_files_sha256": __import__("hashlib").sha256(
            ("\n".join(sorted(changed)) + ("\n" if changed else "")).encode("utf-8")
        ).hexdigest(),
        "network": {"mode": "disabled", "ttl_seconds": 86400},
    }
    document["context_sha256"] = react_gate.canonical_digest(document)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


class ReactGateTests(unittest.TestCase):
    """Verify catalog completeness and deterministic wrapper outcomes."""

    def test_catalog_maps_all_react_workflow_checks(self):
        """Require stable IDs and explicit network/NV semantics for all 15 checks.

        No arguments/return. Reads the candidate catalog only; no writes, Git, DB,
        subprocess, environment mutation, or network access.
        """
        catalog = json.loads((ROOT / "templates/ai/checks/react.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"], 2)
        self.assertEqual([item["id"] for item in catalog["checks"]], [
            "react.audit", "react.typecheck", "react.lint", "react.file-size", "react.stubs",
            "react.feature-readmes", "react.api-types", "react.contract-sync", "react.plan-sync",
            "react.routes-sync", "react.guides-sync", "react.unit-coverage", "react.build",
            "react.bundle-size", "react.e2e",
        ])
        for item in catalog["checks"]:
            self.assertIn(item["network_access"], {"none", "loopback", "external"})
            self.assertIsInstance(item["not_verified_exit_codes"], list)
        by_id = {item["id"]: item for item in catalog["checks"]}
        for check_id in ("react.file-size", "react.stubs", "react.feature-readmes"):
            self.assertEqual(by_id[check_id]["argv"][1], "--login")
        self.assertEqual(catalog["inventory"]["expected_steps"], 55)

    def test_exact_policy_uses_only_context_changed_manifest(self):
        """Exercise plan/routes/guides without environment or Git fallback.

        No arguments/return. Writes disposable candidate/base/context fixtures only;
        no subprocess, Git, DB, environment mutation, or network access.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base"
            candidate = root / "candidate"
            base.mkdir()
            candidate.mkdir()
            (candidate / ".claude/memory").mkdir(parents=True)
            (candidate / ".claude/memory/routes.json").write_text("{}", encoding="utf-8")
            changed = [
                ".claude/memory/routes.json", "docs/guides/user.md", "docs/plans/0001.md",
                "docs/verify/router.md", "src/app/router.tsx", "src/lib/auth/token.ts", "src/x.ts",
            ]
            ctx = context(root / "context.json", changed)
            self.assertEqual(react_gate.policy("plan", candidate, ctx, base), 0)
            self.assertEqual(react_gate.policy("routes", candidate, ctx, base), 0)
            self.assertEqual(react_gate.policy("guides", candidate, ctx, base), 0)
            failing = context(root / "failing.json", ["src/app/router.tsx", "src/a.ts", "src/b.ts"])
            self.assertEqual(react_gate.policy("plan", candidate, failing, base), 1)
            self.assertEqual(react_gate.policy("routes", candidate, failing, base), 1)
            self.assertEqual(react_gate.policy("guides", candidate, failing, base), 1)

    def test_context_digest_tampering_is_rejected(self):
        """Reject any changed-file mutation not covered by the exact context digest.

        No arguments/return. Writes one disposable JSON document; no subprocess,
        Git, DB, environment mutation, or network.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = context(Path(directory) / "context.json", ["src/a.ts"])
            document = json.loads(path.read_text(encoding="utf-8"))
            document["changed_files"] = ["src/other.ts"]
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(ValueError):
                react_gate.load_run_context(path)

    def test_audit_distinguishes_vulnerability_from_network_outage(self):
        """Keep advisory findings FAIL while classifying transport outage as NV.

        No arguments/return. Mocks the local npm child; no files, Git, DB, process,
        environment mutation, or network access.
        """
        vulnerable = subprocess.CompletedProcess(
            ["npm"], 1, json.dumps({"metadata": {"vulnerabilities": {"high": 1, "critical": 0}}}), ""
        )
        with mock.patch.object(react_gate, "run_process", return_value=vulnerable):
            self.assertEqual(react_gate.audit(ROOT), 1)
        outage = subprocess.CompletedProcess(["npm"], 1, json.dumps({"error": {"code": "ENETUNREACH"}}), "")
        with mock.patch.object(react_gate, "run_process", return_value=outage):
            with self.assertRaises(react_gate.NotVerified):
                react_gate.audit(ROOT)

    def test_contract_sync_binds_remote_vendor_and_lock_bytes(self):
        """Pass only when public remote, vendor, and lock digests are identical.

        No arguments/return. Uses disposable local bytes and a mocked HTTPS response;
        no real network, Git, DB, subprocess, or environment mutation.
        """
        class Response:
            """Minimal bounded URL response fixture."""

            status = 200

            def __enter__(self):
                """Return this fixture without side effects."""
                return self

            def __exit__(self, *_args):
                """Close the synthetic context without suppressing errors."""
                return False

            def read(self, _limit):
                """Return the reviewed synthetic OpenAPI bytes."""
                return b"openapi: 3.1.0\n"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src/lib/api").mkdir(parents=True)
            payload = b"openapi: 3.1.0\n"
            (root / "src/lib/api/openapi.yml").write_bytes(payload)
            digest = __import__("hashlib").sha256(payload).hexdigest()
            (root / "contract.lock.json").write_text(json.dumps({
                "repo": "owner/repository", "version": "v1.0.0", "path": "openapi.yml", "sha256": digest,
            }), encoding="utf-8")
            with mock.patch.object(react_gate, "urlopen", return_value=Response()):
                self.assertEqual(react_gate.contract_sync(root), 0)

    def test_bundle_budget_is_strict_and_shell_independent(self):
        """Enforce real gzip limits without Git Bash or fail-open shell helpers.

        No arguments/return. Writes disposable build assets and budget JSON only;
        no subprocess, Git, DB, environment mutation, or network access.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "dist/assets"
            assets.mkdir(parents=True)
            (root / "dist/index.html").write_text(
                '<script type="module" src="/assets/app.js"></script>', encoding="utf-8"
            )
            (assets / "app.js").write_bytes(b"const payload='" + os.urandom(4096) + b"';")
            (assets / "lazy.js").write_bytes(os.urandom(2048))
            budget = {"bundle": {
                "initialJsGzipKb": 10, "totalInitialTransferGzipKb": 10, "lazyChunkGzipKb": 10,
            }}
            (root / ".performance-budget.json").write_text(json.dumps(budget), encoding="utf-8")
            self.assertEqual(react_gate.bundle_budget(root), 0)
            budget["bundle"]["initialJsGzipKb"] = 0.1
            (root / ".performance-budget.json").write_text(json.dumps(budget), encoding="utf-8")
            self.assertEqual(react_gate.bundle_budget(root), 1)

    def test_playwright_config_delegates_server_lifecycle_to_wrapper(self):
        """Prevent Playwright from starting a second server in wrapper mode.

        No arguments/return. Reads the checked-in TypeScript config only; no writes,
        subprocess, Git, DB, environment mutation, or network access.
        """
        config = (ROOT / "playwright.config.ts").read_text(encoding="utf-8")
        self.assertIn("process.env.PLAYWRIGHT_BASE_URL ??", config)
        self.assertIn("process.env.PLAYWRIGHT_EXTERNAL_SERVER === 'true' ? undefined", config)

    def test_local_node_cli_is_candidate_bound(self):
        """Resolve only a real provisioned CLI below the exact candidate export.

        No arguments/return. Writes one disposable CLI fixture; no subprocess, Git,
        DB, environment mutation, or network access.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / "node_modules/tool/cli.js"
            cli.parent.mkdir(parents=True)
            cli.write_text("", encoding="utf-8")
            argv = react_gate.local_node_cli(root, "tool/cli.js")
            self.assertEqual(Path(argv[1]), cli.resolve())
            with self.assertRaises(react_gate.NotVerified):
                react_gate.local_node_cli(root, "missing/cli.js")


if __name__ == "__main__":
    unittest.main()
