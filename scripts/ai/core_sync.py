"""Deliver core files from an exact Git revision or the owner's local source."""

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

from core_paths import contained, digest

PIN = "docs/ai/core-source.json"
MANIFEST = "docs/ai/core-manifest.json"


def git(source: Path, *args: str) -> str:
    """Read UTF-8 Git output from source; raise on command or decode failure.

    Args: source is a reviewed repository; args are separate Git argv entries.
    Returns: Text with normalized newlines. Side effects: read-only subprocess;
        no shell, database, network, config mutation or credential access.
    """
    return subprocess.check_output(["git", "-C", str(source), *args]).decode("utf-8").replace("\r\n", "\n")


def safe_name(name: str) -> None:
    """Reject unsafe portable manifest names; return None or raise ValueError.

    Args: name is a POSIX-relative path from untrusted metadata.
    No writes, database access or other side effects occur. Secret paths and
    Git/runtime metadata are never deliverable payloads.
    """
    path = PurePosixPath(name)
    if not name or path.is_absolute() or "\\" in name or ":" in name or any(
        part in ("..", ".git", ".ai-runtime", "secrets", "credentials") or part.startswith(".env")
        for part in path.parts
    ) or path.as_posix() != name:
        raise ValueError(f"Unsafe core path: {name}")


