# Browser Agent Guide website

The production-intended static website is in `index.html`, `styles.css`, `main.js`, and `favicon.svg`—no bundler or JavaScript framework. **Not deployed.** This is a pre-release interface with original, clearly labeled illustrations, not live agent/session data.

## Local preview

From the repository root:

```bash
python3 -m http.server 8765 --directory website
```

Open `http://localhost:8765`. No build step is required. Google Fonts are requested for IBM Plex Sans, IBM Plex Mono, and Instrument Serif, with system/Georgia fallbacks if unavailable.

The demonstration's Queue → Next command → Reset controls model a **local visual-only state machine**. They never contact an agent, browser session, or remote service. The planned installation command can be copied, but public installation is not yet available.

## Quality checks

```bash
python3 -m unittest discover -s tests -v
node --check website/main.js
git diff --check -- website
```

In addition, inspect screenshots and interactions in a real browser at desktop, tablet, and phone widths; include color-theme changes, mobile menu, keyboard focus, and the guide-state sequence. Structural tests are not a substitute for visual inspection.

## Publishing plan

Keep the website in this repository. A dedicated GitHub Pages Actions workflow should upload **only `website/`** with `actions/upload-pages-artifact`, then use `actions/deploy-pages`. Do not publish the repository root as the website. The repository and website must not be made public without separate user authorization.

Before publication, verify accurate installation links, record and include authentic product demonstrations, complete the release/security checks in `ROADMAP.md`, and test the public site from a signed-out browser. Preserve the distinction between the Playwright skill and optional Chrome Guide extension. A custom domain is optional.

[GitHub Pages publishing sources](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
