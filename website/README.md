# Browser Agent Guide website

The public static website is deployed to **https://veer376.github.io/browser-agent-guide/** by [the GitHub Pages workflow](../.github/workflows/pages.yml), which publishes only `website/`. The site uses `index.html`, `styles.css`, `main.js`, `favicon.svg` and PNG icons—no bundler or JavaScript framework. The human-guidance experience remains an explicitly labeled visual simulation, not live agent/session data.

## Local preview

From the repository root:

```bash
python3 -m http.server 8765 --directory website
```

Open `http://localhost:8765`. No build step is required. Google Fonts are requested for IBM Plex Sans, IBM Plex Mono, and Instrument Serif, with system/Georgia fallbacks if unavailable.

The demonstration's Queue → Next command → Reset controls model a **local visual-only state machine**. They never contact an agent, browser session, or remote service. The public skill installation command can be copied; the optional Chrome Guide extension remains experimental.

## Quality checks

```bash
python3 -m unittest discover -s tests -v
node --check website/main.js
git diff --check -- website
```

In addition, inspect screenshots and interactions in a real browser at desktop, tablet, and phone widths; include color-theme changes, mobile menu, keyboard focus, and the guide-state sequence. Structural tests are not a substitute for visual inspection.

## Deployment

Keep the website in this repository. The dedicated [GitHub Pages workflow](../.github/workflows/pages.yml) uploads **only `website/`** with `actions/upload-pages-artifact` and deploys with `actions/deploy-pages`. The repository root and private development files are not hosted as the website. Every approved update to `website/` on `main` triggers a new Pages deployment.

Before replacing the current illustrative experience with real footage, verify authentic recordings and privacy, accurate installation links and responsive behavior. Preserve the distinction between the Playwright skill and optional Chrome Guide extension. A custom domain is optional.

[GitHub Pages publishing sources](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
