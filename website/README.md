# Browser Agent Guide website

The public static website is deployed to **https://veer376.github.io/browser-agent-guide/** by [the GitHub Pages workflow](../.github/workflows/pages.yml), which publishes only `website/`. The site uses `index.html`, `styles.css`, `main.js`, `favicon.svg` and PNG icons—no bundler or JavaScript framework. The human-guidance experience remains an explicitly labeled visual simulation, not live agent/session data.

## Local preview

From the repository root:

```bash
python3 -m http.server 8765 --directory website
```

Open `http://localhost:8765`. No build step is required. Google Fonts are requested for IBM Plex Sans, IBM Plex Mono, and Instrument Serif, with system/Georgia fallbacks if unavailable.

The demonstration's Queue → Next command → Reset controls model a **local visual-only state machine**. They never contact an agent, browser session, or remote service. The public skill installation command can be copied; the optional Chrome Guide extension remains experimental.

## Morrow appointment-booking test page

The independent, fictional healthcare booking experience is at [`appointment-demo/`](appointment-demo/). It is a realistic browser-automation target with a long scrollable layout, interactive care/date/time selections, patient form validation, review/edit/confirmation and no external booking backend. Its illustrative photos and provenance are documented in [appointment-demo/ASSETS.md](appointment-demo/ASSETS.md).

The [automation and video plan](../docs/appointment-demo-production-plan.md) documents the Playwright visual acceptance and real-browser recording script. The demo route is public at [Morrow's booking page](https://veer376.github.io/browser-agent-guide/appointment-demo/), and the 39-second recorded browser workflow is embedded in the [website showcase](https://veer376.github.io/browser-agent-guide/#demo). The optimized H.264 MP4 and poster image are served from `media/`; the original raw recording remains ignored and local.

The embedded video shows real Playwright browser actions with a recording-only cursor and captions. It **does not** demonstrate live Chrome Guide extension delivery; the correction prompt is explicitly editorial, whereas the existing queue animation is a separate local-only simulation.

## Quality checks

```bash
python3 -m unittest discover -s tests -v
node --check website/main.js
git diff --check -- website
```

In addition, inspect screenshots and interactions in a real browser at desktop, tablet, and phone widths; include color-theme changes, mobile menu, keyboard focus, and the guide-state sequence. Structural tests are not a substitute for visual inspection.

## Deployment

Keep the website in this repository. The dedicated [GitHub Pages workflow](../.github/workflows/pages.yml) uploads **only `website/`** with `actions/upload-pages-artifact` and deploys with `actions/deploy-pages`. The repository root and private development files are not hosted as the website. Every approved update to `website/` on `main` triggers a new Pages deployment.

Any future film that claims a working Chrome Guide-to-agent handoff must first pass the independent extension/native-host acceptance checks and be recorded from a real connected session. Preserve the distinction between the Playwright skill and optional Chrome Guide extension. A custom domain is optional.

[GitHub Pages publishing sources](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