def payload(source: Path, commit: str) -> tuple[dict, dict[str, str]]:
    """Load verified core source bytes from an exact commit, ignoring dirty files.

    Args: source is a local reviewed Git repository; commit is a full SHA-1.
    Returns: Version metadata and runtime-path/content mapping.
    Raises: ValueError for an invalid pin, unsupported manifest, linked Git entry,
        or digest mismatch; subprocess and JSON errors propagate.
    Side effects: Read-only Git subprocesses. No network, database or writes.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Source pin must be a full lowercase commit SHA")
    if git(source, "rev-parse", "--verify", commit + "^{commit}").strip() != commit:
        raise ValueError("Pin does not identify a commit")
    prefix = "template-core/"
    entries = {}
    for record in git(source, "ls-tree", "-rz", commit, "--", "template-core").split("\0"):
        if record:
            metadata, name = record.split("\t", 1)
            mode, kind, oid = metadata.split()
            if mode not in ("100644", "100755") or kind != "blob":
                raise ValueError(f"Linked or unsupported source entry: {name}")
            entries[name.removeprefix(prefix)] = oid
    if MANIFEST not in entries:
        raise ValueError("Source revision has no core manifest")
    manifest_text = git(source, "cat-file", "blob", entries[MANIFEST])
    manifest = json.loads(manifest_text)
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("Unsupported core manifest")
    files = {}
    for name, record in manifest["files"].items():
        safe_name(name)
        if name not in entries or record.get("ownership") != "template":
            raise ValueError(f"Missing or unsupported source ownership: {name}")
        content = git(source, "cat-file", "blob", entries[name])
        if digest(content) != record.get("sha256"):
            raise ValueError(f"Pinned source digest mismatch: {name}")
        if name.startswith(("scripts/ai/", "templates/ai/", "docs/ai/")) and name not in (
            "scripts/ai/generate_core.py", "scripts/ai/install_core.py"
        ):
            files[name] = content
    config = json.loads(git(source, "cat-file", "blob", entries["core.json"]))
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported core version metadata")
    metadata = {"schema_version": 1, "source_repository": config["source_repository"],
                "source_commit": commit, "version": config["version"],
                "source_manifest_digest": digest(manifest_text),
                "files": {name: {"sha256": digest(text), "ownership": "template"}
                          for name, text in sorted(files.items())}}
    return metadata, files


def target_root(target: Path) -> Path:
    """Return an absolute nonlinked target root or raise ValueError.

    Args: target is an installation directory, possibly absent.
    Side effects: Metadata reads only, including ancestors; no DB or writes.
    """
    target = target.absolute()
    if any(p.is_symlink() or p.is_junction() for p in (target, *target.parents)):
        raise ValueError("Target path cannot traverse a link or junction")
    if target.exists() and not target.is_dir():
        raise ValueError("Target must be a directory")
    return target


def local_payload(source: Path) -> tuple[dict, dict[str, str]]:
    """Read the owning repository's local core using content-based provenance.

    Args: source is the repository containing a generated template-core tree.
    Returns: Local-source receipt and runtime payload, without a commit claim.
    Raises: ValueError for unsafe paths, stale manifests or invalid ownership;
        filesystem/JSON errors propagate. Every listed source file is verified.
    Side effects: File reads only; no Git, network, database or writes. Source-only
        installers, tests and README are excluded from the project payload.
    """
    root = target_root(source / "template-core")
    manifest_text = contained(root, MANIFEST).read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("Unsupported local core manifest")
    files = {}
    for name, record in manifest["files"].items():
        safe_name(name)
        content = contained(root, name).read_text(encoding="utf-8")
        if record.get("ownership") != "template" or digest(content) != record.get("sha256"):
            raise ValueError(f"Local source digest/ownership mismatch: {name}")
        if name.startswith(("scripts/ai/", "templates/ai/", "docs/ai/")) and name not in (
            "scripts/ai/generate_core.py", "scripts/ai/install_core.py"
        ):
            files[name] = content
    if "core.json" not in manifest["files"] or not files:
        raise ValueError("Local manifest lacks version metadata or runtime files")
    config = json.loads(contained(root, "core.json").read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported local core version metadata")
    return {"schema_version": 1, "source_repository": config["source_repository"],
            "source_kind": "local", "source_path": "template-core", "pin_status": "local",
            "version": config["version"], "source_manifest_digest": digest(manifest_text),
            "files": {name: {"sha256": digest(text), "ownership": "template"}
                      for name, text in sorted(files.items())}}, files


def preview(target: Path, metadata: dict, files: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Prepare all changes, preserving project/custom files and previous pins.

    Args: target is nonlinked; metadata/files come from verified payload().
    Returns: Pending writes and conflicts. No files are written; no DB/network.
    Raises: ValueError for malformed prior metadata or unsafe destination paths.
    Removed source files are retained and reported as conflicts, never deleted.
    """
    pin_path = contained(target, PIN)
    old = json.loads(pin_path.read_text(encoding="utf-8")) if pin_path.exists() else {}
    if old and (old.get("schema_version") != 1 or not isinstance(old.get("files"), dict)):
        raise ValueError("Unsupported installed core pin")
    pending, conflicts = {}, []
    for name, incoming in files.items():
        safe_name(name)
        path = contained(target, name)
        if not path.exists():
            pending[name] = incoming
            continue
        current = path.read_text(encoding="utf-8")
        previous = old.get("files", {}).get(name, {})
        if current == incoming:
            continue
        if previous.get("ownership") == "template" and digest(current) == previous.get("sha256"):
            pending[name] = incoming
        else:
            conflicts.append(name)
    for name in set(old.get("files", {})) - files.keys():
        safe_name(name)
        if contained(target, name).exists():
            conflicts.append(name)
    pin_text = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    if not pin_path.exists() or pin_path.read_text(encoding="utf-8") != pin_text:
        pending[PIN] = pin_text
    return pending, sorted(conflicts)


