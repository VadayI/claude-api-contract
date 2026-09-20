"""Behavioral acceptance fixtures for maturity and deployment readiness."""

import copy
import hashlib
import json
import sys
from pathlib import Path
import unittest
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/ai"))
from readiness import CATALOG, checklist, migrate_stage, profile_digest, verdict


class ReadinessTests(unittest.TestCase):
    """Resolve all profiles and prevent missing or stale evidence becoming ready."""

    def profile(self, **overrides):
        """Return an isolated valid profile; kwargs override fields, no I/O or DB."""
        return dict(stage="experiment", target="vps_smoke", kind="react",
                    exposure="private", data="synthetic", features=[],
                    phase="pre_deploy", artifact="sha256:fixture", config="sha256:config") | overrides

    def evidence(self, profile):
        """Create bound PASS fixtures for a profile; returns records without I/O/DB."""
        return [{"id": item["id"], "status": "PASS", "artifact": profile["artifact"],
                 "config": profile["config"], "phase": profile["phase"], "observed_at": 1000,
                 "profile_digest": profile_digest(profile),
                 "catalog_digest": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
                 "evidence": "reports/check.json"} for item in checklist(profile)]

    def test_all_24_profiles_are_deterministic_and_keep_baseline(self):
        """Check the full matrix without deployments; no side effects or DB access."""
        for stage in ("experiment", "poc", "prototype", "mvp", "beta", "production"):
            for target in ("vps_smoke", "demo", "staging", "live"):
                with self.subTest(stage=stage, target=target):
                    profile = self.profile(stage=stage, target=target)
                    rows = checklist(profile)
                    self.assertEqual(rows, checklist(copy.deepcopy(profile)))
                    ids = {row["id"] for row in rows}
                    self.assertTrue({"full_profile", "contract_integrity", "secrets_config", "build", "startup_health", "run_stop"} <= ids)
                    self.assertEqual(verdict(profile, self.evidence(profile), now=1000)["verdict"], "READY")

    def test_failure_precedes_missing_evidence(self):
        """Known mandatory failure wins over missing evidence; no I/O or DB use."""
        profile = self.profile()
        evidence = self.evidence(profile)[:1]
        evidence[0]["status"] = "FAIL"
        self.assertEqual(verdict(profile, evidence, now=1000)["verdict"], "NOT_READY")
        self.assertEqual(verdict(profile, [], now=1000)["verdict"], "NOT_VERIFIED")

    def test_changed_artifact_config_phase_or_expired_evidence_is_missing(self):
        """Reject stale bindings/timestamps; no side effects or DB interaction."""
        profile = self.profile()
        for field, value in (("artifact", "different"), ("config", "different"),
                             ("phase", "post_deploy"), ("observed_at", 9999999)):
            records = self.evidence(profile)
            records[0][field] = value
            with self.subTest(field=field):
                self.assertEqual(verdict(profile, records, now=1000)["verdict"], "NOT_VERIFIED")
        self.assertEqual(verdict(profile, self.evidence(profile), now=1000000)["verdict"], "NOT_VERIFIED")

    def test_public_real_poc_with_database_requires_access_and_restore(self):
        """Exposure/data activate protection regardless of stage; no I/O or DB."""
        ids = {row["id"] for row in checklist(self.profile(stage="poc", exposure="public", data="real", features=["persistence"]))}
        self.assertTrue({"access_control", "tls_ingress", "backup_restore", "data_handling"} <= ids)
        smoke_ids = {row["id"] for row in checklist(self.profile())}
        self.assertNotIn("load_failures", smoke_ids)
        self.assertNotIn("backup_restore", smoke_ids)

    def test_unknown_or_incomplete_profiles_never_pass(self):
        """Reject unknown settings instead of skipping checks; no I/O or DB use."""
        for field, value in (("stage", "unknown"), ("target", "unknown"), ("kind", "unknown"),
                             ("exposure", ""), ("data", ""), ("features", ["imagined"]),
                             ("artifact", ""), ("config", "")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                checklist(self.profile(**{field: value}))

    def test_legacy_mapping_preserves_floor_and_unknown_is_unresolved(self):
        """Preserve old taxonomy and required checks; no filesystem or DB effects."""
        for legacy, stage in (("demo", "prototype"), ("prototype", "prototype"),
                              ("PoC", "poc"), ("MVP", "mvp"), ("production", "production"), ("other", "mvp")):
            with self.subTest(legacy=legacy):
                migration = migrate_stage(legacy, "django")
                self.assertEqual(migration["stage"], stage)
                profile = self.profile(kind="django", stage=stage, legacy=migration["legacy"])
                ids = {row["id"] for row in checklist(profile)}
                self.assertTrue(set(migration["legacy"]["required_checks"]) <= ids)
        self.assertIsNone(migrate_stage("mystery", "django")["stage"])

    def test_legacy_floor_cannot_be_silently_removed(self):
        """Assert a claimed migration cannot strip required checks; no I/O or DB."""
        migration = migrate_stage("production", "django")
        migration["legacy"]["required_checks"] = []
        with self.assertRaises(ValueError):
            checklist(self.profile(kind="django", stage="experiment", legacy=migration["legacy"]))

    def test_post_deploy_requires_actual_target_smoke(self):
        """Local evidence cannot prove a remote deployed host; no network or DB."""
        before = self.profile()
        after = self.profile(phase="post_deploy")
        self.assertNotIn("target_smoke", {row["id"] for row in checklist(before)})
        self.assertIn("target_smoke", {row["id"] for row in checklist(after)})
        self.assertEqual(verdict(after, self.evidence(before), now=1000)["verdict"], "NOT_VERIFIED")

    def test_optional_limitation_cannot_hide_mandatory_skip(self):
        """Only optional failure becomes a limitation; no side effects or DB access."""
        profile = self.profile(stage="mvp")
        records = self.evidence(profile)
        for record in records:
            if record["id"] == "risk_review":
                record["status"] = "NOT_VERIFIED"
        self.assertEqual(verdict(profile, records, now=1000)["verdict"], "READY_WITH_LIMITATIONS")
        records[0]["status"] = "NOT_APPLICABLE"
        self.assertEqual(verdict(profile, records, now=1000)["verdict"], "NOT_VERIFIED")

    def test_contract_artifact_never_claims_backend_health(self):
        """Artifact-only profiles select consumer checks, not server proof; no I/O/DB."""
        profile = self.profile(kind="contract", contract_mode="artifact")
        ids = {row["id"] for row in checklist(profile)}
        self.assertIn("consumer_artifact", ids)
        self.assertNotIn("startup_health", ids)
        with self.assertRaises(ValueError):
            checklist(self.profile(kind="contract"))

    def test_target_stage_and_catalog_changes_invalidate_proof(self):
        """Reject evidence from different requirements or targets; temporary I/O, no DB."""
        profile = self.profile()
        records = self.evidence(profile)
        for change in ({"target": "live"}, {"stage": "production"}):
            self.assertEqual(verdict(profile | change, records, now=1000)["verdict"], "NOT_VERIFIED")
        records[0]["catalog_digest"] = "old-catalog"
        self.assertEqual(verdict(profile, records, now=1000)["verdict"], "NOT_VERIFIED")

    def test_duplicate_and_secret_evidence_paths_rejected(self):
        """Ambiguous or secret-path proof is invalid, without reading it; no DB/I/O."""
        profile = self.profile()
        records = self.evidence(profile)
        with self.assertRaises(ValueError):
            verdict(profile, records + records[:1], now=1000)
        for path in ("../escape", "C:/secret", ".env", "reports/.env.production", "secrets/key"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                verdict(profile, [records[0] | {"evidence": path}], now=1000)

    def test_malformed_catalog_cannot_silently_remove_a_requirement(self):
        """Reject empty predicates and invalid TTLs; temporary file writes, no DB."""
        for mutation in ({"when": []}, {"ttl_seconds": True}, {"when": [{"stage": []}]}):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
                catalog["rules"][0].update(mutation)
                path = Path(directory) / "catalog.json"
                path.write_text(json.dumps(catalog), encoding="utf-8")
                with self.assertRaises(ValueError):
                    checklist(self.profile(), path)


if __name__ == "__main__":
    unittest.main()
