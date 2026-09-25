"""Report shared session context and record agent-neutral session handoffs."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import subprocess
import sys

from core_paths import contained_entry
from core_sync import safe_name, target_root
import project_state
import schema


# Kandydaci w kolejności: jawna mapa z project.json zawsze wygrywa; bez niej
# pierwszy istniejący kandydat, a gdy żaden nie istnieje — pierwszy (jako brak).
DOCUMENTATION_DEFAULTS = {
    "readme": ("README.md",),
    "project": ("docs/PROJECT.md", "PROJECT.md"),
    "architecture": ("docs/ARCHITECTURE.md", "docs/ai/rules/architecture.md",
                     "docs/ai/rules/contract-first.md"),
    "decisions": ("docs/decisions",),
    "handoff": ("docs/HANDOFF.md",),
    "sessions": ("docs/sessions",),
    "backlog": ("docs/todo.md",),
    "lessons": ("docs/lessons.md",),
    "worklog": ("docs/WORKLOG.md",),
}
PURPOSE_KEYS = ("project", "readme")
REQUIRED_KEYS = ("architecture", "decisions", "handoff")
# Ścieżki ciągłości zmieniają się przy każdym zapisie sesji; nie są „istotnym diffem”.
CONTINUITY_KEYS = ("handoff", "sessions", "worklog", "backlog", "lessons")
RECORD_FIELDS = ("session", "agent", "recorded", "branch", "revision")
RECORD_SECTIONS = ("Task", "Changes", "Decisions", "Checks", "Limitations", "Next step")
REQUIRED_SECTIONS = ("Task", "Changes", "Checks", "Limitations", "Next step")
SESSION_ID = re.compile(r"^(\d{8}T\d{6}Z)-([a-z0-9][a-z0-9-]{0,31})-([0-9a-f]{6})$")
AGENT = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
REVISION = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64}|unborn)$")
RECORDED = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
PLACEHOLDER = "{TODO"
DOCUMENT_SUFFIXES = {".md", ".markdown", ".txt", ".rst", ".adoc"}
MAX_LISTED_PATHS = 20
MAX_EXCERPT_LINES = 6


def _git(root: Path, *args: str) -> subprocess.CompletedProcess | None:
    """Run one read-only Git query in the project without optional index writes.

    Args:
        root: Validated project root passed to ``git -C``.
        *args: Git subcommand and arguments as separate argv entries.
    Returns:
        The completed process, or ``None`` when Git is not installed or times out.
    Raises:
        None; unavailable Git is reported by the caller as missing evidence.
    Side effects:
        Starts a Git subprocess with ``GIT_OPTIONAL_LOCKS=0`` so status queries
        never refresh or lock the index; no network, database or credential use.
    """
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
    try:
        return subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(root), *args],
                              capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              env=env, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _git_text(root: Path, *args: str) -> str | None:
    """Return stripped stdout of a successful Git query, otherwise ``None``.

    Args:
        root: Validated project root.
        *args: Git argv after ``git -C root``.
    Returns:
        Output text without surrounding whitespace, or ``None`` on any failure.
    Side effects:
        Same as :func:`_git`.
    """
    result = _git(root, *args)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


def git_state(root: Path) -> dict:
    """Describe branch, revision, working tree and last-fetched upstream state.

    Args:
        root: Validated project root.
    Returns:
        A dictionary with ``available``; when available also ``branch`` (``None``
        when detached), ``head`` (full SHA or ``None`` for an unborn branch),
        ``changed`` (count of porcelain entries) and optional ``upstream`` with
        ``ahead``/``behind`` counts from local refs.
    Raises:
        None.
    Side effects:
        Read-only Git queries; no fetch, so upstream counts reflect the last
        fetch and are labelled that way by the renderer. No network or database.
    """
    if _git_text(root, "rev-parse", "--is-inside-work-tree") != "true":
        return {"available": False}
    state = {"available": True,
             "branch": _git_text(root, "symbolic-ref", "--quiet", "--short", "HEAD"),
             "head": _git_text(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")}
    # Bez -z: nazwy z nietypowymi znakami są cytowane, więc linia = jeden wpis.
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=normal")
    state["changed"] = (len([line for line in status.stdout.splitlines() if line.strip()])
                        if status is not None and status.returncode == 0 else None)
    upstream = _git_text(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if upstream and state["head"]:
        counts = _git_text(root, "rev-list", "--left-right", "--count", f"{upstream}...HEAD")
        if counts and len(counts.split()) == 2:
            behind, ahead = (int(value) for value in counts.split())
            state["upstream"] = {"name": upstream, "ahead": ahead, "behind": behind}
    return state


def load_project(root: Path) -> tuple[str | None, dict | None]:
    """Read project settings through the shared canonical/legacy resolver.

    Args:
        root: Validated project root.
    Returns:
        ``(relative_path, settings)``; both ``None`` when no settings file exists.
    Raises:
        ValueError: For conflicting canonical/legacy copies, invalid JSON or a
            non-object document.
        OSError: If an existing settings file cannot be read.
    Side effects:
        Reads at most the two allowlisted settings paths; no writes or network.
    Business rules:
        Only the documentation map and summary fields are interpreted here; full
        schema validation remains ``schema.py``'s responsibility.
    """
    path = project_state.resolve_state(root, "project.json")
    if not path.exists():
        return None, None
    data = schema.load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Project settings must be a JSON object: {path}")
    return path.relative_to(root).as_posix(), data


def documentation_name(name: object, key: str = "entry") -> str:
    """Validate a documentation map path before any filesystem access.

    Args:
        name: Candidate root-relative POSIX path from the map or defaults.
        key: Documentation role, used only in error messages.
    Returns:
        The unchanged path string.
    Raises:
        ValueError: For non-strings, unsafe/absolute/traversing names, hidden
            components (for example ``.npmrc`` or ``.git-credentials``), names
            mentioning secrets/credentials, or a file suffix that is not a
            document format.
    Side effects:
        None; purely lexical checks.
    Business rules:
        Documentation roles point at human-readable notes or directories, never
        at configuration, key material or runtime state that an agent following
        the map would then open.
    """
    if not isinstance(name, str):
        raise ValueError(f"Documentation entry must be a path string: {key}")
    safe_name(name)
    parts = PurePosixPath(name).parts
    if any(part.startswith(".") for part in parts) or any(
            marker in part.casefold() for part in parts for marker in ("secret", "credential")):
        raise ValueError(f"Documentation entry cannot name hidden or secret paths: {name}")
    suffix = PurePosixPath(name).suffix.casefold()
    if suffix and suffix not in DOCUMENT_SUFFIXES:
        raise ValueError(f"Documentation entry must be a document or directory: {name}")
    return name


def _entry(root: Path, key: str, name: str, source: str) -> dict:
    """Validate one documentation entry and describe its presence.

    Args:
        root: Validated project root.
        key: Documentation role such as ``handoff``.
        name: Root-relative POSIX path from the map or defaults.
        source: ``map`` for an explicit project entry, ``default`` otherwise.
    Returns:
        ``{"key", "path", "source", "kind"}`` where kind is ``file``,
        ``directory`` or ``missing``; directories also report ``entries``.
    Raises:
        ValueError: For unsafe, secret, runtime, linked or non-document paths.
    Side effects:
        Filesystem metadata reads and one directory listing; no content reads.
    """
    documentation_name(name, key)
    path = contained_entry(root, name)
    entry = {"key": key, "path": name, "source": source}
    if path.is_dir():
        entry["kind"] = "directory"
        entry["entries"] = sum(1 for item in path.iterdir() if not item.name.startswith("."))
    elif path.is_file():
        if path.suffix.casefold() not in DOCUMENT_SUFFIXES:
            raise ValueError(f"Documentation entry must be a document or directory: {name}")
        entry["kind"] = "file"
        entry["empty"] = path.stat().st_size == 0
    else:
        entry["kind"] = "missing"
    return entry

def documentation_map(root: Path, project: dict | None) -> dict[str, dict]:
    """Combine the explicit project documentation map with family defaults.

    Args:
        root: Validated project root.
        project: Decoded project settings or ``None``.
    Returns:
        Ordered mapping from documentation role to its described entry. Standard
        roles come first in :data:`DOCUMENTATION_DEFAULTS` order, then extra
        project-defined roles sorted by name.
    Raises:
        ValueError: If the map is not an object or contains an unsafe path.
    Side effects:
        Filesystem metadata reads only.
    Business rules:
        An explicit entry is authoritative even when its file is missing; this
        reports the gap instead of silently choosing another document. Defaults
        never duplicate documents: README or a rule file may serve a role.
    """
    explicit = {} if project is None else project.get("documentation", {})
    if not isinstance(explicit, dict):
        raise ValueError("Project documentation map must be an object")
    result = {}
    for key, candidates in DOCUMENTATION_DEFAULTS.items():
        if key in explicit:
            result[key] = _entry(root, key, explicit[key], "map")
            continue
        chosen = None
        for candidate in candidates:
            entry = _entry(root, key, candidate, "default")
            if entry["kind"] != "missing":
                chosen = entry
                break
        result[key] = chosen or _entry(root, key, candidates[0], "default")
    for key in sorted(set(explicit) - set(DOCUMENTATION_DEFAULTS)):
        result[key] = _entry(root, key, explicit[key], "map")
    return result


def parse_record(path: Path) -> dict:
    """Parse a session record's front matter and level-two sections.

    Args:
        path: Existing Markdown record named ``<session-id>.md``.
    Returns:
        ``{"fields": {...}, "sections": {...}}`` with raw string values.
    Raises:
        ValueError: If the file does not start with a ``---`` front-matter block.
        OSError/UnicodeError: If the record cannot be read as UTF-8.
    Side effects:
        Reads one file; no writes, subprocess, network or database.
    Business rules:
        A UTF-8 BOM and CRLF line endings (Windows editors) are accepted.
        ``## `` lines inside fenced code blocks belong to the current section.
    """
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].strip() != "---" or "---" not in (line.strip() for line in lines[1:]):
        raise ValueError(f"Session record lacks front matter: {path.name}")
    end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    fields = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    sections, current, fence = {}, None, None
    for line in lines[end + 1:]:
        marker = line.lstrip()[:3]
        if marker in ("```", "~~~"):
            # Otwarcie/zamknięcie bloku kodu; nagłówki w środku nie dzielą sekcji.
            fence = marker if fence is None else (None if marker == fence else fence)
        if fence is None and line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {"fields": fields, "sections": {name: "\n".join(body).strip()
                                          for name, body in sections.items()}}


def record_findings(path: Path, record: dict) -> list[str]:
    """List structural problems that would hide context from the next session.

    Args:
        path: Record path; its stem must equal the ``session`` field.
        record: Output of :func:`parse_record`.
    Returns:
        Human-readable findings; an empty list means the record is complete.
    Side effects:
        None.
    Business rules:
        Task, changes, checks, limitations and the next step must be filled.
        A ``{TODO`` placeholder left in any section, including Decisions,
        counts as unfilled; write "none" instead.
    """
    fields, sections, findings = record["fields"], record["sections"], []
    for name in RECORD_FIELDS:
        if not fields.get(name):
            findings.append(f"{path.name}: missing front-matter field '{name}'")
    if fields.get("session") and fields["session"] != path.stem:
        findings.append(f"{path.name}: session field differs from file name")
    if fields.get("agent") and not AGENT.fullmatch(fields["agent"]):
        findings.append(f"{path.name}: invalid agent name")
    if fields.get("revision") and not REVISION.fullmatch(fields["revision"]):
        findings.append(f"{path.name}: revision must be a full commit id or 'unborn'")
    if fields.get("recorded") and not RECORDED.fullmatch(fields["recorded"]):
        findings.append(f"{path.name}: recorded must be UTC YYYY-MM-DDTHH:MM:SSZ")
    for name in RECORD_SECTIONS:
        body = sections.get(name, "")
        if (name in REQUIRED_SECTIONS and not body) or PLACEHOLDER in body:
            findings.append(f"{path.name}: section '{name}' is empty or unfilled")
    return findings

def list_records(root: Path, sessions: dict) -> tuple[list[Path], list[str]]:
    """Return well-named session records oldest first and ignored entry names.

    Args:
        root: Validated project root.
        sessions: The documentation entry for the ``sessions`` role.
    Returns:
        ``(records, ignored)``; record order follows the UTC timestamp prefix of
        the session identifier, then agent and random suffix.
    Raises:
        ValueError: If the sessions entry is a file or a record is a link.
    Side effects:
        Lists one directory; no content reads.
    """
    if sessions["kind"] == "missing":
        return [], []
    if sessions["kind"] != "directory":
        raise ValueError(f"Sessions entry must be a directory: {sessions['path']}")
    directory = contained_entry(root, sessions["path"])
    records, ignored = [], []
    for item in sorted(directory.iterdir(), key=lambda entry: entry.name):
        if item.name.startswith("."):
            continue
        if item.is_symlink() or item.is_junction():
            raise ValueError(f"Linked session record: {item.name}")
        if item.is_file() and item.suffix == ".md" and SESSION_ID.fullmatch(item.stem):
            records.append(item)
        else:
            ignored.append(item.name)
    return records, ignored


def snapshot(root: Path, path: Path, revision: str | None,
             documentation: dict[str, dict]) -> dict:
    """Compare a record's recorded revision and commit with the current HEAD.

    Args:
        root: Validated project root (the repository top level or a subdirectory).
        path: Session record file.
        revision: The record's ``revision`` field.
        documentation: Resolved documentation map used to ignore continuity files.
    Returns:
        ``committed`` (bool), ``dirty`` (uncommitted edits to the record),
        ``record_commit``, ``shallow``, ``revision_known``,
        ``revision_ancestor``, ``commits_since`` and sorted ``relevant_paths``
        (root-relative) changed after the commit that last changed the record.
    Side effects:
        Read-only Git queries; no fetch, writes, network or database.
    Business rules:
        A mismatch means "inspect this diff", not "the handoff is false". Only
        committed records are visible to another machine or agent. The
        revision is validated before it reaches Git, so a malformed field can
        never be read as an option.
    """
    relative = path.relative_to(root).as_posix()
    result = {"record": relative}
    commit = _git_text(root, "log", "-1", "--format=%H", "--", relative)
    result["committed"] = bool(commit)
    result["record_commit"] = commit or None
    status = _git_text(root, "status", "--porcelain=v1", "--", relative)
    result["dirty"] = bool(commit) and bool(status)
    result["shallow"] = _git_text(root, "rev-parse", "--is-shallow-repository") == "true"
    if revision and revision != "unborn" and REVISION.fullmatch(revision):
        known = _git(root, "cat-file", "-e", f"{revision}^{{commit}}")
        result["revision_known"] = known is not None and known.returncode == 0
        if result["revision_known"]:
            ancestor = _git(root, "merge-base", "--is-ancestor", revision, "HEAD")
            result["revision_ancestor"] = ancestor is not None and ancestor.returncode == 0
    if commit:
        count = _git_text(root, "rev-list", "--count", f"{commit}..HEAD")
        result["commits_since"] = int(count) if count and count.isdigit() else None
        # --relative: ścieżki względem --root także wtedy, gdy projekt jest podkatalogiem repo.
        changed = _git_text(root, "diff", "--relative", "--name-only", commit, "HEAD") or ""
        ignored = tuple(documentation[key]["path"] for key in CONTINUITY_KEYS if key in documentation)
        result["relevant_paths"] = sorted(
            name for name in changed.splitlines()
            if name and not any(name == prefix or name.startswith(prefix.rstrip("/") + "/")
                                for prefix in ignored))
    return result

def union_merge_paths(root: Path, documentation: dict[str, dict]) -> list[str]:
    """Report continuity paths whose Git attributes select ``merge=union``.

    Args:
        root: Validated project root.
        documentation: Resolved documentation map.
    Returns:
        Sorted continuity paths (or a probe record path for directories) that
        Git would merge with the union driver.
    Side effects:
        One read-only ``git check-attr`` query; no writes or network.
    Business rules:
        Union merges silently interleave parallel HANDOFF/record edits, so the
        family requires ordinary content merges instead.
    """
    probes = []
    for key in CONTINUITY_KEYS:
        entry = documentation.get(key)
        if entry is None:
            continue
        # Katalog sprawdzamy przykładową ścieżką pliku, bo atrybuty dotyczą plików.
        probes.append(entry["path"].rstrip("/") + "/probe.md"
                      if entry["kind"] == "directory" or key == "sessions" else entry["path"])
    result = _git(root, "check-attr", "merge", "--", *probes)
    if result is None or result.returncode != 0:
        return []
    return sorted(line.split(": merge: ")[0] for line in result.stdout.splitlines()
                  if line.endswith(": merge: union"))


def _field(project: dict, section: str, key: str) -> object:
    """Return ``project[section][key]`` when the section is an object, else ``None``.

    Args:
        project: Decoded project settings.
        section: Top-level section name.
        key: Field inside that section.
    Returns:
        The stored value or ``None``; malformed sections are left to ``schema.py``.
    Side effects:
        None.
    """
    value = project.get(section)
    return value.get(key) if isinstance(value, dict) else None


def build_report(root: Path) -> dict:
    """Assemble the complete start context and continuity findings.

    Args:
        root: Project root; it is validated before any read.
    Returns:
        A JSON-serializable report with Git state, project settings summary,
        documentation map, session records, snapshot comparison, runtime
        presence and ``findings``.
    Raises:
        ValueError: For unsafe documentation paths, invalid settings JSON,
            conflicting settings copies or linked records.
        OSError: For unreadable settings or records.
    Side effects:
        Read-only filesystem and Git queries. ``.ai-runtime`` is only checked
        for existence and never read, so another machine gets the same context.
    Business rules:
        The latest record is the newest one present in the working tree (by
        its UTC identifier), whichever branch it was written on: merged
        records are part of this branch's history. Every record is validated.
        Relevant commits after the latest record are a finding because that
        work is not yet described; a recorded revision missing from this
        clone (squash/rebase merge, shallow or single-branch clone) is only
        reported, since the record's own commit anchors the comparison.
    """
    root = target_root(root)
    report = {"root": str(root), "findings": []}
    findings = report["findings"]
    git = git_state(root)
    report["git"] = git
    if not git["available"]:
        findings.append("Git state unavailable: branch and revision are not verified")
    settings_path, project = load_project(root)
    report["project"] = None if project is None else {
        "path": settings_path,
        "ci": _field(project, "ci", "execution"),
        "maturity": _field(project, "maturity", "stage"),
        "template": _field(project, "template", "kind"),
    }
    documentation = documentation_map(root, project)
    report["documentation"] = list(documentation.values())
    if not any(documentation[key]["kind"] == "file" and not documentation[key].get("empty")
               for key in PURPOSE_KEYS):
        findings.append("Project purpose not found: map 'project' or 'readme' to an existing document")
    for key in REQUIRED_KEYS:
        entry = documentation[key]
        # Pusty katalog nie trafia do Gita, więc na innej maszynie go nie ma.
        if entry["kind"] == "missing" or entry.get("empty") or entry.get("entries") == 0:
            hint = " (commit an ADR or an index stating none exist yet)" if key == "decisions" else ""
            findings.append(f"Documentation '{key}' is missing or empty: {entry['path']}{hint}")
    paths, ignored = list_records(root, documentation["sessions"])
    report["ignored_session_entries"] = ignored
    parsed = []
    for path in paths:
        try:
            record = parse_record(path)
        except (UnicodeError, ValueError) as error:
            findings.append(str(error))
            continue
        findings.extend(record_findings(path, record))
        parsed.append((path, record))
    report["session_records"] = len(parsed)
    if not parsed:
        findings.append(f"No session record in {documentation['sessions']['path']}")
        report["latest"] = None
    else:
        path, record = parsed[-1]
        latest = {"path": path.relative_to(root).as_posix(), "fields": record["fields"],
                  "next_step": record["sections"].get("Next step", ""),
                  "limitations": record["sections"].get("Limitations", ""),
                  "checks": record["sections"].get("Checks", "")}
        if git["available"]:
            snap = snapshot(root, path, record["fields"].get("revision"), documentation)
            latest["snapshot"] = snap
            if not snap["committed"]:
                findings.append(f"{path.name}: record is not committed; other machines cannot see it")
            elif snap["dirty"]:
                findings.append(f"{path.name}: record has uncommitted changes; other machines see the committed version")
            if snap.get("relevant_paths"):
                findings.append(f"{snap['commits_since']} commit(s) after {path.name} changed "
                                f"{len(snap['relevant_paths'])} relevant path(s); record this work "
                                "or inspect the diff before relying on the notes")
        report["latest"] = latest
    if git["available"]:
        for name in union_merge_paths(root, documentation):
            findings.append(f"merge=union applies to {name}; use ordinary content merges")
    report["runtime_present"] = (root / ".ai-runtime").is_dir()
    return report


def _excerpt(text: str, limit: int = MAX_EXCERPT_LINES) -> list[str]:
    """Return the first non-empty lines of a section for compact display.

    Args:
        text: Section body.
        limit: Maximum number of lines to keep.
    Returns:
        Up to ``limit`` lines plus an ellipsis marker when truncated.
    Side effects:
        None.
    """
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return lines[:limit] + (["…"] if len(lines) > limit else [])


def render(report: dict) -> str:
    """Render the report as compact text for an agent's first context read.

    Args:
        report: Output of :func:`build_report`.
    Returns:
        Plain text with bounded length (path lists and excerpts are truncated).
    Side effects:
        None.
    """
    out = ["Session context"]
    git = report["git"]
    if git["available"]:
        head = (git["head"] or "unborn")[:12]
        line = f"Git: {git['branch'] or '(detached)'} @ {head}; status entries: {git['changed']}"
        if "upstream" in git:
            upstream = git["upstream"]
            line += (f"; {upstream['name']} ahead {upstream['ahead']} / behind "
                     f"{upstream['behind']} (last fetch, not refreshed)")
        out.append(line)
    else:
        out.append("Git: unavailable")
    project = report["project"]
    out.append("Project settings: absent (CI choice not recorded)" if project is None else
               f"Project settings: {project['path']} — template={project['template']}, "
               f"ci={project['ci']}, maturity={project['maturity']}")
    out.append("Documentation map:")
    for entry in report["documentation"]:
        detail = entry["kind"]
        if entry["kind"] == "directory":
            detail += f", {entry['entries']} entries"
        if entry.get("empty"):
            detail += ", empty"
        out.append(f"  {entry['key']:<13}{entry['path']}  [{detail}; {entry['source']}]")
    latest = report["latest"]
    if latest is None:
        out.append("Latest session record: none")
    else:
        fields = latest["fields"]
        out.append(f"Latest session record: {latest['path']} — agent {fields.get('agent')}, "
                   f"branch {fields.get('branch')}, recorded {fields.get('recorded')}, "
                   f"revision {str(fields.get('revision'))[:12]}")
        snap = latest.get("snapshot")
        if snap is not None:
            if not snap["committed"]:
                out.append("  Snapshot: record not committed yet")
            elif snap.get("commits_since"):
                paths = snap["relevant_paths"]
                shown = paths[:MAX_LISTED_PATHS]
                more = f" … and {len(paths) - len(shown)} more" if len(paths) > len(shown) else ""
                out.append(f"  Snapshot: {snap['commits_since']} commit(s) after the record; "
                           f"relevant paths: {', '.join(shown) or '(continuity files only)'}{more}")
            else:
                out.append("  Snapshot: HEAD has no commits after the record")
            if snap.get("revision_known") is False:
                out.append("  Recorded revision is not in this clone (squash/rebase merge, shallow "
                           "or single-branch clone, or unpushed); the record's commit anchors the comparison")
            elif snap.get("revision_ancestor") is False:
                out.append("  Recorded revision is not an ancestor of HEAD (other branch or rewritten history)")
            if snap.get("shallow"):
                out.append("  Shallow clone: history-based comparison is limited")
        for title, key in (("Checks", "checks"), ("Limitations", "limitations"),
                           ("Next step", "next_step")):
            excerpt = _excerpt(latest[key])
            if excerpt:
                out.append(f"  {title}:")
                out.extend(f"    {line}" for line in excerpt)
    out.append("Machine-local reports (.ai-runtime/): "
               + ("present" if report["runtime_present"] else "absent")
               + " — not needed for this context")
    out.append("Runtime-private memory (Claude auto memory, Codex memories) is not shared: "
               "move durable facts into the mapped documents at wrap-up.")
    if report["findings"]:
        out.append("Continuity findings:")
        out.extend(f"  - {finding}" for finding in report["findings"])
    else:
        out.append("Continuity: PASS")
    return "\n".join(out) + "\n"


RECORD_TEMPLATE = """---
session: {session}
agent: {agent}
recorded: {recorded}
branch: {branch}
revision: {revision}
---

# Session {session}

<!-- Fill every section before committing. Record facts with their source; never
paste transcripts, env values, tokens or raw logs. -->

## Task

{{TODO: the concrete task and where it came from (plan step, issue, request)}}

## Changes

{{TODO: changed paths/commits, or "no repository changes"}}

## Decisions

{{TODO: decisions with their source or ADR, or "none"}}

## Checks

{{TODO: exact commands, exit status and candidate/base; PASS/FAIL/NOT_VERIFIED}}

## Limitations

{{TODO: what was not verified and why, or "none known"}}

## Next step

{{TODO: the single next action and who owns it}}
"""


def new_record(root: Path, agent: str, now: datetime | None = None) -> Path:
    """Create a uniquely named session record skeleton without overwriting.

    Args:
        root: Project root.
        agent: Lowercase runtime name such as ``claude`` or ``codex``.
        now: Optional UTC timestamp (tests); defaults to the current time.
    Returns:
        Path of the created record under the mapped sessions directory.
    Raises:
        ValueError: For an invalid agent name, unavailable Git state, a sessions
            entry that is not a directory, or unsafe documentation paths.
        OSError: If the directory or file cannot be created.
    Side effects:
        Creates the sessions directory if needed and exactly one new file with
        exclusive creation; reads Git branch/HEAD. No network or database.
    Business rules:
        The identifier combines UTC time, agent and random hex so parallel
        sessions on any machine produce distinct files and ordinary Git merges.
        The revision is the known HEAD at recording time, never a future commit.
    """
    if not AGENT.fullmatch(agent):
        raise ValueError("Agent must match [a-z0-9][a-z0-9-]{0,31}")
    root = target_root(root)
    git = git_state(root)
    if not git["available"]:
        raise ValueError("Git state unavailable: cannot record branch and revision")
    _, project = load_project(root)
    sessions = documentation_map(root, project)["sessions"]
    if sessions["kind"] == "file":
        raise ValueError(f"Sessions entry must be a directory: {sessions['path']}")
    directory = contained_entry(root, sessions["path"])
    directory.mkdir(parents=True, exist_ok=True)
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for _ in range(5):
        session = f"{moment:%Y%m%dT%H%M%SZ}-{agent}-{secrets.token_hex(3)}"
        path = directory / f"{session}.md"
        text = RECORD_TEMPLATE.format(session=session, agent=agent,
                                      recorded=f"{moment:%Y-%m-%dT%H:%M:%SZ}",
                                      branch=git["branch"] or "(detached)",
                                      revision=git["head"] or "unborn")
        # Tryb "x" = O_EXCL; open() Pythona pisze LF także na Windows (bez trybu tekstowego CRT).
        try:
            with open(path, "x", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        except FileExistsError:
            continue
        return path
    raise OSError("Could not allocate a unique session record name")


def main() -> int:
    """Print start context, check continuity, or create a session record.

    Args:
        CLI ``--root`` selects the project; the default prints the start
        context; ``--check`` exits nonzero on continuity findings; ``--json``
        prints the machine report; ``--new-record --agent NAME`` creates a
        record skeleton and prints its root-relative path.
    Returns:
        0 for printed context, PASS or a created record; 1 when ``--check`` has
        findings; 2 for invalid configuration, unsafe paths or I/O errors.
    Raises:
        None; expected errors are converted to exit code 2 with a message.
    Side effects:
        Read-only except ``--new-record``, which creates one file (and the
        sessions directory when absent). No network or database access.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--check", action="store_true")
    operation.add_argument("--new-record", action="store_true")
    parser.add_argument("--agent", help="runtime name for --new-record, e.g. claude or codex")
    parser.add_argument("--json", action="store_true", help="print the machine-readable report")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    # Windows: potok hooka ma kodowanie ANSI, a rekordy zawierają tekst UTF-8 (np. cyrylicę).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        if args.new_record:
            if not args.agent:
                parser.error("--new-record requires --agent")
            root = target_root(args.root)
            print(new_record(root, args.agent).relative_to(root).as_posix())
            return 0
        report = build_report(args.root)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
              if args.json else render(report), end="" if not args.json else "\n")
        return 1 if args.check and report["findings"] else 0
    except (OSError, ValueError) as error:
        print(f"Session context error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
