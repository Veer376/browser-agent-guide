# Browser Agent Guide — roadmap

**Status:** Public GitHub repository and [deployed website](https://veer376.github.io/browser-agent-guide/) for the independently installable `playwright` skill, initially tested on macOS. The Chrome guidance extension is **experimental**, not a Chrome Web Store release. The fictional [Morrow appointment-demo page](https://veer376.github.io/browser-agent-guide/appointment-demo/) and [real Playwright recording](https://veer376.github.io/browser-agent-guide/#demo) are published as a separate demonstration of the independently installable browser skill.

## Available now

- The skill installs through `npx skills add Veer376/browser-agent-guide --skill playwright`; see [installation](docs/install-skill.md).
- Isolated local macOS tests cover installation with Skills CLI, `pw doctor`, browser launch, navigation, snapshot, clicks, screenshots, prerequisite recovery and session separation.
- Developer tests cover the Python adapter, extension protocol, native messaging, documentation, website and contributor policy. GitHub Actions runs unit and isolated browser E2Es.
- The optional [Chrome guidance setup](docs/install-extension.md) is available for testing and development; the [guidance architecture](docs/guidance.md) documents what is and is not guaranteed.
- The homepage is live through a website-only GitHub Pages workflow. A fictional Morrow booking test site lives under `website/appointment-demo/`: responsive care site and booking flow with editable dates, form validation, review and reset. Real Playwright tests passed at four viewport sizes. A 39-second Playwright-driven cursor-visible H.264 video and poster are published from `website/media/`; the higher-bitrate source remains ignored in `demo-artifacts/`. See the [production and integrated-guide follow-up plan](docs/appointment-demo-production-plan.md). Do not portray its editorial correction cue as a connected Chrome Guide message.

## Planned / not yet guaranteed

- Complete independent fresh-Chrome guidance end-to-end acceptance, native-host recovery and extension packaging; no Chrome Web Store listing yet.
- Keep the existing homepage queue illustration explicitly labeled as simulated. Separately record an authentic **Chrome Guide extension** integrated demo after clean-profile end-to-end verification; the published Morrow recording demonstrates Playwright only.
- Complete Windows/Linux support testing before claiming cross-platform compatibility.
- Improve error handling, default setup and contributor experience based on external feedback.

## Security and contribution boundaries

- [Security policy](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Third-party credits](NOTICE).
- Chrome browser access can operate on authenticated websites; explicit setup consent and local private tokens are required. The Guide broker is not a multi-user sandbox.
- Guide messages are queued until a supported command runs; delivered does not imply read or followed.
- The source assets and application code are licensed as described in [LICENSE](LICENSE) and [NOTICE](NOTICE); Browser Agent Guide is not affiliated with Microsoft.
