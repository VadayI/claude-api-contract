"""Preview, generate or check runtime adapters with conservative ownership updates."""

import argparse
import json
from pathlib import Path
import sys

from adapters import outputs, read_source
from core_paths import contained, digest
from core_sync import safe_name, target_root
from schema import load_json

MANIFEST = "docs/ai/generated/adapters-manifest.json"
LEGACY = "docs/ai/delivery-manifest.json"


def receipt(root: Path, name: str) -> dict:
    """Read optional ownership metadata and reject invalid records before planning.

    Args: root is a nonlinked project; name is a known manifest-relative path.
    Returns: Validated metadata or an empty mapping when absent.
    Raises: ValueError/OSError for malformed or inaccessible metadata/unsafe paths.
    Side effects: Reads one JSON file; no writes, database, subprocess or network.
    """
    path = contained(root, name)
    if not path.exists():
        return {}
    document = load_json(path)
    if not isinstance(document, dict) or document.get("schema_version") != 1 or not isinstance(document.get("files"), dict):
        raise ValueError("Invalid adapter ownership manifest")
    for filename, record in document["files"].items():
        safe_name(filename)
        if not isinstance(record, dict) or record.get("ownership") not in ("template", "mixed") or not isinstance(record.get("sha256"), str):
            raise ValueError("Invalid adapter ownership record")
    return document


def plan(root: Path, import_legacy: bool = False) -> tuple[dict[str, str], list[str]]:
    """Render a complete candidate and preserve customized outputs/settings.

    Args: root contains canonical catalog/sources; import_legacy explicitly accepts
        unmodified template outputs recorded by the React pilot delivery manifest.
    Returns: Pending UTF-8 writes and conflict paths; no changes are applied.
    Raises: ValueError/OSError for invalid sources, paths, collisions or receipts.
    Side effects: Local reads only; no database, network or subprocess operations.
    Mixed CLAUDE.md is created if absent or accepted when identical, never replaced
    with different contents. Removed generated files require explicit reconciliation.
    """
    root = target_root(root)
    generated = outputs(root)
    if len(read_source(root, "AGENTS.md").encode("utf-8")) > 16384:
        raise ValueError("AGENTS.md exceeds the 16 KiB startup budget")
    catalog = load_json(contained(root, "docs/ai/catalog.json"))
    sources = {"AGENTS.md", "docs/ai/catalog.json"}
    sources.update(item["path"] for item in catalog["rules"])
    sources.update(item["path"] for item in catalog["roles"].values())
    sources.update(catalog["workflows"].values())
    names = [*generated, MANIFEST]
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("Case-insensitive generated path collision")
    if {name.casefold() for name in names} & {name.casefold() for name in sources}:
        raise ValueError("Generated output collides with canonical source")
    previous = receipt(root, MANIFEST)
    legacy = receipt(root, LEGACY) if import_legacy and not previous else {}
    records = previous.get("files", legacy.get("files", {}))
    pending, conflicts = {}, []
    for name, incoming in generated.items():
        safe_name(name)
        destination = contained(root, name)
        if not destination.exists():
            pending[name] = incoming
            continue
        current = destination.read_text(encoding="utf-8")
        if current == incoming:
            continue
        old = records.get(name, {})
        if name != "CLAUDE.md" and old.get("ownership") == "template" and digest(current) == old.get("sha256"):
            pending[name] = incoming
        else:
            conflicts.append(name)
    for name in set(previous.get("files", {})) - generated.keys():
        if contained(root, name).exists():
            conflicts.append(name)
    metadata = {"schema_version": 1, "generator": "family-core",
                "sources": {name: digest(read_source(root, name)) for name in sorted(sources)},
                "files": {name: {"sha256": digest(text), "ownership": "mixed" if name == "CLAUDE.md" else "template"}
                          for name, text in sorted(generated.items())}}
    content = json.dumps(metadata, sort_keys=True, indent=2) + "\n"
    path = contained(root, MANIFEST)
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        pending[MANIFEST] = content
    return pending, sorted(set(conflicts))


def main() -> int:
    """Preview by default, explicitly apply, or check drift without repairs.

    Args: CLI --root, --check/--apply and optional --import-legacy select operation.
    Returns: 0 consistent/planned/applied; 1 conflicts/drift; 2 invalid input.
    Side effects: Apply writes only a fully preflighted set, manifest last. Other
        modes read only; no deletion, database, network, model or trust changes.
    Interrupted generation can be repeated: outputs already equal to the candidate
    are accepted. Concurrent writers and full transactional rollback are unsupported.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--import-legacy", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    try:
        root = target_root(args.root)
        pending, conflicts = plan(root, args.import_legacy)
        print(json.dumps({"mode": "apply" if args.apply else "check" if args.check else "preview",
                          "writes": sorted(pending), "conflicts": conflicts}))
        if conflicts or (args.check and pending):
            return 1
        if args.apply:
            for name, content in pending.items():
                destination = contained(root, name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8", newline="\n")
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f"Adapter generation error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
