"""Validate the family's deliberately small, offline JSON Schema vocabulary."""

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from core_paths import contained, contained_entry
from core_sync import safe_name

KEYWORDS = {"$schema", "title", "description", "type", "const", "enum", "required",
            "properties", "additionalProperties", "items", "minItems", "uniqueItems",
            "minLength", "pattern", "minimum", "minProperties", "oneOf", "anyOf",
            "not", "maxItems", "allOf", "if", "then", "else", "maximum"}
TYPES = {"object": dict, "array": list, "string": str, "integer": int,
         "boolean": bool, "null": type(None)}


def check_schema(schema: dict) -> None:
    """Reject unsupported or malformed schema constructs before inspecting input.

    Args: schema is a decoded schema using the bundled vocabulary only.
    Returns: None. Raises: ValueError for unsupported keywords/types or shapes.
    Side effects: None; no reference resolution, file, network or database access.
    Business rule: An unknown validation keyword must never silently pass.
    """
    if not isinstance(schema, dict) or set(schema) - KEYWORDS:
        raise ValueError("Unsupported schema vocabulary")
    if schema.get("type") not in TYPES:
        raise ValueError("Every schema requires one supported type")
    typed_keywords = {"object": {"properties", "required", "additionalProperties", "minProperties"},
                      "array": {"items", "minItems", "maxItems", "uniqueItems"},
                      "string": {"minLength", "pattern"}, "integer": {"minimum", "maximum"}}
    for kind, keywords in typed_keywords.items():
        if schema["type"] != kind and keywords.intersection(schema):
            raise ValueError(f"Schema keyword requires {kind} type")
    for key in ("minItems", "maxItems", "minLength", "minimum", "maximum", "minProperties"):
        if key in schema and (type(schema[key]) is not int or schema[key] < 0):
            raise ValueError(f"Invalid schema {key}")
    if "uniqueItems" in schema and type(schema["uniqueItems"]) is not bool:
        raise ValueError("Invalid uniqueItems")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ValueError("Invalid enum")
    if "pattern" in schema:
        if not isinstance(schema["pattern"], str):
            raise ValueError("Invalid pattern")
        try:
            re.compile(schema["pattern"])
        except re.error as error:
            raise ValueError("Invalid pattern") from error
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError("Invalid properties")
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(key, str) for key in required):
        raise ValueError("Invalid required properties")
    if len(set(required)) != len(required):
        raise ValueError("Duplicate required properties")
    for child in properties.values():
        check_schema(child)
    additional = schema.get("additionalProperties", True)
    if type(additional) is not bool:
        check_schema(additional)
    if additional is False and set(required) - properties.keys():
        raise ValueError("Required property excluded by closed schema")
    if "items" in schema:
        check_schema(schema["items"])
    if "oneOf" in schema:
        if not isinstance(schema["oneOf"], list) or not schema["oneOf"]:
            raise ValueError("Invalid oneOf branches")
        for child in schema["oneOf"]:
            check_schema(child)
    if "anyOf" in schema:
        if not isinstance(schema["anyOf"], list) or not schema["anyOf"]:
            raise ValueError("Invalid anyOf branches")
        for child in schema["anyOf"]:
            check_schema(child)
    if "not" in schema:
        check_schema(schema["not"])
    if "allOf" in schema:
        if not isinstance(schema["allOf"], list) or not schema["allOf"]:
            raise ValueError("Invalid allOf branches")
        for child in schema["allOf"]:
            check_schema(child)
    if "if" in schema:
        check_schema(schema["if"])
        if "then" in schema:
            check_schema(schema["then"])
        if "else" in schema:
            check_schema(schema["else"])


