"""Resolve and migrate project-owned state from legacy agent paths."""

import argparse
import json
import os
from pathlib import Path
import sys

from core_paths import contained
from core_sync import target_root
import schema


PROJECT_STATE = {
    "project.json": "docs/project-state/project.json",
    "endpoints.json": "docs/project-state/endpoints.json",
    "routes.json": "docs/project-state/routes.json",
    "pages.json": "docs/project-state/pages.json",
    "template-sync.json": "docs/project-state/template-lineage.json",
}
RUNTIME_STATE = {
    "env-detect.json": ".ai-runtime/environment.json",
    "command-log.jsonl": ".ai-runtime/command-log.jsonl",
}
LEGACY_DIRECTORY = ".claude/memory"


def artifact_paths(root: Path, name: str, category: str = "project") -> tuple[Path, Path]:
    """Return canonical and legacy paths for one allowlisted state artifact.

    Args:
        root: Repository root containing the artifact locations.
        name: Allowlisted artifact basename, such as ``routes.json``.
        category: ``project`` for versioned state or ``runtime`` for local state.
    Returns:
        A pair containing the canonical path and its legacy ``.claude/memory`` path.
    Raises:
        ValueError: If the category or artifact is not in the explicit migration map.
    Side effects:
        Reads filesystem metadata to reject links; performs no writes, database
        access, subprocess calls, network access, or credential discovery.
    Business rules:
        Unknown legacy files are never assigned a destination automatically.
    """
    if category == "project":
        mapping = PROJECT_STATE
    elif category == "runtime":
        mapping = RUNTIME_STATE
    else:
        raise ValueError(f"Unknown state category: {category}")
    if name not in mapping:
        raise ValueError(f"Unknown {category} state artifact: {name}")
    root = target_root(root)
    return contained(root, mapping[name]), contained(root, f"{LEGACY_DIRECTORY}/{name}")


def resolve_state(root: Path, name: str, category: str = "project") -> Path:
    """Resolve a canonical state file, falling back to its legacy location.

    Args:
        root: Repository root containing canonical or legacy state.
        name: Allowlisted artifact basename.
        category: ``project`` or ``runtime`` artifact category.
    Returns:
        Canonical path when present, otherwise the legacy path when present;
        returns the canonical path when neither exists so callers can report a
        clear missing-file error.
    Raises:
        ValueError: If canonical and legacy copies differ, or a path is unsafe.
    Side effects:
        Reads metadata and, when both paths exist, bytes for equality comparison.
        Performs no writes, database access, subprocess calls, or network access.
    Business rules:
        Conflicting copies fail closed; modification times never choose a winner.
    """
    canonical, legacy = artifact_paths(root, name, category)
    if canonical.exists() and legacy.exists():
        if canonical.read_bytes() != legacy.read_bytes():
            raise ValueError(f"Conflicting state copies: {canonical} and {legacy}")
        return canonical
    if canonical.exists():
        return canonical
    if legacy.exists():
        return legacy
    return canonical


def writable_state_path(root: Path, name: str, category: str = "project") -> Path:
    """Return the canonical path for a new write only after legacy migration.

    Args:
        root: Repository root containing the state locations.
        name: Allowlisted artifact basename.
        category: ``project`` or ``runtime`` artifact category.
    Returns:
        Canonical project-state or runtime path.
    Raises:
        ValueError: If the legacy copy still exists or paths are unsafe.
    Side effects:
        Reads filesystem metadata only; it does not create directories or files,
        access a database, invoke subprocesses, or use the network.
    Business rules:
        New writes must not create a second independently writable copy beside
        an unmigrated legacy artifact.
    """
    canonical, legacy = artifact_paths(root, name, category)
    if legacy.exists():
        raise ValueError(f"Migrate legacy state before writing: {legacy}")
    return canonical


def _validate_artifact(name: str, content: bytes) -> None:
    """Validate a known JSON or JSONL artifact before copying it.

    Args:
        name: Allowlisted project or runtime artifact basename.
        content: Exact source bytes read from the legacy file.
    Returns:
        None when all records are valid JSON.
    Raises:
        ValueError: For invalid UTF-8, malformed JSON, duplicate keys, or
            non-standard JSON constants.
    Side effects:
        Parses in-memory data only; no writes, database, network, or subprocess.
    """
    text = content.decode("utf-8")
    if name.endswith(".jsonl"):
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                json.loads(line, object_pairs_hook=schema.unique_object,
                           parse_constant=schema.reject_constant)
            except ValueError as error:
                raise ValueError(f"Invalid {name} record at line {line_number}: {error}") from None
        return
    json.loads(text, object_pairs_hook=schema.unique_object,
               parse_constant=schema.reject_constant)


def _legacy_directory(root: Path) -> Path:
    """Resolve the legacy memory directory while rejecting linked ancestors.

    Args:
        root: Previously validated repository root.
    Returns:
        The absent or existing ``.claude/memory`` directory path.
    Raises:
        ValueError: If any component is a link, escapes root, or is not a directory.
    Side effects:
        Reads filesystem metadata only; performs no writes, database, subprocess,
        network, or credential access.
    """
    path = root / LEGACY_DIRECTORY
    current = root
    for part in Path(LEGACY_DIRECTORY).parts:
        current = current / part
        if current.is_symlink() or current.is_junction():
            raise ValueError(f"Linked legacy state path: {current}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Legacy state path escapes repository: {path}")
    if path.exists() and not path.is_dir():
        raise ValueError(f"Legacy state location is not a directory: {path}")
    return path


