"""Deterministic readiness resolution; inspection only, never deployment.

Python 3.13+ and the standard library suffice. Proof records must be produced or
reviewed by the caller; this resolver does not authenticate self-reported evidence.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

STAGES = ("experiment", "poc", "prototype", "mvp", "beta", "production")
TARGETS = ("vps_smoke", "demo", "staging", "live")
FEATURES = {"persistence", "workers", "auth", "schema", "frontend", "integrations"}
LEGACY = {"demo": "prototype", "prototype": "prototype", "PoC": "poc",
          "MVP": "mvp", "production": "production", "other": "mvp"}
CATALOG = Path(__file__).resolve().parents[2] / "templates/ai/readiness-catalog.json"


def profile_digest(profile: dict) -> str:
    """Bind a proof to every readiness input, including target and maturity.

    Args: profile is JSON-compatible non-secret configuration.
    Returns: SHA-256 of canonical JSON. Raises TypeError for unsupported values.
    Side effects: None; no filesystem, database or network interaction.
    """
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def migrate_stage(value: str, kind: str) -> dict:
    """Map historical stages while retaining a mandatory auditable legacy floor.

    Args: value is the exact old stage; kind is react/django/contract/adopted.
    Returns: Proposed stage and legacy metadata; unknown values remain unresolved.
    Raises: ValueError for an unsupported kind. No writes, DB or network effects.
    Business rules: Explicit 'other' keeps MVP; absence is never an implicit MVP.
    """
    if kind not in ("react", "django", "contract", "adopted"):
        raise ValueError("Unknown template kind")
    stage = LEGACY.get(value)
    requirements = [f"legacy_{kind}_{value.lower()}"] if stage and kind in ("django", "contract") else []
    return {"stage": stage, "legacy": {"original": value, "kind": kind,
            "floor_stage": stage, "required_checks": requirements,
            "resolution": "mapped" if stage else "unresolved"}}


def validate(profile: dict) -> None:
    """Reject unresolved or malformed profiles rather than skip required checks.

    Args: profile contains explicit stage/target/kind/exposure/data/features,
        phase and artifact/config identifiers; legacy is optional migration data.
    Returns: None. Raises ValueError for missing, unknown or inconsistent fields.
    Side effects: None; no DB/network use. Credentials never belong in a profile.
    """
    enums = {"stage": STAGES, "target": TARGETS,
             "kind": ("react", "django", "contract", "adopted"),
             "exposure": ("local", "private", "public"),
             "data": ("synthetic", "real", "sensitive"),
             "phase": ("pre_deploy", "post_deploy")}
    if not isinstance(profile, dict):
        raise ValueError("Profile must be an object")
    for field, allowed in enums.items():
        if profile.get(field) not in allowed:
            raise ValueError(f"Unknown or missing {field}")
    for field in ("artifact", "config"):
        if not isinstance(profile.get(field), str) or not profile[field].strip():
            raise ValueError(f"Missing {field} identity")
    features = profile.get("features")
    if not isinstance(features, list) or any(not isinstance(item, str) or item not in FEATURES for item in features) or len(features) != len(set(features)):
        raise ValueError("Features must be an explicit unique list of verified capabilities")
    if profile["kind"] == "contract" and profile.get("contract_mode") not in ("artifact", "mock"):
        raise ValueError("Contract requires artifact/mock mode")
    if "legacy" in profile:
        legacy = profile["legacy"]
        if not isinstance(legacy, dict) or not isinstance(legacy.get("original"), str):
            raise ValueError("Invalid legacy migration")
        expected = migrate_stage(legacy["original"], profile["kind"])["legacy"]
        if expected["resolution"] != "mapped" or any(legacy.get(key) != value for key, value in expected.items()):
            raise ValueError("Unresolved or weakened legacy floor")


def matches(predicate: dict, profile: dict) -> bool:
    """Evaluate a conjunction of explicit enum/capability predicates.

    Args: predicate maps fields to accepted values; profile is validated input.
    Returns: True if every field matches. Raises ValueError for unknown fields.
    Side effects: None; no database, subprocess or network operations.
    """
    if not isinstance(predicate, dict):
        raise ValueError("Predicate must be an object")
    allowed = {"stage": STAGES, "target": TARGETS,
               "kind": ("react", "django", "contract", "adopted"),
               "exposure": ("local", "private", "public"),
               "data": ("synthetic", "real", "sensitive"),
               "phase": ("pre_deploy", "post_deploy"), "features": FEATURES,
               "contract_mode": ("artifact", "mock"),
               "legacy_requirement": {f"legacy_{kind}_{value.lower()}" for kind in ("django", "contract") for value in LEGACY}}
    for field, values in predicate.items():
        if field not in allowed or not isinstance(values, list) or not values or any(not isinstance(value, str) or value not in allowed[field] for value in values):
            raise ValueError(f"Invalid predicate values: {field}")
    for field, values in predicate.items():
        if field == "legacy_requirement":
            actual = profile.get("legacy", {}).get("required_checks", [])
        elif field in {"stage", "target", "kind", "exposure", "data", "phase", "features", "contract_mode"}:
            actual = profile.get(field)
        else:
            raise ValueError(f"Unknown predicate field: {field}")
        if isinstance(actual, list):
            if not set(actual).intersection(values):
                return False
        elif actual not in values:
            return False
    return True


def checklist(profile: dict, catalog_path: Path = CATALOG) -> list[dict]:
    """Resolve stage, deployment and inherited requirements deterministically.

    Args: profile is explicit readiness configuration; catalog_path is a JSON file.
    Returns: Applicable rules sorted by stable ID, with legacy floors retained.
    Raises: ValueError for malformed inputs/catalog; filesystem/JSON errors propagate.
    Side effects: Reads the catalog only, no DB or network; never executes commands.
    """
    validate(profile)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 1 or not isinstance(catalog.get("rules"), list):
        raise ValueError("Unsupported readiness catalog")
    identifiers = [row["id"] for row in catalog["rules"]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate readiness IDs")
    profiles = [profile]
    if profile.get("legacy"):
        profiles.append(profile | {"stage": profile["legacy"]["floor_stage"]})
    result = []
    for row in catalog["rules"]:
        if not isinstance(row.get("mandatory"), bool) or row.get("severity") not in ("blocker", "advisory"):
            raise ValueError("Invalid requirement severity")
        if type(row.get("ttl_seconds")) is not int or row["ttl_seconds"] <= 0:
            raise ValueError("Invalid evidence TTL")
        if not isinstance(row.get("when"), list) or not row["when"] or not isinstance(row.get("unless"), list):
            raise ValueError("Invalid requirement applicability")
        for predicate in row["when"] + row["unless"]:
            matches(predicate, profile)
        for candidate in profiles:
            if any(matches(condition, candidate) for condition in row["when"]) and not any(matches(condition, candidate) for condition in row["unless"]):
                result.append(dict(row))
                break
    return sorted(result, key=lambda row: row["id"])


def verdict(profile: dict, evidence: list[dict], *, now: float | None = None,
            catalog_path: Path = CATALOG) -> dict:
    """Aggregate exact-profile evidence without converting missing proof to PASS.

    Args: profile identifies artifact/config/stage/target; evidence contains ID,
        status, bindings, timestamp and a sanitized relative evidence path; now
        is Unix time (current time by default); catalog_path selects requirements.
    Returns: Verdict, digest, resolved checks and deployment-not-performed marker.
    Raises: ValueError for duplicate/invalid proof records or unsafe evidence paths.
    Side effects: Catalog read and optional clock read only; no DB/network/deploy.
    Business rules: Mandatory FAIL outranks missing proof, which outranks optional
        limitations. Wrong bindings, future/expired proof and mandatory N/A are
        NOT_VERIFIED. Readiness never proves host access without target evidence.
    """
    rows = checklist(profile, catalog_path)
    current = time.time() if now is None else now
    if not isinstance(current, (int, float)) or not math.isfinite(current):
        raise ValueError("Invalid evaluation time")
    binding = profile_digest(profile)
    catalog_digest = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    records = {}
    for record in evidence:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ValueError("Invalid evidence record")
        if record["id"] in records:
            raise ValueError("Duplicate evidence IDs")
        if record.get("status") not in ("PASS", "FAIL", "NOT_APPLICABLE", "NOT_VERIFIED"):
            raise ValueError("Invalid evidence status")
        path = record.get("evidence", "")
        parts = path.replace("\\", "/").split("/") if isinstance(path, str) else []
        if not parts or not path or Path(path).is_absolute() or ":" in path or ".." in parts or any(part.startswith(".env") or part.lower() in ("secrets", "credentials") for part in parts):
            raise ValueError("Evidence requires a sanitized relative non-secret path")
        records[record["id"]] = record
    checks = []
    for row in rows:
        record = records.get(row["id"], {})
        timestamp = record.get("observed_at")
        bound = (all(record.get(field) == profile[field] for field in ("artifact", "config", "phase"))
                 and record.get("profile_digest") == binding
                 and record.get("catalog_digest") == catalog_digest)
        fresh = isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool) and math.isfinite(timestamp) and 0 <= current - timestamp <= row["ttl_seconds"]
        status = record.get("status", "NOT_VERIFIED") if bound and fresh else "NOT_VERIFIED"
        if row["mandatory"] and status == "NOT_APPLICABLE":
            status = "NOT_VERIFIED"
        checks.append({"id": row["id"], "mandatory": row["mandatory"], "status": status})
    failed = any(row["mandatory"] and row["status"] == "FAIL" for row in checks)
    missing = any(row["mandatory"] and row["status"] != "PASS" for row in checks)
    limited = any(not row["mandatory"] and row["status"] not in ("PASS", "NOT_APPLICABLE") for row in checks)
    result = "NOT_READY" if failed else "NOT_VERIFIED" if missing else "READY_WITH_LIMITATIONS" if limited else "READY"
    return {"schema_version": 1, "verdict": result, "profile_digest": binding,
            "catalog_digest": catalog_digest,
            "profile": profile, "checks": checks, "deployment_performed": False}


def main() -> int:
    """Print checklist/verdict JSON for explicit profile and evidence files.

    Args: CLI profile path, optional --evidence path and --now Unix time.
    Returns: 0 ready/checklist, 1 NOT_READY, 2 NOT_VERIFIED/invalid inputs.
    Side effects: Non-secret input reads and stdout only; no DB/network/deployment.
    Errors: Invalid JSON/config and I/O failures produce an actionable stderr error.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--now", type=float)
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        if args.evidence is None:
            print(json.dumps({"profile_digest": profile_digest(profile), "checks": checklist(profile)}, indent=2))
            return 0
        records = json.loads(args.evidence.read_text(encoding="utf-8"))
        result = verdict(profile, records, now=args.now)
        print(json.dumps(result, indent=2))
        return {"READY": 0, "READY_WITH_LIMITATIONS": 0, "NOT_READY": 1, "NOT_VERIFIED": 2}[result["verdict"]]
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"Readiness input error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
