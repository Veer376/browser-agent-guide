# Browser Agent Guide — roadmap

**Status:** Public GitHub repository for the independently installable `playwright` skill, initially tested on macOS. The Chrome guidance extension is **experimental**, not a Chrome Web Store release. The website is source-only and not deployed.

## Available now

- The skill installs through `npx skills add Veer376/browser-agent-guide --skill playwright`; see [installation](docs/install-skill.md).
- Isolated local macOS tests cover installation with Skills CLI, `pw doctor`, browser launch, navigation, snapshot, clicks, screenshots, prerequisite recovery and session separation.
- Developer tests cover the Python adapter, extension protocol, native messaging, documentation, website and contributor policy. GitHub Actions runs unit and isolated browser E2Es.
- The optional [Chrome guidance setup](docs/install-extension.md) is available for testing and development; the [guidance architecture](docs/guidance.md) documents what is and is not guaranteed.

## Planned / not yet guaranteed

- Complete independent fresh-Chrome guidance end-to-end acceptance, native-host recovery and extension packaging; no Chrome Web Store listing yet.
- Record authentic demos, update placeholder illustrations and launch the website on GitHub Pages after separate review.
- Complete Windows/Linux support testing before claiming cross-platform compatibility.
- Improve error handling, default setup and contributor experience based on external feedback.

## Security and contribution boundaries

- [Security policy](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Third-party credits](NOTICE).
- Chrome browser access can operate on authenticated websites; explicit setup consent and local private tokens are required. The Guide broker is not a multi-user sandbox.
- Guide messages are queued until a supported command runs; delivered does not imply read or followed.
- The source assets and application code are licensed as described in [LICENSE](LICENSE) and [NOTICE](NOTICE); Browser Agent Guide is not affiliated with Microsoft.
