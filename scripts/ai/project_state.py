"""Resolve and migrate project-owned state from legacy agent paths."""

import argparse
import json
import os
from pathlib import Path
import re
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
    # Raport stack-specyficznego probe'a (detect-env.mjs / detect-env.py) zachowuje
    # własny schemat; .ai-runtime/environment.json jest zarezerwowany dla raportu
    # wspólnego detektora (scripts/ai/detector.py --write).
    "env-detect.json": ".ai-runtime/env-detect.json",
    "command-log.jsonl": ".ai-runtime/command-log.jsonl",
}
CATEGORIES = {"project": PROJECT_STATE, "runtime": RUNTIME_STATE}
LEGACY_DIRECTORY = ".claude/memory"
# Preferencja języka: kanoniczna dla obu runtime'ów, legacy tylko dla Claude.
LANGUAGE_CANONICAL = "docs/ai/overrides/output-language.md"
LANGUAGE_LEGACY = ".claude/rules/output-language.md"
LANGUAGE_POINTER = (
    "# Output language (moved)\n\n"
    "The project language preference lives in `docs/ai/overrides/output-language.md`,\n"
    "which Claude and Codex read through AGENTS.md. Read and follow that file. Do not\n"
    "edit this pointer; `python scripts/ai/project_state.py --root . --language`\n"
    "reports the state.\n"
)
LANGUAGE_PATTERN = re.compile(r"Always respond in ([^.\n{}]+?)\.")


def artifact_relative_paths(name: str, category: str = "project") -> tuple[str, str]:
    """Return canonical and legacy root-relative POSIX paths for one artifact.

    Args:
        name: Allowlisted artifact basename, such as ``routes.json``.
        category: ``project`` for versioned state or ``runtime`` for local state.
    Returns:
        A pair ``(canonical, legacy)`` suitable for comparing against Git
        changed-file lists, which are always root-relative POSIX strings.
    Raises:
        ValueError: If the category or artifact is not in the explicit migration map.
    Side effects:
        None; no filesystem, database, subprocess, or network access.
    Business rules:
        Policy gates accept either spelling while a project may be unmigrated,
        but never a third location.
    """
    mapping = CATEGORIES.get(category)
    if mapping is None:
        raise ValueError(f"Unknown state category: {category}")
    if name not in mapping:
        raise ValueError(f"Unknown {category} state artifact: {name}")
    return mapping[name], f"{LEGACY_DIRECTORY}/{name}"


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
    canonical, legacy = artifact_relative_paths(name, category)
    root = target_root(root)
    return contained(root, canonical), contained(root, legacy)


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


def _selected_categories(categories: tuple[str, ...] | None) -> tuple[str, ...]:
    """Validate the requested migration categories in their canonical order.

    Args:
        categories: Optional subset of ``project``/``runtime``; ``None`` selects both.
    Returns:
        The selected category names ordered ``project`` then ``runtime``.
    Raises:
        ValueError: If a name is outside the explicit category map.
    Side effects:
        None.
    """
    selected = tuple(CATEGORIES) if categories is None else tuple(categories)
    unknown = [name for name in selected if name not in CATEGORIES]
    if unknown:
        raise ValueError(f"Unknown state category: {unknown[0]}")
    return tuple(name for name in CATEGORIES if name in selected)


def plan_migration(root: Path, categories: tuple[str, ...] | None = None) -> dict:
    """Inspect all allowlisted legacy artifacts without changing the repository.

    Args:
        root: Repository root whose ``.claude/memory`` directory is inspected.
        categories: Optional subset of ``project``/``runtime`` artifacts to plan;
            the default inspects both. Unknown legacy names are always reported.
    Returns:
        A deterministic report with artifact actions, conflicts, unknown names,
        and invalid artifact details; file contents are never included.
    Raises:
        OSError: If a selected path cannot be inspected or read.
        ValueError: If the root or one of the allowlisted paths traverses a link,
            or a category name is unknown.
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

    for category in _selected_categories(categories):
        artifacts = CATEGORIES[category]
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


def apply_migration(root: Path, categories: tuple[str, ...] | None = None) -> dict:
    """Copy nonconflicting verified legacy state to canonical locations.

    Args:
        root: Repository root to migrate.
        categories: Optional subset of ``project``/``runtime`` artifacts to move;
            the default migrates both categories.
    Returns:
        The post-migration report for the selected categories. Conflicting,
        invalid and unknown data are reported; valid canonical files are created
        and legacy copies are removed only after byte equality is confirmed.
    Raises:
        OSError: If a source changes, a destination appears, or a write fails.
        ValueError: If a path is unsafe, a category is unknown, or a source
            changes after preflight.
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
    before = plan_migration(root, categories)
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
    return plan_migration(root, categories)