def integrated_pin(source: Path, metadata: dict) -> dict:
    """Verify remote main availability and source ancestry before a final pin.

    Args: source holds required Git objects; metadata is a verified source pin.
    Returns: A copy recording the observed upstream main SHA and integrated status.
    Raises: ValueError/subprocess errors for an unavailable remote, missing object
        or a source commit outside remote main. No fetch or merge is performed.
    Side effects: Read-only ls-remote network request using normal Git auth;
        local ancestry inspection. No files, credentials, config or DB are written.
    """
    remote = metadata["source_repository"]
    observed = git(source, "ls-remote", "--exit-code", "--", remote, "refs/heads/main").splitlines()
    if len(observed) != 1:
        raise ValueError("Cannot verify a unique upstream main revision")
    head, ref = observed[0].split()
    if ref != "refs/heads/main" or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("Invalid upstream main response")
    git(source, "merge-base", "--is-ancestor", metadata["source_commit"], head)
    return {**metadata, "pin_status": "integrated", "observed_upstream_main": head}


def verify(target: Path) -> list[str]:
    """Verify installed payload against its pin without source checkout access.

    Args: target is a reviewed nonlinked project root. Receipts can identify an
        exact commit or local source content; local receipts cannot claim a SHA.
    Returns: Drift paths; malformed or missing metadata raises ValueError/OSError.
    Side effects: Reads only. Does not establish remote availability, integration,
        source authenticity, test success or deployment readiness; no DB/network.
    """
    pin = json.loads(contained(target, PIN).read_text(encoding="utf-8"))
    local = pin.get("source_kind") == "local"
    valid_source = (pin.get("source_path") == "template-core" and pin.get("pin_status") == "local"
                    and "source_commit" not in pin and bool(re.fullmatch(
                        r"[0-9a-f]{64}", pin.get("source_manifest_digest", "")))) if local else bool(
                            re.fullmatch(r"[0-9a-f]{40}", pin.get("source_commit", "")))
    if pin.get("schema_version") != 1 or not valid_source:
        raise ValueError("Invalid installed source pin")
    if not isinstance(pin.get("files"), dict) or not pin["files"]:
        raise ValueError("Empty or invalid installed manifest")
    drift = []
    for name, record in pin["files"].items():
        safe_name(name)
        path = contained(target, name)
        if record.get("ownership") != "template" or not path.is_file() or digest(path.read_text(encoding="utf-8")) != record.get("sha256"):
            drift.append(name)
    return drift


def main() -> int:
    """Preview/apply pinned delivery or check installed drift, with explicit errors.

    CLI args select target and exact source repository/commit provenance, or
        --local-source for target/template-core and digest-based provenance.
    Returns: 0 consistent/success; 1 conflict/drift; 2 invalid configuration.
    Side effects: Apply writes planned UTF-8 files only after complete preflight;
        preview/check are read-only. Integrated pins inspect remote main with
        ls-remote; no deletion, shell, deployment or database access occurs.
    Interrupted writes can be retried; conflicts preserve all existing bytes.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path)
    parser.add_argument("--commit")
    provenance = parser.add_mutually_exclusive_group()
    provenance.add_argument("--development-pin", action="store_true")
    provenance.add_argument("--integrated-pin", action="store_true")
    provenance.add_argument("--local-source", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    try:
        target = target_root(args.target)
        if args.local_source:
            if args.commit is not None or args.source is not None:
                raise ValueError("Local source uses target/template-core, without --source or --commit")
            metadata, files = local_payload(target)
        elif args.check and args.source is None:
            drift = verify(target)
            print(json.dumps({"mode": "check", "drift": drift}))
            return int(bool(drift))
        else:
            if args.source is None or args.commit is None or not (args.development_pin or args.integrated_pin):
                raise ValueError("Delivery requires --source, --commit and an explicit --development-pin or --integrated-pin")
            metadata, files = payload(args.source, args.commit)
            if args.integrated_pin:
                metadata = integrated_pin(args.source, metadata)
            else:
                metadata["pin_status"] = "development"
        pending, conflicts = preview(target, metadata, files)
        print(json.dumps({"mode": "apply" if args.apply else "check" if args.check else "preview",
                          "writes": sorted(pending), "conflicts": conflicts}))
        if conflicts or (args.check and pending):
            return 1
        if args.apply:
            for name, content in pending.items():
                path = contained(target, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Core sync error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
