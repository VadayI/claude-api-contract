"""Regression coverage for literal dotenv compatibility and child-only credentials."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/ai"))
from legacy_launch import dotenv_values, environment


class LegacyLauncherTests(unittest.TestCase):
    """Use synthetic values only; never access project secrets or the database."""

    def test_shell_content_is_literal_and_unknown_keys_are_excluded(self):
        """Keep shell metacharacters as data; no I/O or execution; assertions may fail.

        Takes no arguments and returns None. This tests the literal parser contract.
        """
        values = dotenv_values('export CONTRACT_REPO="$(touch canary)"\nDATABASE_URL=secret\n'
                               'CONTEXT7_API_KEY=`command` # comment\n')
        self.assertEqual(values, {"CONTRACT_REPO": "$(touch canary)",
                                  "CONTEXT7_API_KEY": "`command`"})

    def test_child_credentials_do_not_mutate_parent(self):
        """Preserve blank fallback and PAT precedence in a child-only dictionary.

        Takes no arguments/returns None; no I/O, DB or side effects. Assertions
        fail on lost config, unexpected secret inheritance or parent mutation.
        """
        parent = {"CONTRACT_VERSION": "v1", "GH_TOKEN": "old", "GITHUB_TOKEN": "old2",
                  "DATABASE_URL": "private", "GITHUB_PERSONAL_ACCESS_TOKEN": "parent"}
        before = dict(parent)
        values = dotenv_values('CONTRACT_VERSION=\nGITHUB_PERSONAL_ACCESS_TOKEN="new"')
        child = environment("claude", parent, values)
        self.assertEqual(parent, before)
        self.assertEqual(child["GH_TOKEN"], "new")
        self.assertEqual(child["CONTRACT_VERSION"], "v1")
        self.assertNotIn("GITHUB_TOKEN", child)
        self.assertNotIn("DATABASE_URL", child)

    def test_ambiguous_assignments_fail_without_disclosing_values(self):
        """Reject duplicates/multiline data without secret text in errors.

        Takes no arguments/returns None; no I/O, DB or mutation. Assertion
        failures identify accepted ambiguous configuration or value disclosure.
        """
        for text in ('CONTRACT_REPO=a\nCONTRACT_REPO=b', 'CONTEXT7_API_KEY="synthetic-secret'):
            with self.assertRaises(ValueError) as caught:
                dotenv_values(text)
            self.assertNotIn("synthetic-secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
