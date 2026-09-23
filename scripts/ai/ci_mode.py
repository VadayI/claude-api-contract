"""Materialize contract workflows only after an explicit project CI choice."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from core_paths import contained
from core_sync import target_root

WORKFLOWS = ("contract-checks.yml", "contract-audit.yml")
LEGACY_AUTO = ("contract-ci.yml", "contract-policy.yml", "scheduled-audit.yml")
PROJECT = "docs/project-state/project.json"
RECEIPT = "docs/ai/ci-workflow-receipt.json"
EVENTS = {
    "contract-checks.yml": ("  push:\n    branches: [main]\n  pull_request:\n    branches: [main]\n"
                            "  merge_group:\n  workflow_dispatch:\n    inputs:\n      base:\n"
                            "        description: Exact ancestor commit for manual verification\n"
                            "        required: true\n        type: string\n"),
    "contract-audit.yml": ("  schedule:\n    - cron: '0 6 * * 1'\n  workflow_dispatch:\n"
                           "    inputs:\n      base:\n"
                           "        description: Exact ancestor commit for manual audit\n"
                           "        required: false\n        type: string\n"),
}


def digest(content: str) -> str:
    """Hash normalized UTF-8 workflow text for ownership comparison.

    Args: content is decoded workflow text.
    Returns: Lowercase SHA-256 hex digest.
    Raises: None for a string input.
    Side effects: None; no filesystem, database, or network interaction.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def render(source: Path, filename: str, mode: str) -> str:
    """Render reviewed contract events while keeping exact runner jobs intact.

    Args: source is template root; filename is allowlisted; mode local/github.
    Returns: Workflow text with local manual-only or GitHub automatic events.
    Raises: ValueError for an unknown mode, source event drift or malformed YAML.
    Side effects: Reads one inert template; no writes, DB, or network access.
    Business rule: The job body and exact runner argv are identical by mode;
        unknown source trigger edits fail closed rather than being copied.
    """
    if filename not in WORKFLOWS or mode not in {"local", "github"}:
        raise ValueError("Unsupported contract workflow or mode")
    canonical = contained(source, f"templates/.github/workflows/{filename}").read_text(encoding="utf-8")
    name = "Contract exact checks" if filename == "contract-checks.yml" else "Contract exact audit"
    prefix = f"name: {name}\non:\n" + EVENTS[filename]
    marker = "\npermissions:\n"
    if not canonical.startswith(prefix + marker) or "\njobs:\n" not in canonical:
        raise ValueError(f"Unreviewed contract workflow events: {filename}")
    if mode == "github":
        return canonical
    manual = EVENTS[filename].split("  workflow_dispatch:\n", 1)[1]
    return f"name: {name}\non:\n  workflow_dispatch:\n" + manual + canonical[len(prefix):]


def project_text(target: Path, mode: str) -> str:
    """Save the explicit CI choice while retaining existing project fields.

    Args: target is derived root; mode is local/github.
    Returns: Stable project-owned JSON text.
    Raises: ValueError for invalid mode or unsupported existing metadata.
    Side effects: Reads project.json if present; no writes, DB, or network.
    Business rule: Fresh maturity is conservatively experiment; the artifact
        location is known, while contract pin/readiness remain unresolved.
    """
    if mode not in {"local", "github"}:
        raise ValueError("CI mode must be local or github")
    path = contained(target, PROJECT)
    if path.exists():
        config = json.loads(path.read_text(encoding="utf-8"))
        if config.get("schema_version") != 1 or not isinstance(config.get("ci"), dict):
            raise ValueError("Unsupported project configuration")
    else:
        config = {"schema_version": 1, "template": {"kind": "contract", "is_scaffold": False},
                  "ci": {}, "git": {"merge_policy": "user_command"},
                  "orchestration": {"coordinator_read": "reported_files_only"},
                  "maturity": {"stage": "experiment"},
                  "contract": {"source": "repo_pin", "artifact": "openapi.yml"},
                  "documentation": {}, "features": [], "deployment": {}}
    config["ci"]["execution"] = mode
    return json.dumps(config, indent=2, sort_keys=True) + "\n"


def plan(source: Path, target: Path, mode: str) -> tuple[dict[str, str], list[str]]:
    """Preflight both active workflows, receipt and saved project choice.

    Args: source is reviewed template; target is derived project; mode explicit.
    Returns: Pending path/text writes and sorted conflict paths.
    Raises: ValueError for invalid links, receipt, source or mode.
    Side effects: File reads only; no writes, database, Git, or network.
    Business rule: Unknown/custom active workflows and copied upstream auto
        workflows block all writes; unrelated workflows and project-owned
        preferences are preserved. A GitHub template copy cannot be certified
        local while its old automatic workflow files remain active.
    """
    source, target = target_root(source), target_root(target)
    receipt_path = contained(target, RECEIPT)
    previous = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    if previous and (previous.get("schema_version") != 1 or not isinstance(previous.get("files"), dict)):
        raise ValueError("Invalid contract CI ownership receipt")
    pending, conflicts, files = {}, [], {}
    for filename in LEGACY_AUTO:
        name = f".github/workflows/{filename}"
        if contained(target, name).exists():
            conflicts.append(name)
    for filename in WORKFLOWS:
        name = f".github/workflows/{filename}"
        incoming = render(source, filename, mode)
        path = contained(target, name)
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current is not None and current != incoming and digest(current) != previous.get("files", {}).get(name):
            conflicts.append(name)
        if current != incoming:
            pending[name] = incoming
        files[name] = digest(incoming)
    receipt = json.dumps({"schema_version": 1, "mode": mode, "files": files},
                         indent=2, sort_keys=True) + "\n"
    if not receipt_path.exists() or receipt_path.read_text(encoding="utf-8") != receipt:
        pending[RECEIPT] = receipt
    project_path = contained(target, PROJECT)
    project = project_text(target, mode)
    if not project_path.exists() or project_path.read_text(encoding="utf-8") != project:
        pending[PROJECT] = project
    return pending, sorted(conflicts)


def main() -> int:
    """Preview or apply selected contract CI mode with conflict-before-write.

    Args: CLI --target is derived root; --mode is required; --apply writes.
    Returns: 0 safe, 1 conflicts, 2 invalid metadata or filesystem state.
    Raises: None; supported errors are converted to exit two.
    Side effects: Apply writes only preflighted files; no database, network,
        Git mutation, workflow run, branch API, release, deploy, or merge.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=("local", "github"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ required")
    try:
        target = target_root(args.target)
        pending, conflicts = plan(Path(__file__).resolve().parents[2], target, args.mode)
        print(json.dumps({"writes": sorted(pending), "conflicts": conflicts}))
        if conflicts:
            return 1
        if args.apply:
            for name, content in pending.items():
                path = contained(target, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"Contract CI mode error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
