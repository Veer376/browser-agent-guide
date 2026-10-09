"""Checks for the self-contained, GitHub Pages-ready visual website."""

from html.parser import HTMLParser
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / "website"


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.anchors = []
        self.assets = []
        self.headings = []
        self.main_count = 0
        self.html_lang = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if tag == "a" and values.get("href", "").startswith("#"):
            self.anchors.append(values["href"][1:])
        if tag in {"script", "link"}:
            address = values.get("src") or values.get("href") or ""
            if address and not address.startswith(("http:", "https:", "data:", "#")):
                self.assets.append(address)
        if tag in {"h1", "h2", "h3"}:
            self.headings.append(tag)
        if tag == "main":
            self.main_count += 1
        if tag == "html":
            self.html_lang = values.get("lang")


class WebsiteChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text()
        cls.css = (ROOT / "styles.css").read_text()
        cls.js = (ROOT / "main.js").read_text()
        cls.page = PageParser()
        cls.page.feed(cls.html)

    def test_local_assets_exist_without_project_paths(self):
        for file in self.page.assets:
            with self.subTest(file=file):
                self.assertTrue((ROOT / file).is_file(), file)
        for content in (self.html, self.css, self.js):
            self.assertNotIn("/Users/", content)
            self.assertNotIn("/mnt/data/", content)

    def test_local_navigation_targets_exist(self):
        self.assertEqual(len(self.page.ids), len(set(self.page.ids)), "Duplicate HTML id")
        for anchor in self.page.anchors:
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, self.page.ids)

    def test_document_landmarks(self):
        self.assertEqual(self.page.html_lang, "en")
        self.assertEqual(self.page.main_count, 1)
        self.assertEqual(self.page.headings.count("h1"), 1)
        for anchor in ("experience", "capabilities", "architecture", "install"):
            self.assertIn(anchor, self.page.ids)

    def test_pre_release_truthful_disclaimers(self):
        self.assertIn("pre-release", self.html.lower())
        self.assertIn("PUBLIC SKILL · OPTIONAL GUIDE EXPERIMENTAL", self.html)
        self.assertIn("NOT A CONNECTED AGENT", self.html)
        self.assertIn("DELIVERED DOES NOT MEAN FOLLOWED", self.html)
        self.assertIn('href="https://github.com/Veer376/browser-agent-guide"', self.html)

    def test_recorded_showcase_and_real_booking_target_are_linked(self):
        self.assertIn('id="demo"', self.html)
        self.assertIn('href="#demo"', self.html)
        self.assertIn('id="appointment-video"', self.html)
        self.assertIn('controls playsinline preload="metadata"', self.html)
        self.assertNotIn('autoplay', self.html)
        self.assertIn('src="media/appointment-playwright.mp4"', self.html)
        self.assertIn('poster="media/appointment-playwright-poster.jpg"', self.html)
        self.assertIn('href="appointment-demo/"', self.html)
        self.assertIn("not a connected Chrome Guide event", self.html)
        recording = ROOT / "media/appointment-playwright.mp4"
        poster = ROOT / "media/appointment-playwright-poster.jpg"
        self.assertTrue(recording.is_file())
        self.assertGreater(recording.stat().st_size, 100_000)
        self.assertLess(recording.stat().st_size, 5_000_000)
        self.assertTrue(poster.read_bytes().startswith(b"\xff\xd8\xff"))
        self.assertTrue((ROOT / "appointment-demo/index.html").is_file())
        readme = (ROOT.parent / "README.md").read_text()
        self.assertIn("website/media/appointment-playwright-poster.jpg", readme)
        self.assertIn("https://veer376.github.io/browser-agent-guide/#demo", readme)
        self.assertIn("https://veer376.github.io/browser-agent-guide/appointment-demo/", readme)

    def test_visual_design_contract_and_responsiveness(self):
        for token in ("--paper", "--ink", "--blue", "--human", "--border"):
            self.assertIn(token, self.css)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertRegex(self.css, r"@media\s*\(max-width:\s*760px\)")
        self.assertRegex(self.css, r"@media\s*\(max-width:\s*520px\)")
        self.assertIn("font-family: 'Instrument Serif'", self.css)
        self.assertIn("font-family: 'IBM Plex Mono'", self.css)

    def test_interactions_have_a_bound_target(self):
        for ident in ("theme-toggle", "menu-toggle", "demo-queue", "demo-deliver",
                      "demo-reset", "copy-command", "copy-feedback", "demo-status"):
            self.assertIn(ident, self.page.ids)
            self.assertIn(f"$('{ident}')", self.js)
        self.assertIn("aria-expanded", self.js)
        self.assertIn("role=\"status\"", self.html)


if __name__ == "__main__":
    unittest.main()
