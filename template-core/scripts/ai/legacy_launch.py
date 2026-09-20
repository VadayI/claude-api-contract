"""Compatibility launcher: parse selected dotenv data without executing shell code."""

import argparse
import os
from pathlib import Path
import re
import shutil
import sys

from core_paths import contained
from core_sync import target_root
from launch import child_environment, execute

CONFIG_NAMES = {"CONTRACT_REPO", "CONTRACT_VERSION", "VITE_API_BASE_URL",
                "VITE_OPENAPI_URL", "VITE_MSW_ENABLED"}
CREDENTIAL_NAMES = {"GITHUB_PERSONAL_ACCESS_TOKEN", "CONTEXT7_API_KEY"}


def dotenv_values(text: str) -> dict[str, str]:
    """Parse only legacy launcher keys as literal single-line dotenv values.

    Args: text is explicitly selected project dotenv content, never logged.
    Returns: Allowed nonempty values; blank placeholders preserve inherited values.
    Raises: ValueError for malformed allowed assignments or duplicate keys.
    Side effects: None; no shell expansion, file access, database or execution.
    Unknown application keys are ignored. Quotes are stripped, not interpreted;
    inline comments require whitespace before # in an unquoted value.
    """
    result, seen = {}, set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if key not in CONFIG_NAMES | CREDENTIAL_NAMES:
            continue
        if not separator or key in seen:
            raise ValueError(f"Invalid or duplicate dotenv assignment for {key}")
        seen.add(key)
        value = value.strip()
        if value.startswith(("'", '"')):
            quote = value[0]
            closing = value.find(quote, 1)
            if closing < 0 or (value[closing + 1:].strip() and
                               not value[closing + 1:].strip().startswith("#")):
                raise ValueError(f"Unsupported multiline/quoted dotenv value for {key}")
            value = value[1:closing]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        if "\0" in value:
            raise ValueError(f"Invalid dotenv value for {key}")
        if value:
            result[key] = value
    return result


def environment(runtime: str, inherited: dict[str, str], values: dict[str, str]) -> dict[str, str]:
    """Build a child-only environment retaining the legacy credential precedence.

    Args: runtime selects Claude/Codex; inherited is caller environment; values
        is parsed allowed dotenv data. Returns: Independent filtered environment.
    Raises: ValueError for unsupported runtime or unexpected supplied keys.
    Side effects: None; no caller mutation, file/DB/network access or logging.
    Nonempty PAT takes precedence as GH_TOKEN and removes stale GITHUB_TOKEN.
    """
    if set(values) - (CONFIG_NAMES | CREDENTIAL_NAMES):
        raise ValueError("Unexpected legacy environment key")
    child = child_environment(runtime, inherited, sorted(CREDENTIAL_NAMES | {"GH_TOKEN", "GITHUB_TOKEN"}))
    child.update({name: value for name, value in inherited.items() if name in CONFIG_NAMES})
    child.update(values)
    if child.get("GITHUB_PERSONAL_ACCESS_TOKEN"):
        child["GH_TOKEN"] = child["GITHUB_PERSONAL_ACCESS_TOKEN"]
        child.pop("GITHUB_TOKEN", None)
    return child


def main() -> int:
    """Launch a legacy entry point using argv and explicitly selected dotenv data.

    Args: CLI runtime, --root, --env-file (default .env), then -- and runtime args.
    Returns: Runtime exit status, or 2 for invalid configuration/process startup.
    Side effects: Reads the selected dotenv file if present and starts the CLI
        with ordinary existing permissions; no parent env/trust/config mutation.
    The wrapper adds no model, approval or permission flags. Runtime arguments
        are user supplied; values never pass through a shell or appear in logs.
    No direct database operations occur; the launched agent retains its scope.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", choices=("claude", "codex"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--env-file", default=".env")
    raw = sys.argv[1:]
    boundary = raw.index("--") if "--" in raw else len(raw)
    args = parser.parse_args(raw[:boundary])
    forwarded = raw[boundary + 1:]
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    try:
        root = target_root(args.root)
        path = contained(root, args.env_file)
        values = dotenv_values(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
        executable = shutil.which(args.runtime)
        if not executable:
            raise ValueError(f"Missing executable: {args.runtime}")
        return execute([executable, *forwarded], root,
                       environment(args.runtime, dict(os.environ), values), None)
    except (OSError, ValueError) as error:
        print(f"Legacy launcher error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
