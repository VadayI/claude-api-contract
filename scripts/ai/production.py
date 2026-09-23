"""Generate and deliver the contract instruction/seed payload conservatively."""

import argparse
import json
from pathlib import Path
import re
import sys

from adapters import outputs, read_source
from core_paths import contained, digest
from core_sync import safe_name, target_root, verify
from generate_adapters import plan as adapter_plan, MANIFEST as ADAPTERS
from schema import load_json

MANIFEST = "docs/ai/production-manifest.json"
INPUTS = "templates/ai/production-inputs.json"


def records(document: dict, hashed: bool) -> dict:
    """Validate ownership records before using metadata to authorize any write.

    Args: document is decoded JSON; hashed selects a generated digest requirement.
    Returns: The validated path-to-record mapping. Raises: ValueError on malformed
        versions, hashes, fields or ownership. No I/O, side effects, DB/network.
    """
    if not isinstance(document, dict) or set(document) != {"schema_version", "files"} or document["schema_version"] != 1 or not isinstance(document["files"], dict):
        raise ValueError("Invalid production ownership document")
    for name, record in document["files"].items():
        required = {"ownership", "sha256"} if hashed else {"ownership"}
        allowed = required | {"legacy_sha256"}
        if not isinstance(name, str) or not isinstance(record, dict) or not required.issubset(record) or set(record) - allowed or record["ownership"] not in ("template", "mixed", "project"):
            raise ValueError("Invalid production ownership record")
        for key in ("sha256", "legacy_sha256"):
            if key in record and (not isinstance(record[key], str) or not re.fullmatch(r"[0-9a-f]{64}", record[key])):
                raise ValueError("Invalid production ownership digest")
    names = document["files"]
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("Case-insensitive production path collision")
    return names


def payload_text(root: Path, name: str) -> str:
    """Read a public payload path, allowing only the literal env example.

    Args: root is source; name is an explicit manifest path. Returns: UTF-8 text.
    Raises: ValueError for secret/runtime/Git paths or links; I/O propagates.
    Side effects: Public file reads only; no DB/network. Actual env/local settings
        and private-key names are rejected before opening their contents.
    """
    if name != ".env.example":
        safe_name(name)
    path = Path(name)
    if path.suffix.lower() in (".pem", ".key", ".p12", ".pfx") or path.name in (
        "settings.local.json", "id_rsa", "id_ed25519"
    ) or path.name.startswith("credentials"):
        raise ValueError(f"Private payload path: {name}")
    return contained(root, name).read_text(encoding="utf-8")


def manifest(root: Path, generated: dict[str, str]) -> str:
    """Describe every explicit payload path with its normalized content digest.

    Args: root contains reviewed inputs; generated maps adapter paths to text.
    Returns: Deterministically serialized ownership manifest, excluding itself.
    Raises: ValueError/OSError for invalid paths or unavailable source files.
    Side effects: Reads public template inputs only; no writes, secrets, DB/network.
    Business rules: Input membership is explicit, never inferred from untracked files.
    """
    inputs = records(load_json(contained(root, INPUTS)), False)
    result = {}
    for name, metadata in sorted(inputs.items()):
        text = generated[name] if name in generated else payload_text(root, name)
        result[name] = {**metadata, "sha256": digest(text)}
    for name, text in sorted(generated.items()):
        result.setdefault(name, {"ownership": "mixed" if name == "CLAUDE.md" else "template"})
        result[name]["sha256"] = digest(text)
    return json.dumps({"schema_version": 1, "files": result}, sort_keys=True, indent=2) + "\n"


