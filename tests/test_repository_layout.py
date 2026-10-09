"""Dependency-free checks for paths, docs and release scaffolding."""

from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryLayoutTests(unittest.TestCase):
    def test_installable_skill_and_extension_are_separate(self):
        skill = ROOT / "skills/playwright"
        self.assertTrue((skill / "SKILL.md").is_file())
        self.assertTrue((skill / "references/setup.md").is_file())
        self.assertTrue((skill / "scripts/pw.py").is_file())
        self.assertFalse((skill / "guidance-extension").exists())
        manifest = json.loads((ROOT / "extension/manifest.json").read_text())
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("nativeMessaging", manifest["permissions"])

    def test_release_files_exist(self):
        for name in (
            "README.md", "ROADMAP.md", "LICENSE", "NOTICE", "CONTRIBUTING.md",
            "SECURITY.md", "CODE_OF_CONDUCT.md", "CHANGELOG.md",
            "docs/architecture.md", "docs/install-skill.md", "docs/install-extension.md",
            "docs/features.md", ".github/workflows/ci.yml", "website/index.html",
            "scripts/link-local-skill.sh",
        ):
            with self.subTest(file=name):
                self.assertTrue((ROOT / name).is_file(), f"Missing: {name}")

    def test_internal_markdown_links_resolve(self):
        documents = [ROOT / "README.md", ROOT / "ROADMAP.md", ROOT / "CONTRIBUTING.md"]
        documents += list((ROOT / "docs").glob("*.md"))
        documents += list((ROOT / "skills/playwright/references").glob("*.md"))
        link = re.compile(r"(?<!!)\]\(([^)]+)\)")
        for document in documents:
            for destination in link.findall(document.read_text()):
                destination = destination.split("#", 1)[0]
                if not destination or destination.startswith(("https://", "http://", "mailto:")):
                    continue
                with self.subTest(file=str(document.relative_to(ROOT)), link=destination):
                    self.assertTrue((document.parent / destination).exists(), destination)

    def test_no_generated_browser_state_tracked(self):
        ignore = (ROOT / ".gitignore").read_text()
        for entry in (".playwright-cli/", "*.env", "__pycache__/", ".venv/"):
            self.assertIn(entry, ignore)


if __name__ == "__main__":
    unittest.main()