def migrate_runtime(root: Path) -> dict:
    """Move only machine-local runtime records before a runtime writer runs.

    Args:
        root: Repository root whose legacy runtime files should move.
    Returns:
        The post-migration report restricted to the ``runtime`` category.
    Raises:
        OSError: If a runtime file cannot be read, created, or removed.
        ValueError: If a path is unsafe or the root traverses a link.
    Side effects:
        Same as :func:`apply_migration` for ``.ai-runtime`` artifacts only;
        project registries and unknown files are never touched.
    Business rules:
        Runtime writers (detector hooks, command loggers) may migrate their own
        gitignored records automatically because they are disposable; a runtime
        conflict is still reported and the writer must refuse instead of
        creating a second copy.
    """
    return apply_migration(root, ("runtime",))


def _language_text(path: Path) -> str | None:
    """Read one language preference file with normalized newlines.

    Args:
        path: Canonical or legacy language path produced by :func:`contained`.
    Returns:
        UTF-8 text with ``\\r\\n`` normalized to ``\\n``, or ``None`` if absent.
    Raises:
        ValueError: If the path is a directory.
        OSError/UnicodeError: If the file cannot be read as UTF-8.
    Side effects:
        Reads one file; no writes, network or database.
    """
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Language preference is not a file: {path}")
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def language_state(root: Path) -> dict:
    """Describe the project output-language preference and its migration state.

    Args:
        root: Repository root.
    Returns:
        ``{"status", "canonical", "legacy", "legacy_kind", "language", "source"}``.
        Status is ``none`` (no preference), ``canonical`` (only the shared file
        or a pointer beside it), ``legacy`` (only the Claude-specific file),
        ``identical`` (both hold the same preference), ``conflict`` (they
        differ) or ``pointer-only`` (a pointer without its canonical file).
        ``language`` is the native name parsed from the effective file, or
        ``None`` when absent or still a template placeholder.
    Raises:
        ValueError: For linked or non-file paths.
        OSError/UnicodeError: If an existing file cannot be read.
    Side effects:
        Reads at most the two allowlisted files; no writes, network or database.
    Business rules:
        The shared file is authoritative once present; a legacy copy with a
        different preference is a conflict for a human, never resolved by mtime.
    """
    root = target_root(root)
    canonical_path = contained(root, LANGUAGE_CANONICAL)
    legacy_path = contained(root, LANGUAGE_LEGACY)
    canonical, legacy = _language_text(canonical_path), _language_text(legacy_path)
    legacy_kind = None if legacy is None else ("pointer" if legacy == LANGUAGE_POINTER else "preference")
    if canonical is None and legacy_kind is None:
        status = "none"
    elif canonical is None:
        status = "pointer-only" if legacy_kind == "pointer" else "legacy"
    elif legacy_kind in (None, "pointer"):
        status = "canonical"
    else:
        status = "identical" if legacy == canonical else "conflict"
    effective, source = ((canonical, LANGUAGE_CANONICAL) if canonical is not None else
                         (legacy, LANGUAGE_LEGACY) if legacy_kind == "preference" else (None, None))
    match = LANGUAGE_PATTERN.search(effective or "")
    return {"status": status, "canonical": LANGUAGE_CANONICAL if canonical is not None else None,
            "legacy": LANGUAGE_LEGACY if legacy is not None else None, "legacy_kind": legacy_kind,
            "language": match.group(1).strip() if match else None, "source": source}


