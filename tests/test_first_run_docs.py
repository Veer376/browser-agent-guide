"""Critical user/agent first-run setup claims remain consistent across docs."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "playwright"
SETUP = SKILL / "references" / "setup.md"


class FirstRunDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.setup = SETUP.read_text(encoding="utf-8")
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.install = (ROOT / "docs/install-skill.md").read_text(encoding="utf-8")

    def test_setup_and_token_helper_are_bundled_in_installable_skill(self):
        self.assertTrue((SKILL / "SKILL.md").is_file())
        self.assertTrue((SKILL / "scripts/pw.py").is_file())
        self.assertTrue((SKILL / "scripts/save_extension_token_from_clipboard.sh").is_file())
        self.assertIn("save_extension_token_from_clipboard.sh", self.setup)
        self.assertIn("$SKILL_DIR/scripts/pw.py", self.setup)

    def test_starter_prompt_is_in_setup_and_readme(self):
        for doc in (self.setup, self.readme, self.install):
            with self.subTest(document=doc[:45]):
                self.assertIn("references/setup.md", doc)
                self.assertIn("existing Chrome", doc)
                self.assertIn("separate", doc)
                self.assertIn("token", doc.lower())
        self.assertIn("## Starter prompt", self.setup)
        self.assertIn("## Guided first-time setup", self.readme)

    def test_different_extension_types_and_opt_in_token(self):
        self.assertIn("official Microsoft Playwright extension", self.setup)
        self.assertIn("Browser Agent Guide extension", self.setup)
        self.assertIn("PW_BROWSER_MODE=standalone", self.setup)
        self.assertIn("PW_BROWSER_MODE=existing", self.setup)
        self.assertIn("chrome.env", self.setup)
        self.assertIn("clipboard", self.setup)
        self.assertIn("explicit approval", self.setup)
        self.assertIn("does **not** bypass", self.setup)
        self.assertIn("not a", self.setup.lower())

    def test_current_chrome_is_default_without_bundled_personal_preferences(self):
        skill_doc = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertFalse((SKILL / "references/user-preferences.md").exists())
        self.assertNotIn("user-preferences.md", skill_doc)
        self.assertIn("By default, `pw open` attaches", skill_doc)
        self.assertIn("`PW_BROWSER_MODE=standalone` only when a separate browser is requested", skill_doc)
        self.assertIn("Preserve the user's active tab/window", skill_doc)
        for content in (self.setup, self.readme, self.install):
            with self.subTest(document=content[:45]):
                self.assertIn("Chrome", content)
                self.assertIn("default", content)
                self.assertIn("standalone", content)

    def test_relative_links_in_setup_are_in_installable_skill(self):
        # Local Markdown links in the installed setup must not expect repo-root docs.
        import re

        for link in re.findall(r"\]\(([^)]+)\)", self.setup):
            if link.startswith(("https://", "http://", "#")):
                continue
            with self.subTest(link=link):
                self.assertTrue((SETUP.parent / link).exists(), link)


if __name__ == "__main__":
    unittest.main()
