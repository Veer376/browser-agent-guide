# Browser Agent Guide

### Guide your browser agent—right from Chrome.

Your AI agent is working in Chrome. You notice something it should do differently. **Instead of finding its chat thread, send guidance from the Chrome toolbar while viewing the tab it's controlling.** Browser Agent Guide queues your instruction for the correct agent session and delivers it at the next supported browser command.

The project also includes a standalone browser skill powered by [Microsoft Playwright CLI](https://github.com/microsoft/playwright-cli), with navigation, UI inspection, temporal observation, and debugging tools. The Chrome guidance extension is optional.

> **macOS first · public skill.** The `playwright` skill is available from this GitHub repository. The optional Chrome guidance extension and static website are **experimental and not distributed through Skills CLI**. Browser access to a personal Chrome profile requires your permission.

**[Install the skill](docs/install-skill.md)** · **[Add human guidance](docs/install-extension.md)** · **[Setup with your agent](skills/playwright/references/setup.md)** · **[Explore the capabilities](docs/features.md)**

**Prerequisites:** macOS, a compatible coding agent, Node.js/npm, Python, and a supported browser. Pillow is optional for temporal observation (`pw observe`). The agent can check dependencies using `pw doctor` and guide first-time setup. [Detailed requirements and recovery →](docs/install-skill.md)

## Guided first-time setup

After installing the `playwright` skill using the [Skills CLI](docs/install-skill.md), paste this **starter prompt into your coding agent**:

> Read my installed `playwright` skill and `references/setup.md`, then guide me through Browser Agent Guide setup on macOS. Use my running Chrome profile by default, or a separate automation browser if I request it. Locate the installed skill and check prerequisites with its `scripts/pw.py doctor --json`. Ask before installing software, connecting my personal Chrome for the first time, or reading the clipboard. Guide me through copying the official Playwright extension token and, with my permission, saving it locally; never reveal it in chat. Verify actual browser control with a safe snapshot. Offer the separate Browser Agent Guide toolbar extension only if I want in-browser guidance.

**What the agent will guide you through:**

1. **Confirm the browser:** existing Chrome is the default; choose a separate browser if preferred. The agent asks before first connecting to personal Chrome.
2. **Check requirements:** the agent locates the installed skill, runs its diagnostic, and requests approval for any missing dependency or browser installation.
3. **Optional existing-Chrome pairing:** you install Microsoft's official Playwright extension, use its own **Copy token** control, and authorize the agent to run the bundled local save helper. The token is stored in a private file, not in chat.
4. **Verify:** the agent opens or attaches to the chosen browser, reads a harmless snapshot, checks the intended tab/session, and reports any remaining limitations.
5. **Optional human guidance:** install the **separate** Browser Agent Guide toolbar extension and local helper if you want to send instructions to the agent from Chrome.

**About repeated permission prompts:** Microsoft's connection token can bypass the official Playwright extension's repeated *connection-approval dialog* while that token stays valid. <https://github.com/microsoft/playwright/blob/main/packages/extension/README.md> It does **not** bypass your coding agent's tool approvals, website/browser permission prompts, or confirmation for consequential actions. The Guide toolbar extension does not need this copied token. [Both human-readable steps and the agent's setup contract →](skills/playwright/references/setup.md)

## See it in action

*Demo recordings are being prepared.* The optional Guide extension queues instructions to the agent at its next supported browser command; it does not instantly interrupt or wake an idle agent. See the [technical guidance guide](docs/guidance.md) for details.

## Start with what you need

| | Browser skill | Chrome guidance (optional) |
|---|---|---|
| What it does | Lets your coding agent operate and inspect a browser | Lets you send timely guidance to the agent controlling a Chrome tab |
| Ideal for | Building, debugging, testing, research workflows | Correcting direction during an active browser task |
| Requires | Your existing coding agent + browser tooling | Browser skill, Chrome extension, local helper; existing-Chrome connection setup |
| Installation | Use the skill installer; choose your agent and global/project scope | Follow a separate, one-time Chrome setup guide |

### 1. Install the browser skill

The planned installation uses the existing [Skills CLI](https://github.com/vercel-labs/skills), which lets you pick your coding agent and installation scope. The compatible skill is currently named `playwright`:

```bash
npx skills add Veer376/browser-agent-guide --skill playwright
```

Start with the skill alone. You **do not need the Guide extension** to use a newly launched automation browser. The skill install copies agent instructions; browser/runtime dependencies are checked during first-run setup.

**Requirements:** macOS, a supported coding agent, Node.js/npm, Python and a Playwright-compatible browser. The additional `pw observe` command requires the Python **Pillow** package; ordinary browser actions do not. See the [dependency and first-run guide](docs/install-skill.md) for details.

**[Skill installation and requirements →](docs/install-skill.md)**

### 2. Pair your existing Chrome session (default browser mode)

`pw open` defaults to your running Chrome profile through the **official Playwright browser extension**. First-use attachment requires your authorization. An optional one-time token can be saved securely on your machine so you normally don't have to approve each new extension connection. The agent can guide you through setup. If you prefer a separate browser, request standalone mode instead.

**[First-run setup and trusted Chrome connection →](skills/playwright/references/setup.md)**

### 3. Guide the agent from Chrome (optional)

With the **Browser Agent Guide extension**, select a tab controlled by your agent, enter a message such as *“Don't submit yet—check the date first”*, and queue it for the correct session. You can inspect or cancel a message while it is still pending.

The queue delivers guidance at the next supported agent browser-command boundary. **Queued is not the same as read or followed**, and it does not wake an idle agent.

**[Chrome extension + local helper setup →](docs/install-extension.md)**

## Beyond basic browser clicks

The browser skill is built around the official Playwright CLI, with additional workflows for:

- **Observe over time:** `pw observe` samples an element or viewport for several seconds and builds contact sheets with timestamps and a capture manifest—useful for video, animation and transient UI.
- **Inspect and troubleshoot:** snapshots, targeted screenshots, browser console/request inspection, and Playwright tracing.
- **Control with context:** session-owned browser tabs, bounded recovery diagnostics, and task-scoped outputs.
- **Human guidance:** a separate Chrome popup with session-aware message routing, pending-message review and cancellation.

These capabilities exist in the current internal implementation; packaging and independent installation are still being validated. **[Examples, behavior and limitations →](docs/features.md)**

## Platform and availability

**Initial release target: macOS.** Windows and Linux are not advertised as supported in this first version. Windows compatibility and a Chrome Web Store listing are planned; until they pass real tests, the extension will be installed manually using the published setup guide.

This project is **not** a standalone AI model or an official Microsoft product. It adds agent-facing workflows, session handling, observation and human guidance on top of Playwright. Your coding agent supplies the reasoning; Playwright supplies browser automation.

## Security and credits

- Browser access can act on authenticated websites. Review agent permissions and supervise consequential actions.
- The existing-Chrome token is a secret stored in a user-local, permission-restricted file; **never paste it into a chat, README, issue or commit**. If it expires or is revoked, repeat pairing.
- The optional guidance helper uses Chrome native messaging and an authenticated loopback broker; it is **not** an internet-facing service or a general security sandbox.
- Built on [Microsoft Playwright CLI](https://github.com/microsoft/playwright-cli) and [Playwright](https://github.com/microsoft/playwright), which are licensed under **Apache License 2.0**. This project also selects Apache 2.0 and will preserve applicable upstream copyright and notices. [Playwright's license and attribution](https://github.com/microsoft/playwright/blob/main/LICENSE).

**Contribute:** [CONTRIBUTING.md](CONTRIBUTING.md) · **Security:** [SECURITY.md](SECURITY.md) · **License:** [Apache 2.0](LICENSE) · **Attribution:** [NOTICE](NOTICE) · **Roadmap:** [ROADMAP.md](ROADMAP.md). The public skill is available; versioned releases and the website launch are separate steps.