def validate(value: object, schema: dict, location: str = "$") -> None:
    """Validate JSON recursively against a previously checked bundled schema.

    Args: value is decoded JSON; schema passed check_schema; location labels errors.
    Returns: None. Raises: ValueError on the first violated constraint.
    Side effects: None, including no database, filesystem or external references.
    Booleans are never integers; comparisons retain JSON type distinctions.
    """
    if type(value) is not TYPES[schema["type"]]:
        raise ValueError(f"{location}: expected {schema['type']}")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ValueError(f"{location}: unexpected constant")
    if "enum" in schema and not any(type(value) is type(item) and value == item for item in schema["enum"]):
        raise ValueError(f"{location}: unknown value")
    if isinstance(value, dict):
        if len(value) < schema.get("minProperties", 0):
            raise ValueError(f"{location}: too few properties")
        if set(schema.get("required", [])) - value.keys():
            raise ValueError(f"{location}: missing required fields")
        for key, item in value.items():
            child = schema.get("properties", {}).get(key, schema.get("additionalProperties", True))
            if child is False:
                raise ValueError(f"{location}.{key}: unknown field")
            if isinstance(child, dict):
                validate(item, child, f"{location}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{location}: too few items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ValueError(f"{location}: too many items")
        encoded = [json.dumps(item, sort_keys=True) for item in value]
        if schema.get("uniqueItems") and len(set(encoded)) != len(encoded):
            raise ValueError(f"{location}: duplicate items")
        if "items" in schema:
            for index, item in enumerate(value):
                validate(item, schema["items"], f"{location}[{index}]")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or ("pattern" in schema and not re.search(schema["pattern"], value)):
            raise ValueError(f"{location}: invalid string")
    if type(value) is int and value < schema.get("minimum", value):
        raise ValueError(f"{location}: below minimum")
    if type(value) is int and value > schema.get("maximum", value):
        raise ValueError(f"{location}: above maximum")
    if "oneOf" in schema:
        matches = 0
        for child in schema["oneOf"]:
            try:
                validate(value, child, location)
            except ValueError:
                continue
            matches += 1
        if matches != 1:
            raise ValueError(f"{location}: expected exactly one schema branch")
    if "anyOf" in schema:
        for child in schema["anyOf"]:
            try:
                validate(value, child, location)
            except ValueError:
                continue
            break
        else:
            raise ValueError(f"{location}: expected at least one schema branch")
    if "not" in schema:
        try:
            validate(value, schema["not"], location)
        except ValueError:
            pass
        else:
            raise ValueError(f"{location}: forbidden schema matched")
    if "allOf" in schema:
        for child in schema["allOf"]:
            validate(value, child, location)
    if "if" in schema:
        try:
            validate(value, schema["if"], location)
            matched = True
        except ValueError:
            matched = False
        branch = schema.get("then") if matched else schema.get("else")
        if branch is not None:
            validate(value, branch, location)


def catalog_links(catalog: dict, root: Path) -> None:
    """Check rule routing and contained non-secret sources without reading contents.

    Args: catalog passed the catalog schema; root is its project directory.
    Returns: None. Raises: ValueError for duplicate IDs, dangling references,
        missing files, unsafe paths or incomplete role dependency closure.
    Side effects: Filesystem metadata reads only; no writes, database or network.
    Cyclic dependencies require full closure. Coordinator-only rules are not
    inherited by workers through links in shared rules (D02).
    """
    rules = {rule["id"]: rule for rule in catalog["rules"]}
    if len(rules) != len(catalog["rules"]):
        raise ValueError("Duplicate rule IDs")
    roles = catalog["roles"]
    paths = [rule["path"] for rule in rules.values()]
    paths += [role["path"] for role in roles.values()]
    paths += list(catalog["workflows"].values())
    for name in paths:
        safe_name(name)
        if not contained(root, name).is_file():
            raise ValueError(f"Missing catalog source: {name}")
    for rule in rules.values():
        if set(rule["dependencies"]) - rules.keys():
            raise ValueError(f"Unknown dependency: {rule['id']}")
        for field in ("explicit_consumers", "declared_consumers"):
            if set(rule[field]) - roles.keys():
                raise ValueError(f"Unknown consumer: {rule['id']}")
    for name, role in roles.items():
        selected = set(role["rules"])
        if selected - rules.keys():
            raise ValueError(f"Unknown role rule: {name}")
        missing = {dependency for rule in selected for dependency in rules[rule]["dependencies"]
                   if dependency not in selected and rules[dependency]["scope"] not in ("coordinator", "coordinator-only")}
        if missing:
            raise ValueError(f"Incomplete dependency closure: {name}")


def project_links(project: dict, root: Path) -> None:
    """Validate policy relationships, provenance and safe project documentation paths.

    Args: project passed the project schema; root is the project directory.
    Returns: None. Raises: ValueError for missing contract provenance, unsafe URLs,
        paths, unknown capabilities, altered legacy floors or invalid saved profiles.
        Documentation entries may name document files or directories (ADRs,
        session records), never hidden, secret or non-document files; the
        contract artifact must be a file path.
    Side effects: Path metadata reads only; no URL fetching, writes or database.
    Schema validity alone never establishes the truth of a capability or evidence.
    """
    import readiness

    contract = project["contract"]
    if not contract.get("url") or not contract.get("digest"):
        raise ValueError("Contract source requires explicit URL and sha256 digest")
    url = urlsplit(contract["url"])
    if url.scheme not in ("https", "http") or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Contract URL must be HTTP(S) without credentials, query or fragment")
    if contract["source"] == "repo_pin" and not contract.get("pin"):
        raise ValueError("Repository contract source requires an explicit pin")
    safe_name(contract["artifact"])
    contained(root, contract["artifact"])
    # Wpisy mapy dokumentacji mogą wskazywać katalogi (ADR, rekordy sesji), ale nie
    # pliki ukryte, sekrety ani nie-dokumenty — ta sama reguła co session_context.
    import session_context
    for name in project["documentation"].values():
        session_context.documentation_name(name)
        contained_entry(root, name)
    if set(project["features"]) - readiness.FEATURES:
        raise ValueError("Unknown feature capability")
    maturity = project["maturity"]
    if "legacy" in maturity:
        legacy = maturity["legacy"]
        if not isinstance(legacy.get("original"), str):
            raise ValueError("Invalid legacy migration")
        expected = readiness.migrate_stage(legacy["original"], project["template"]["kind"])["legacy"]
        if expected["resolution"] != "mapped" or legacy != expected:
            raise ValueError("Unresolved or altered legacy floor")
    for profile in project["deployment"].values():
        readiness.validate(profile)
        if profile["kind"] != project["template"]["kind"] or profile["stage"] != maturity["stage"]:
            raise ValueError("Saved deployment kind/stage differs from project")
        if profile["features"] != project["features"] or profile.get("legacy") != maturity.get("legacy"):
            raise ValueError("Saved deployment capabilities/legacy differ from project")


def load_json(path: Path) -> object:
    """Read strict UTF-8 JSON, rejecting ambiguous duplicate keys and non-JSON numbers.

    Args: path is an explicitly selected non-secret JSON file.
    Returns: Decoded data. Raises: ValueError/OSError for invalid or unreadable data.
    Side effects: One file read; no writes, execution, network or database.
    """
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def unique_object(pairs: list) -> dict:
    """Build a JSON object from pairs; raise ValueError on duplicate keys.

    Args: pairs are decoder-provided key/value pairs. Returns: A unique-key dict.
    Side effects: None; no I/O or database. Duplicate policy values are ambiguous.
    """
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    """Reject a decoder's NaN/Infinity token with ValueError; no I/O or return value."""
    raise ValueError(f"Non-JSON number: {value}")


def main() -> int:
    """Validate project/catalog inputs using installed schemas without repairing them.

    Args: CLI kind, input path and optional --root for catalog source validation.
    Returns: 0 valid; 2 invalid input/schema/path. Side effects: Read-only local I/O;
        no secret discovery, subprocess, network, settings changes or database.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("project", "catalog"))
    parser.add_argument("input", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    try:
        schema = load_json(Path(__file__).resolve().parents[2] / f"templates/ai/schemas/{args.kind}.schema.json")
        check_schema(schema)
        value = load_json(args.input)
        validate(value, schema)
        if args.kind == "catalog":
            catalog_links(value, args.root)
        else:
            project_links(value, args.root)
        print(json.dumps({"status": "PASS", "kind": args.kind}))
        return 0
    except (OSError, ValueError) as error:
        print(f"Schema validation error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
