"""Production icon stays faithful to the approved Playwright cursor artwork."""

import json
from pathlib import Path
import re
import struct
import unittest
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SVG_NS = "{http://www.w3.org/2000/svg}"


class ProductIconTests(unittest.TestCase):
    def test_extension_and_website_share_one_icon(self):
        extension = (ROOT / "extension/icons/agent.svg").read_text()
        favicon = (ROOT / "website/favicon.svg").read_text()
        self.assertEqual(extension, favicon)

        root = ET.fromstring(extension)
        self.assertEqual(root.tag, SVG_NS + "svg")
        self.assertEqual(root.attrib["viewBox"], "0 0 128 128")

        # Owner-approved E: a full dark rounded-square tile with one light
        # cursor silhouette. No browser-frame line or rotated diamond.
        tiles = root.findall(SVG_NS + "rect")
        self.assertEqual(len(tiles), 1)
        self.assertEqual(tiles[0].attrib["width"], "128")
        self.assertEqual(tiles[0].attrib["height"], "128")
        self.assertEqual(tiles[0].attrib["rx"], "26")
        self.assertEqual(tiles[0].attrib["fill"], "#17191d")
        self.assertNotIn("transform", tiles[0].attrib)

        cursors = root.findall(SVG_NS + "path")
        self.assertEqual(len(cursors), 1)
        self.assertEqual(cursors[0].attrib["transform"], "translate(27 25.5) scale(1.66)")
        self.assertEqual(cursors[0].attrib["fill"], "#f8f8f4")

        source = (ROOT / "skills/playwright/scripts/visual-system/cursor.cjs").read_text()
        paths = dict(re.findall(r"\b(outer|inner): '([^']+)'", source))
        self.assertEqual({"outer", "inner"}, paths.keys())
        self.assertEqual(cursors[0].attrib["d"], paths["outer"])

    def test_manifest_icons_are_real_pngs_at_declared_dimensions(self):
        manifest = json.loads((ROOT / "extension/manifest.json").read_text())
        for size, relative in manifest["icons"].items():
            with self.subTest(size=size):
                data = (ROOT / "extension" / relative).read_bytes()
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack(">II", data[16:24]),
                                 (int(size), int(size)))

    def test_website_wordmark_uses_the_same_favicon(self):
        html = (ROOT / "website/index.html").read_text()
        css = (ROOT / "website/styles.css").read_text()
        self.assertIn('<img class="mark" src="favicon.svg" alt="" aria-hidden="true">', html)
        self.assertNotIn('.mark::before', css)
        self.assertNotIn('.mark i {', css)

    def test_website_favicon_footer_and_readme_use_approved_identity(self):
        icon = (ROOT / "website/favicon.svg").read_text()
        self.assertEqual(icon, (ROOT / "extension/icons/agent.svg").read_text())
        self.assertEqual(icon, (ROOT / "skills/playwright/assets/guide-mark.svg").read_text())

        html = (ROOT / "website/index.html").read_text()
        self.assertIn('href="favicon.svg" type="image/svg+xml"', html)
        self.assertIn('href="favicon-32.png" type="image/png"', html)
        self.assertIn('<div class="footer-brand"><img src="favicon.svg"', html)

        for dest, source in (("favicon-32.png", "agent-32.png"),
                             ("social-icon.png", "agent-128.png")):
            with self.subTest(asset=dest):
                self.assertEqual((ROOT / "website" / dest).read_bytes(),
                                 (ROOT / "extension/icons" / source).read_bytes())

        readme = (ROOT / "README.md").read_text()
        self.assertIn('<img src="website/favicon.svg"', readme)
        self.assertIn('https://veer376.github.io/browser-agent-guide/', readme)
        self.assertIn("npx skills add Veer376/browser-agent-guide --skill playwright", readme)
        self.assertIn("EXPERIMENTAL", readme)


if __name__ == "__main__":
    unittest.main()
