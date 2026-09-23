"""Generate or read-only check the independently installable core draft manifest."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from schema import check_schema, load_json


def manifest(root: Path) -> str:
    """Hash all core source/delivery files with normalized UTF-8 ownership.

    Args: root contains only the shared-core source, not application files.
    Returns: Deterministic JSON; the manifest excludes itself and Python caches.
    Raises: ValueError for linked paths or unsupported bundled schemas;
        file/decode errors propagate. Schemas are checked before publication.
    Side effects: File reads only; no database, subprocess or network operations.
    """
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"Linked core path: {path}")
        name = path.relative_to(root).as_posix()
        if not path.is_file() or "__pycache__" in path.parts or name == "docs/ai/core-manifest.json":
            continue
        if path.suffix not in (".md", ".py", ".json", ".sh", ".ps1", ".toml"):
            raise ValueError(f"Unclassified core file: {name}")
        text = path.read_text(encoding="utf-8")
        if name.startswith("templates/ai/schemas/") and name.endswith(".schema.json"):
            check_schema(load_json(path))
        files[name] = {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "ownership": "template"}
    version = json.loads((root / "core.json").read_text(encoding="utf-8"))["version"]
    return json.dumps({"schema_version": 1, "phase": "P05-in-progress", "core_version": version, "files": files}, sort_keys=True, indent=2) + "\n"


def main() -> int:
    """Generate core ownership metadata or report drift without repairs.

    Args: CLI --check selects read-only operation.
    Returns: 0 consistent/generated; 1 drift. Argparse errors exit 2.
    Side effects: Generation writes one manifest; checks only read. No DB/network.
    Raises: Filesystem, unsafe path and decode errors propagate explicitly.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    root = Path(__file__).resolve().parents[2]
    destination = root / "docs/ai/core-manifest.json"
    content = manifest(root)
    if args.check:
        valid = destination.is_file() and destination.read_text(encoding="utf-8") == content
        print("PASS: core manifest" if valid else "FAIL: core manifest drift")
        return 0 if valid else 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8", newline="\n")
    print("PASS: generated core manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