def plan_migration(root: Path) -> dict:
    """Inspect all allowlisted legacy artifacts without changing the repository.

    Args:
        root: Repository root whose ``.claude/memory`` directory is inspected.
    Returns:
        A deterministic report with artifact actions, conflicts, unknown names,
        and invalid artifact details; file contents are never included.
    Raises:
        OSError: If a selected path cannot be inspected or read.
        ValueError: If the root or one of the allowlisted paths traverses a link.
    Side effects:
        Reads only the explicitly allowlisted artifacts and directory entry names.
        Performs no writes, database access, subprocess calls, or network access.
    Business rules:
        Project registries/lineage go to ``docs/project-state``; detector and
        command logs go to gitignored ``.ai-runtime``. Unknown files remain
        untouched and are reported for human classification.
    """
    root = target_root(root)
    legacy_dir = _legacy_directory(root)
    report = {"actions": [], "conflicts": [], "invalid": [], "unknown": []}
    if legacy_dir.exists():
        known = set(PROJECT_STATE) | set(RUNTIME_STATE)
        report["unknown"] = sorted(item.name for item in legacy_dir.iterdir()
                                   if item.name not in known)

    for category, artifacts in (("project", PROJECT_STATE), ("runtime", RUNTIME_STATE)):
        for name in sorted(artifacts):
            canonical, legacy = artifact_paths(root, name, category)
            if not legacy.exists():
                continue
            if not legacy.is_file():
                raise ValueError(f"Legacy artifact is not a file: {legacy}")
            try:
                source = legacy.read_bytes()
                _validate_artifact(name, source)
            except (UnicodeError, ValueError) as error:
                report["invalid"].append({"legacy": legacy.relative_to(root).as_posix(),
                                          "reason": str(error)})
                continue
            if canonical.exists():
                if canonical.read_bytes() == source:
                    report["actions"].append({"artifact": name, "category": category,
                                              "status": "identical", "canonical": canonical.relative_to(root).as_posix()})
                else:
                    report["conflicts"].append({"artifact": name, "category": category,
                                                "canonical": canonical.relative_to(root).as_posix(),
                                                "legacy": legacy.relative_to(root).as_posix()})
                continue
            report["actions"].append({"artifact": name, "category": category,
                                      "status": "copy", "canonical": canonical.relative_to(root).as_posix(),
                                      "legacy": legacy.relative_to(root).as_posix()})
    return report


def _create_file(path: Path, content: bytes) -> None:
    """Create a destination exclusively and remove only its partial file on error.

    Args:
        path: Validated canonical destination that does not already exist.
        content: Exact bytes from the validated legacy source.
    Returns:
        None after the complete content has been written and flushed.
    Raises:
        FileExistsError: If another process created the destination after preflight.
        OSError: If directory creation or writing fails.
    Side effects:
        Creates parent directories and one file; no database, subprocess, or network.
    Business rules:
        Exclusive creation prevents replacing project-owned canonical content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(content)
            destination.flush()
            os.fsync(destination.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def apply_migration(root: Path) -> dict:
    """Copy nonconflicting verified legacy state to canonical locations.

    Args:
        root: Repository root to migrate.
    Returns:
        The post-migration report. Conflicting, invalid and unknown data are
        reported; valid canonical files are created and identical legacy copies
        are removed.
    Raises:
        OSError: If a source changes, a destination appears, or a write fails.
        ValueError: If a path is unsafe or a source changes after preflight.
    Side effects:
        Creates canonical files under ``docs/project-state`` or ``.ai-runtime``
        and removes a legacy file only after byte equality with its canonical
        copy is confirmed. No database, subprocess, or network access occurs.
    Business rules:
        Conflicts are isolated to their artifact; other verified items can move.
        Conflicts and unknown data remain untouched. Older unmigrated projects
        continue to use the legacy read fallback; migrated writes use only the
        canonical path.
    """
    root = target_root(root)
    before = plan_migration(root)
    for action in before["actions"]:
        if action["status"] not in {"copy", "identical"}:
            continue
        canonical, legacy = artifact_paths(root, action["artifact"], action["category"])
        source = legacy.read_bytes()
        _validate_artifact(action["artifact"], source)
        if action["status"] == "copy":
            _create_file(canonical, source)
        if canonical.read_bytes() == source and legacy.read_bytes() == source:
            legacy.unlink()
    return plan_migration(root)


def main() -> int:
    """Preview or apply allowlisted shared-state migration for a project.

    Args:
        CLI options select a repository root and optional ``--apply`` operation.
    Returns:
        0 when there are no conflicts/invalid artifacts, 1 when any conflict or
        invalid artifact remains, and 2 for unsafe paths or I/O errors.
    Raises:
        None; expected path and content errors are converted to exit codes.
    Side effects:
        Preview is read-only. ``--apply`` creates canonical copies for safe
        artifacts but never deletes legacy files or writes a database.
    Business rules:
        A conflict is never resolved by timestamp or by automatic overwrite.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    try:
        report = apply_migration(args.root) if args.apply else plan_migration(args.root)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        return 1 if report["conflicts"] or report["invalid"] or report["unknown"] else 0
    except (OSError, ValueError) as error:
        print(f"Project state migration error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
