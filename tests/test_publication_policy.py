"""Tests for publication and contribution safety checks.

These tests use fake local repositories and synthetic secrets only.
"""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_publication", ROOT / "scripts/check_publication.py")
preflight = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preflight
SPEC.loader.exec_module(preflight)


class PublicationPolicyTests(unittest.TestCase):
    def test_rejects_sensitive_filenames_but_allows_example_config(self):
        for name in (
            ".env", ".env.production", "notes.md", ".playwright-cli/page.yml",
            "diagnostics/scope/record.json", "auth/pairing.json",
            "temp/id_rsa", "profiles/cookies.json", ".venv/settings.py",
            "agent.key", "state.sqlite",
        ):
            with self.subTest(name=name):
                self.assertTrue(preflight.path_issues(name))
        for name in (".env.example", "extension/manifest.json",
                     "website/index.html", "tests/test_guidance.py"):
            with self.subTest(name=name):
                self.assertFalse(preflight.path_issues(name))

    def test_detects_synthetic_credentials_without_echoing_them(self):
        fixtures = {
            "GitHub credential": b"ghp_" + b"x" * 38,
            "OpenAI credential": b"sk-" + b"X" * 42,
            "AWS credential": b"AKIA" + b"Q" * 16,
            "Playwright pairing credential": b"PLAYWRIGHT_MCP_EXTENSION_TOKEN=" + b"z" * 43,
            "private key": b"-----BEGIN " + b"OPENSSH PRIVATE KEY-----",
            "developer home path": b"/Users/" + b"sample-user" + b"/scratch/demo",
        }
        for category, data in fixtures.items():
            with self.subTest(category=category):
                self.assertIn(category, preflight.content_issues(data))
        self.assertFalse(preflight.content_issues(b"Bearer test-token\n127.0.0.1:8799"))
        self.assertFalse(preflight.content_issues(b"\x89PNG\r\n\x1a\n\x00binary"))

    def test_reads_git_tracked_and_untracked_but_not_ignored(self):
        with tempfile.TemporaryDirectory(prefix="bag-publication-policy-") as folder:
            root = Path(folder)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text(".env\nprivate-notes.txt\n", encoding="utf-8")
            (root / "README.md").write_text("clean public source", encoding="utf-8")
            (root / "new.txt").write_text("also clean", encoding="utf-8")
            (root / ".env").write_text("not-read-by-check", encoding="utf-8")
            (root / "private-notes.txt").write_text("not-read-by-check", encoding="utf-8")
            subprocess.run(["git", "add", "README.md", ".gitignore"], cwd=root, check=True)
            self.assertEqual(preflight.candidates(root),
                             [".gitignore", "README.md", "new.txt"])
            self.assertFalse(preflight.audit(root))

            (root / "new.txt").write_bytes(b"ghp_" + b"Z" * 38)
            self.assertIn(("new.txt", "GitHub credential"), preflight.audit(root))
            (root / "new.txt").write_text("clean", encoding="utf-8")
            outside = root.parent / "not-in-this-repository"
            (root / "outside-link").symlink_to(outside)
            self.assertIn(("outside-link", "broken symbolic link"), preflight.audit(root))

    def test_current_candidate_repository_has_no_preflight_findings(self):
        self.assertEqual(preflight.audit(), [])


class ContributionContractTests(unittest.TestCase):
    def test_ci_runs_on_unprivileged_external_pull_requests(self):
        ci = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("pull_request:", ci)
        self.assertNotIn("pull_request_target:", ci)
        self.assertIn("contents: read", ci)
        self.assertIn("persist-credentials: false", ci)
        self.assertIn("scripts/check_publication.py", ci)
        self.assertIn("test_publication_policy.py", ci)
        self.assertIn("unittest discover -s skills/playwright/tests", ci)
        self.assertIn("unittest discover -s tests", ci)
        self.assertIn("BAG_RUN_BROWSER_E2E", ci)
        self.assertIn("fetch-depth: 0", ci)
        self.assertIn('git diff --check "origin/$BASE_REF...HEAD"', ci)

    def test_contribution_templates_request_evidence_without_secrets(self):
        pull = (ROOT / ".github/pull_request_template.md").read_text()
        for expected in ("Verification", "Compatibility", "check_publication.py",
                         "credentials", "tests"):
            self.assertIn(expected, pull)
        for name in ("bug_report.yml", "feature_request.yml"):
            template = (ROOT / ".github/ISSUE_TEMPLATE" / name).read_text()
            self.assertIn("name:", template)
            self.assertIn("description:", template)
            self.assertIn("body:", template)
            self.assertIn("required: true", template)
        bug = (ROOT / ".github/ISSUE_TEMPLATE/bug_report.yml").read_text().lower()
        self.assertIn("token", bug)
        self.assertIn("reproduction steps", bug)

    def test_contribution_docs_include_reproducible_checks_and_safety_boundary(self):
        contributing = (ROOT / "CONTRIBUTING.md").read_text()
        for expected in ("scripts/check_publication.py",
                         "unittest discover -s tests",
                         "unittest discover -s skills/playwright/tests",
                         "BAG_RUN_BROWSER_E2E", "disposable", "SECURITY.md"):
            self.assertIn(expected, contributing)
        self.assertIn("Apache", (ROOT / "LICENSE").read_text()[:160])
        self.assertIn("Microsoft", (ROOT / "NOTICE").read_text())


if __name__ == "__main__":
    unittest.main()