def generation(root: Path) -> tuple[dict[str, str], list[str]]:
    """Plan adapters and full payload metadata while preserving custom outputs.

    Args: root is the contract source checkout. Returns: Pending writes/conflicts.
    Raises: ValueError on local-core/source drift; filesystem errors propagate.
    Side effects: Reads only; no subprocess, database, network or global settings.
    Legacy import is allowed only for the exact reviewed baseline hashes.
    """
    drift = verify(root)
    if drift:
        raise ValueError(f"Core drift: {drift}")
    pending, conflicts = adapter_plan(root)
    rendered = outputs(root)
    inputs = records(load_json(contained(root, INPUTS)), False)
    for name in list(conflicts):
        accepted = inputs.get(name, {}).get("legacy_sha256")
        if accepted and digest(read_source(root, name)) == accepted:
            pending[name] = rendered[name]
            conflicts.remove(name)
    rendered[ADAPTERS] = pending.get(ADAPTERS, read_source(root, ADAPTERS) if contained(root, ADAPTERS).exists() else "")
    text = manifest(root, rendered)
    current = contained(root, MANIFEST)
    if not current.exists() or current.read_text(encoding="utf-8") != text:
        pending[MANIFEST] = text
    return pending, conflicts


def delivery(source: Path, target: Path) -> tuple[dict[str, str], list[str]]:
    """Preflight a fresh seed or update without reading project-owned content.

    Args: source is verified payload; target is a nonlinked project directory.
    Returns: UTF-8 pending writes and conflicting paths; neither tree is changed.
    Raises: ValueError for source drift/invalid receipts/unsafe paths; I/O propagates.
    Side effects: Reads listed public files/receipts only; no secret, DB/network use.
    Project notes are seed-once; mixed custom config requires manual reconciliation.
    Exact old template files can migrate; no force flag bypasses ownership.
    """
    source, target = target_root(source), target_root(target)
    pending_generation, conflicts = generation(source)
    if pending_generation or conflicts:
        raise ValueError("Source generation drift: regenerate the reviewed source first")
    incoming_text = read_source(source, MANIFEST)
    incoming = records(load_json(contained(source, MANIFEST)), True)
    receipt = contained(target, MANIFEST)
    previous = load_json(receipt) if receipt.exists() else {"schema_version": 1, "files": {}}
    previous = records(previous, True)
    pending, conflicts = {}, []
    for name, metadata in incoming.items():
        content = payload_text(source, name)
        if digest(content) != metadata["sha256"]:
            raise ValueError(f"Source digest mismatch: {name}")
        path = contained(target, name)
        if path.exists():
            if metadata["ownership"] == "project":
                continue
            current = path.read_text(encoding="utf-8")
            if current == content:
                continue
            old = previous.get(name, {})
            known_old = metadata.get("legacy_sha256") == digest(current)
            owned = old.get("ownership") == "template" and old.get("sha256") == digest(current)
            if not (known_old or metadata["ownership"] == "template" and owned):
                conflicts.append(name)
                continue
        pending[name] = content
    if not receipt.exists() or receipt.read_text(encoding="utf-8") != incoming_text:
        pending[MANIFEST] = incoming_text
    return pending, conflicts


def apply(root: Path, pending: dict[str, str]) -> None:
    """Write a fully preflighted payload, with the receipt written last.

    Args: root is a contained destination; pending is the approved text plan.
    Returns: None. Raises: OSError on failed writes; already-written identical
        files are accepted when retrying. No deletion or full atomic rollback.
    Side effects: Creates listed directories/files only; no DB/network/secret use.
    """
    for name in sorted(pending, key=lambda item: (item == MANIFEST, item)):
        path = contained(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pending[name], encoding="utf-8", newline="\n")


def main() -> int:
    """Generate/check this source or preview/apply a seed to an explicit target.

    Args: CLI --target selects delivery, otherwise generation; --apply writes,
        --check fails on pending changes. Returns: 0 valid, 1 conflict/drift,
        2 invalid input. Side effects: --apply performs preflighted writes only.
    Errors are reported without file contents; no DB/network/global mutations.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    try:
        root = target_root(Path(__file__).resolve().parents[2])
        target = target_root(args.target) if args.target else root
        pending, conflicts = delivery(root, target) if args.target else generation(root)
        print(json.dumps({"writes": sorted(pending), "conflicts": conflicts}))
        if conflicts or args.check and pending:
            return 1
        if args.apply:
            apply(target, pending)
        return 0
    except (OSError, UnicodeError):
        print("Production delivery error: unreadable public file; no content shown", file=sys.stderr)
        return 2
    except (ValueError, KeyError) as error:
        print(f"Production delivery error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
