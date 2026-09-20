"""Shared path containment and normalized text hashing for core delivery."""

import hashlib
from pathlib import Path


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


