"""Exercise shared session context, records and cross-agent continuity fixtures."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ai"))
import session_context

SCRIPT = ROOT / "scripts/ai/session_context.py"
FILLED = {
    "Task": "P07 continuity fixture task from the plan.",
    "Changes": "src/app.py",
    "Decisions": "none",
    "Checks": "python -m unittest: exit 0 (PASS)",
    "Limitations": "Windows run NOT_VERIFIED in this fixture.",
    "Next step": "Codex continues with the review of src/app.py.",
}


class SessionContextTests(unittest.TestCase):
    """Use disposable local Git repositories; no network, database or global config."""

    def setUp(self):
        """Create a committed project with purpose, architecture, ADR and handoff docs."""
        self.temp = tempfile.TemporaryDirectory(prefix="session context ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "project Україна"
        self.repo.mkdir()
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        for name, text in {"README.md": "# Fixture\n\nPurpose: continuity fixtures.\n",
                           "docs/ai/rules/architecture.md": "# Architecture\n",
                           "docs/decisions/0001-start.md": "# ADR 0001\n",
                           "docs/HANDOFF.md": "# HANDOFF\n\nRolling notes.\n",
                           ".gitignore": ".ai-runtime/\n"}.items():
            self.write(name, text)
        self.commit("fixture", ".")

    def git(self, *args: str, cwd: Path | None = None) -> str:
        """Run a fixture-local Git command and return its stripped stdout.

        Args:
            *args: Git argv scoped to the fixture repository.
            cwd: Optional repository; defaults to the main fixture.
        Returns:
            Standard output without surrounding whitespace.
        Raises:
            subprocess.CalledProcessError when the fixture command fails.
        Side effects:
            Mutates only disposable fixture repositories.
        """
        return subprocess.run(["git", "-C", str(cwd or self.repo), *args], capture_output=True,
                              text=True, check=True, timeout=30).stdout.strip()

    def write(self, name: str, text: str, root: Path | None = None) -> Path:
        """Write one UTF-8 fixture file, creating parents; return its path."""
        path = (root or self.repo) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def commit(self, message: str, *paths: str, cwd: Path | None = None) -> str:
        """Stage explicit fixture paths, commit them and return the new HEAD."""
        self.git("add", "--", *paths, cwd=cwd)
        self.git("commit", "-q", "-m", message, cwd=cwd)
        return self.git("rev-parse", "HEAD", cwd=cwd)

    def fill(self, path: Path, next_step: str | None = None) -> None:
        """Replace every placeholder section of a record with fixture facts."""
        text = path.read_text(encoding="utf-8")
        for title, body in FILLED.items():
            if title == "Next step" and next_step:
                body = next_step
            head, _, rest = text.partition(f"## {title}\n\n")
            _, _, tail = rest.partition("\n")
            text = f"{head}## {title}\n\n{body}\n{tail}"
        path.write_text(text, encoding="utf-8", newline="\n")

    def record(self, agent: str, moment: datetime, next_step: str | None = None,
               root: Path | None = None) -> Path:
        """Create, fill and commit one session record for the given agent."""
        root = root or self.repo
        path = session_context.new_record(root, agent, moment)
        self.fill(path, next_step)
        self.commit(f"session {agent}", path.relative_to(root).as_posix(), cwd=root)
        return path

    def test_fresh_project_has_context_but_no_record(self):
        """Purpose, architecture, ADRs and handoff resolve; missing record is a finding."""
        report = session_context.build_report(self.repo)
        keys = {entry["key"]: entry for entry in report["documentation"]}
        self.assertEqual(keys["architecture"]["path"], "docs/ai/rules/architecture.md")
        self.assertEqual(keys["decisions"]["kind"], "directory")
        self.assertEqual(report["findings"], ["No session record in docs/sessions"])
        self.assertFalse(report["runtime_present"])
        self.assertIn("Latest session record: none", session_context.render(report))

    def test_empty_decisions_directory_is_a_finding(self):
        """An uncommittable empty ADR directory does not count as recorded decisions."""
        self.git("rm", "-q", "docs/decisions/0001-start.md")
        (self.repo / "docs/decisions").mkdir(exist_ok=True)
        findings = session_context.build_report(self.repo)["findings"]
        self.assertIn("Documentation 'decisions' is missing or empty: docs/decisions "
                      "(commit an ADR or an index stating none exist yet)", findings)

    def test_record_skeleton_must_be_filled(self):
        """A new record carries branch/revision/agent and fails until its sections are filled."""
        head = self.git("rev-parse", "HEAD")
        path = session_context.new_record(self.repo, "claude", datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc))
        record = session_context.parse_record(path)
        self.assertEqual(record["fields"]["revision"], head)
        self.assertEqual(record["fields"]["branch"], "main")
        self.assertRegex(path.stem, r"^20260925T070000Z-claude-[0-9a-f]{6}$")
        findings = session_context.build_report(self.repo)["findings"]
        self.assertTrue(any("'Next step' is empty or unfilled" in item for item in findings))
        self.assertTrue(any("not committed" in item for item in findings))
        self.fill(path)
        self.commit("record", path.relative_to(self.repo).as_posix())
        self.assertEqual(session_context.build_report(self.repo)["findings"], [])

    def test_claude_codex_claude_and_other_machine(self):
        """Each agent sees the previous agent's record; a clone without .ai-runtime does too."""
        self.record("claude", datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc),
                    "Codex reviews src/app.py.")
        codex_view = session_context.build_report(self.repo)
        self.assertEqual(codex_view["latest"]["fields"]["agent"], "claude")
        self.assertIn("Codex reviews src/app.py.", codex_view["latest"]["next_step"])
        self.write("src/app.py", "print('codex')\n")
        self.commit("codex change", "src/app.py")
        self.record("codex", datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
                    "Claude merges after the user's command.")
        (self.repo / ".ai-runtime").mkdir()
        self.write(".ai-runtime/environment.json", "{}\n")
        claude_view = session_context.build_report(self.repo)
        self.assertEqual(claude_view["latest"]["fields"]["agent"], "codex")
        self.assertEqual(claude_view["findings"], [])

        other = self.base / "other machine"
        subprocess.run(["git", "clone", "-q", str(self.repo), str(other)], check=True,
                       capture_output=True, timeout=60)
        remote_view = session_context.build_report(other)
        self.assertFalse(remote_view["runtime_present"])
        self.assertEqual(remote_view["findings"], [])
        self.assertEqual(remote_view["latest"]["fields"]["agent"], "codex")
        self.assertIn("Claude merges after the user's command.",
                      session_context.render(remote_view))

    def test_parallel_records_merge_without_conflict(self):
        """Parallel sessions on two branches create distinct files that merge cleanly."""
        moment = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
        self.git("switch", "-q", "-c", "feat/a")
        first = self.record("claude", moment)
        self.git("switch", "-q", "main")
        self.git("switch", "-q", "-c", "feat/b")
        second = self.record("codex", moment)
        self.git("merge", "-q", "--no-edit", "feat/a")
        self.assertTrue(first.exists() and second.exists())
        self.assertNotEqual(first.name, second.name)
        self.assertEqual(session_context.build_report(self.repo)["session_records"], 2)

    def test_identifier_collision_retries_without_overwrite(self):
        """An existing name is never overwritten; allocation retries with a new suffix."""
        moment = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
        with mock.patch.object(session_context.secrets, "token_hex",
                               side_effect=["aaaaaa", "aaaaaa", "bbbbbb"]):
            first = session_context.new_record(self.repo, "codex", moment)
            original = first.read_text(encoding="utf-8")
            second = session_context.new_record(self.repo, "codex", moment)
        self.assertTrue(first.name.endswith("-aaaaaa.md"))
        self.assertTrue(second.name.endswith("-bbbbbb.md"))
        self.assertEqual(first.read_text(encoding="utf-8"), original)

    def test_snapshot_lists_relevant_changes_after_record(self):
        """Commits after the record are reported by path; continuity files are excluded."""
        self.record("claude", datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc))
        self.write("src/app.py", "print('later')\n")
        self.write("docs/HANDOFF.md", "# HANDOFF\n\nUpdated.\n")
        self.commit("later work", "src/app.py", "docs/HANDOFF.md")
        report = session_context.build_report(self.repo)
        snap = report["latest"]["snapshot"]
        self.assertEqual(snap["commits_since"], 1)
        self.assertEqual(snap["relevant_paths"], ["src/app.py"])
        self.assertTrue(snap["revision_ancestor"])
        self.assertTrue(any("record this work" in item for item in report["findings"]), report["findings"])

    def test_missing_revision_in_clone_is_reported_not_failed(self):
        """A revision absent from a clone (unpushed/squashed) is information, not a failure."""
        self.git("switch", "-q", "-c", "local-only")
        self.write("local.txt", "local\n")
        self.commit("local only", "local.txt")
        path = session_context.new_record(self.repo, "claude",
                                          datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc))
        self.fill(path)
        self.git("switch", "-q", "main")
        self.commit("record from local branch", path.relative_to(self.repo).as_posix())
        other = self.base / "single branch clone"
        # --no-local: klon przez transport Git, więc obiekty z innych gałęzi nie są kopiowane.
        subprocess.run(["git", "clone", "-q", "--no-local", "--single-branch", "--branch", "main",
                        str(self.repo), str(other)], check=True, capture_output=True, timeout=60)
        report = session_context.build_report(other)
        self.assertEqual(report["findings"], [])
        self.assertFalse(report["latest"]["snapshot"]["revision_known"])
        self.assertIn("Recorded revision is not in this clone", session_context.render(report))
        shallow = self.base / "shallow clone"
        subprocess.run(["git", "clone", "-q", "--no-local", "--depth", "1", str(self.repo), str(shallow)],
                       check=True, capture_output=True, timeout=60)
        shallow_report = session_context.build_report(shallow)
        self.assertEqual(shallow_report["findings"], [])
        self.assertTrue(shallow_report["latest"]["snapshot"]["shallow"])

    def test_dirty_committed_record_is_a_finding(self):
        """Edits after the record's commit are invisible elsewhere and must be committed."""
        path = session_context.new_record(self.repo, "claude",
                                          datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc))
        self.commit("skeleton", path.relative_to(self.repo).as_posix())
        self.fill(path)
        findings = session_context.build_report(self.repo)["findings"]
        self.assertTrue(any("uncommitted changes" in item for item in findings), findings)

    def test_newest_record_in_tree_wins_after_merge_and_all_are_validated(self):
        """A merged newer record is the latest; an incomplete merged record is reported."""
        self.record("claude", datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc), "Old main step.")
        self.git("switch", "-q", "-c", "feat/x")
        self.record("codex", datetime(2026, 9, 20, 7, 0, tzinfo=timezone.utc), "Feature step.")
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "--no-edit", "feat/x")
        report = session_context.build_report(self.repo)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["latest"]["next_step"], "Feature step.")
        self.git("switch", "-q", "-c", "feat/y", "HEAD~1")
        skeleton = session_context.new_record(self.repo, "codex",
                                              datetime(2026, 9, 10, 7, 0, tzinfo=timezone.utc))
        self.commit("skeleton only", skeleton.relative_to(self.repo).as_posix())
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "--no-edit", "feat/y")
        findings = session_context.build_report(self.repo)["findings"]
        self.assertTrue(any(skeleton.name in item and "'Task'" in item for item in findings), findings)

    def test_bom_crlf_fences_and_decisions_placeholder(self):
        """Windows encodings parse; fenced headings stay in their section; placeholders fail."""
        path = session_context.new_record(self.repo, "codex",
                                          datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc))
        self.fill(path, "Run:\n```text\n## Checks\nnot a heading\n```")
        text = path.read_text(encoding="utf-8")
        path.write_bytes(b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8"))
        record = session_context.parse_record(path)
        self.assertEqual(record["fields"]["agent"], "codex")
        self.assertEqual(record["sections"]["Checks"], FILLED["Checks"])
        self.assertIn("not a heading", record["sections"]["Next step"])
        self.assertEqual(session_context.record_findings(path, record), [])
        record["sections"]["Decisions"] = "{TODO: decisions}"
        self.assertEqual(session_context.record_findings(path, record),
                         [f"{path.name}: section 'Decisions' is empty or unfilled"])

    def test_subdirectory_root_reports_root_relative_paths(self):
        """A project below the repository top level sees only its own relevant paths."""
        project = self.repo / "proj"
        for name in ("README.md", "docs/ai/rules/architecture.md", "docs/decisions/0001.md",
                     "docs/HANDOFF.md"):
            self.write(f"proj/{name}", "# fixture\n")
        self.commit("subproject", "proj")
        self.record("claude", datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc), root=project)
        self.write("other.txt", "outside\n")
        self.write("proj/docs/HANDOFF.md", "# updated\n")
        self.write("proj/src/app.py", "print(1)\n")
        self.commit("later", "other.txt", "proj/docs/HANDOFF.md", "proj/src/app.py")
        snap = session_context.build_report(project)["latest"]["snapshot"]
        self.assertEqual(snap["relevant_paths"], ["src/app.py"])

    def test_union_merge_attributes_are_rejected(self):
        """merge=union on handoff or session records is reported as a finding."""
        self.write(".gitattributes", "docs/HANDOFF.md merge=union\ndocs/sessions/*.md merge=union\n")
        findings = session_context.build_report(self.repo)["findings"]
        self.assertIn("merge=union applies to docs/HANDOFF.md; use ordinary content merges", findings)
        self.assertIn("merge=union applies to docs/sessions/probe.md; use ordinary content merges", findings)

    def test_explicit_map_legacy_settings_and_unsafe_paths(self):
        """The project map is authoritative, legacy settings are read, unsafe paths fail."""
        settings = {"documentation": {"architecture": "README.md", "handoff": "notes/HANDOFF.md",
                                      "runbook": "docs/runbook.md"}}
        self.write(".claude/memory/project.json", json.dumps(settings))
        report = session_context.build_report(self.repo)
        keys = {entry["key"]: entry for entry in report["documentation"]}
        self.assertEqual(report["project"]["path"], ".claude/memory/project.json")
        self.assertEqual((keys["architecture"]["path"], keys["architecture"]["source"]), ("README.md", "map"))
        self.assertEqual(keys["runbook"]["kind"], "missing")
        self.assertIn("Documentation 'handoff' is missing or empty: notes/HANDOFF.md", report["findings"])
        self.write("config/secrets.json", "{}\n")
        self.write("docs/settings.json", "{}\n")
        for unsafe in ("../outside.md", ".ai-runtime/notes.md", ".env.local", "C:/notes.md",
                       ".npmrc", ".git-credentials", "config/secrets.json", "docs/settings.json",
                       ".claude/notes.md"):
            settings["documentation"]["handoff"] = unsafe
            self.write(".claude/memory/project.json", json.dumps(settings))
            with self.subTest(path=unsafe), self.assertRaises(ValueError):
                session_context.build_report(self.repo)

    def test_cli_exit_codes_and_json(self):
        """Start context exits 0, --check exits 1 with findings, bad input exits 2."""
        def run(*args):
            return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.repo), *args],
                                  capture_output=True, text=True, encoding="utf-8", timeout=60)
        start = run()
        self.assertEqual(start.returncode, 0, start.stderr)
        self.assertIn("Continuity findings:", start.stdout)
        self.assertEqual(run("--check").returncode, 1)
        self.assertEqual(json.loads(run("--json").stdout)["session_records"], 0)
        self.assertEqual(run("--new-record").returncode, 2)
        self.assertEqual(run("--new-record", "--agent", "Bad Agent").returncode, 2)
        created = run("--new-record", "--agent", "codex")
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertTrue(created.stdout.strip().startswith("docs/sessions/"))
        record = self.repo / created.stdout.strip()
        self.fill(record, "Наступний крок: перевірити на Windows.")
        ansi = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.repo)],
                              capture_output=True, env={**os.environ, "PYTHONIOENCODING": "cp1252"},
                              timeout=60)
        self.assertEqual(ansi.returncode, 0, ansi.stderr)
        self.assertIn("Наступний крок", ansi.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
