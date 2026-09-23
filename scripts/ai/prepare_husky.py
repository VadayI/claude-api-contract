"""Install Husky only when doing so preserves an existing hooks path."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def prepare(root: Path, check: bool = False) -> int:
    """Inspect local Git hooks configuration before optional Husky setup.

    Args: root is the package/repository root; check requests read-only status.
    Returns: 0 for compatible setup/archive, 1 for a foreign or absent hook in
        check mode, or the Husky process exit code on installation failure.
    Raises: OSError for a missing local executable or unreadable Git metadata.
    Side effects: Reads local Git config; when allowed and not check, Husky may
        set only repository-local core.hooksPath. No global config, DB, network,
        foreign hook edits, Git refs, or application files are changed.
    Business rule: Existing non-Husky core.hooksPath is preserved and requires
        an explicit reviewed chain by the project owner.
    """
    repository = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True, check=False)
    if repository.returncode or repository.stdout.strip() != "true":
        print("[hooks] Git archive/export: Husky installation skipped")
        return 0
    configured = subprocess.run(["git", "-C", str(root), "config", "--local", "--get", "core.hooksPath"],
                                capture_output=True, text=True, check=False)
    path = configured.stdout.strip() if configured.returncode == 0 else ""
    if path and path.replace("\\", "/").rstrip("/") != ".husky/_":
        print(f"[hooks] Existing core.hooksPath preserved: {path}; chain Husky manually after review")
        return 1 if check else 0
    if check:
        return 0 if path else 1
    executable = shutil.which("npx")
    if not executable:
        raise OSError("npx is required for local Husky installation")
    return subprocess.run([executable, "--no-install", "husky"], cwd=root, check=False).returncode


def main() -> int:
    """Run package prepare or read-only hooks compatibility check.

    Args: CLI --check performs no installation.
    Returns: 0 installed/compatible or archive; 1 manual chain/check missing;
        2 for executable/filesystem errors.
    Raises: None for supported OSError; it is reported without secret content.
    Side effects: Only default mode may install repo-local Husky hooks; no DB,
        network, global Git setting, release, deployment, or merge.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        return prepare(Path(__file__).resolve().parents[2], args.check)
    except OSError as error:
        print(f"[hooks] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