def _replace_file(path: Path, text: str) -> None:
    """Atomically replace one existing file with LF text.

    Args:
        path: Existing contained file.
        text: New UTF-8 content.
    Returns:
        None after ``os.replace`` has swapped the fully written temporary file.
    Raises:
        OSError: If writing or replacing fails; the original stays intact.
    Side effects:
        Creates and removes a sibling temporary file; no network or database.
    """
    temporary = path.with_name(path.name + ".tmp-p07")
    with open(temporary, "x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def migrate_language(root: Path, apply: bool = False, keep_shared: bool = False) -> dict:
    """Preview or apply the move of a legacy language preference to the shared file.

    Args:
        root: Repository root.
        apply: ``False`` for a read-only preview, ``True`` to write.
        keep_shared: Resolve a ``conflict`` in favour of the shared file, which
            the set-language procedure has just written from the user's current
            choice; the legacy preference is then replaced with the pointer.
    Returns:
        ``{"before": state, "actions": [...], "after": state}``; actions are
        ``create-canonical`` and/or ``replace-legacy-with-pointer``.
    Raises:
        OSError: If a write fails (the legacy preference is replaced only after
            the canonical copy is verified).
        ValueError: For linked or non-file paths.
    Side effects:
        With ``apply``: creates ``docs/ai/overrides/output-language.md``
        exclusively and replaces ``.claude/rules/output-language.md`` with a
        pointer, so exactly one writable preference remains. Preview reads only.
    Business rules:
        Without ``keep_shared`` a conflict or a pointer without its canonical
        file is reported and nothing is written; repeating a completed
        migration changes nothing. The legacy text is never copied over an
        existing shared file.
    """
    root = target_root(root)
    before = language_state(root)
    actions = []
    if before["status"] == "legacy":
        actions = ["create-canonical", "replace-legacy-with-pointer"]
    elif before["status"] == "identical" or (before["status"] == "conflict" and keep_shared):
        actions = ["replace-legacy-with-pointer"]
    if apply and actions:
        canonical = contained(root, LANGUAGE_CANONICAL)
        legacy = contained(root, LANGUAGE_LEGACY)
        if "create-canonical" in actions:
            _create_file(canonical, legacy.read_bytes())
        # Wskaźnik zastępuje legacy dopiero po potwierdzeniu identycznej treści kanonicznej
        # (albo po jawnym wyborze pliku wspólnego przy konflikcie).
        if before["status"] != "conflict" and _language_text(canonical) != _language_text(legacy):
            raise OSError(f"Canonical language preference differs from legacy: {canonical}")
        _replace_file(legacy, LANGUAGE_POINTER)
    return {"before": before, "actions": actions,
            "after": language_state(root) if apply else before}


def _relative_posix(root: Path, path: Path) -> str:
    """Render a contained path relative to the validated root in POSIX form.

    Args:
        root: Validated repository root.
        path: A path produced by :func:`artifact_paths` beneath ``root``.
    Returns:
        The root-relative path with forward slashes for shell and Node callers.
    Side effects:
        None.
    """
    return path.relative_to(root).as_posix()


def main() -> int:
    """Preview or apply allowlisted shared-state migration for a project.

    Args:
        CLI options select a repository root and exactly one operation: the
        default read-only preview, ``--apply`` (both categories),
        ``--migrate-runtime`` (runtime records only), ``--resolve NAME`` (print
        the readable path chosen by the fallback rule) or ``--writable NAME``
        (print the canonical write path, refusing while a legacy copy remains).
        ``--language`` previews the output-language preference move and, with
        ``--apply``, performs it; ``--keep-shared`` additionally resolves a
        conflict in favour of the shared file.
    Returns:
        0 when there are no conflicts/invalid/unknown artifacts (or the path was
        printed), 1 when any conflict, invalid or unknown artifact remains (for
        ``--language``: a conflict or a pointer without its canonical file), and
        2 for unsafe paths, conflicts in path resolution, or I/O errors.
    Raises:
        None; expected path and content errors are converted to exit codes.
    Side effects:
        Preview and path resolution are read-only. ``--apply`` and
        ``--migrate-runtime`` create canonical copies for safe artifacts and
        remove a legacy file only after confirming identical bytes. No database,
        subprocess, or network access occurs.
    Business rules:
        A conflict is never resolved by timestamp or by automatic overwrite.
        Shell and Node consumers call ``--resolve``/``--writable`` so that the
        fallback rule has exactly one implementation.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--apply", action="store_true")
    operation.add_argument("--migrate-runtime", action="store_true")
    operation.add_argument("--resolve", metavar="NAME")
    operation.add_argument("--writable", metavar="NAME")
    parser.add_argument("--category", choices=tuple(CATEGORIES), default="project",
                        help="artifact category for --resolve/--writable")
    parser.add_argument("--language", action="store_true",
                        help="preview (or with --apply migrate) the output-language preference")
    parser.add_argument("--keep-shared", action="store_true",
                        help="with --language --apply: resolve a conflict in favour of the shared file")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    if args.language and (args.migrate_runtime or args.resolve or args.writable):
        parser.error("--language combines only with --apply")
    if args.keep_shared and not (args.language and args.apply):
        parser.error("--keep-shared requires --language --apply")
    # Windows: potok ma kodowanie ANSI, a JSON zawiera nazwy języków (np. cyrylicę).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        if args.language:
            report = migrate_language(args.root, args.apply, args.keep_shared)
            print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
            return 1 if report["after"]["status"] in ("conflict", "pointer-only") else 0
        if args.resolve or args.writable:
            root = target_root(args.root)
            if args.resolve:
                path = resolve_state(root, args.resolve, args.category)
            else:
                path = writable_state_path(root, args.writable, args.category)
            print(_relative_posix(root, path))
            return 0
        if args.apply:
            report = apply_migration(args.root)
        elif args.migrate_runtime:
            report = migrate_runtime(args.root)
        else:
            report = plan_migration(args.root)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        # Nieznane pliki legacy nie blokują writera runtime: on rusza tylko swoje rekordy.
        blocking = report["conflicts"] or report["invalid"] or (
            report["unknown"] and not args.migrate_runtime)
        return 1 if blocking else 0
    except (OSError, ValueError) as error:
        print(f"Project state migration error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
