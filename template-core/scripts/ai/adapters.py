"""Render complete runtime adapters and role packs from a validated neutral catalog."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tomllib
import re

from core_paths import contained
from core_sync import safe_name
from schema import load_json, check_schema, validate, catalog_links


def read_source(root: Path, name: str) -> str:
    """Read a repo-contained UTF-8 source, rejecting escapes and symlinks.

    Args: root is the checkout; name is a relative catalog path.
    Returns: Full normalized text, never a truncated read.
    Raises: ValueError for unsafe paths; OSError or UnicodeError for invalid files.
    Side effects: File reads only; no database/network access.
    """
    safe_name(name)
    return contained(root, name).read_text(encoding="utf-8")



def outputs(root: Path) -> dict[str, str]:
    """Resolve catalog dependencies and render deterministic runtime entry points.

    Args: root is the template checkout containing docs/ai/catalog.json.
    Returns: Relative output paths mapped to complete UTF-8 file contents.
    Raises: ValueError/KeyError on invalid catalogs, missing rules or unsafe paths.
    Side effects: Reads sources; no writes, subprocesses, network or DB operations.
    Business rules: Coordinator-only rules never enter worker packs; inherited
        model choices remain untouched; every pack ends with a completeness marker.
    """
    catalog = load_json(contained(root, "docs/ai/catalog.json"))
    schema = load_json(Path(__file__).resolve().parents[2] / "templates/ai/schemas/catalog.schema.json")
    check_schema(schema)
    validate(catalog, schema)
    catalog_links(catalog, root)
    legacy_paths = [rule["legacy_path"].casefold() for rule in catalog["rules"] if "legacy_path" in rule]
    if len(legacy_paths) != len(set(legacy_paths)):
        raise ValueError("Duplicate legacy adapter path")
    for identifier in [*catalog["roles"], *catalog["workflows"]]:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", identifier):
            raise ValueError("Unsafe role/workflow identifier")
    if catalog["schema_version"] != 1:
        raise ValueError("Unsupported catalog version")
    rules = {rule["id"]: rule for rule in catalog["rules"]}
    if len(rules) != len(catalog["rules"]):
        raise ValueError("Duplicate rule IDs")
    generated = {
        "CLAUDE.md": "@AGENTS.md\n\n# Claude adapter\n\nUse docs/ai/catalog.json and neutral procedures. Role models inherit user/runtime\nsettings. Claude import syntax applies only to this wrapper. Tool names in examples\nare not cross-runtime contracts. Do not install optional plugins or change trust.\n",
    }
    for rule in rules.values():
        read_source(root, rule["path"])
        for dependency in rule["dependencies"]:
            if dependency not in rules:
                raise ValueError(f"Unknown dependency: {dependency}")
        if "legacy_path" not in rule:
            continue
        safe_name(rule["legacy_path"])
        if not rule["legacy_path"].startswith(".claude/rules/") or not rule["legacy_path"].endswith(".md"):
            raise ValueError("Legacy adapter must be a Claude rule Markdown path")
        generated[rule["legacy_path"]] = (
            "# Generated rule entry point — do not edit\n\n"
            f"Canonical rule: `{rule['path']}`. Read the full source when its catalog\n"
            "scope applies. Worker rule lists are explicit in docs/ai/catalog.json.\n"
            "The workflow rule is coordinator-only; workers are not coordinators.\n"
        )
    for role, metadata in catalog["roles"].items():
        required = set(metadata["rules"])
        missing = required - rules.keys()
        if missing:
            raise ValueError(f"Unknown role rules: {missing}")
        for rule_id in required:
            if rules[rule_id]["scope"] in ("coordinator", "coordinator-only"):
                raise ValueError(f"Coordinator rule leaked to worker: {role}")
            dependencies = {item for item in rules[rule_id]["dependencies"] if rules[item]["scope"] not in ("coordinator", "coordinator-only")}
            if not dependencies.issubset(required):
                raise ValueError(f"Missing transitive rules for {role}: {dependencies - required}")
        role_text = read_source(root, metadata["path"])
        rule_list = "\n".join(f"- `{rules[name]['path']}`" for name in metadata["rules"])
        instructions = (
            f"Read AGENTS.md, then {metadata['path']}. You are the {role} role, not the coordinator.\n"
            "Read every required rule below completely before design, implementation or review.\n"
            "Use bounded reads and verify file endings; do not treat truncated output as read.\n"
            + rule_list
            + "\nRead the full generated role pack by default; verify its END marker. The explicit source list remains a fallback.\n"
            + f"Pack: docs/ai/generated/role-packs/{role}.md\n"
            + "Report revision, exact file paths/lines, changed files, checks and limitations.\n"
        )
        if metadata.get("read_only", role == "reviewer"):
            instructions += "Read-only: never modify code, notes, plans or settings. Return findings only.\n"
        generated[f".codex/agents/{role}.toml"] = (
            f"name = {json.dumps(role)}\n"
            f"description = {json.dumps('Project ' + role + ' role; follows the neutral contract.')}\n"
            + ('sandbox_mode = "read-only"\n' if metadata.get("read_only", role == "reviewer") else "")
            + f"developer_instructions = {json.dumps(instructions)}\n"
        )
        tools = "Read, Glob, Grep" if metadata.get("read_only", role == "reviewer") else "Read, Glob, Grep, Write, Edit, Bash"
        generated[f".claude/agents/{role}.md"] = (
            f"---\nname: {role}\ndescription: Project {role} role following the neutral contract.\ntools: [{tools}]\n---\n\n"
            + instructions
        )
        pack = [f"# Generated role pack: {role}\n\nDo not edit; generated from full canonical sources.\n", f"<!-- SOURCE {metadata['path']} SHA256 {hashlib.sha256(role_text.encode('utf-8')).hexdigest()} -->\n{role_text}\n<!-- END SOURCE {metadata['path']} -->"]
        for name in metadata["rules"]:
            path = rules[name]["path"]
            body = read_source(root, path)
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            pack.append(f"\n<!-- SOURCE {path} SHA256 {digest} -->\n\n{body}\n<!-- END SOURCE {path} -->\n")
        pack.append(f"\n<!-- END ROLE PACK {role} -->\n")
        generated[f"docs/ai/generated/role-packs/{role}.md"] = "\n".join(pack)
    for name in sorted(catalog["workflows"]):
        if name == "orchestrate":
            continue
        path = catalog["workflows"][name]
        read_source(root, path)
        description = {
            "doctor": "Inspect this template project environment and report missing capabilities without repairs.",
            "verify": "Verify a project feature and maintain its real route-based manual verification guide.",
            "wrap-up": "Finalize an authorized project work session with checks, shared memory, commit, push and PR; merge requires a user command.",
        }.get(name, f"Execute the full project {name} procedure using available capabilities.")
        generated[f".agents/skills/{name}/SKILL.md"] = (
            f"---\nname: {name}\ndescription: {description}\n---\n\n"
            f"Read repository AGENTS.md and [{name} procedure](../../../{path}).\n"
            "Execute the full neutral procedure using available runtime capabilities.\n"
            "User choices and authorization persist; do not invent missing tools or evidence.\n"
        )
        generated[f".claude/commands/{name}.md"] = (
            f"# Generated {name} entry point\n\nRead AGENTS.md and `{path}`.\n"
            "Use the current request arguments as procedure input. Follow every step with\n"
            "actual available capabilities; do not interpret Codex tools as Claude tools.\n"
        )
    for path, text in generated.items():
        if path.endswith(".toml"):
            tomllib.loads(text)
    return generated

