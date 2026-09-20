"""Install shared-core draft files with explicit, non-destructive updates."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


def contained(root: Path, name: str) -> Path:
    """Resolve a regular relative destination without traversing symbolic links.

    Args: root is the installation directory; name is a manifest-relative path.
    Returns: A contained path, which need not exist yet.
    Raises: ValueError for absolute paths, traversal, symlinks or directories.
    Side effects: Filesystem metadata reads only; no database or network access.
    """
    relative = Path(name)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError(f"Unsafe path: {name}")
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"Linked path: {name}")
    if not path.resolve().is_relative_to(root.resolve()) or path.is_dir():
        raise ValueError(f"Invalid destination: {name}")
    return path


def digest(text: str) -> str:
    """Hash normalized UTF-8 text for cross-platform ownership comparison.

    Args: text is decoded text with universal newlines already normalized.
    Returns: Hexadecimal SHA-256. No side effects, exceptions or DB interaction.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan(source: Path, target: Path) -> tuple[dict[str, str], list[str]]:
    """Preflight the complete payload and preserve locally customized files.

    Args: source contains the generated manifest; target is the project directory.
    Returns: Pending UTF-8 writes and conflict paths; never writes either tree.
    Raises: ValueError for corrupt manifests, digest mismatches or unsafe paths;
        OSError/UnicodeError for unreadable files.
    Business rules: Missing/identical files are safe. Previously installed,
        unmodified template files may update; mixed-ownership entry points require
        manual reconciliation when different. No deletion or execution occurs.
    Side effects: Reads project and template files only; no DB or network access.
    """
    manifest_name = "docs/ai/core-manifest.json"
    manifest_text = contained(source, manifest_name).read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported source manifest")
    previous_path = contained(target, manifest_name)
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    if previous and previous.get("schema_version") != 1:
        raise ValueError("Unsupported installed manifest")
    pending, conflicts = {}, []
    for name, metadata in manifest["files"].items():
        incoming = contained(source, name).read_text(encoding="utf-8")
        if digest(incoming) != metadata["sha256"]:
            raise ValueError(f"Source digest mismatch: {name}; regenerate first")
        destination = contained(target, name)
        if not destination.exists():
            pending[name] = incoming
            continue
        existing = destination.read_text(encoding="utf-8")
        if existing == incoming:
            continue
        old = previous.get("files", {}).get(name, {})
        if metadata["ownership"] == "template" and old.get("ownership") == "template" and digest(existing) == old.get("sha256"):
            pending[name] = incoming
        else:
            conflicts.append(name)
    if not previous_path.exists() or previous_path.read_text(encoding="utf-8") != manifest_text:
        pending[manifest_name] = manifest_text
    return pending, conflicts


def main() -> int:
    """Preview or apply a fully preflighted instruction delivery.

    Args: CLI --target selects the project; --apply enables writes.
    Returns: 0 for a valid plan/application, 1 for conflicts; argparse errors exit 2.
    Side effects: --apply creates only planned files/directories after preflight.
        Preview and conflicting plans write nothing. No subprocess/network/DB use.
    Raises: Filesystem errors propagate; interrupted writes can be safely retried.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    source = Path(__file__).resolve().parents[2]
    target = args.target.absolute()
    if target.is_symlink() or target.is_junction():
        parser.error("Target cannot be a linked directory")
    pending, conflicts = plan(source, target)
    print(json.dumps({"mode": "apply" if args.apply else "preview", "writes": sorted(pending), "conflicts": sorted(conflicts)}, indent=2))
    if conflicts:
        print("No files written. Reconcile conflicts explicitly; local files are preserved.")
        return 1
    if args.apply:
        for name, content in pending.items():
            destination = contained(target, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
